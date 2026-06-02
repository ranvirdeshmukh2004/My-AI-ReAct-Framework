"""
pdf_viewer.py — Streamlit PDF Viewer Component
==================================================
Wraps the official pdf.js viewer served from the static directory.
Handles communication between the viewer and Streamlit session state.

Usage:
    from components.pdf_viewer import render_pdf_viewer
    render_pdf_viewer(pdf_filename, height=700)
"""

import os
import streamlit as st
import streamlit.components.v1 as components

def render_pdf_viewer(pdf_filename: str, height: int = 750, key: str = "pdf_viewer") -> None:
    """
    Render an interactive PDF viewer in Streamlit using the official pdf.js.

    Args:
        pdf_filename: The basename of the PDF file (e.g. 'document.pdf'). The file must exist in static/uploads/
        height: Height of the viewer component in pixels.
        key: Unique key for the Streamlit component.
    """
    # Point the iframe to the locally hosted pdf.js viewer and pass the file path
    viewer_url = f"app/static/pdfjs/web/viewer.html?file=../../uploads/{pdf_filename}"
    
    st.components.v1.iframe(
        viewer_url,
        height=height,
        scrolling=False,
    )


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
