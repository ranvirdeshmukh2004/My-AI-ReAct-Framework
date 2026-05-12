# ⚡ AI Agent — ReAct Framework

An autonomous AI agent that thinks step-by-step, selects tools dynamically, executes them, observes outputs, and delivers intelligent answers — powered by **Grok** via OpenRouter.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
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
3. **Grok LLM** reasons about the question and decides what to do
4. If a **tool** is needed, the agent executes it and reads the result
5. Steps 3-4 repeat until Grok has enough information
6. **Final answer** is delivered and saved to **Supabase**

### Architecture

```mermaid
graph TD
    A["👤 User Input"] --> B["⚡ Check Redis Cache"]
    B -->|Hit| Z["✅ Return Cached Answer"]
    B -->|Miss| C["🧠 Think — Grok LLM"]
    C --> D{"Need a Tool?"}
    D -->|Yes| E["🔧 Execute Tool"]
    E --> F["👁️ Observe Result"]
    F --> G["💾 Cache Tool Result in Redis"]
    G --> C
    D -->|"Need Document?"| P["📚 Vector DB Search (Pinecone/Weaviate)"]
    P --> F
    D -->|No| H["✅ Final Answer"]
    H --> I["💾 Save to Supabase PostgreSQL"]
    H --> J["⚡ Cache Answer in Redis"]
```

---

## 🛠️ Tools (9)

| Tool | Description | API |
|------|-------------|-----|
| 🌐 `web_search` | Search the web | DuckDuckGo (free) |
| 🧮 `calculator` | Safe math evaluation | SymPy (local) |
| 🌤️ `weather` | Current weather for any city | wttr.in (free) |
| 📖 `wikipedia` | Wikipedia article summaries | Wikipedia REST API (free) |
| 🔗 `read_url` | Fetch & read any web page | httpx (local) |
| 🕐 `datetime` | Time zones & date calculations | Python stdlib |
| 📄 `read_file` | Read TXT and PDF files | PyPDF2 (local) |
| 🐍 `python_executor` | Execute Python code (sandboxed) | subprocess (local) |
| 📚 `doc_search` | RAG semantic search over documents | Pinecone, Weaviate, or Qdrant (cloud) |

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

Queries are normalized before hashing — `"What's the weather in Tokyo?"` and `"weather in tokyo"` hit the same cache.

| Category | TTL |
|----------|-----|
| LLM responses | 1 hour |
| Calculator | Never (deterministic) |
| Weather | 30 minutes |
| Wikipedia | 24 hours |
| Web search | 15 minutes |

---

## 📦 Project Structure

```
My-AI-ReAct-Framework/
├── app.py                    # ⚡ Streamlit frontend
├── supabase_setup.sql        # 🗄️ PostgreSQL schema
├── agent/
│   ├── react_agent.py        # 🧠 Core ReAct reasoning loop
│   ├── llm.py                # 🤖 OpenRouter API client
│   ├── parser.py             # 📝 Parse Thought/Action/Final Answer
│   ├── memory.py             # 💾 Supabase + SQLite memory
│   ├── cache.py              # ⚡ Redis caching layer
│   ├── rag.py                # 📚 Multi-provider RAG wrapper
│   └── vector_stores/        # 🗄️ Vector database providers
│       ├── __init__.py       # Factory: get_vector_store(provider)
│       ├── base.py           # Abstract base class
│       ├── pinecone_store.py # Pinecone implementation
│       ├── weaviate_store.py # Weaviate implementation
│       └── qdrant_store.py   # Qdrant implementation
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
# Edit .env → add OPENROUTER_API_KEY (get free at https://openrouter.ai/keys)

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
3. In **Secrets**, add:
   ```toml
   OPENROUTER_API_KEY = "your-key"
   DEFAULT_MODEL = "x-ai/grok-4.1-fast"
   SUPABASE_URL = "https://your-project.supabase.co"
   SUPABASE_KEY = "your-anon-key"
   REDIS_URL = "redis://default:password@host:port"
   PINECONE_API_KEY = "your-pinecone-key"
   WEAVIATE_URL = "https://your-cluster.weaviate.network"
   WEAVIATE_API_KEY = "your-weaviate-key"
   QDRANT_URL = "https://your-cluster.cloud.qdrant.io:6333"
   QDRANT_API_KEY = "your-qdrant-key"
   ```

---

## 🔧 Tech Stack

| Component | Technology |
|-----------|------------|
| LLM | Grok 4.1 Fast (via OpenRouter) |
| Frontend | Streamlit |
| Relational DB | PostgreSQL (Supabase) |
| Vector DB | Pinecone / Weaviate / Qdrant (selectable) |
| Cache | Redis |
| Search | DuckDuckGo |
| Math | SymPy |
| PDF | PyPDF2 |

---

## 📄 License

MIT License — free to use, modify, and share.
