"""
weaviate_store.py — Weaviate Vector Store
=============================================
Cloud-hosted vector database with built-in vectorizer modules.
Uses Weaviate's text2vec-weaviate module for server-side embeddings.

Setup:
    1. Sign up at https://console.weaviate.cloud
    2. Create a free Sandbox cluster
    3. Copy the REST Endpoint URL and API Key
    4. Set WEAVIATE_URL and WEAVIATE_API_KEY in .env
"""

import hashlib
from agent.vector_stores.base import VectorStoreBase, _get_secret, chunk_text


COLLECTION_NAME = "AiAgentDocs"


class WeaviateStore(VectorStoreBase):
    """Weaviate-backed vector store for RAG."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._documents = {}
        self._available = False
        self._error = None
        self._init()

    def _init(self):
        """Initialize Weaviate connection."""
        url = _get_secret("WEAVIATE_URL")
        api_key = _get_secret("WEAVIATE_API_KEY")

        if not url or not api_key:
            self._error = "No WEAVIATE_URL or WEAVIATE_API_KEY configured"
            return

        try:
            import weaviate
            from weaviate.classes.init import Auth

            client = weaviate.connect_to_weaviate_cloud(
                cluster_url=url,
                auth_credentials=Auth.api_key(api_key),
            )

            # Create collection if it doesn't exist
            if not client.collections.exists(COLLECTION_NAME):
                from weaviate.classes.config import (
                    Configure,
                    Property,
                    DataType,
                    VectorDistances,
                )

                client.collections.create(
                    name=COLLECTION_NAME,
                    vectorizer_config=Configure.Vectorizer.text2vec_weaviate(),
                    vector_index_config=Configure.VectorIndex.hnsw(
                        distance_metric=VectorDistances.COSINE,
                    ),
                    properties=[
                        Property(name="text", data_type=DataType.TEXT),
                        Property(
                            name="source",
                            data_type=DataType.TEXT,
                            skip_vectorization=True,
                        ),
                        Property(
                            name="chunk_index",
                            data_type=DataType.INT,
                            skip_vectorization=True,
                        ),
                        Property(
                            name="doc_hash",
                            data_type=DataType.TEXT,
                            skip_vectorization=True,
                        ),
                    ],
                )

            self._client = client
            self._collection = client.collections.get(COLLECTION_NAME)
            self._available = True
            print("✅ Weaviate initialized successfully")

        except ImportError:
            self._error = "weaviate-client package not installed"
        except Exception as e:
            self._error = str(e)
            print(f"⚠️ Weaviate init failed: {e}")

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
        return "Weaviate"

    def add_document(self, filename: str, text: str) -> int:
        if not self._available:
            return 0

        doc_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
        chunks = chunk_text(text)
        if not chunks:
            return 0

        try:
            # Insert chunks in a batch
            with self._collection.batch.dynamic() as batch:
                for chunk in chunks:
                    batch.add_object(
                        properties={
                            "text": chunk["text"],
                            "source": filename,
                            "chunk_index": chunk["index"],
                            "doc_hash": doc_hash,
                        }
                    )

            self._documents[filename] = len(chunks)
            return len(chunks)

        except Exception as e:
            print(f"⚠️ Weaviate add_document failed: {e}")
            return 0

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        if not self._available or not self._documents:
            return []

        try:
            results = self._collection.query.near_text(
                query=query,
                limit=top_k,
                return_metadata=["distance"],
            )

            output = []
            for obj in results.objects:
                props = obj.properties
                # Weaviate returns distance (0 = identical), convert to similarity score
                distance = obj.metadata.distance if obj.metadata.distance is not None else 0.5
                score = round(1.0 - distance, 3)

                output.append({
                    "text": props.get("text", ""),
                    "source": props.get("source", "unknown"),
                    "chunk_index": props.get("chunk_index", 0),
                    "score": score,
                })
            return output

        except Exception as e:
            return [{"text": f"Search error: {str(e)}", "source": "error", "score": 0, "chunk_index": 0}]

    def clear(self):
        if self._available and self._client:
            try:
                self._client.collections.delete(COLLECTION_NAME)
                self._documents.clear()
                # Recreate empty collection
                self._init()
            except Exception:
                pass

    def __del__(self):
        """Close the Weaviate client connection on cleanup."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
