# ⚡ AI Agent — ReAct Framework

An autonomous AI agent that thinks step-by-step, selects from **14 tools**,
executes them, observes the results, and answers with inline citations —
powered by **Groq**, **Anthropic** and **OpenRouter** with automatic failover,
plus built-in quality validation and auditing.

Every external service is optional: Supabase, Redis and the vector databases
each degrade to a local fallback, so the app runs with a single LLM key.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLM-F55036?style=for-the-badge)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude-D4A27F?style=for-the-badge)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-RAG-000000?style=for-the-badge)
![Weaviate](https://img.shields.io/badge/Weaviate-RAG-00C982?style=for-the-badge)
![Qdrant](https://img.shields.io/badge/Qdrant-RAG-DC244C?style=for-the-badge)

---

## 🚀 How It Works

The agent uses the **ReAct (Reason + Act)** framework:

1. **User** sends a question
2. **Redis cache** is checked first — if the same question was asked before, returns instantly
3. **LLM** reasons about the question and decides what to do
4. If a **tool** is needed, the agent executes it and reads the result
5. Steps 3-4 repeat until the LLM has enough information
6. **Final answer** is delivered and saved to **Supabase**
7. **Validator** grades the response quality using an independent LLM
8. **Auditor** fact-checks claims and analyzes efficiency

**Loop limits.** The loop runs at most `MAX_ITERATIONS` steps (default 10,
adjustable live from the sidebar between 1 and 20). It also **stops early
after 3 consecutive tool failures** and asks the model to answer from what it
already has — without that circuit breaker a broken tool would burn every
remaining step retrying, which reads to the user as an agent stuck thinking
long after the error was reported.

**Streaming.** Responses stream by default: each reasoning step, tool call
and tool result appears live in a status panel, and the final answer types
out word by word. Toggle **🌊 Stream Response** off in the sidebar for a
single blocking response instead.

### Architecture

```mermaid
graph TD
    A["👤 User Input"] --> B["⚡ Check Cache"]
    B -->|Hit| Z["✅ Return Cached Answer"]
    B -->|Miss| C["🧠 Think — LLM"]
    C --> D{"Need a Tool?"}
    D -->|Yes| E["🔧 Execute Tool"]
    D -->|"Need Document?"| P["📚 Vector DB Search"]
    P --> F
    E --> F["👁️ Observe Result"]
    F --> K{"Tool failed?"}
    K -->|No| G["💾 Cache Tool Result"]
    G --> C
    K -->|"Yes — 3rd in a row"| S["🛑 Stop early, answer from context"]
    K -->|"Yes — retry"| C
    S --> H
    D -->|No| H["✅ Final Answer"]
    H --> V["🔍 Validator — Quality Evaluation"]
    H --> AU["🛡️ Auditor — Fact Check + Cost Audit"]
    H --> I["💾 Save to Supabase / SQLite"]
    H --> J["⚡ Cache Answer"]
```

---

## 🤖 Multi-Provider LLM Architecture

The agent uses a **multi-provider routing** system with intelligent fallbacks:

Three providers are routed by model-ID prefix — `groq::`, `claude::`, or a
bare ID for OpenRouter — and the requested model is tried first, then the
fallback chain below (only the entries whose API key is actually present).

| Priority | Provider | Model | Rate Limits |
|----------|----------|-------|-------------|
| 🥇 Primary | **Groq** | Llama 4 Scout 17B | 30 req/min (per-account) |
| 🥈 Fallback 1 | **Groq** | Llama 3.3 70B Versatile | 30 req/min (per-account) |
| 🥉 Fallback 2 | **Anthropic** | Claude Sonnet 4 | Paid, per-account |
| 4️⃣ Fallback 3 | **OpenRouter** | Nemotron 3 Super 120B (free) | Shared global limit |
| 5️⃣ Fallback 4 | **OpenRouter** | Nemotron 3 Nano Omni 30B (free) | Shared global limit |
| 6️⃣ Fallback 5 | **OpenRouter** | Gemma 4 31B (free) | Shared global limit |

Claude uses the Anthropic Messages API, which differs from the OpenAI schema
(system prompt in its own field, strict user/assistant alternation, and
`stop_sequences` rather than `stop`); the client translates transparently in
both blocking and streaming modes.

**Smart Retry Logic:**
- Groq 429 (rate limit) → **waits 5-10s and retries the same model** (limits reset quickly)
- OpenRouter 429 → switches to the next model immediately (shared limits don't reset)
- Handles 404, 401, 403, 500, 502, 503, 529 with automatic fallback
- **Dead-provider short-circuit**: a 401/403 means the key is missing, invalid
  or revoked, and that will not fix itself mid-session. The provider is
  remembered and skipped for the rest of the process, so an expired key costs
  one wasted round-trip per session rather than one per request.

> ⚠️ OpenRouter retires free model IDs regularly. The IDs above were verified
> against `https://openrouter.ai/api/v1/models`; a stale ID returns 404 and
> silently consumes a fallback slot on every request. Keep `AGENT_MODELS` in
> `app.py` and `_build_fallback_list()` in `agent/llm.py` in sync.

---

## 🔍 Validator & Auditor

Every response is independently evaluated by two quality-checking systems:

### Validator (Quality Evaluation)
- Uses a **different model** than the agent to avoid self-grading bias
- Scores on **5 criteria** (1-10 each): Relevance, Completeness, Accuracy, Clarity, Helpfulness
- Weighted formula: `R×0.25 + Co×0.25 + Ac×0.20 + Cl×0.15 + H×0.15`
- Math re-verification: Re-runs calculator expressions with Python to verify correctness
- **Cost**: 1 extra LLM call (free tier)

### Auditor (Fact Check + Cost)
- **Quality Scorer**: Rates accuracy, completeness, relevance, and citation quality
- **Fact Checker**: Extracts 3-7 claims → labels each as verified, unverified, or hallucinated
- **Cost Auditor**: Pure Python analysis of tool usage efficiency, duplicate calls, token consumption
- **Cost**: 1 extra LLM call (quality + fact check combined) + 0 calls (cost audit)

---

## 🎨 Interface

- **Light and dark mode** — toggle at the top of the sidebar. The stylesheet
  is built on CSS custom properties, so the two themes differ only in one
  token block; every rule consumes tokens rather than hard-coded colours.
  Light uses warm paper (`#fbfbfa`) on ink (`#16191d`) rather than pure
  white-on-black, which is fatiguing over a long session.
- **Live reasoning trace** — every Thought → Action → Observation step is
  shown as it happens, with the tool used, its input, its output and whether
  the result came from cache.
- **Inline citations** — sources gathered from tools are numbered, rendered
  as hoverable pills in the answer, and listed in a sources popover.
- **Run metrics** — model, vector DB, total/LLM/vector-search latency, input
  and output tokens, and LLM call count for every response.
- **Session history** — past conversations are listed in the sidebar and can
  be reopened or deleted.

---

## 📄 Interactive PDF Preview

The frontend features a custom-built, split-pane PDF viewer that tightly integrates with the AI agent:
- **Side-by-side Layout**: Uploaded PDFs open in a resizable left panel, keeping the chat active on the right.
- **Contextual Querying**: Select any text in the PDF, right-click, and choose to **Ask AI**, **Explain**, **Summarize**, or **Define**.
- **Streamlit-Native Fallback**: An interactive "Ask about PDF content" expander allows seamless copy-pasting for environments where right-click context menus are restricted.
- **Full PDF Capabilities**: Zoom, fit-to-width, page navigation, and in-document search (Ctrl+F).
- **RAG Integration**: Any uploaded PDF is automatically indexed into the selected Vector DB (Pinecone/Weaviate/Qdrant) and available for semantic search via the `doc_search` tool.

---

## 🛠️ Tools (14)

Every tool is key-free unless noted, retries on transient failures, and
returns a `[SOURCES]` block where citation applies.

| Tool | Description | API |
|------|-------------|-----|
| 🌐 `web_search` | Web + news search. Operators: `site:`, `news:`, `recent:`. Domain de-duplicated | DuckDuckGo (free) |
| 🧮 `calculator` | Algebra, calculus, matrices, number theory, statistics. Exact **and** decimal results | SymPy (local) |
| 🐍 `python_executor` | Sandboxed Python with numpy/pandas. AST-validated, resource-limited | subprocess (local) |
| 📄 `read_file` | PDF, DOCX, XLSX, CSV/TSV, JSON, Markdown, source. CSVs return shape, dtypes and stats | PyPDF2 / pandas (local) |
| 🔗 `read_url` | Page → clean Markdown. Boilerplate stripped, SSRF-guarded, handles JSON/text | BeautifulSoup (local) |
| 📖 `wikipedia` | Article summaries with search fallback | Wikipedia REST API (free) |
| 📚 `doc_search` | RAG semantic search over uploaded documents | Pinecone / Weaviate / Qdrant |
| 📈 `stock_quote` | Stocks, ETFs, indices, crypto, commodities: price, change, ranges, volume | Yahoo Finance (free) |
| 💱 `currency_convert` | FX conversion with the rate and its quotation date | frankfurter.app / ECB (free) |
| 🔄 `unit_convert` | 11 dimensions; MB vs MiB kept distinct. Offline and instant | local |
| 🔬 `arxiv_search` | Papers with authors, abstract, categories, PDF links. `au:` `ti:` `cat:` | arXiv API (free) |
| 💻 `github_search` | Repositories with stars, language, licence, last push | GitHub API (free) |
| 🌤️ `weather` | Current conditions for any city | wttr.in (free) |
| 🕐 `datetime` | Time zones & date arithmetic | Python stdlib |

### Safety

The tools that touch untrusted input are hardened rather than trusting:

- **`python_executor`** validates the **AST** before execution — an import
  allowlist plus rejection of the `__class__`/`__subclasses__` escape chain,
  then runs in an isolated subprocess with CPU, memory and file-size limits.
  A substring blocklist would be bypassable; this is not.
- **`read_url`** refuses loopback, RFC1918 and cloud-metadata addresses
  (`169.254.169.254`), and non-HTTP schemes, so the agent cannot be steered
  into leaking instance credentials.
- **`read_file`** resolves symlinks and `..` before checking that the target
  is inside the project, and denies `.env` and key material outright.

---

## 🗄️ Database Stack

| Database | Purpose | Fallback |
|----------|---------|----------|
| **PostgreSQL** (Supabase) | Persistent conversations across deploys/devices | SQLite (local) |
| **Pinecone**, **Weaviate**, or **Qdrant** | RAG — semantic document search via cloud vectors | Direct text injection |
| **Redis** (Redis Cloud) | Cache LLM + tool responses to save cost & latency | In-memory Python dict |

All databases have **graceful fallbacks** — the app works without any external services.

### Database Selection

Users can switch between vector database providers directly from the **Streamlit sidebar** — no code changes needed. The system uses a **Provider Pattern** with an abstract base class, so adding new providers is straightforward.

Currently supported:
- **Pinecone** — Cloud-hosted, server-side embeddings, zero local dependencies
- **Weaviate** — Cloud-hosted, built-in vectorizer modules, 14-day free sandbox
- **Qdrant** — Cloud-hosted, local FastEmbed embeddings, 1GB free forever

### Cache Strategy

**Prose is normalized, code is not.** Natural-language categories are
lowercased, stripped of punctuation and filler words before hashing, so
`"What's the weather in Tokyo?"` and `"weather in tokyo"` share an entry.

Categories whose input is an expression, path or symbol are hashed
**verbatim**. Normalizing them is actively wrong: it strips the operator, so
`2+2` and `2-2` both collapse to `22` and the calculator returns a cached
answer for a different question. Exact-match categories are `calculator`,
`python_executor`, `read_file`, `read_url`, `doc_search`, `stock_quote`,
`currency_convert`, `unit_convert` and `github_search`.

**Failures are never cached.** Several categories have a TTL of 0, so caching
one transient tool error would replay it forever.

| Category | TTL | Why |
|----------|-----|-----|
| `llm` | 1 hour | Answers stay valid briefly |
| `calculator` | Never | Deterministic |
| `python_executor` | Never | Deterministic |
| `read_file` | Never | File content is static |
| `unit_convert` | Never | Pure arithmetic |
| `stock_quote` | 1 minute | Prices move |
| `datetime` | 1 minute | Clock advances |
| `doc_search` | 5 minutes | Index may change on upload |
| `web_search` | 15 minutes | Results churn |
| `weather` | 30 minutes | Conditions change |
| `github_search` | 30 minutes | Stars/pushes change slowly |
| `read_url` | 1 hour | Pages change slowly |
| `currency_convert` | 1 hour | ECB publishes daily |
| `wikipedia` | 24 hours | Articles are stable |
| `arxiv_search` | 24 hours | Papers are immutable |

---

## 📦 Project Structure

```
My-AI-ReAct-Framework/
├── app.py                        # ⚡ Streamlit frontend (UI + theming)
├── server.py                     # 🌐 FastAPI backend (optional REST API)
├── supabase_setup.sql            # 🗄️ PostgreSQL schema
├── .streamlit/
│   └── config.toml               # 🎨 Theme + static file serving
├── components/
│   ├── __init__.py
│   └── pdf_viewer.py             # 📄 pdf.js viewer wrapper
├── static/
│   ├── pdfjs/                    # 📄 Bundled Mozilla pdf.js viewer
│   └── uploads/                  # 📎 Uploaded documents (gitignored)
├── data/
│   └── memory.db                 # 💾 SQLite fallback store (gitignored)
├── agent/
│   ├── react_agent.py            # 🧠 Core ReAct reasoning loop
│   ├── llm.py                    # 🤖 Multi-provider LLM client (Groq + OpenRouter)
│   ├── parser.py                 # 📝 Parse Thought/Action/Final Answer
│   ├── memory.py                 # 💾 Supabase + SQLite memory
│   ├── cache.py                  # ⚡ Redis caching layer
│   ├── rag.py                    # 📚 Multi-provider RAG wrapper
│   ├── events.py                 # 📡 Streaming event system
│   ├── auditor/                  # 🛡️ Post-response audit system
│   │   ├── __init__.py           # Orchestrator (run_full_audit)
│   │   ├── base.py               # Data models (AuditReport, QualityScore)
│   │   ├── quality_scorer.py     # LLM-based quality + fact checking
│   │   └── cost_auditor.py       # Rule-based efficiency analysis
│   ├── validator/                # 🔍 Independent quality validation
│   │   ├── __init__.py           # Orchestrator (run_full_validation)
│   │   ├── base.py               # Data models (ValidationReport)
│   │   ├── quality.py            # 5-criteria quality evaluation
│   │   └── math_validator.py     # Calculator re-verification
│   ├── mcp/                      # 🔌 MCP (Model Context Protocol) client
│   │   ├── __init__.py           # Exports MCPManager
│   │   ├── client.py             # Multi-server connection manager
│   │   └── bridge.py             # MCP tool → ReAct tool converter
│   └── vector_stores/            # 🗄️ Vector database providers
│       ├── __init__.py           # Factory: get_vector_store(provider)
│       ├── base.py               # Abstract base class
│       ├── pinecone_store.py     # Pinecone implementation
│       ├── weaviate_store.py     # Weaviate implementation
│       └── qdrant_store.py       # Qdrant implementation
├── tools/
│   ├── base.py                   # 🔧 Tool registry
│   ├── common.py                 # 🔧 Retrying HTTP, SSRF guard, ToolError
│   ├── search_tool.py            # 🌐 Web + news search
│   ├── calculator_tool.py        # 🧮 Symbolic & numeric math
│   ├── weather_tool.py           # 🌤️ Weather
│   ├── wikipedia_tool.py         # 📖 Wikipedia
│   ├── url_reader_tool.py        # 🔗 URL → Markdown
│   ├── datetime_tool.py          # 🕐 Date/time
│   ├── file_tool.py              # 📄 PDF/DOCX/XLSX/CSV/JSON reader
│   ├── python_tool.py            # 🐍 Sandboxed Python
│   ├── finance_tool.py           # 📈 Quotes  💱 Currency
│   ├── convert_tool.py           # 🔄 Unit conversion
│   ├── research_tool.py          # 🔬 arXiv  💻 GitHub
│   └── rag_search_tool.py        # 📚 Document search (RAG)
├── prompts/
│   ├── react_prompt.txt          # 📋 Agent system prompt
│   ├── auditor_prompt.txt        # 🛡️ Auditor evaluation prompt
│   ├── quality_eval_prompt.txt   # 🔍 Validator scoring rubric
│   └── validator_prompt.txt      # ✅ Validation instructions
├── mcp_servers.json              # 🔌 MCP server configuration
├── .env.example
└── requirements.txt
```

---

## ⚡ Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/ranvirdeshmukh2004/My-AI-ReAct-Framework.git
cd My-AI-ReAct-Framework

# 2. Virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Minimum: add ONE LLM key — GROQ_API_KEY (free at https://console.groq.com)
#          or OPENROUTER_API_KEY (free at https://openrouter.ai/keys)
# Everything else (Supabase, Redis, Pinecone/Weaviate/Qdrant, Anthropic) is
# optional — each degrades gracefully when absent.

# 5. Run
streamlit run app.py
```

---

## ☁️ Cloud Database Setup

### Supabase — Persistent Memory
1. Go to [supabase.com](https://supabase.com) → Create free project
2. Open **SQL Editor** → paste `supabase_setup.sql` → Run
3. Go to **Settings → API** → copy `Project URL` and `anon public` key
4. Add to `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```

### Redis — Response Caching
1. Go to [redis.io/try-free](https://redis.io/try-free) → Create free database
2. Copy public endpoint and password
3. Add to `.env`:
   ```
   REDIS_URL=redis://default:PASSWORD@your-host:PORT
   ```

### Pinecone — RAG Document Search (Option 1)
1. Go to [app.pinecone.io](https://app.pinecone.io) → Sign up free
2. Go to **API Keys** → copy your key
3. Add to `.env`:
   ```
   PINECONE_API_KEY=your-api-key
   ```
4. The index (`ai-agent-docs`) is created automatically on first run

### Weaviate — RAG Document Search (Option 2)
1. Go to [console.weaviate.cloud](https://console.weaviate.cloud) → Sign up free
2. Create a **Sandbox** cluster (free, 14-day)
3. Copy the **REST Endpoint** URL and **API Key**
4. Add to `.env`:
   ```
   WEAVIATE_URL=https://your-cluster.weaviate.network
   WEAVIATE_API_KEY=your-api-key
   ```
5. The collection (`AiAgentDocs`) is created automatically on first run

### Qdrant — RAG Document Search (Option 3)
1. Go to [cloud.qdrant.io](https://cloud.qdrant.io) → Sign up free
2. Create a **Free** cluster (1GB, permanent)
3. Copy the **Cluster URL** and **API Key**
4. Add to `.env`:
   ```
   QDRANT_URL=https://your-cluster.cloud.qdrant.io:6333
   QDRANT_API_KEY=your-api-key
   ```
5. The collection (`ai_agent_docs`) is created automatically on first run

---

## 🌐 Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → Deploy this repo
3. In **Settings → Secrets**, add:
   ```toml
   GROQ_API_KEY = "your-groq-key"
   OPENROUTER_API_KEY = "your-openrouter-key"
   ANTHROPIC_API_KEY = "your-anthropic-key"   # optional
   DEFAULT_MODEL = "groq::meta-llama/llama-4-scout-17b-16e-instruct"
   MAX_ITERATIONS = "6"
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   REDIS_URL = "redis://default:password@host:port"
   PINECONE_API_KEY = "your-pinecone-key"
   WEAVIATE_URL = "https://your-cluster.weaviate.network"
   WEAVIATE_API_KEY = "your-weaviate-key"
   QDRANT_URL = "https://your-cluster.cloud.qdrant.io:6333"
   QDRANT_API_KEY = "your-qdrant-key"
   AUDITOR_MODEL = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
   ```

Only **one** LLM key is strictly required — everything else is optional and
falls back cleanly. `static/uploads/` is created automatically at runtime.

---

## 🔌 MCP (Model Context Protocol)

The agent supports **MCP** — an open standard for connecting AI apps to external tool servers. This is fully optional and toggleable from the sidebar.

### How It Works
1. Toggle **🔌 Enable MCP** in the sidebar
2. Click **➕ Add MCP Server** → enter server name, URL, and optional API key
3. The agent discovers tools from that server and adds them to its toolkit
4. Use the tools alongside the 14 built-in native tools

### Supported Transports
| Transport | Works On | Use Case |
|-----------|----------|----------|
| **SSE/HTTP** | Everywhere (including Streamlit Cloud) | Remote MCP servers via URL |
| **stdio** | Local dev only | Local subprocess servers |

### Example MCP Servers
| Server | What It Adds |
|--------|-------------|
| Brave Search | Enhanced web search with local business results |
| GitHub | Repository management, issues, PRs, code search |
| Filesystem | Secure file read/write/search |
| PostgreSQL | Direct database queries |
| Puppeteer | Full browser automation and screenshots |

> MCP is additive — all 14 native tools always work. If MCP is disabled, the agent operates exactly as before.

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| LLM (Primary) | Llama 4 Scout via Groq |
| LLM (Fallback) | Claude Sonnet 4 (Anthropic), Nemotron 3 / Gemma 4 (OpenRouter) |
| Frontend | Streamlit (custom token-based light/dark theme) |
| Backend (Optional) | FastAPI + Uvicorn |
| Relational DB | PostgreSQL (Supabase) → SQLite fallback |
| Vector DB | Pinecone / Weaviate / Qdrant (selectable) |
| Cache | Redis → in-memory fallback |
| MCP | Model Context Protocol (SSE/HTTP + stdio) |
| Validator | Independent LLM judge (5-criteria scoring) |
| Auditor | LLM fact-checker + Python cost analyzer |
| Search | DuckDuckGo via `ddgs` |
| Math | SymPy |
| Data analysis | numpy + pandas (in the Python sandbox and CSV profiling) |
| HTML extraction | BeautifulSoup + lxml + markdownify |
| Documents | PyPDF2 (PDF), openpyxl (XLSX), stdlib zipfile/XML (DOCX) |
| PDF viewer | Mozilla pdf.js (bundled, self-hosted) |

---

## 🩺 Troubleshooting

| Symptom | Cause & fix |
|---------|-------------|
| `❌ All models failed: …→401` | The API key is missing, invalid or revoked. Check `GROQ_API_KEY` / `OPENROUTER_API_KEY` in `.env`. The log line `🔑 <provider> rejected the API key` names the offender. |
| `…→404` on a free model | That OpenRouter model ID was retired. Check `https://openrouter.ai/api/v1/models` and update `AGENT_MODELS` in `app.py`. |
| Sidebar shows **RAG: Unavailable** | No vector-DB key is set, or the cluster expired (Weaviate sandboxes last 14 days). The app still runs; `doc_search` is simply inactive. |
| Sidebar shows **Memory: SQLite** | Supabase is unreachable or unset. Conversations still persist locally in `data/memory.db`. |
| Sidebar shows **Cache: In-Memory** | Redis is unreachable or unset. Caching still works, but only for the current process. |
| `⚠️ Cloud memory failed … falling back to SQLite` | Supabase went away mid-session. Handled automatically; no data is lost. |
| Web search returns nothing | Ensure `ddgs` is installed, **not** the deprecated `duckduckgo-search` — the old package imports fine but returns zero results. |
| `Blocked for safety` from `python_executor` | The code touched a disallowed import, builtin or dunder attribute. The sandbox is compute-only: no filesystem, network or process access. |
| PDF preview is blank | `enableStaticServing = true` must be set in `.streamlit/config.toml`, and the file must be under `static/uploads/`. |

---

## 📄 License

MIT License — free to use, modify, and share.
