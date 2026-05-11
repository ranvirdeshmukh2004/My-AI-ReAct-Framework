# ⚡ AI Agent — ReAct Framework

An autonomous AI agent that thinks step-by-step, selects tools dynamically, executes them, observes outputs, and delivers intelligent answers — powered by **Grok** via OpenRouter.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Cache-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-orange?style=for-the-badge)

---

## 🚀 How It Works

The agent uses the **ReAct (Reason + Act)** framework:

1. **User** sends a question
2. **Cache** is checked first — if the same question was asked before, the cached answer is returned instantly
3. **Grok LLM** reads the question and decides what to do
4. If a **tool** is needed, the agent executes it and reads the result
5. Steps 3-4 repeat until Grok has enough information
6. **Final answer** is delivered and saved to the database

### Architecture

```
User Input → Redis Cache Check → Grok LLM → Tool Execution → Observe
                                    ↑                            ↓
                                    └──── Loop until done ───────┘
                                              ↓
                                    Final Answer → Save to Supabase
```

---

## 🛠️ Tools (9)

| Tool | Description | API |
|------|-------------|-----|
| 🌐 `web_search` | Search the web via DuckDuckGo | DuckDuckGo (free) |
| 🧮 `calculator` | Safe math with sympy | Local (sympy) |
| 🌤️ `weather` | Current weather for any city | wttr.in (free) |
| 📖 `wikipedia` | Wikipedia article summaries | Wikipedia REST API (free) |
| 🔗 `read_url` | Fetch & read any web page | httpx (local) |
| 🕐 `datetime` | Time zones & date calculations | Python stdlib |
| 📄 `read_file` | Read TXT and PDF files | PyPDF2 (local) |
| 🐍 `python_executor` | Execute Python code (sandboxed) | subprocess (local) |
| 📚 `doc_search` | RAG semantic search over documents | ChromaDB (local) |

---

## 🗄️ Database Stack

| Database | Purpose | How It's Used | Fallback |
|----------|---------|---------------|----------|
| **PostgreSQL** (Supabase) | Persistent conversations | Every message is saved; history is loaded on each prompt | SQLite (local file) |
| **Redis** (Redis Cloud) | Caching LLM + tool responses | Checked before every API call; saves costs and speeds up repeated queries | In-memory Python dict |
| **ChromaDB** | RAG document search | Uploaded files are chunked and embedded; agent searches by meaning, not keywords | Direct full-text injection |

All databases have **graceful fallbacks** — the app works without any external services.

### Cache Strategy

The caching layer normalizes queries before hashing — so `"What's the weather in Tokyo?"` and `"weather in tokyo"` hit the same cache entry.

| Category | TTL (Expiry) |
|----------|-------------|
| LLM responses | 1 hour |
| Calculator | Never (deterministic) |
| Weather | 30 minutes |
| Wikipedia | 24 hours |
| Web search | 15 minutes |
| URL reader | 1 hour |

---

## 📦 Project Structure

```
My-AI-ReAct-Framework/
├── app.py                    # ⚡ Streamlit frontend
├── server.py                 # 🔌 FastAPI backend (optional)
├── supabase_setup.sql        # 🗄️ PostgreSQL schema
├── packages.txt              # 📦 System deps for Streamlit Cloud
├── agent/
│   ├── react_agent.py        # 🧠 Core ReAct reasoning loop
│   ├── llm.py                # 🤖 OpenRouter API client
│   ├── parser.py             # 📝 Parse Thought/Action/Final Answer
│   ├── memory.py             # 💾 Supabase + SQLite memory
│   ├── cache.py              # ⚡ Redis caching layer
│   └── rag.py                # 📚 ChromaDB RAG pipeline
├── tools/
│   ├── base.py               # 🔧 Tool registry
│   ├── search_tool.py        # 🌐 Web search
│   ├── calculator_tool.py    # 🧮 Calculator
│   ├── weather_tool.py       # 🌤️ Weather
│   ├── wikipedia_tool.py     # 📖 Wikipedia
│   ├── url_reader_tool.py    # 🔗 URL reader
│   ├── datetime_tool.py      # 🕐 Date/time
│   ├── file_tool.py          # 📄 File reader
│   ├── python_tool.py        # 🐍 Python executor
│   └── rag_search_tool.py    # 📚 Document search (RAG)
├── prompts/
│   └── react_prompt.txt      # 📋 System prompt template
├── .env.example              # 🔑 Environment template
├── .streamlit/
│   └── config.toml           # 🎨 Theme config
└── requirements.txt          # 📦 Python dependencies
```

---

## ⚡ Quick Start (Local)

```bash
# 1. Clone
git clone https://github.com/ranvirdeshmukh2004/My-AI-ReAct-Framework.git
cd My-AI-ReAct-Framework

# 2. Virtual environment
python3 -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env → add your OPENROUTER_API_KEY
# (Get a free key at https://openrouter.ai/keys)

# 5. Run
streamlit run app.py
```

The app works immediately with SQLite + in-memory cache (no cloud services needed).

---

## ☁️ Cloud Database Setup (Optional)

### Supabase — Persistent Memory
1. Go to [supabase.com](https://supabase.com) → Create free project
2. Open **SQL Editor** → paste contents of `supabase_setup.sql` → Run
3. Go to **Settings → API** → copy `Project URL` and `anon public` key
4. Add to `.env`:
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   ```

### Redis — Response Caching
1. Go to [redis.io/try-free](https://redis.io/try-free) → Create free database
2. Copy the public endpoint and password
3. Add to `.env`:
   ```
   REDIS_URL=redis://default:PASSWORD@your-host:PORT
   ```

### ChromaDB — RAG Search
No setup needed. Runs locally in-memory. Upload files via the sidebar and use `doc_search` to query them.

---

## 🌐 Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → Select this repo
3. Set **Main file path** to `app.py`
4. In **Secrets**, add your keys in TOML format:
   ```toml
   OPENROUTER_API_KEY = "your-key"
   DEFAULT_MODEL = "x-ai/grok-4.1-fast"
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   REDIS_URL = "redis://default:password@host:port"
   ```
5. Deploy!

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | Grok 4.1 Fast (via OpenRouter) |
| Frontend | Streamlit |
| Backend (optional) | FastAPI |
| Relational DB | PostgreSQL (Supabase) |
| Vector DB | ChromaDB |
| Cache | Redis |
| Search | DuckDuckGo |
| Math | SymPy |
| PDF | PyPDF2 |

---

## 📄 License

MIT License — free to use, modify, and share.
