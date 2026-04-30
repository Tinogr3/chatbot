"""
UserMemoryManager - Sistema de Memoria de Usuario (backend).
"""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import get_credentials_and_project
from gemini_models import gemini_flash_model_id


class UserFactSchema(BaseModel):
    tipo: str = Field(description="Categoría: nombre, trabajo, educacion, stack_tecnologico, preferencias, ubicacion, otro")
    valor: str = Field(description="Valor del hecho mencionado por el usuario")
    confianza: float = Field(default=0.8, ge=0.0, le=1.0, description="Confianza en el hecho (0-1)")


class UserFactsOutputSchema(BaseModel):
    facts: List[UserFactSchema] = Field(default_factory=list, description="Lista de hechos concretos extraídos")


def _get_db_path() -> str:
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "chat_history.db")


class UserMemoryManager:
    """Gestor de memoria de usuario a largo plazo."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or _get_db_path()
        self._create_tables()
        self._llm_cache: Dict[int, Optional[ChatGoogleGenerativeAI]] = {}

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
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    fact_value TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, fact_type, fact_value)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_profile_session ON user_profile(session_id)")
            conn.commit()

    def _get_llm(self, max_tokens: int = 65535) -> Optional[ChatGoogleGenerativeAI]:
        if max_tokens not in self._llm_cache:
            credentials, project_id = get_credentials_and_project()
            if not project_id:
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
                if not api_key:
                    return None
                flash = gemini_flash_model_id()
                self._llm_cache[max_tokens] = ChatGoogleGenerativeAI(
                    model=flash,
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    api_key=api_key
                )
            else:
                flash = gemini_flash_model_id()
                self._llm_cache[max_tokens] = ChatGoogleGenerativeAI(
                    model=flash,
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    vertexai=True,
                    project=project_id,
                    location="global",
                )
        return self._llm_cache[max_tokens]

    def extract_user_facts(self, user_message: str, ai_response: str, max_tokens: int = 65535) -> List[Dict[str, Any]]:
        llm = self._get_llm(max_tokens=max_tokens)
        if not llm:
            return []
        prompt = f"""Analiza la siguiente conversación y extrae hechos concretos y relevantes sobre el usuario.

MENSAJE DEL USUARIO:
{user_message}

RESPUESTA DEL ASISTENTE:
{ai_response}

INSTRUCCIONES:
- Extrae SOLO hechos explícitos mencionados por el usuario (no inferencias).
- Categoriza cada hecho en uno de estos tipos: nombre, trabajo, educacion, stack_tecnologico, preferencias, ubicacion, otro.
- Si NO hay hechos relevantes, devuelve una lista vacía de facts."""
        try:
            structured_llm = llm.with_structured_output(UserFactsOutputSchema)
            result = structured_llm.invoke(prompt)
            if result is None or not result.facts:
                return []
            return [{"tipo": f.tipo, "valor": f.valor, "confianza": f.confianza} for f in result.facts]
        except Exception:
            return []

    def save_facts(self, session_id: str, facts: List[Dict[str, Any]], max_retries: int = 3) -> int:
        if not facts:
            return 0
        saved_count = 0
        for attempt in range(max_retries):
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    for fact in facts:
                        try:
                            cursor.execute("""
                                INSERT INTO user_profile (session_id, fact_type, fact_value, confidence)
                                VALUES (?, ?, ?, ?)
                                ON CONFLICT(session_id, fact_type, fact_value)
                                DO UPDATE SET confidence = MAX(confidence, excluded.confidence),
                                    updated_at = CURRENT_TIMESTAMP
                            """, (session_id, fact["tipo"], fact["valor"], fact.get("confianza", 0.8)))
                            saved_count += 1
                        except (sqlite3.IntegrityError, Exception):
                            pass
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.5 * (attempt + 1))
                else:
                    break
            except Exception:
                break
        return saved_count

    def get_user_facts(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fact_type, fact_value, confidence
                FROM user_profile WHERE session_id = ?
                ORDER BY confidence DESC, updated_at DESC
            """, (session_id,))
            return [
                {"tipo": row["fact_type"], "valor": row["fact_value"], "confianza": row["confidence"]}
                for row in cursor.fetchall()
            ]

    def get_user_facts_formatted(self, session_id: str) -> str:
        facts = self.get_user_facts(session_id)
        if not facts:
            return ""
        facts_by_type = {}
        for fact in facts:
            t = fact["tipo"]
            if t not in facts_by_type:
                facts_by_type[t] = []
            facts_by_type[t].append(fact["valor"])
        type_labels = {
            "nombre": "Nombre", "trabajo": "Trabajo/Profesión", "educacion": "Educación",
            "stack_tecnologico": "Stack Tecnológico", "preferencias": "Preferencias",
            "ubicacion": "Ubicación", "otro": "Otros datos"
        }
        lines = []
        for tipo, valores in facts_by_type.items():
            label = type_labels.get(tipo, tipo.capitalize())
            lines.append(f"- {label}: {', '.join(valores)}" if len(valores) > 1 else f"- {label}: {valores[0]}")
        return "\n".join(lines)

    def delete_user_facts(self, session_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile WHERE session_id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount

    def extract_and_save_async(self, session_id: str, user_message: str, ai_response: str, max_tokens: int = 65535) -> None:
        def _run() -> None:
            try:
                facts = self.extract_user_facts(user_message, ai_response, max_tokens=max_tokens)
                if facts:
                    self.save_facts(session_id, facts)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
