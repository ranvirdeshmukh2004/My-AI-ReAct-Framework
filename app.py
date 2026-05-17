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

/* Source Badges — clean oval pills like Grok */
.src-badge {
    display: inline-flex; align-items: center;
    font-size: 0.68rem; font-weight: 500; letter-spacing: 0.01em;
    color: #8b95a5; background: rgba(255,255,255,0.06);
    padding: 2px 10px; border-radius: 12px; margin: 0 2px;
    cursor: pointer; text-decoration: none;
    border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.2s ease; position: relative;
    vertical-align: middle; white-space: nowrap;
}
.src-badge:hover {
    background: rgba(99,102,241,0.15); color: #a5b4fc;
    border-color: rgba(99,102,241,0.25);
}
.src-badge .src-tip {
    visibility: hidden; opacity: 0;
    position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%);
    background: #1a1a2e; color: #c8d1e0; padding: 8px 12px;
    border-radius: 8px; font-size: 0.72rem; white-space: nowrap;
    box-shadow: 0 6px 20px rgba(0,0,0,0.6); z-index: 9999;
    pointer-events: none; transition: opacity 0.2s ease;
    font-weight: 400; max-width: 420px;
    overflow: hidden; text-overflow: ellipsis;
    border: 1px solid rgba(255,255,255,0.06);
}
.src-badge .src-tip::after {
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 5px solid transparent; border-top-color: #1a1a2e;
}
.src-badge:hover .src-tip { visibility: visible; opacity: 1; }

