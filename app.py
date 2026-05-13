"""
app.py — AI Agent Frontend (Streamlit)
========================================
Premium dark-themed chat interface with infrastructure monitoring,
cache stats, and RAG knowledge base display.
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ============================================
# Page Config
# ============================================
st.set_page_config(
    page_title="AI Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================
# Premium Dark Theme CSS
# ============================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
.stApp { font-family: 'Inter', sans-serif; }

/* Hero */
.hero { text-align: center; padding: 2.5rem 1rem 1.5rem; position: relative; }
.hero::before {
    content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%);
    border-radius: 50%; pointer-events: none;
}
.hero h1 {
    font-size: 2.6rem; font-weight: 800; margin: 0; letter-spacing: -0.02em;
    background: linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero .subtitle { color: #64748b; font-size: 0.95rem; margin-top: 0.4rem; }
.hero .badge-row { display: flex; justify-content: center; gap: 0.5rem; margin-top: 1rem; flex-wrap: wrap; }
.hero .hbadge {
    background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2);
    color: #a5b4fc; padding: 0.3rem 0.8rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.03em;
}

/* Sidebar */
.sb-logo { text-align: center; padding: 1.2rem 0 0.5rem; }
.sb-logo .icon { font-size: 2.2rem; }
.sb-logo .title {
    font-size: 1.15rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #c084fc);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-top: 0.15rem;
}
.sb-section {
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.1em; color: #818cf8; margin: 1rem 0 0.4rem;
    display: flex; align-items: center; gap: 0.35rem;
}
.sb-card {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 0.55rem 0.75rem; margin-bottom: 0.35rem;
    transition: all 0.2s ease;
}
.sb-card:hover { background: rgba(255,255,255,0.06); border-color: rgba(129,140,248,0.3); }
.sb-card .name { font-weight: 600; font-size: 0.82rem; color: #e2e8f0; }
.sb-card .desc { font-size: 0.68rem; color: #64748b; margin-top: 0.15rem; line-height: 1.4; }
.model-card {
    background: linear-gradient(135deg, rgba(99,102,241,0.08), rgba(192,132,252,0.08));
    border: 1px solid rgba(99,102,241,0.2); border-radius: 12px; padding: 0.75rem 1rem;
}
.model-card .dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    margin-right: 6px; animation: blink 2s ease-in-out infinite;
}
.dot-green { background: #34d399; }
.dot-red { background: #f87171; }
.dot-yellow { background: #fbbf24; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.model-card .mname { font-weight: 700; font-size: 0.85rem; color: #e2e8f0; }
.model-card .mprov { font-size: 0.7rem; color: #64748b; }
.divider { border: none; border-top: 1px solid rgba(255,255,255,0.05); margin: 0.75rem 0; }

/* Infrastructure */
.infra-row {
    display: flex; align-items: center; gap: 0.5rem;
    padding: 0.35rem 0; font-size: 0.78rem;
}
.infra-row .label { color: #94a3b8; flex: 1; }
.infra-row .value { color: #e2e8f0; font-weight: 600; font-size: 0.72rem; }
.infra-badge {
    display: inline-flex; align-items: center; gap: 0.3rem;
    padding: 0.15rem 0.5rem; border-radius: 999px; font-size: 0.65rem; font-weight: 600;
}
.infra-badge.green { background: rgba(52,211,153,0.12); color: #34d399; border: 1px solid rgba(52,211,153,0.2); }
.infra-badge.red { background: rgba(248,113,113,0.12); color: #f87171; border: 1px solid rgba(248,113,113,0.2); }
.infra-badge.yellow { background: rgba(251,191,36,0.12); color: #fbbf24; border: 1px solid rgba(251,191,36,0.2); }

/* Cache stats */
.cache-stats {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; margin-top: 0.3rem;
}
.cache-stat {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px; padding: 0.4rem 0.6rem; text-align: center;
}
.cache-stat .num { font-size: 1.1rem; font-weight: 700; color: #818cf8; }
.cache-stat .lbl { font-size: 0.6rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }

/* Reasoning Trace */
.trace-step {
    background: rgba(255,255,255,0.02); border-left: 3px solid transparent;
    padding: 0.65rem 0.9rem; margin: 0.3rem 0; border-radius: 0 8px 8px 0;
    font-size: 0.82rem; line-height: 1.55;
}
.trace-step.thought { border-left-color: #c084fc; }
.trace-step.action { border-left-color: #38bdf8; }
.trace-step.observation { border-left-color: #34d399; }
.trace-label { font-weight: 700; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.2rem; }
.trace-label.thought { color: #c084fc; }
.trace-label.action { color: #38bdf8; }
.trace-label.observation { color: #34d399; }
.tool-chip {
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(56,189,248,0.12); border: 1px solid rgba(56,189,248,0.25);
    color: #38bdf8; padding: 0.2rem 0.6rem; border-radius: 999px;
    font-size: 0.7rem; font-weight: 600;
}
.cached-chip {
    display: inline-flex; align-items: center; gap: 0.2rem;
    background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.25);
    color: #34d399; padding: 0.15rem 0.5rem; border-radius: 999px;
    font-size: 0.62rem; font-weight: 700; margin-left: 0.4rem;
}
.step-num { color: #475569; font-size: 0.65rem; font-weight: 500; text-align: right; margin-top: 0.15rem; }

/* Welcome */
.welcome-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; max-width: 600px; margin: 1.5rem auto; }
.welcome-card {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 1rem; cursor: pointer; transition: all 0.2s ease; text-align: left;
}
.welcome-card:hover { background: rgba(99,102,241,0.08); border-color: rgba(129,140,248,0.3); transform: translateY(-1px); }
.welcome-card .wicon { font-size: 1.3rem; margin-bottom: 0.35rem; }
.welcome-card .wtitle { font-size: 0.82rem; font-weight: 600; color: #e2e8f0; }
.welcome-card .wdesc { font-size: 0.7rem; color: #64748b; margin-top: 0.15rem; }

.footer { text-align: center; padding: 1.5rem 0 0.75rem; color: #334155; font-size: 0.7rem; letter-spacing: 0.02em; }

/* Token Stats */
.token-bar {
    display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
    padding: 0.4rem 0.75rem; margin-top: 0.6rem;
    background: rgba(99,102,241,0.06); border: 1px solid rgba(99,102,241,0.12);
    border-radius: 8px; font-size: 0.68rem; color: #94a3b8;
}
.token-bar .tk { font-weight: 700; color: #818cf8; }
.token-bar .sep { color: rgba(255,255,255,0.15); }
.token-bar .prov { background: rgba(99,102,241,0.15); padding: 0.15rem 0.45rem; border-radius: 4px; color: #a5b4fc; font-weight: 600; }

/* Inline Citations */
.cite-link {
    display: inline; font-size: 0.7em; vertical-align: super;
    color: #818cf8; font-weight: 700; cursor: pointer;
    text-decoration: none; position: relative;
    background: rgba(99,102,241,0.1); padding: 0 3px;
    border-radius: 3px; margin: 0 1px;
    transition: all 0.15s ease;
}
.cite-link:hover { background: rgba(99,102,241,0.25); color: #a5b4fc; }
.cite-link .cite-tip {
    visibility: hidden; opacity: 0;
    position: absolute; bottom: 130%; left: 50%; transform: translateX(-50%);
    background: #1e1b4b; color: #e0e7ff; padding: 6px 10px;
    border-radius: 6px; font-size: 0.75rem; white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4); z-index: 999;
    pointer-events: none; transition: opacity 0.15s ease;
    font-weight: 400; vertical-align: baseline;
    max-width: 350px; overflow: hidden; text-overflow: ellipsis;
}
.cite-link:hover .cite-tip { visibility: visible; opacity: 1; }

/* References Panel */
.ref-panel {
    margin-top: 0.5rem; padding: 0.6rem 0.8rem;
    background: rgba(30, 27, 75, 0.3); border: 1px solid rgba(99,102,241,0.15);
    border-radius: 8px; font-size: 0.78rem;
}
.ref-panel-title {
    font-weight: 700; color: #a5b4fc; margin-bottom: 0.3rem; font-size: 0.8rem;
}
.ref-item {
    padding: 0.25rem 0; color: #94a3b8; line-height: 1.4;
}
.ref-item a {
    color: #818cf8; text-decoration: none; word-break: break-all;
}
.ref-item a:hover { text-decoration: underline; color: #a5b4fc; }
.ref-num { font-weight: 700; color: #818cf8; margin-right: 0.3rem; }
</style>
""", unsafe_allow_html=True)


