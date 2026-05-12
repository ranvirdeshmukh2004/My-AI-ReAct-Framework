"""
qdrant_store.py — Qdrant Vector Store
========================================
Cloud-hosted vector database with local FastEmbed embeddings.
Uses Qdrant's high-level API for automatic embedding generation.

Setup:
    1. Sign up at https://cloud.qdrant.io
    2. Create a free cluster
    3. Copy the Cluster URL and API Key
    4. Set QDRANT_URL and QDRANT_API_KEY in .env
"""

import hashlib
from agent.vector_stores.base import VectorStoreBase, _get_secret, chunk_text


COLLECTION_NAME = "ai_agent_docs"


class QdrantStore(VectorStoreBase):
    """Qdrant-backed vector store for RAG."""

    def __init__(self):
        self._client = None
        self._documents = {}
        self._available = False
        self._error = None
        self._init()

    def _init(self):
        """Initialize Qdrant connection."""
        url = _get_secret("QDRANT_URL")
        api_key = _get_secret("QDRANT_API_KEY")

        if not url or not api_key:
            self._error = "No QDRANT_URL or QDRANT_API_KEY configured"
            return

        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                url=url,
                api_key=api_key,
            )

            # Test connectivity
            client.get_collections()

            self._client = client
            self._available = True
            print("✅ Qdrant initialized successfully")

        except ImportError:
            self._error = "qdrant-client package not installed"
        except Exception as e:
            self._error = str(e)
            print(f"⚠️ Qdrant init failed: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> str:
        return self._error or ""

    @property
    def indexed_documents(self) -> dict:
        return self._documents.copy()

    @property
    def provider_name(self) -> str:
        return "Qdrant"

    def add_document(self, filename: str, text: str) -> int:
        if not self._available:
            return 0

        doc_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
        chunks = chunk_text(text)
        if not chunks:
            return 0

        try:
            # Use Qdrant's high-level add() with built-in FastEmbed
            # This handles embedding generation automatically
            documents = [c["text"] for c in chunks]
            metadata = [
                {
                    "source": filename,
                    "chunk_index": c["index"],
                    "doc_hash": doc_hash,
                    "document": c["text"],
                }
                for c in chunks
            ]
            ids = [
                int(hashlib.md5(f"{doc_hash}_{c['index']}".encode()).hexdigest()[:15], 16)
                for c in chunks
            ]

            self._client.add(
                collection_name=COLLECTION_NAME,
                documents=documents,
                metadata=metadata,
                ids=ids,
            )

            self._documents[filename] = len(chunks)
            return len(chunks)

        except Exception as e:
            print(f"⚠️ Qdrant add_document failed: {e}")
            return 0

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self._available:
            return []

        try:
            # Use Qdrant's high-level query() with built-in FastEmbed
            results = self._client.query(
                collection_name=COLLECTION_NAME,
                query_text=query,
                limit=top_k,
            )

            output = []
            for point in results:
                meta = point.metadata or {}
                output.append({
                    "text": meta.get("document", ""),
                    "source": meta.get("source", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(point.score, 3),
                })
            return output

        except Exception as e:
            return [{"text": f"Search error: {str(e)}", "source": "error", "score": 0, "chunk_index": 0}]

    def clear(self):
        if self._available and self._client:
            try:
                self._client.delete_collection(COLLECTION_NAME)
                self._documents.clear()
            except Exception:
                pass
