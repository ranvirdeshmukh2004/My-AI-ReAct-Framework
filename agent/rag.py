"""
rag.py — RAG Document Store (ChromaDB)
=========================================
Manages document chunking, embedding, and semantic search
using ChromaDB. Enables the agent to search through uploaded
documents for relevant information instead of reading the
entire document.

Flow:
1. User uploads a PDF/TXT
2. File is split into ~500-char chunks
3. Chunks are embedded and stored in ChromaDB
4. Agent queries with natural language
5. Most relevant chunks are returned
"""

import os
import sys
import hashlib
from typing import Optional

# Fix for Streamlit Cloud: ChromaDB requires sqlite3 >= 3.35.0
# but Streamlit Cloud's Ubuntu has an older version.
# pysqlite3-binary provides a newer sqlite3.
try:
    import pysqlite3
    sys.modules["sqlite3"] = pysqlite3
except ImportError:
    pass  # Not needed locally (system sqlite3 is new enough)

# Track init errors for UI display
_chroma_error = None


# ============================================
# Text Chunking
# ============================================

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """
    Split text into overlapping chunks for embedding.
    
    Args:
        text: The full text to chunk.
        chunk_size: Target size of each chunk in characters.
        overlap: Number of characters to overlap between chunks.
    
    Returns:
        List of dicts with 'text' and 'index' keys.
    """
    chunks = []
    start = 0
    index = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at a sentence boundary
        if end < len(text):
            # Look for the last period, newline, or question mark
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


# ============================================
# Document Store
# ============================================

class DocumentStore:
    """
    ChromaDB-backed document store for RAG.
    
    Usage:
        store = DocumentStore()
        store.add_document("uploads/report.pdf", extracted_text)
        results = store.search("What are the main findings?")
    """

    def __init__(self):
        """Initialize ChromaDB collection."""
        self._client = None
        self._collection = None
        self._documents = {}  # Track indexed files: {filename: chunk_count}
        self._available = False
        self._init_chroma()

    def _init_chroma(self):
        """Try to initialize ChromaDB."""
        try:
            import chromadb
            from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            
            self._client = chromadb.Client()  # In-memory (ephemeral)
            
            # Use default embedding function explicitly
            ef = DefaultEmbeddingFunction()
            
            self._collection = self._client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
                embedding_function=ef,
            )
            self._available = True
            print("✅ ChromaDB initialized successfully")
        except ImportError as e:
            global _chroma_error
            _chroma_error = str(e)
            print(f"⚠️ ChromaDB import error: {e}. RAG features disabled.")
        except Exception as e:
            global _chroma_error
            _chroma_error = str(e)
            print(f"⚠️ ChromaDB init failed: {e}. RAG features disabled.")

    @property
    def is_available(self) -> bool:
        """Whether ChromaDB is available."""
        return self._available

    @property
    def init_error(self) -> str:
        """Get ChromaDB initialization error if any."""
        return _chroma_error or ""

    @property
    def indexed_documents(self) -> dict:
        """Get list of indexed documents and their chunk counts."""
        return self._documents.copy()

    def add_document(self, filename: str, text: str) -> int:
        """
        Index a document into ChromaDB.
        
        Args:
            filename: Name of the file (for reference).
            text: The full extracted text content.
        
        Returns:
            Number of chunks created.
        """
        if not self._available:
            return 0

        # Generate a unique doc ID prefix
        doc_hash = hashlib.md5(filename.encode()).hexdigest()[:8]

        # Remove old chunks for this document (re-index)
        try:
            existing = self._collection.get(where={"source": filename})
            if existing and existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # Chunk the text
        chunks = chunk_text(text)
        if not chunks:
            return 0

        # Add chunks to ChromaDB
        ids = [f"{doc_hash}_{c['index']}" for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "source": filename,
                "chunk_index": c["index"],
                "start_char": c["start_char"],
            }
            for c in chunks
        ]

        self._collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        self._documents[filename] = len(chunks)
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Search for relevant chunks across all indexed documents.
        
        Args:
            query: Natural language search query.
            top_k: Number of results to return.
        
        Returns:
            List of dicts with 'text', 'source', 'score', 'chunk_index'.
        """
        if not self._available or not self._documents:
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, self._collection.count()),
            )

            output = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results["distances"] else 0
                    score = round(1 - distance, 3)  # Convert distance to similarity
                    output.append({
                        "text": doc,
                        "source": meta.get("source", "unknown"),
                        "chunk_index": meta.get("chunk_index", 0),
                        "score": score,
                    })
            return output

        except Exception as e:
            return [{"text": f"Search error: {str(e)}", "source": "error", "score": 0, "chunk_index": 0}]

    def clear(self):
        """Remove all indexed documents."""
        if self._available and self._client:
            try:
                self._client.delete_collection("documents")
                self._collection = self._client.get_or_create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"},
                )
                self._documents.clear()
            except Exception:
                pass
