"""
vector_stores — Vector Database Provider Factory
===================================================
Supports multiple vector database backends for RAG.
Use get_vector_store(provider) to get the correct backend.
"""

from agent.vector_stores.base import VectorStoreBase


def get_vector_store(provider: str = "pinecone") -> VectorStoreBase:
    """
    Factory: return the correct vector store based on provider name.

    Supported providers:
        - "pinecone"  → Pinecone Cloud (default)
        - "weaviate"  → Weaviate Cloud
        - "qdrant"    → Qdrant Cloud
    """
    provider = provider.lower().strip()

    if provider == "pinecone":
        from agent.vector_stores.pinecone_store import PineconeStore
        return PineconeStore()

    elif provider == "weaviate":
        from agent.vector_stores.weaviate_store import WeaviateStore
        return WeaviateStore()

    elif provider == "qdrant":
        from agent.vector_stores.qdrant_store import QdrantStore
        return QdrantStore()

    else:
        raise ValueError(f"Unknown vector store provider: '{provider}'. Supported: pinecone, weaviate, qdrant")
