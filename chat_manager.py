"""
ChatHistoryManager - Gestión de persistencia del historial de chat usando SQLite.
Este módulo permite guardar, recuperar y eliminar el historial de conversaciones.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager


class ChatHistoryManager:
    """
    Gestor de historial de chat con persistencia en SQLite.
    """
    
    def __init__(self, db_path: str = "chat_history.db"):
        """
        Inicializa el gestor de historial.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite.
        """
        self.db_path = db_path
        self._create_tables()
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager para obtener una conexión a la base de datos.
        Maneja automáticamente el cierre de la conexión.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _create_tables(self):
        """
        Crea las tablas necesarias si no existen.
        """
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
            # Crear índice para búsquedas rápidas por session_id
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON chat_messages(session_id)
            """)
            conn.commit()
    
    def save_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        sources: Optional[List[str]] = None
    ) -> int:
        """
        Guarda un mensaje en la base de datos.
        
        Args:
            session_id: Identificador único de la sesión.
            role: Rol del mensaje ('user' o 'assistant').
            content: Contenido del mensaje.
            sources: Lista opcional de fuentes utilizadas (para respuestas del asistente).
        
        Returns:
            ID del mensaje insertado.
        """
        sources_json = json.dumps(sources) if sources else None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_messages (session_id, role, content, sources)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, sources_json))
            conn.commit()
            return cursor.lastrowid
    
    def get_history(
        self, 
        session_id: str, 
        limit: int = 50
    ) -> List[Dict]:
        """
        Recupera el historial de mensajes de una sesión.
        
        Args:
            session_id: Identificador único de la sesión.
            limit: Número máximo de mensajes a recuperar (por defecto 50).
        
        Returns:
            Lista de diccionarios con los mensajes, ordenados cronológicamente.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, sources, created_at
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                LIMIT ?
            """, (session_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                message = {
                    "role": row["role"],
                    "content": row["content"]
                }
                if row["sources"]:
                    message["sources"] = json.loads(row["sources"])
                messages.append(message)
            
            return messages
    
    def delete_history(self, session_id: str) -> int:
        """
        Elimina todo el historial de una sesión.
        
        Args:
            session_id: Identificador único de la sesión.
        
        Returns:
            Número de mensajes eliminados.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM chat_messages
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            return cursor.rowcount
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Obtiene una lista de todas las sesiones con sus estadísticas.
        
        Returns:
            Lista de diccionarios con información de cada sesión.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    session_id,
                    COUNT(*) as message_count,
                    MIN(created_at) as first_message,
                    MAX(created_at) as last_message
                FROM chat_messages
                GROUP BY session_id
                ORDER BY last_message DESC
            """)
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row["session_id"],
                    "message_count": row["message_count"],
                    "first_message": row["first_message"],
                    "last_message": row["last_message"]
                })
            
            return sessions
