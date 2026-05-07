"""
memory.py — Conversation Memory (SQLite)
==========================================
Stores conversation history in a local SQLite database.
Each conversation session gets a unique ID so you can
revisit past chats.

Features:
- Add messages (user, assistant, system, tool)
- Retrieve conversation history by session
- List all past sessions
- Clear a session
"""

import os
import sqlite3
import uuid
from datetime import datetime
from typing import Optional


# ============================================
# Default database path
# ============================================

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "data/memory.db")


class ConversationMemory:
    """
    SQLite-backed conversation memory.
    
    Usage:
        memory = ConversationMemory()
        memory.add_message("session_1", "user", "Hello!")
        memory.add_message("session_1", "assistant", "Hi there!")
        history = memory.get_history("session_1")
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize the memory store.
        
        Args:
            db_path: Path to the SQLite database file.
                     Will be created if it doesn't exist.
        """
        self.db_path = db_path

        # Ensure the data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Create the database and table
        self._init_db()

    def _init_db(self):
        """Create the messages table if it doesn't exist."""
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
            # Index for fast session lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session 
                ON messages(session_id)
            """)
            conn.commit()

    def add_message(self, session_id: str, role: str, content: str):
        """
        Store a message in the database.
        
        Args:
            session_id: Unique identifier for the conversation session.
            role: One of "user", "assistant", "system", or "tool".
            content: The message content.
        """
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, role, content, timestamp),
            )
            conn.commit()

    def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict]:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: The session to retrieve.
            limit: Maximum number of messages to return.
        
        Returns:
            List of message dicts with 'role', 'content', and 'timestamp'.
        """
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
        """
        Get conversation history formatted for the LLM API.
        
        Returns only 'role' and 'content' keys, suitable for
        passing directly to the chat completion API.
        
        Args:
            session_id: The session to retrieve.
            limit: Maximum number of messages.
        
        Returns:
            List of dicts with 'role' and 'content' keys.
        """
        history = self.get_history(session_id, limit)
        return [{"role": msg["role"], "content": msg["content"]} for msg in history]

    def list_sessions(self) -> list[dict]:
        """
        List all conversation sessions with their first message and timestamp.
        
        Returns:
            List of session info dicts.
        """
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
        """
        Delete all messages in a session.
        
        Args:
            session_id: The session to clear.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()

    def clear_all(self):
        """Delete all messages across all sessions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()

    @staticmethod
    def new_session_id() -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())[:8]