# ============================================
# Session State
# ============================================
def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_provider" not in st.session_state:
        st.session_state.vector_provider = "pinecone"
    if "agent" not in st.session_state:
        from agent.react_agent import ReactAgent
        st.session_state.agent = ReactAgent(vector_provider=st.session_state.vector_provider)
    if "session_id" not in st.session_state:
        from agent.memory import ConversationMemory
        st.session_state.session_id = ConversationMemory.new_session_id()
    if "uploaded_file_path" not in st.session_state:
        st.session_state.uploaded_file_path = None
    if "indexed_docs" not in st.session_state:
        st.session_state.indexed_docs = {}
    if "cache_enabled" not in st.session_state:
        st.session_state.cache_enabled = True
    # Restore indexed_docs tracker into the doc_store (survives Streamlit reruns)
    if st.session_state.indexed_docs and hasattr(st.session_state.agent, 'doc_store'):
        try:
            st.session_state.agent.doc_store._store._documents.update(st.session_state.indexed_docs)
        except AttributeError:
            pass

init_session_state()

TOOL_ICONS = {
    "web_search": "🌐", "calculator": "🧮", "read_file": "📄",
    "python_executor": "🐍", "weather": "🌤️", "wikipedia": "📖",
    "read_url": "🔗", "datetime": "🕐", "doc_search": "📚",
}


