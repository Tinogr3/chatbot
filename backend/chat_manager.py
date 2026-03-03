"""
ChatHistoryManager - Gestión de persistencia del historial de chat usando SQLite (backend).
"""
import sqlite3
import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional


def _get_db_path() -> str:
    import os
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "chat_history.db")


class ChatHistoryManager:
    """Gestor de historial de chat con persistencia en SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _get_db_path()
        self._create_tables()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _create_tables(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)
            """)
            conn.commit()

    def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[str]] = None
    ) -> int:
        sources_json = json.dumps(sources) if sources else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages (session_id, role, content, sources)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, sources_json))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, sources, created_at
                FROM chat_messages WHERE session_id = ?
                ORDER BY created_at ASC LIMIT ?
            """, (session_id, limit))
            messages = []
            for row in cursor.fetchall():
                msg = {"role": row["role"], "content": row["content"]}
                if row["sources"]:
                    msg["sources"] = json.loads(row["sources"])
                messages.append(msg)
            return messages

    def delete_history(self, session_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount
