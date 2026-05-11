"""
memory.py — Conversation Memory (Supabase + SQLite Fallback)
===============================================================
Stores conversation history. Uses Supabase PostgreSQL if configured,
falls back to local SQLite if not.

Features:
- Add messages (user, assistant, system, tool)
- Retrieve conversation history by session
- List all past sessions
- Clear sessions
- Graceful fallback: Supabase → SQLite
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional


# ============================================
# SQLite Memory (Local Fallback)
# ============================================

class SQLiteMemory:
    """SQLite-backed conversation memory (local fallback)."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.getenv("DATABASE_PATH", "data/memory.db")
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON messages(session_id)
            """)
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str):
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp),
            )
            conn.commit()

    def get_history(self, session_id: str, limit: int = 50) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT role, content, timestamp FROM messages "
                "WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit),
            )
            return [
                {"role": row[0], "content": row[1], "timestamp": row[2]}
                for row in cursor.fetchall()
            ]

    def get_messages_for_llm(self, session_id: str, limit: int = 20) -> list[dict]:
        history = self.get_history(session_id, limit)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]

    def list_sessions(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id, 
                       MIN(timestamp) as started,
                       COUNT(*) as message_count,
                       (SELECT content FROM messages m2 
                        WHERE m2.session_id = m.session_id 
                        AND m2.role = 'user' 
                        ORDER BY m2.id ASC LIMIT 1) as first_message
                FROM messages m
                GROUP BY session_id
                ORDER BY started DESC
            """)
            return [
                {
                    "session_id": row[0],
                    "started": row[1],
                    "message_count": row[2],
                    "first_message": row[3] or "Empty session",
                }
                for row in cursor.fetchall()
            ]

    def clear_session(self, session_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

    def clear_all(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()


# ============================================
# Supabase Memory (Cloud Persistent)
# ============================================

class SupabaseMemory:
    """Supabase PostgreSQL-backed conversation memory."""

    def __init__(self):
        from supabase import create_client
        url = _get_secret("SUPABASE_URL")
        key = _get_secret("SUPABASE_KEY")
        self.client = create_client(url, key)

    def add_message(self, session_id: str, role: str, content: str):
        self.client.table("messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
        }).execute()

    def get_history(self, session_id: str, limit: int = 50) -> list[dict]:
        response = (
            self.client.table("messages")
            .select("role, content, timestamp")
            .eq("session_id", session_id)
            .order("id", desc=False)
            .limit(limit)
            .execute()
        )
        return [
            {"role": r["role"], "content": r["content"], "timestamp": str(r["timestamp"])}
            for r in response.data
        ]

    def get_messages_for_llm(self, session_id: str, limit: int = 20) -> list[dict]:
        history = self.get_history(session_id, limit)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]

    def list_sessions(self) -> list[dict]:
        # Get unique sessions with first message
        response = (
            self.client.table("messages")
            .select("session_id, content, timestamp, role")
            .order("timestamp", desc=False)
            .execute()
        )
        # Group by session
        sessions = {}
        for row in response.data:
            sid = row["session_id"]
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "started": str(row["timestamp"]),
                    "message_count": 0,
                    "first_message": "Empty session",
                }
            sessions[sid]["message_count"] += 1
            if row["role"] == "user" and sessions[sid]["first_message"] == "Empty session":
                sessions[sid]["first_message"] = row["content"]

        # Sort by most recent first
        result = sorted(sessions.values(), key=lambda x: x["started"], reverse=True)
        return result

    def clear_session(self, session_id: str):
        self.client.table("messages").delete().eq("session_id", session_id).execute()

    def clear_all(self):
        self.client.table("messages").delete().neq("id", 0).execute()


# ============================================
# Helper: Get secrets
# ============================================

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
# Factory Function
# ============================================

def get_memory():
    """
    Return the best available memory backend.
    Tries Supabase first, falls back to SQLite.
    
    Returns:
        (memory_instance, backend_name) tuple
    """
    supabase_url = _get_secret("SUPABASE_URL")
    supabase_key = _get_secret("SUPABASE_KEY")

    if supabase_url and supabase_key:
        try:
            memory = SupabaseMemory()
            return memory, "Supabase PostgreSQL"
        except Exception as e:
            print(f"⚠️ Supabase connection failed ({e}), falling back to SQLite")

    return SQLiteMemory(), "SQLite (local)"


# ============================================
# Backward Compatibility
# ============================================

class ConversationMemory(SQLiteMemory):
    """Alias for backward compatibility."""
    
    @staticmethod
    def new_session_id() -> str:
        return str(uuid.uuid4())[:8]


# Add new_session_id to both classes
SQLiteMemory.new_session_id = staticmethod(lambda: str(uuid.uuid4())[:8])
SupabaseMemory.new_session_id = staticmethod(lambda: str(uuid.uuid4())[:8])
