"""
base.py — Abstract Base Class for Vector Stores
==================================================
All vector database providers must implement this interface.
"""

import os
import hashlib
from abc import ABC, abstractmethod


def _get_secret(key: str, default: str = "") -> str:
    """Get a secret from st.secrets (Streamlit Cloud) or environment."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """
    Split text into overlapping chunks for embedding.
    Shared by all vector store implementations.
    """
    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary
        if end < len(text):
            for sep in ["\n\n", ".\n", ". ", "\n", "? ", "! "]:
                last_sep = text[start:end].rfind(sep)
                if last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "text": chunk,
                "index": index,
                "start_char": start,
            })
            index += 1

        start = end - overlap

    return chunks


class VectorStoreBase(ABC):
    """
    Abstract base class for all vector database providers.

    Every provider must implement:
        - is_available: bool
        - init_error: str
        - indexed_documents: dict
        - provider_name: str
        - add_document(filename, text) -> int
        - search(query, top_k) -> list[dict]
        - clear()
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is connected and ready."""
        pass

    @property
    @abstractmethod
    def init_error(self) -> str:
        """Return the initialization error message, if any."""
        pass

    @property
    @abstractmethod
    def indexed_documents(self) -> dict:
        """Return dict of {filename: chunk_count} for indexed documents."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the display name of this provider (e.g. 'Pinecone')."""
        pass

    @abstractmethod
    def add_document(self, filename: str, text: str) -> int:
        """
        Index a document into the vector store.
        Returns the number of chunks indexed.
        """
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Search for relevant chunks.
        Returns list of dicts with keys: text, source, chunk_index, score.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Remove all vectors from the store."""
        pass
