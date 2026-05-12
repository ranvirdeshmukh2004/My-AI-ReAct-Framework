"""
rag.py — RAG Document Store (Multi-Provider)
===============================================
Thin wrapper around the vector_stores factory.
Maintains backward compatibility with existing imports.

Supported providers:
    - Pinecone (cloud, default)
    - Weaviate (cloud)

Usage:
    from agent.rag import DocumentStore
    store = DocumentStore(provider="pinecone")
"""

from agent.vector_stores import get_vector_store
from agent.vector_stores.base import VectorStoreBase, chunk_text


class DocumentStore:
    """
    Multi-provider document store for RAG.

    Wraps the vector_stores factory to provide a single interface
    for the rest of the application. Provider can be switched
    dynamically via the Streamlit UI.
    """

    def __init__(self, provider: str = "pinecone"):
        self._provider_name = provider
        self._store: VectorStoreBase = get_vector_store(provider)

    @property
    def is_available(self) -> bool:
        return self._store.is_available

    @property
    def init_error(self) -> str:
        return self._store.init_error

    @property
    def indexed_documents(self) -> dict:
        return self._store.indexed_documents

    @property
    def provider_name(self) -> str:
        return self._store.provider_name

    def add_document(self, filename: str, text: str) -> int:
        return self._store.add_document(filename, text)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        return self._store.search(query, top_k)

    def clear(self):
        self._store.clear()