# ============================================
# Citation Rendering Helpers
# ============================================
import re as _re_app
import html as _html_mod

def render_citations(answer: str, sources: list) -> str:
    """
    Replace [N] markers in the answer with styled HTML citation links.
    Also strips out any ### References block the LLM may have appended
    (we render our own from the sources list).
    """
    if not sources:
        return answer

    # Remove LLM-generated ### References section (we render our own)
    answer = _re_app.sub(r'###\s*References.*', '', answer, flags=_re_app.DOTALL | _re_app.IGNORECASE).strip()

    def _cite_replace(m):
        num = int(m.group(1))
        idx = num - 1
        if 0 <= idx < len(sources):
            src = sources[idx]
            title = _html_mod.escape(src.get("title", f"Source {num}"))
            url = src.get("url", "#")
            is_doc = url.startswith("uploaded-document:")
            if is_doc:
                # No clickable link for uploaded documents
                return (
                    f'<span class="cite-link">[{num}]'
                    f'<span class="cite-tip">📄 {title}</span>'
                    f'</span>'
                )
            return (
                f'<a class="cite-link" href="{_html_mod.escape(url)}" target="_blank" rel="noopener">[{num}]'
                f'<span class="cite-tip">{title} — {_html_mod.escape(url)}</span>'
                f'</a>'
            )
        return m.group(0)

    return _re_app.sub(r'\[(\d+)\]', _cite_replace, answer)


def render_references_panel(sources: list) -> str:
    """Build HTML for the collapsible references panel."""
    if not sources:
        return ""
    items = []
    for i, src in enumerate(sources, 1):
        title = _html_mod.escape(src.get("title", f"Source {i}"))
        url = src.get("url", "")
        is_doc = url.startswith("uploaded-document:")
        if is_doc:
            doc_name = _html_mod.escape(url.replace("uploaded-document:", ""))
            items.append(
                f'<div class="ref-item">'
                f'<span class="ref-num">[{i}]</span> 📄 {title} — <em>{doc_name}</em>'
                f'</div>'
            )
        else:
            items.append(
                f'<div class="ref-item">'
                f'<span class="ref-num">[{i}]</span> {title} — '
                f'<a href="{_html_mod.escape(url)}" target="_blank" rel="noopener">{_html_mod.escape(url)}</a>'
                f'</div>'
            )
    return (
        '<div class="ref-panel">'
        '<div class="ref-panel-title">📎 References</div>'
        + "".join(items)
        + '</div>'
    )


