"""
UserMemoryManager - Sistema de Memoria de Usuario a Largo Plazo.
Extrae y almacena hechos sobre el usuario para personalizar las respuestas del chatbot.
"""

import os
import sqlite3
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from config import get_credentials_and_project


class UserFactSchema(BaseModel):
    """Un hecho extraído sobre el usuario."""

    tipo: str = Field(description="Categoría: nombre, trabajo, educacion, stack_tecnologico, preferencias, ubicacion, otro")
    valor: str = Field(description="Valor del hecho mencionado por el usuario")
    confianza: float = Field(default=0.8, ge=0.0, le=1.0, description="Confianza en el hecho (0-1)")


class UserFactsOutputSchema(BaseModel):
    """Lista de hechos sobre el usuario extraídos de la conversación."""

    facts: List[UserFactSchema] = Field(default_factory=list, description="Lista de hechos concretos extraídos")


class UserMemoryManager:
    """
    Gestor de memoria de usuario a largo plazo.
    Extrae hechos relevantes del usuario y los almacena en SQLite.
    """
    
    def __init__(self, db_path: str = "chat_history.db"):
        """
        Inicializa el gestor de memoria de usuario.
        
        Args:
            db_path: Ruta al archivo de base de datos SQLite.
        """
        self.db_path = db_path
        self._create_tables()
        self._llm_cache: Dict[int, Optional[ChatGoogleGenerativeAI]] = {}
    
    @contextmanager
    def _get_connection(self):
        """Context manager para obtener conexión a la base de datos."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _create_tables(self):
        """Crea la tabla user_profile si no existe."""
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_profile_session 
                ON user_profile(session_id)
            """)
            conn.commit()
    
    def _get_llm(self, max_tokens: int = 65535):
        """Obtiene o inicializa el LLM (Gemini Flash) para extracción de hechos. Cache por max_tokens."""
        if max_tokens not in self._llm_cache:
            credentials, project_id = get_credentials_and_project()
            if not project_id:
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
                if not api_key:
                    return None
                self._llm_cache[max_tokens] = ChatGoogleGenerativeAI(
                    model="gemini-3-flash-preview",
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    api_key=api_key
                )
            else:
                self._llm_cache[max_tokens] = ChatGoogleGenerativeAI(
                    model="gemini-3-flash-preview",
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    vertexai=True,
                    project=project_id,
                    location="global",
                )
        return self._llm_cache[max_tokens]
    
    def extract_user_facts(self, user_message: str, ai_response: str, max_tokens: int = 65535) -> List[Dict]:
        """
        Extrae hechos relevantes sobre el usuario usando Gemini Flash.
        
        Args:
            user_message: Mensaje del usuario.
            ai_response: Respuesta del asistente.
            max_tokens: Límite de tokens (p. ej. st.session_state["max_tokens"]).
        
        Returns:
            Lista de diccionarios con los hechos extraídos.
        """
        llm = self._get_llm(max_tokens=max_tokens)
        if not llm:
            return []

        extraction_prompt = f"""Analiza la siguiente conversación y extrae hechos concretos y relevantes sobre el usuario.

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
            result = structured_llm.invoke(extraction_prompt)
            if result is None or not result.facts:
                return []
            return [
                {"tipo": f.tipo, "valor": f.valor, "confianza": f.confianza}
                for f in result.facts
            ]
        except Exception as e:
            print(f"[UserMemory] Error extrayendo hechos: {e}")
            return []
    
    def save_facts(self, session_id: str, facts: List[Dict], max_retries: int = 3) -> int:
        """
        Guarda los hechos extraídos en la base de datos.
        
        Args:
            session_id: ID de la sesión del usuario.
            facts: Lista de hechos a guardar.
            max_retries: Número máximo de reintentos si la DB está bloqueada.
        
        Returns:
            Número de hechos guardados.
        """
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
                                DO UPDATE SET 
                                    confidence = MAX(confidence, excluded.confidence),
                                    updated_at = CURRENT_TIMESTAMP
                            """, (session_id, fact["tipo"], fact["valor"], fact.get("confianza", 0.8)))
                            saved_count += 1
                        except sqlite3.IntegrityError as e:
                            print(f"[UserMemory] Hecho duplicado ignorado: {e}")
                        except Exception as e:
                            print(f"[UserMemory] Error guardando hecho: {e}")
                    conn.commit()
                # Si llegamos aquí, el commit fue exitoso
                break
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    print(f"[UserMemory] DB bloqueada, reintentando ({attempt + 1}/{max_retries})...")
                    time.sleep(0.5 * (attempt + 1))  # Backoff exponencial
                else:
                    print(f"[UserMemory] Error SQLite: {e}")
                    break
            except Exception as e:
                print(f"[UserMemory] Error inesperado guardando hechos: {e}")
                break
        
        if saved_count > 0:
            print(f"[UserMemory] ✅ Guardados {saved_count} hechos para sesión {session_id}")
        
        return saved_count
    
    def get_user_facts(self, session_id: str) -> List[Dict]:
        """
        Recupera todos los hechos conocidos de un usuario.
        
        Args:
            session_id: ID de la sesión del usuario.
        
        Returns:
            Lista de diccionarios con los hechos del usuario.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fact_type, fact_value, confidence
                FROM user_profile
                WHERE session_id = ?
                ORDER BY confidence DESC, updated_at DESC
            """, (session_id,))
            
            facts = []
            for row in cursor.fetchall():
                facts.append({
                    "tipo": row["fact_type"],
                    "valor": row["fact_value"],
                    "confianza": row["confidence"]
                })
            
            return facts
    
    def get_user_facts_formatted(self, session_id: str) -> str:
        """
        Recupera los hechos del usuario en formato de texto para inyectar en el prompt.
        
        Args:
            session_id: ID de la sesión del usuario.
        
        Returns:
            String formateado con los hechos del usuario.
        """
        facts = self.get_user_facts(session_id)
        
        if not facts:
            return ""
        
        # Agrupar hechos por tipo
        facts_by_type = {}
        for fact in facts:
            tipo = fact["tipo"]
            if tipo not in facts_by_type:
                facts_by_type[tipo] = []
            facts_by_type[tipo].append(fact["valor"])
        
        # Formatear para el prompt
        lines = []
        type_labels = {
            "nombre": "Nombre",
            "trabajo": "Trabajo/Profesión",
            "educacion": "Educación",
            "stack_tecnologico": "Stack Tecnológico",
            "preferencias": "Preferencias",
            "ubicacion": "Ubicación",
            "otro": "Otros datos"
        }
        
        for tipo, valores in facts_by_type.items():
            label = type_labels.get(tipo, tipo.capitalize())
            if len(valores) == 1:
                lines.append(f"- {label}: {valores[0]}")
            else:
                lines.append(f"- {label}: {', '.join(valores)}")
        
        return "\n".join(lines)
    
    def delete_user_facts(self, session_id: str) -> int:
        """
        Elimina todos los hechos de un usuario.
        
        Args:
            session_id: ID de la sesión del usuario.
        
        Returns:
            Número de hechos eliminados.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_profile
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
            return cursor.rowcount
    
    def extract_and_save_async(self, session_id: str, user_message: str, ai_response: str, max_tokens: int = 65535):
        """
        Extrae y guarda hechos de forma asíncrona (en un thread separado).
        No bloquea el hilo principal del chat.
        
        Args:
            session_id: ID de la sesión del usuario.
            user_message: Mensaje del usuario.
            ai_response: Respuesta del asistente.
            max_tokens: Límite de tokens (p. ej. st.session_state["max_tokens"]).
        """
        def _extract_and_save():
            try:
                facts = self.extract_user_facts(user_message, ai_response, max_tokens=max_tokens)
                if facts:
                    saved = self.save_facts(session_id, facts)
                    print(f"[UserMemory] Extraídos y guardados {saved} hechos del usuario")
            except Exception as e:
                print(f"[UserMemory] Error en extracción asíncrona: {e}")
        
        # Ejecutar en un thread separado para no bloquear
        thread = threading.Thread(target=_extract_and_save, daemon=True)
        thread.start()
