"""
rag_search_tool.py — Document Search Tool (RAG)
==================================================
Semantic search across uploaded documents using Pinecone.
Returns the most relevant chunks for a query.

This tool is powered by the RAG pipeline:
Upload → Chunk → Embed → Store → Search
"""

from tools.base import Tool


# Global reference to the document store (set by the agent)
_document_store = None


def set_document_store(store):
    """Set the shared DocumentStore instance."""
    global _document_store
    _document_store = store


def doc_search(query: str) -> str:
    """
    Search uploaded documents for relevant information.
    
    Args:
        query: Natural language search query.
    
    Returns:
        Top matching document chunks with sources.
    """
    query = query.strip().strip("'\"")

    if _document_store is None or not _document_store.is_available:
        return "No documents indexed. Please upload a file first."

    if not _document_store.indexed_documents:
        return "No documents have been uploaded yet. Upload a PDF or TXT file first."

    results = _document_store.search(query, top_k=3)

    if not results:
        return f"No relevant content found for: '{query}'"

    formatted = [f"📚 Document search results for: '{query}'\n"]
    for i, r in enumerate(results, 1):
        score_pct = int(r["score"] * 100)
        formatted.append(
            f"**Result {i}** (relevance: {score_pct}%) — from: {r['source']}\n"
            f"{r['text']}\n"
        )

    return "\n---\n".join(formatted)


# ============================================
# Register as a Tool
# ============================================

rag_search_tool = Tool(
    name="doc_search",
    description=(
        "Search through uploaded documents for relevant information. "
        "Uses semantic search to find the most relevant sections. "
        "Use this when the user asks about content in their uploaded files. "
        "Input should be a natural language query."
    ),
    function=doc_search,
)
