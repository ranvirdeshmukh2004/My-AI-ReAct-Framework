"""
file_tool.py — File Reader Tool
==================================
Reads and extracts text from TXT and PDF files.
Useful for document analysis and summarization tasks.

Supports:
- .txt files: Direct text reading
- .pdf files: Text extraction via PyPDF2
"""

import os
from tools.base import Tool


def read_file(file_path: str) -> str:
    """
    Read and extract text from a file.
    
    Args:
        file_path: Path to the file to read.
                   Supports .txt and .pdf formats.
    
    Returns:
        The extracted text content.
    """
    file_path = file_path.strip().strip("'\"")

    # Check if file exists
    if not os.path.exists(file_path):
        return f"Error: File not found at '{file_path}'"

    # Get file extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    try:
        if ext == ".txt":
            return _read_txt(file_path)
        elif ext == ".pdf":
            return _read_pdf(file_path)
        else:
            return f"Error: Unsupported file type '{ext}'. Supported formats: .txt, .pdf"
    except Exception as e:
        return f"Error reading file: {str(e)}"


def _read_txt(file_path: str) -> str:
    """Read a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Truncate if too long (to avoid overwhelming the LLM)
    max_chars = 10000
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... [Truncated — file has {len(content)} characters total]"

    return f"📄 File: {os.path.basename(file_path)}\n\n{content}"


def _read_pdf(file_path: str) -> str:
    """Extract text from a PDF file using PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return "Error: PyPDF2 not installed. Run: pip install PyPDF2"

    reader = PdfReader(file_path)
    pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append(f"--- Page {i + 1} ---\n{text}")

    if not pages:
        return "Error: Could not extract text from PDF. The file may be scanned/image-based."

    content = "\n\n".join(pages)

    # Truncate if too long
    max_chars = 10000
    if len(content) > max_chars:
        content = content[:max_chars] + f"\n\n... [Truncated — PDF has {len(reader.pages)} pages total]"

    return f"📄 PDF: {os.path.basename(file_path)} ({len(reader.pages)} pages)\n\n{content}"


# ============================================
# Register as a Tool
# ============================================

file_tool = Tool(
    name="read_file",
    description=(
        "Read and extract text from files. "
        "Supports .txt and .pdf formats. "
        "Input should be the file path. "
        "Use this when the user uploads a file or asks about a document."
    ),
    function=read_file,
)