# ============================================
# Sidebar
# ============================================
with st.sidebar:
    st.markdown("""
    <div class="sb-logo">
        <div class="icon">⚡</div>
        <div class="title">AI Agent</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # --- Infrastructure Status ---
    st.markdown('<div class="sb-section">🗄️ Infrastructure</div>', unsafe_allow_html=True)
    infra = st.session_state.agent.get_infrastructure_status()

    # Memory
    mem_color = "green" if "Supabase" in infra["memory"]["backend"] else "yellow"
    mem_label = infra["memory"]["backend"]
    st.markdown(f'<div class="infra-row"><span class="label">💾 Memory</span><span class="infra-badge {mem_color}"><span class="dot dot-{mem_color}"></span>{mem_label}</span></div>', unsafe_allow_html=True)

    # Cache
    cache_color = "green" if infra["cache"]["connected"] else "yellow"
    cache_label = infra["cache"]["backend"]
    st.markdown(f'<div class="infra-row"><span class="label">⚡ Cache</span><span class="infra-badge {cache_color}"><span class="dot dot-{cache_color}"></span>{cache_label}</span></div>', unsafe_allow_html=True)

    # RAG
    rag_color = "green" if infra["rag"]["connected"] else "red"
    rag_label = infra["rag"]["backend"] if infra["rag"]["connected"] else "Unavailable"
    st.markdown(f'<div class="infra-row"><span class="label">📚 RAG</span><span class="infra-badge {rag_color}"><span class="dot dot-{rag_color}"></span>{rag_label}</span></div>', unsafe_allow_html=True)

    # --- Vector Database Selection ---
    st.markdown('<div class="sb-section">📚 Vector Database</div>', unsafe_allow_html=True)
    provider_options = ["Pinecone", "Weaviate", "Qdrant"]
    provider_map = {"Pinecone": "pinecone", "Weaviate": "weaviate", "Qdrant": "qdrant"}
    current_idx = 0
    for i, name in enumerate(provider_options):
        if provider_map[name] == st.session_state.vector_provider:
            current_idx = i
            break
    selected_provider = st.selectbox(
        "Select Provider",
        options=provider_options,
        index=current_idx,
        label_visibility="collapsed",
        help="Choose the vector database for document search (RAG)",
    )
    new_provider = provider_map[selected_provider]
    if new_provider != st.session_state.vector_provider:
        st.session_state.vector_provider = new_provider
        from agent.react_agent import ReactAgent
        st.session_state.agent = ReactAgent(vector_provider=new_provider)
        st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # --- Cache Stats ---
    cache_stats = infra["cache"]["stats"]
    if cache_stats["total"] > 0:
        st.markdown('<div class="sb-section">📊 Cache Stats</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="cache-stats">
            <div class="cache-stat"><div class="num">{cache_stats['hits']}</div><div class="lbl">Hits</div></div>
            <div class="cache-stat"><div class="num">{cache_stats['misses']}</div><div class="lbl">Misses</div></div>
            <div class="cache-stat"><div class="num">{cache_stats['hit_rate']}%</div><div class="lbl">Hit Rate</div></div>
            <div class="cache-stat"><div class="num">{st.session_state.agent.cache.size()}</div><div class="lbl">Cached</div></div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🗑️ Clear Cache", use_container_width=True):
            st.session_state.agent.cache.clear()
            st.rerun()
        st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # --- Model ---
    st.markdown('<div class="sb-section">🤖 Model</div>', unsafe_allow_html=True)
    model_name = os.getenv("DEFAULT_MODEL", "x-ai/grok-4.1-fast")
    st.markdown(f"""
    <div class="model-card">
        <span class="dot dot-green"></span><span class="mname">{model_name.split('/')[-1]}</span>
        <div class="mprov">via OpenRouter</div>
    </div>
    """, unsafe_allow_html=True)

    # --- Tools ---
    st.markdown('<div class="sb-section">🔧 Tools</div>', unsafe_allow_html=True)
    for tool in st.session_state.agent.get_available_tools():
        icon = TOOL_ICONS.get(tool["name"], "🔧")
        short_desc = tool["description"][:65]
        st.markdown(f"""
        <div class="sb-card">
            <div class="name">{icon} {tool['name']}</div>
            <div class="desc">{short_desc}...</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # --- File Upload + Knowledge Base ---
    st.markdown('<div class="sb-section">📁 Upload File</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload", type=["txt", "pdf"], label_visibility="collapsed")
    if uploaded_file:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.uploaded_file_path = file_path

        # Index into vector store for RAG
        if st.session_state.agent.doc_store.is_available:
            from tools.file_tool import read_file
            text = read_file(file_path)
            chunks = st.session_state.agent.doc_store.add_document(uploaded_file.name, text)
            # Persist in session state so it survives reruns
            st.session_state.indexed_docs[uploaded_file.name] = chunks
            st.success(f"✅ {uploaded_file.name} — indexed {chunks} chunks")
        else:
            st.success(f"✅ {uploaded_file.name}")

    # Show indexed documents (from session state — persists across reruns)
    indexed = st.session_state.indexed_docs
    if indexed:
        st.markdown('<div class="sb-section">📚 Knowledge Base</div>', unsafe_allow_html=True)
        for doc_name, chunk_count in indexed.items():
            st.markdown(f"""
            <div class="sb-card">
                <div class="name">📄 {doc_name}</div>
                <div class="desc">{chunk_count} chunks indexed</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # --- History ---
    st.markdown('<div class="sb-section">📜 History</div>', unsafe_allow_html=True)
    sessions = st.session_state.agent.memory.list_sessions()
    if sessions:
        for sess in sessions[:6]:
            preview = sess["first_message"][:30] + "..." if len(sess["first_message"]) > 30 else sess["first_message"]
            col_load, col_del = st.columns([4, 1])
            with col_load:
                if st.button(f"💬 {preview}", key=f"s_{sess['session_id']}", use_container_width=True):
                    st.session_state.session_id = sess["session_id"]
                    history = st.session_state.agent.memory.get_history(sess["session_id"])
                    st.session_state.messages = [{"role": m["role"], "content": m["content"]} for m in history]
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{sess['session_id']}", help="Delete this chat"):
                    st.session_state.agent.memory.clear_session(sess["session_id"])
                    if st.session_state.session_id == sess["session_id"]:
                        from agent.memory import ConversationMemory
                        st.session_state.session_id = ConversationMemory.new_session_id()
                        st.session_state.messages = []
                    st.rerun()
    else:
        st.caption("No conversations yet")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    # Actions
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 New Chat", use_container_width=True):
            from agent.memory import ConversationMemory
            st.session_state.session_id = ConversationMemory.new_session_id()
            st.session_state.messages = []
            st.session_state.uploaded_file_path = None
            st.rerun()
    with c2:
        if st.button("🗑️ Clear All", use_container_width=True):
            st.session_state.agent.memory.clear_all()
            st.session_state.messages = []
            from agent.memory import ConversationMemory
            st.session_state.session_id = ConversationMemory.new_session_id()
            st.rerun()

    # Settings
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="sb-section">⚙️ Settings</div>', unsafe_allow_html=True)
    max_iter = st.slider("Max Reasoning Steps", 1, 20, st.session_state.agent.max_iterations,
                         help="Maximum Thought→Action→Observation cycles")
    st.session_state.agent.max_iterations = max_iter

    st.session_state.cache_enabled = st.toggle("⚡ Enable Cache", value=st.session_state.cache_enabled,
                                                help="Disable to force fresh LLM + vector DB calls (for benchmarking)")



# ============================================
# Header
# ============================================
st.markdown("""
<div class="hero">
    <h1>⚡ AI Agent</h1>
    <div class="subtitle">Autonomous reasoning & tool execution — Powered by Grok</div>
    <div class="badge-row">
        <span class="hbadge">🌐 Web Search</span>
        <span class="hbadge">🧮 Calculator</span>
        <span class="hbadge">🌤️ Weather</span>
        <span class="hbadge">📖 Wikipedia</span>
        <span class="hbadge">🐍 Python</span>
        <span class="hbadge">🔗 URL Reader</span>
        <span class="hbadge">🕐 DateTime</span>
        <span class="hbadge">📄 File Reader</span>
        <span class="hbadge">📚 Doc Search</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ============================================
# Reasoning Trace Display
# ============================================
def display_reasoning_trace(steps: list):
    with st.expander("🔍 View Reasoning Trace", expanded=False):
        for step in steps:
            if step["type"] == "tool_use":
                if step.get("thought"):
                    st.markdown(f"""<div class="trace-step thought">
                        <div class="trace-label thought">💭 Thought</div>
                        {step['thought']}
                    </div>""", unsafe_allow_html=True)

                icon = TOOL_ICONS.get(step['action'], '🔧')
                cached_chip = '<span class="cached-chip">⚡ CACHED</span>' if step.get("cached") else ""
                st.markdown(f"""<div class="trace-step action">
                    <div class="trace-label action">⚡ Action</div>
                    <span class="tool-chip">{icon} {step['action']}</span>{cached_chip}
                    <br><code>{step['action_input']}</code>
                </div>""", unsafe_allow_html=True)

                if step.get("observation"):
                    obs = step["observation"][:500]
                    if len(step["observation"]) > 500:
                        obs += "..."
                    st.markdown(f"""<div class="trace-step observation">
                        <div class="trace-label observation">👁️ Observation</div>
                        <pre style="white-space:pre-wrap;font-size:0.78rem;color:#94a3b8;
                            background:rgba(0,0,0,0.2);padding:0.5rem;border-radius:6px;
                            margin-top:0.3rem;">{obs}</pre>
                    </div>""", unsafe_allow_html=True)

                st.markdown(f'<div class="step-num">Step {step["iteration"]}</div>', unsafe_allow_html=True)

            elif step["type"] in ("final_answer", "max_iterations"):
                cached_note = ""
                if step.get("cached"):
                    cached_note = ' <span class="cached-chip">⚡ CACHED</span>'
                if step.get("thought"):
                    st.markdown(f"""<div class="trace-step thought">
                        <div class="trace-label thought">💭 Final Thought{cached_note}</div>
                        {step['thought']}
                    </div>""", unsafe_allow_html=True)


# ============================================
# Chat Messages
# ============================================
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
    elif message["role"] == "assistant":
        with st.chat_message("assistant", avatar="⚡"):
            # Render with citations if sources available
            msg_sources = message.get("sources", [])
            if msg_sources:
                st.markdown(render_citations(message["content"], msg_sources), unsafe_allow_html=True)
            else:
                st.markdown(message["content"])
            if "steps" in message:
                display_reasoning_trace(message["steps"])
            # Collapsible references panel
            if msg_sources:
                with st.expander("📎 View References", expanded=False):
                    st.markdown(render_references_panel(msg_sources), unsafe_allow_html=True)
            usage = message.get("token_usage", {})
            timing = message.get("timing", {})
            provider = message.get("vector_provider", "—")
            total_ms = timing.get("total_ms", 0)
            llm_ms = timing.get("llm_ms", 0)
            vs_ms = timing.get("vector_search_ms", 0)
            if usage.get("total_tokens", 0) > 0 or total_ms > 0:
                st.markdown(f"""
                <div class="token-bar">
                    <span class="prov">🗄️ {provider}</span>
                    <span class="sep">|</span>
                    <span>⏱️ Total <span class="tk">{total_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>🤖 LLM <span class="tk">{llm_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>🔍 VectorDB <span class="tk">{vs_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>📥 In <span class="tk">{usage.get('prompt_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>📤 Out <span class="tk">{usage.get('completion_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>Σ <span class="tk">{usage.get('total_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>Calls <span class="tk">{usage.get('llm_calls', 0)}</span></span>
                </div>
                """, unsafe_allow_html=True)

# Welcome state
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-grid">
        <div class="welcome-card">
            <div class="wicon">🌤️</div>
            <div class="wtitle">Check Weather</div>
            <div class="wdesc">What's the weather in Tokyo?</div>
        </div>
        <div class="welcome-card">
            <div class="wicon">🧮</div>
            <div class="wtitle">Calculate</div>
            <div class="wdesc">What is sqrt(2025)?</div>
        </div>
        <div class="welcome-card">
            <div class="wicon">🌐</div>
            <div class="wtitle">Search the Web</div>
            <div class="wdesc">Latest news about SpaceX</div>
        </div>
        <div class="welcome-card">
            <div class="wicon">📖</div>
            <div class="wtitle">Wikipedia</div>
            <div class="wdesc">Tell me about quantum computing</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================
# Chat Input
# ============================================
if prompt := st.chat_input("Ask me anything — I can search, calculate, check weather, read pages, and more..."):
    if st.session_state.uploaded_file_path:
        prompt += f"\n\n[Uploaded file available at: {st.session_state.uploaded_file_path}]"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚡"):
        with st.spinner("⚡ Reasoning..."):
            try:
                result = st.session_state.agent.run(
                    user_input=prompt,
                    session_id=st.session_state.session_id,
                    skip_cache=not st.session_state.cache_enabled,
                )
                # Show cached indicator
                if result.get("cached"):
                    st.markdown('<span class="cached-chip" style="margin-bottom:0.5rem;display:inline-flex;">⚡ Served from cache</span>', unsafe_allow_html=True)

                # Render answer with inline citations
                sources = result.get("sources", [])
                if sources:
                    cited_answer = render_citations(result["final_answer"], sources)
                    st.markdown(cited_answer, unsafe_allow_html=True)
                else:
                    st.markdown(result["final_answer"])

                if result["steps"]:
                    display_reasoning_trace(result["steps"])

                # Collapsible references panel
                if sources:
                    with st.expander("📎 View References", expanded=False):
                        st.markdown(render_references_panel(sources), unsafe_allow_html=True)

                # Comprehensive metrics display
                usage = result.get("token_usage", {})
                timing = result.get("timing", {})
                provider = result.get("vector_provider", "—")
                total_ms = timing.get("total_ms", 0)
                llm_ms = timing.get("llm_ms", 0)
                vs_ms = timing.get("vector_search_ms", 0)

                st.markdown(f"""
                <div class="token-bar">
                    <span class="prov">🗄️ {provider}</span>
                    <span class="sep">|</span>
                    <span>⏱️ Total <span class="tk">{total_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>🤖 LLM <span class="tk">{llm_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>🔍 VectorDB <span class="tk">{vs_ms:,.0f}ms</span></span>
                    <span class="sep">|</span>
                    <span>📥 In <span class="tk">{usage.get('prompt_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>📤 Out <span class="tk">{usage.get('completion_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>Σ <span class="tk">{usage.get('total_tokens', 0):,}</span></span>
                    <span class="sep">|</span>
                    <span>Calls <span class="tk">{usage.get('llm_calls', 0)}</span></span>
                </div>
                """, unsafe_allow_html=True)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["final_answer"],
                    "steps": result["steps"],
                    "token_usage": usage,
                    "timing": timing,
                    "vector_provider": provider,
                    "sources": sources,
                })
            except ValueError as e:
                st.error(str(e))
                st.info("💡 Get a free API key at https://openrouter.ai/keys")
            except Exception as e:
                st.error(f"❌ {str(e)}")

st.markdown('<div class="footer">Built with ❤️ — AI Agent • Powered by Grok via OpenRouter • PostgreSQL + Pinecone/Weaviate/Qdrant + Redis</div>', unsafe_allow_html=True)
