"""
rag.py — RAG Document Store (Pinecone)
=========================================
Manages document chunking and semantic search using Pinecone's
cloud vector database with integrated inference (embeddings
generated server-side — no local model needed).

Flow:
1. User uploads a PDF/TXT
2. File is split into ~500-char chunks
3. Chunks are sent to Pinecone (embeds + stores automatically)
4. Agent queries with natural language
5. Most relevant chunks are returned
"""

import os
import hashlib
from typing import Optional


# ============================================
# Text Chunking
# ============================================

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """
    Split text into overlapping chunks for embedding.
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


def _get_secret(key: str, default: str = "") -> str:
    """Get a secret from st.secrets or environment."""
    try:
        import streamlit as st
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


# ============================================
# Document Store (Pinecone)
# ============================================

INDEX_NAME = "ai-agent-docs"


class DocumentStore:
    """
    Pinecone-backed document store for RAG.

    Uses Pinecone's integrated inference — embeddings are
    generated server-side, no local model needed.
    """

    def __init__(self):
        self._index = None
        self._documents = {}  # Track indexed files: {filename: chunk_count}
        self._available = False
        self._error = None
        self._init_pinecone()

    def _init_pinecone(self):
        """Try to initialize Pinecone."""
        api_key = _get_secret("PINECONE_API_KEY")
        if not api_key:
            self._error = "No PINECONE_API_KEY configured"
            return

        try:
            from pinecone import Pinecone, ServerlessSpec

            pc = Pinecone(api_key=api_key)

            # Create index if it doesn't exist
            existing = [idx.name for idx in pc.list_indexes()]
            if INDEX_NAME not in existing:
                pc.create_index(
                    name=INDEX_NAME,
                    dimension=1024,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                )

            self._pc = pc
            self._index = pc.Index(INDEX_NAME)
            self._available = True
            print("✅ Pinecone initialized successfully")

        except ImportError:
            self._error = "pinecone package not installed"
        except Exception as e:
            self._error = str(e)
            print(f"⚠️ Pinecone init failed: {e}")

    def _embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        """Generate embeddings using Pinecone's inference API."""
        result = self._pc.inference.embed(
            model="multilingual-e5-large",
            inputs=texts,
            parameters={"input_type": input_type},
        )
        return [item.values for item in result.data]

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def init_error(self) -> str:
        return self._error or ""

    @property
    def indexed_documents(self) -> dict:
        return self._documents.copy()

    def add_document(self, filename: str, text: str) -> int:
        """
        Index a document into Pinecone.
        """
        if not self._available:
            return 0

        doc_hash = hashlib.md5(filename.encode()).hexdigest()[:8]

        # Chunk the text
        chunks = chunk_text(text)
        if not chunks:
            return 0

        # Generate embeddings
        texts = [c["text"] for c in chunks]
        try:
            embeddings = self._embed(texts, input_type="passage")
        except Exception as e:
            print(f"⚠️ Embedding failed: {e}")
            return 0

        # Upsert to Pinecone
        vectors = []
        for i, chunk in enumerate(chunks):
            vectors.append({
                "id": f"{doc_hash}_{chunk['index']}",
                "values": embeddings[i],
                "metadata": {
                    "text": chunk["text"],
                    "source": filename,
                    "chunk_index": chunk["index"],
                },
            })

        # Upsert in batches of 100
        for batch_start in range(0, len(vectors), 100):
            batch = vectors[batch_start:batch_start + 100]
            self._index.upsert(vectors=batch)

        self._documents[filename] = len(chunks)
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Search for relevant chunks across all indexed documents.
        """
        if not self._available or not self._documents:
            return []

        try:
            # Embed the query
            query_embedding = self._embed([query], input_type="query")[0]

            results = self._index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )

            output = []
            for match in results.matches:
                meta = match.metadata or {}
                output.append({
                    "text": meta.get("text", ""),
                    "source": meta.get("source", "unknown"),
                    "chunk_index": meta.get("chunk_index", 0),
                    "score": round(match.score, 3),
                })
            return output

        except Exception as e:
            return [{"text": f"Search error: {str(e)}", "source": "error", "score": 0, "chunk_index": 0}]

    def clear(self):
        """Remove all vectors from the index."""
        if self._available and self._index:
            try:
                self._index.delete(delete_all=True)
                self._documents.clear()
            except Exception:
                pass
