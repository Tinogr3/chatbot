"""
ChatHistoryManager - Gestión de persistencia del historial de chat usando SQLite (backend).
"""
import asyncio
import json
from typing import Any, Dict, List, Optional

import aiosqlite


def _get_db_path() -> str:
    import os
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "chat_history.db")


class ChatHistoryManager:
    """Gestor de historial de chat con persistencia en SQLite (acceso asíncrono)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or _get_db_path()
        self._schema_lock = asyncio.Lock()
        self._schema_ready = False

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("PRAGMA journal_mode=WAL;"):
                    pass
                async with db.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        sources TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """):
                    pass
                async with db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)
                """):
                    pass
                await db.commit()
            self._schema_ready = True

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List[str]] = None,
    ) -> int:
        await self._ensure_schema()
        sources_json = json.dumps(sources) if sources else None
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, sources)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, sources_json),
            ) as cursor:
                row_id = cursor.lastrowid
            await db.commit()
            return int(row_id)

    async def get_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT role, content, sources, created_at
                FROM chat_messages WHERE session_id = ?
                ORDER BY created_at ASC LIMIT ?
                """,
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
            messages: List[Dict[str, Any]] = []
            for row in rows:
                msg = {"role": row["role"], "content": row["content"]}
                if row["sources"]:
                    msg["sources"] = json.loads(row["sources"])
                messages.append(msg)
            return messages

    async def delete_history(self, session_id: str) -> int:
        await self._ensure_schema()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "DELETE FROM chat_messages WHERE session_id = ?",
                (session_id,),
            ) as cursor:
                deleted = cursor.rowcount
            await db.commit()
            return int(deleted)