/* Sources summary pill at bottom */
.sources-pill {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 0.72rem; color: #8b95a5;
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);
    padding: 4px 14px; border-radius: 14px; margin-top: 0.4rem;
    cursor: pointer; transition: all 0.2s ease;
}
.sources-pill:hover { background: rgba(99,102,241,0.1); color: #a5b4fc; }

/* References panel inside expander */
.ref-panel { padding: 0.3rem 0; font-size: 0.76rem; }
.ref-item {
    padding: 0.35rem 0; color: #8b95a5; line-height: 1.5;
    display: flex; align-items: flex-start; gap: 0.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.ref-item:last-child { border-bottom: none; }
.ref-item a { color: #818cf8; text-decoration: none; word-break: break-all; font-size: 0.72rem; }
.ref-item a:hover { text-decoration: underline; color: #a5b4fc; }
.ref-num { font-weight: 600; color: #636e80; min-width: 1rem; font-size: 0.72rem; }
.ref-title { font-weight: 500; color: #94a3b8; }

/* Action bar — small, minimal, Grok-style */
.act-bar {
    display: flex; align-items: center; gap: 2px; margin-top: 0.3rem; padding: 0;
}
.act-btn {
    background: none; border: none; color: #4a5568; cursor: pointer;
    padding: 5px 7px; border-radius: 6px; font-size: 0.82rem;
    transition: all 0.15s ease; display: inline-flex; align-items: center;
    line-height: 1;
}
.act-btn:hover { background: rgba(255,255,255,0.06); color: #a5b4fc; }
.act-btn:active { transform: scale(0.92); }

/* Audit Panel */
.audit-panel {
    background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px; padding: 0.8rem 1rem; margin-top: 0.3rem;
    font-size: 0.78rem; color: #94a3b8;
}
.audit-section { margin-bottom: 0.6rem; }
.audit-section:last-child { margin-bottom: 0; }
.audit-title {
    font-weight: 600; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.05em; color: #636e80; margin-bottom: 0.4rem;
    display: flex; align-items: center; gap: 0.3rem;
}
.audit-score-row {
    display: flex; align-items: center; gap: 0.5rem; margin: 0.25rem 0;
}
.audit-label { min-width: 5.5rem; color: #8b95a5; font-size: 0.74rem; }
.audit-bar-bg {
    flex: 1; height: 6px; background: rgba(255,255,255,0.06);
    border-radius: 3px; overflow: hidden; max-width: 120px;
}
.audit-bar-fill {
    height: 100%; border-radius: 3px;
    transition: width 0.3s ease;
}
.bar-high { background: linear-gradient(90deg, #34d399, #6ee7b7); }
.bar-mid { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
.bar-low { background: linear-gradient(90deg, #f87171, #ef4444); }
.audit-val { font-weight: 600; font-size: 0.74rem; min-width: 2rem; }
.audit-overall {
    font-size: 1.1rem; font-weight: 700; color: #e2e8f0;
    display: flex; align-items: center; gap: 0.3rem;
}
.audit-summary { color: #8b95a5; font-size: 0.74rem; font-style: italic; margin-top: 0.2rem; }
.fact-item {
    display: flex; align-items: flex-start; gap: 0.4rem;
    padding: 0.2rem 0; font-size: 0.74rem; line-height: 1.4;
}
.fact-icon { flex-shrink: 0; }
.fact-claim { color: #cbd5e1; }
.fact-evidence { color: #636e80; font-size: 0.7rem; }
.cost-grid {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 0.4rem; margin-top: 0.3rem;
}
.cost-item {
    background: rgba(255,255,255,0.03); border-radius: 6px; padding: 0.3rem 0.5rem; text-align: center;
}
.cost-val { font-weight: 600; color: #e2e8f0; font-size: 0.82rem; }
.cost-lbl { font-size: 0.66rem; color: #636e80; }
.eff-badge {
    display: inline-flex; padding: 2px 8px; border-radius: 8px;
    font-size: 0.7rem; font-weight: 600;
}
.eff-optimal { background: rgba(52,211,153,0.15); color: #34d399; }
.eff-good { background: rgba(99,102,241,0.15); color: #a5b4fc; }
.eff-fair { background: rgba(251,191,36,0.15); color: #fbbf24; }
.eff-wasteful { background: rgba(248,113,113,0.15); color: #f87171; }

/* Validation Panel Styles */
.val-panel {
    background: rgba(52,211,153,0.04); border: 1px solid rgba(52,211,153,0.12);
    border-radius: 10px; padding: 0.7rem; margin-top: 0.3rem;
}
.val-section {
    padding: 0.4rem 0; border-bottom: 1px solid rgba(52,211,153,0.08);
}
.val-section:last-child { border-bottom: none; }
.val-title {
    font-size: 0.8rem; font-weight: 600; color: #34d399;
    margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.3rem;
}
.val-overall {
    font-size: 1.1rem; font-weight: 700; color: #e2e8f0;
    display: flex; align-items: center; gap: 0.3rem;
}
.val-bar-bg {
    flex: 1; height: 8px; background: rgba(255,255,255,0.06);
    border-radius: 4px; overflow: hidden; max-width: 150px;
}
.val-bar-fill {
    height: 100%; border-radius: 4px;
    background: linear-gradient(90deg, #34d399, #6ee7b7);
    transition: width 0.4s ease;
}
.val-check {
    display: flex; align-items: center; gap: 0.4rem;
    padding: 0.15rem 0; font-size: 0.74rem; color: #cbd5e1;
}
.val-check-icon { flex-shrink: 0; font-size: 0.8rem; }
.val-detail { color: #636e80; font-size: 0.7rem; }
.val-agree-badge {
    display: inline-flex; padding: 2px 8px; border-radius: 8px;
    font-size: 0.7rem; font-weight: 600;
}
.agree-full { background: rgba(52,211,153,0.15); color: #34d399; }
.agree-partial { background: rgba(251,191,36,0.15); color: #fbbf24; }
.agree-contradiction { background: rgba(248,113,113,0.15); color: #f87171; }
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
    if "agent" not in st.session_state or not hasattr(st.session_state.agent, "run_stream"):
        import importlib
        import agent.react_agent as _agent_mod
        importlib.reload(_agent_mod)
        from agent.react_agent import ReactAgent
        st.session_state.agent = ReactAgent(vector_provider=st.session_state.get("vector_provider", "pinecone"))
    if "session_id" not in st.session_state:
        from agent.memory import ConversationMemory
        st.session_state.session_id = ConversationMemory.new_session_id()
    if "uploaded_file_path" not in st.session_state:
        st.session_state.uploaded_file_path = None
    if "indexed_docs" not in st.session_state:
        st.session_state.indexed_docs = {}
    if "cache_enabled" not in st.session_state:
        st.session_state.cache_enabled = True
    if "audit_enabled" not in st.session_state:
        st.session_state.audit_enabled = True
    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "groq::meta-llama/llama-4-scout-17b-16e-instruct"
    if "selected_auditor_model" not in st.session_state:
        st.session_state.selected_auditor_model = "groq::meta-llama/llama-4-scout-17b-16e-instruct"
    if "validator_enabled" not in st.session_state:
        st.session_state.validator_enabled = True
    if "streaming_enabled" not in st.session_state:
        st.session_state.streaming_enabled = True
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

# Available models for dropdowns
AGENT_MODELS = {
    "⚡ Llama 4 Scout (Groq)": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "⚡ Llama 3.3 70B (Groq)": "groq::llama-3.3-70b-versatile",
    "Gemma 4 31B 🆓": "google/gemma-4-31b-it:free",
    "Llama 3.3 70B 🆓": "meta-llama/llama-3.3-70b-instruct:free",
    "Nemotron 3 Super 120B 🆓": "nvidia/nemotron-3-super-120b-a12b:free",
    "GPT-OSS 120B 🆓": "openai/gpt-oss-120b:free",
}
AUDITOR_MODELS = {
    "⚡ Llama 4 Scout (Groq)": "groq::meta-llama/llama-4-scout-17b-16e-instruct",
    "Gemma 4 31B 🆓": "google/gemma-4-31b-it:free",
    "Nemotron 3 Nano 30B 🆓": "nvidia/nemotron-3-nano-30b-a3b:free",
}

# ============================================
# Citation Rendering Helpers
# ============================================
import re as _re_app
import html as _html_mod
import streamlit.components.v1 as _components


def _get_short_name(title: str) -> str:
    """Extract a short display name from a source title."""
    if "wikipedia" in title.lower():
        return "Wikipedia"
    if "uploaded-document:" in title.lower() or "chunk" in title.lower():
        parts = title.split("(")[0].strip()
        return parts[:18] + "…" if len(parts) > 20 else parts
    words = title.replace(" — ", " ").replace(" - ", " ").split()
    if len(words) <= 3:
        return title
    return " ".join(words[:3])


def _parse_llm_references(answer: str) -> list:
    """Fallback: parse sources from the LLM's own References section."""
    sources = []
    ref_match = _re_app.search(r'(?:#{1,3}\s*)?References\s*\n(.*)', answer, _re_app.DOTALL | _re_app.IGNORECASE)
    if not ref_match:
        return sources
    for line in ref_match.group(1).strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        m = _re_app.match(r'\[(\d+)\]\s*(.+?)\s*\|\s*(https?://\S+)', line)
        if m:
            sources.append({"title": m.group(2).strip(), "url": m.group(3).strip()})
            continue
        m = _re_app.match(r'\[(\d+)\]\s*(.+?)\s*[-—]\s*(https?://\S+)', line)
        if m:
            sources.append({"title": m.group(2).strip(), "url": m.group(3).strip()})
            continue
        m = _re_app.match(r'\[(\d+)\]\s*(.+)', line)
        if m:
            sources.append({"title": m.group(2).strip(), "url": ""})
    return sources


def _strip_references(answer: str) -> str:
    """Remove any References section from LLM output."""
    return _re_app.sub(
        r'\n*(?:#{1,3}\s*)?References\s*\n\s*(\[.*?)$',
        '', answer, flags=_re_app.DOTALL | _re_app.IGNORECASE
    ).strip()


def render_citations(answer: str, sources: list) -> tuple:
    """
    Replace [N] markers with inline source badges.
    Returns (processed_html, final_sources_list).
    """
    if not sources:
        sources = _parse_llm_references(answer)
    answer = _strip_references(answer)

    if not sources:
        cleaned = _re_app.sub(r'\[(\d+)\]', '', answer)
        return cleaned, []

    def _cite_replace(m):
        num = int(m.group(1))
        idx = num - 1
        if 0 <= idx < len(sources):
            src = sources[idx]
            title = _html_mod.escape(src.get("title", f"Source {num}"))
            short = _html_mod.escape(_get_short_name(src.get("title", f"Source {num}")))
            url = src.get("url", "")
            if not url or url.startswith("uploaded-document:"):
                return (
                    f'<span class="src-badge">📄 {short}'
                    f'<span class="src-tip">{title}</span></span>'
                )
            return (
                f'<a class="src-badge" href="{_html_mod.escape(url)}" target="_blank">{short}'
                f'<span class="src-tip">{_html_mod.escape(url)}</span></a>'
            )
        return ""

    processed = _re_app.sub(r'\[(\d+)\]', _cite_replace, answer)
    return processed, sources


def render_sources_panel(sources: list) -> str:
    """Build HTML for the sources panel with hyperlinked titles."""
    if not sources:
        return "<p style='color:#636e80;font-size:0.8rem;'>No sources.</p>"
    items = []
    for i, src in enumerate(sources, 1):
        title = _html_mod.escape(src.get("title", f"Source {i}"))
        url = src.get("url", "")
        is_doc = url.startswith("uploaded-document:") or not url
        if is_doc:
            items.append(f'<div class="ref-item"><span class="ref-num">{i}.</span> 📄 {title}</div>')
        else:
            items.append(
                f'<div class="ref-item"><span class="ref-num">{i}.</span> '
                f'<a href="{_html_mod.escape(url)}" target="_blank">{title}</a></div>'
            )
    return '<div class="ref-panel">' + "".join(items) + '</div>'


def copy_button(text: str, key: str):
    """Working copy button via components.html (bypasses Streamlit JS sanitization)."""
    escaped = text.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$').replace('</script>', '<\\/script>')
    _components.html(f"""
    <button id="cp_{key}" onclick="
        navigator.clipboard.writeText(`{escaped}`).then(function(){{
            document.getElementById('cp_{key}').innerHTML='✅';
            setTimeout(function(){{document.getElementById('cp_{key}').innerHTML='📋'}}, 1200);
        }});
    " style="background:none;border:none;color:#4a5568;cursor:pointer;padding:4px 6px;
    border-radius:5px;font-size:14px;transition:all 0.15s ease;display:inline-flex;align-items:center;"
    title="Copy response" onmouseover="this.style.color='#a5b4fc';this.style.background='rgba(255,255,255,0.06)'"
    onmouseout="this.style.color='#4a5568';this.style.background='none'">📋</button>
    """, height=32)


def render_audit_panel(audit_data: dict) -> str:
    """Build HTML for the audit report panel."""
    if not audit_data:
        return ""

    html_parts = []

    # --- Quality Score Section ---
    q = audit_data.get("quality")
    if q:
        overall = q.get("overall", 0)
        # Overall score with emoji
        if overall >= 8:
            grade_emoji = "🟢"
        elif overall >= 6:
            grade_emoji = "🟡"
        else:
            grade_emoji = "🔴"

        def _bar(val):
            pct = val * 10
            cls = "bar-high" if val >= 7 else ("bar-mid" if val >= 5 else "bar-low")
            color = "#34d399" if val >= 7 else ("#fbbf24" if val >= 5 else "#f87171")
            return (f'<div class="audit-bar-bg"><div class="audit-bar-fill {cls}" '
                    f'style="width:{pct}%"></div></div>'
                    f'<span class="audit-val" style="color:{color}">{val}/10</span>')

        html_parts.append(f'''
        <div class="audit-section">
            <div class="audit-title">📊 Quality Score</div>
            <div class="audit-overall">{grade_emoji} {overall}/10</div>
            <div class="audit-score-row"><span class="audit-label">Accuracy</span>{_bar(q.get("accuracy", 0))}</div>
            <div class="audit-score-row"><span class="audit-label">Completeness</span>{_bar(q.get("completeness", 0))}</div>
            <div class="audit-score-row"><span class="audit-label">Relevance</span>{_bar(q.get("relevance", 0))}</div>
            <div class="audit-score-row"><span class="audit-label">Citations</span>{_bar(q.get("citation_quality", 0))}</div>
            <div class="audit-summary">{_html_mod.escape(q.get("summary", ""))}</div>
        </div>''')

    # --- Fact Check Section ---
    fc = audit_data.get("fact_check")
    if fc and fc.get("total_claims", 0) > 0:
        verified = fc.get("verified", 0)
        total = fc.get("total_claims", 0)
        hallucinated = fc.get("hallucinated", 0)

        if hallucinated > 0:
            fc_emoji = "⚠️"
            fc_color = "#f87171"
        elif verified == total:
            fc_emoji = "✅"
            fc_color = "#34d399"
        else:
            fc_emoji = "🔍"
            fc_color = "#fbbf24"

        claims_html = ""
        for c in fc.get("claims", []):
            status = c.get("status", "unverified")
            if status == "verified":
                icon = "✅"
            elif status == "hallucinated":
                icon = "❌"
            else:
                icon = "⚠️"
            claim_text = _html_mod.escape(c.get("claim", ""))
            evidence = _html_mod.escape(c.get("evidence", ""))
            claims_html += f'''<div class="fact-item">
                <span class="fact-icon">{icon}</span>
                <div><span class="fact-claim">{claim_text}</span>
                <br><span class="fact-evidence">{evidence}</span></div>
            </div>'''

        html_parts.append(f'''
        <div class="audit-section">
            <div class="audit-title">🔍 Fact Check</div>
            <div style="color:{fc_color};font-weight:600;font-size:0.82rem;margin-bottom:0.3rem">
                {fc_emoji} {verified}/{total} claims verified
            </div>
            {claims_html}
        </div>''')

    # --- Cost / Efficiency Section ---
    cost = audit_data.get("cost")
    if cost:
        rating = cost.get("efficiency_rating", "Good")
        rating_cls = f"eff-{rating.lower()}"
        total_ms = cost.get("total_ms", 0)
        total_tokens = cost.get("total_tokens", 0)
        tool_calls = cost.get("tool_calls", 0)
        iterations = cost.get("iterations", 0)

        suggestions_html = ""
        for s in cost.get("suggestions", []):
            suggestions_html += f'<div style="padding:0.15rem 0;font-size:0.72rem">{_html_mod.escape(s)}</div>'

        html_parts.append(f'''
        <div class="audit-section">
            <div class="audit-title">💰 Efficiency <span class="eff-badge {rating_cls}">{rating}</span></div>
            <div class="cost-grid">
                <div class="cost-item"><div class="cost-val">{iterations}</div><div class="cost-lbl">Steps</div></div>
                <div class="cost-item"><div class="cost-val">{tool_calls}</div><div class="cost-lbl">Tool Calls</div></div>
                <div class="cost-item"><div class="cost-val">{total_tokens:,}</div><div class="cost-lbl">Tokens</div></div>
                <div class="cost-item"><div class="cost-val">{total_ms/1000:.1f}s</div><div class="cost-lbl">Time</div></div>
            </div>
            {suggestions_html}
        </div>''')

    if not html_parts:
        return ""

    return '<div class="audit-panel">' + "".join(html_parts) + '</div>'


def render_validation_panel(val_data: dict) -> str:
    """Render validation results as a clean text-based panel (no complex HTML)."""
    if not val_data:
        return ""

    overall = val_data.get("overall_score", 0)
    if overall >= 8:
        grade_emoji = "🟢"
    elif overall >= 6:
        grade_emoji = "🟡"
    else:
        grade_emoji = "🔴"

    # Simple bar using Unicode block characters
    def make_bar(score, max_score=10):
        filled = int(score)
        empty = max_score - filled
        if score >= 8:
            return "🟩" * filled + "⬜" * empty
        elif score >= 6:
            return "🟨" * filled + "⬜" * empty
        else:
            return "🟥" * filled + "⬜" * empty

    lines = []
    lines.append(f"### {grade_emoji} Validation Score: {overall}/10")

    # Quality Breakdown
    quality = val_data.get("quality")
    if quality:
        eval_model = quality.get("evaluator_model", "").replace("groq::", "").split("/")[-1].replace(":free", "")
        reasoning = quality.get("reasoning", "")[:250]

        criteria = [
            ("📌 Relevance", quality.get("relevance", 5)),
            ("📋 Completeness", quality.get("completeness", 5)),
            ("✅ Accuracy", quality.get("accuracy", 5)),
            ("📝 Clarity", quality.get("clarity", 5)),
            ("💡 Helpfulness", quality.get("helpfulness", 5)),
        ]

        lines.append(f"\n**📊 Quality Breakdown** — *Evaluated by: {eval_model}*\n")
        for label, score in criteria:
            bar = make_bar(score)
            lines.append(f"{label} {bar} **{score}/10**")

        if reasoning:
            lines.append(f"\n> 💭 *{reasoning}*")

    # Math Bonus Section
    math = val_data.get("math")
    if math and not math.get("skipped"):
        m_score = math.get("score", 10)
        lines.append(f"\n**🧮 Math Verification ({m_score}/10)**")
        lines.append(f"{math.get('passed', 0)}/{math.get('total_checks', 0)} calculations verified")
        for c in math.get("checks", []):
            icon = "✅" if c.get("match") else "❌"
            lines.append(f"{icon} `{str(c.get('expression', ''))[:60]}` = {str(c.get('verified_result', ''))[:30]}")

    return "\n\n".join(lines)




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

    # --- Model Selection ---
    st.markdown('<div class="sb-section">🤖 Agent Model</div>', unsafe_allow_html=True)
    _model_names = list(AGENT_MODELS.keys())
    _current_model_id = st.session_state.selected_model
    _current_idx = list(AGENT_MODELS.values()).index(_current_model_id) if _current_model_id in AGENT_MODELS.values() else 0
    _sel_name = st.selectbox("Agent Model", _model_names, index=_current_idx, label_visibility="collapsed")
    st.session_state.selected_model = AGENT_MODELS[_sel_name]

    st.markdown('<div class="sb-section">🛡️ Auditor Model</div>', unsafe_allow_html=True)
    _aud_names = list(AUDITOR_MODELS.keys())
    _current_aud_id = st.session_state.selected_auditor_model
    _current_aud_idx = list(AUDITOR_MODELS.values()).index(_current_aud_id) if _current_aud_id in AUDITOR_MODELS.values() else 0
    _sel_aud = st.selectbox("Auditor Model", _aud_names, index=_current_aud_idx, label_visibility="collapsed")
    st.session_state.selected_auditor_model = AUDITOR_MODELS[_sel_aud]

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

    st.session_state.audit_enabled = st.toggle("🛡️ Enable Audit", value=st.session_state.audit_enabled,
                                                help="Post-response quality scoring, fact checking & efficiency analysis")
    st.session_state.agent.audit_enabled = st.session_state.audit_enabled

    st.session_state.validator_enabled = st.toggle("✅ Enable Validator", value=st.session_state.validator_enabled,
                                                    help="Independent verification via multi-model consensus, math checks & source validation")
    st.session_state.agent.validator_enabled = st.session_state.validator_enabled

    st.session_state.streaming_enabled = st.toggle("🌊 Stream Response", value=st.session_state.streaming_enabled,
                                                    help="Show live progress & typing effect (like ChatGPT). Disable for instant full response.")

# ============================================
# Header
# ============================================
st.markdown("""
<div class="hero">
    <h1>⚡ AI Agent</h1>
    <div class="subtitle">Autonomous reasoning & tool execution — Multi-Model via OpenRouter</div>
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
            # Render with citations
            msg_sources = message.get("sources", [])
            cited_html, final_sources = render_citations(message["content"], msg_sources)
            if final_sources:
                st.markdown(cited_html, unsafe_allow_html=True)
            else:
                st.markdown(cited_html)
            if "steps" in message:
                display_reasoning_trace(message["steps"])
            # Action row: copy | regen | sources pill
            _act_cols = st.columns([1, 1, 2, 10])
            with _act_cols[0]:
                copy_button(message["content"], f"hist_{id(message)}")
            with _act_cols[1]:
                _msg_idx = st.session_state.messages.index(message) if message in st.session_state.messages else -1
                if st.button("🔄", key=f"regen_{id(message)}", help="Regenerate"):
                    if _msg_idx > 0:
                        st.session_state.messages.pop(_msg_idx)
                        st.session_state["_regen_prompt"] = st.session_state.messages[_msg_idx - 1]["content"]
                        st.rerun()
            with _act_cols[2]:
                if final_sources:
                    with st.popover(f"🔗 {len(final_sources)} sources"):
                        st.markdown(render_sources_panel(final_sources), unsafe_allow_html=True)
            usage = message.get("token_usage", {})
            timing = message.get("timing", {})
            provider = message.get("vector_provider", "—")
            total_ms = timing.get("total_ms", 0)
            llm_ms = timing.get("llm_ms", 0)
            vs_ms = timing.get("vector_search_ms", 0)
            if usage.get("total_tokens", 0) > 0 or total_ms > 0:
                _hist_model = message.get("model", "").split('/')[-1].replace(':free', '') or "—"
                st.markdown(f"""
                <div class="token-bar">
                    <span class="prov">🤖 {_hist_model}</span>
                    <span class="sep">|</span>
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
            # Audit panel (history replay)
            msg_audit = message.get("audit")
            if msg_audit:
                with st.expander("🛡️ Audit Report", expanded=False):
                    st.markdown(render_audit_panel(msg_audit), unsafe_allow_html=True)
            # Validation panel (history replay)
            msg_val = message.get("validation")
            if msg_val:
                with st.expander("✅ Validation Report", expanded=False):
                    st.markdown(render_validation_panel(msg_val), unsafe_allow_html=True)

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
# Handle regeneration
_regen = st.session_state.pop("_regen_prompt", None)


if prompt := (_regen or st.chat_input("Ask me anything — I can search, calculate, check weather, read pages, and more...")):
    if st.session_state.uploaded_file_path:
        prompt += f"\n\n[Uploaded file available at: {st.session_state.uploaded_file_path}]"

    if not _regen:
        st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="⚡"):
        try:
            # Always skip cache on regeneration
            _force_skip = True if _regen else (not st.session_state.cache_enabled)

            full_answer = ""
            result = None
            audit_data = None
            validation_data = None
            final_sources = []

            if st.session_state.streaming_enabled:
                # ==========================================
                # STREAMING MODE — live progress + typing
                # ==========================================
                status = st.status("⚡ Starting...", expanded=True)
                answer_container = st.empty()
                _step_count = 0

                for event in st.session_state.agent.run_stream(
                    user_input=prompt,
                    session_id=st.session_state.session_id,
                    skip_cache=_force_skip,
                    model=st.session_state.selected_model,
                    auditor_model=st.session_state.selected_auditor_model,
                ):
                    if event.type == "thinking":
                        _iter = event.data.get("iteration", "")
                        _status_msg = event.data.get("status", "")
                        if _status_msg:
                            status.update(label=f"⏳ {_status_msg}", state="running")
                        elif _iter:
                            _step_count = _iter
                            status.update(label=f"🤔 Thinking... (step {_iter})", state="running")

                    elif event.type == "tool_call":
                        tool_name = event.data.get("tool", "?")
                        tool_input = event.data.get("input", "")
                        thought = event.data.get("thought", "")
                        status.update(label=f"🔧 Using {tool_name}...", state="running")
                        if thought:
                            status.write(f"💭 *{thought[:150]}*")
                        status.write(f"**Tool**: `{tool_name}`")
                        if tool_input:
                            status.write(f"**Input**: {tool_input[:200]}")

                    elif event.type == "tool_result":
                        output = event.data.get("output", "")
                        cached = event.data.get("cached", False)
                        cache_tag = " ⚡ (cached)" if cached else ""
                        status.write(f"**Result{cache_tag}**: {output[:150]}...")
                        status.write("---")

                    elif event.type == "answer_start":
                        thought = event.data.get("thought", "")
                        label = f"✅ Done reasoning ({_step_count} steps)" if _step_count else "✅ Done reasoning"
                        status.update(label=label, state="complete", expanded=False)
                        if thought:
                            status.write(f"💭 *{thought[:200]}*")

                    elif event.type == "answer_token":
                        full_answer += event.data.get("token", "")
                        answer_container.markdown(full_answer + "▌")

                    elif event.type == "answer_done":
                        full_answer = event.data.get("answer", full_answer)
                        if event.data.get("cached"):
                            answer_container.markdown(f'<span class="cached-chip" style="margin-bottom:0.5rem;display:inline-flex;">⚡ Served from cache</span>\n\n{full_answer}', unsafe_allow_html=True)
                        else:
                            answer_container.markdown(full_answer)

                    elif event.type == "audit":
                        audit_data = event.data.get("data")

                    elif event.type == "validation":
                        validation_data = event.data.get("data")

                    elif event.type == "error":
                        st.error(f"❌ {event.data.get('message', 'Unknown error')}")

                    elif event.type == "done":
                        result = event.data.get("result", {})

            else:
                # ==========================================
                # BLOCKING MODE — classic spinner + instant
                # ==========================================
                with st.spinner("⚡ Reasoning..."):
                    result = st.session_state.agent.run(
                        user_input=prompt,
                        session_id=st.session_state.session_id,
                        skip_cache=_force_skip,
                        model=st.session_state.selected_model,
                        auditor_model=st.session_state.selected_auditor_model,
                    )
                    full_answer = result["final_answer"]
                    audit_data = result.get("audit")
                    validation_data = result.get("validation")

                    if result.get("cached"):
                        st.markdown('<span class="cached-chip" style="margin-bottom:0.5rem;display:inline-flex;">⚡ Served from cache</span>', unsafe_allow_html=True)

                    # Render answer with inline citations
                    sources = result.get("sources", [])
                    cited_html, final_sources = render_citations(full_answer, sources)
                    if final_sources:
                        st.markdown(cited_html, unsafe_allow_html=True)
                    else:
                        st.markdown(cited_html)

            # ==========================================
            # SHARED: Post-render (metrics, audit, etc.)
            # ==========================================
            if result:
                # For streaming mode, apply citations
                if st.session_state.streaming_enabled:
                    sources = result.get("sources", [])
                    cited_html, final_sources = render_citations(full_answer, sources)
                    if final_sources:
                        answer_container.markdown(cited_html, unsafe_allow_html=True)

                if result["steps"]:
                    display_reasoning_trace(result["steps"])

                # Action row: copy | regen | sources pill
                _new_cols = st.columns([1, 1, 2, 10])
                with _new_cols[0]:
                    copy_button(full_answer, f"new_{len(st.session_state.messages)}")
                with _new_cols[1]:
                    if st.button("🔄", key=f"regen_new_{len(st.session_state.messages)}", help="Regenerate"):
                        st.session_state["_regen_prompt"] = prompt
                        st.rerun()
                with _new_cols[2]:
                    if final_sources:
                        with st.popover(f"🔗 {len(final_sources)} sources"):
                            st.markdown(render_sources_panel(final_sources), unsafe_allow_html=True)

                # Comprehensive metrics display
                usage = result.get("token_usage", {})
                timing = result.get("timing", {})
                provider = result.get("vector_provider", "—")
                total_ms = timing.get("total_ms", 0)
                llm_ms = timing.get("llm_ms", 0)
                vs_ms = timing.get("vector_search_ms", 0)

                _model_short = st.session_state.selected_model.replace('groq::', '').split('/')[-1].replace(':free', '')
                st.markdown(f"""
                <div class="token-bar">
                    <span class="prov">🤖 {_model_short}</span>
                    <span class="sep">|</span>
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

                # Audit panel
                audit_data = audit_data or result.get("audit")
                if audit_data:
                    with st.expander("🛡️ Audit Report", expanded=True):
                        st.markdown(render_audit_panel(audit_data), unsafe_allow_html=True)

                # Validation panel
                validation_data = validation_data or result.get("validation")
                if validation_data:
                    with st.expander("✅ Validation Report", expanded=True):
                        st.markdown(render_validation_panel(validation_data), unsafe_allow_html=True)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_answer,
                    "steps": result["steps"],
                    "token_usage": usage,
                    "timing": timing,
                    "vector_provider": provider,
                    "sources": final_sources,
                    "audit": audit_data,
                    "validation": validation_data,
                    "model": st.session_state.selected_model,
                })
        except ValueError as e:
            # Close the status panel if it exists (streaming mode)
            try:
                status.update(label="❌ Error", state="error", expanded=False)
            except Exception:
                pass
            st.error(str(e))
            st.info("💡 Get a free API key at https://openrouter.ai/keys")
        except Exception as e:
            # Close the status panel if it exists (streaming mode)
            try:
                status.update(label="❌ Error", state="error", expanded=False)
            except Exception:
                pass
            st.error(f"❌ {str(e)}")

st.markdown('<div class="footer">Built with ❤️ — AI Agent • Multi-Model via OpenRouter • PostgreSQL + Pinecone/Weaviate/Qdrant + Redis</div>', unsafe_allow_html=True)
