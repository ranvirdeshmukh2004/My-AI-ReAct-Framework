"""
pdf_viewer.py — Streamlit PDF Viewer Component
==================================================
Wraps the pdf.js-based HTML viewer as a Streamlit component.
Handles PDF loading, base64 encoding, and communication
between the viewer and Streamlit session state.

Usage:
    from components.pdf_viewer import render_pdf_viewer
    render_pdf_viewer(pdf_path, height=700)
"""

import os
import base64
import streamlit as st
import streamlit.components.v1 as components


# Path to the HTML template
_COMPONENT_DIR = os.path.dirname(os.path.abspath(__file__))
_HTML_TEMPLATE_PATH = os.path.join(_COMPONENT_DIR, "pdf_viewer.html")

# Cache the HTML template
_html_template_cache = None


def _load_html_template() -> str:
    """Load and cache the HTML template."""
    global _html_template_cache
    if _html_template_cache is None:
        with open(_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            _html_template_cache = f.read()
    return _html_template_cache


def _encode_pdf(pdf_path: str) -> str:
    """Read a PDF file and return base64-encoded string."""
    with open(pdf_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def render_pdf_viewer(pdf_path: str, height: int = 750, key: str = "pdf_viewer") -> None:
    """
    Render an interactive PDF viewer in Streamlit.

    Args:
        pdf_path: Absolute or relative path to the PDF file.
        height: Height of the viewer component in pixels.
        key: Unique key for the Streamlit component.
    """
    if not os.path.exists(pdf_path):
        st.error(f"PDF file not found: {pdf_path}")
        return

    # Encode PDF to base64
    pdf_b64 = _encode_pdf(pdf_path)

    # Load HTML template and inject PDF data
    html_content = _load_html_template()
    html_content = html_content.replace("__PDF_DATA__", pdf_b64)

    # Render the component
    components.html(
        html_content,
        height=height,
        scrolling=False,
    )


def render_pdf_viewer_header(filename: str) -> None:
    """Render the PDF viewer header with file info and close button."""
    col_info, col_close = st.columns([5, 1])
    with col_info:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:4px 0;">
            <span style="font-size:1.2rem;">📄</span>
            <span style="font-weight:600;font-size:0.9rem;color:#e2e8f0;">
                {filename}
            </span>
            <span style="font-size:0.7rem;color:#636e80;
                background:rgba(129,140,248,0.12);padding:2px 8px;
                border-radius:6px;font-weight:600;">
                PDF Preview
            </span>
        </div>
        """, unsafe_allow_html=True)
    with col_close:
        if st.button("✕ Close", key="close_pdf_preview", use_container_width=True):
            st.session_state.pdf_preview_active = False
            st.session_state.pdf_preview_path = None
            st.rerun()


def get_query_from_selection(selected_text: str, mode: str = "ask") -> str:
    """
    Generate a query string from selected text based on the action mode.

    Args:
        selected_text: The text selected by the user.
        mode: One of 'ask', 'explain', 'summarize', 'define'.

    Returns:
        A formatted query string.
    """
    # Truncate very long selections
    if len(selected_text) > 500:
        selected_text = selected_text[:500] + "..."

    if mode == "explain":
        return f'Explain the following from the uploaded document:\n\n"{selected_text}"'
    elif mode == "summarize":
        return f'Summarize the following section from the uploaded document:\n\n"{selected_text}"'
    elif mode == "define":
        return f'Define and explain the key terms in this text from the uploaded document:\n\n"{selected_text}"'
    else:  # ask
        return f'Based on the uploaded document, tell me about this:\n\n"{selected_text}"'
