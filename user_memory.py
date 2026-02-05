"""
UserMemoryManager - Sistema de Memoria de Usuario a Largo Plazo.
Extrae y almacena hechos sobre el usuario para personalizar las respuestas del chatbot.
"""

import os
import re
import json
import sqlite3
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager

from langchain_google_genai import ChatGoogleGenerativeAI
from config import get_credentials_and_project


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
        self._llm = None
    
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
    
    def _get_llm(self):
        """Obtiene o inicializa el LLM (Gemini Flash) para extracción de hechos."""
        if self._llm is None:
            credentials, project_id = get_credentials_and_project()
            
            if not project_id:
                api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
                if not api_key:
                    return None
                
                self._llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.1,  # Baja temperatura para extracción precisa
                    max_output_tokens=1024,
                    api_key=api_key
                )
            else:
                self._llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash-exp",
                    temperature=0.1,
                    max_output_tokens=1024,
                    vertexai=True,
                    project=project_id,
                    location="us-central1"
                )
        
        return self._llm
    
    def extract_user_facts(self, user_message: str, ai_response: str) -> List[Dict]:
        """
        Extrae hechos relevantes sobre el usuario usando Gemini Flash.
        
        Args:
            user_message: Mensaje del usuario.
            ai_response: Respuesta del asistente.
        
        Returns:
            Lista de diccionarios con los hechos extraídos.
        """
        llm = self._get_llm()
        if not llm:
            return []
        
        extraction_prompt = f"""Analiza la siguiente conversación y extrae ÚNICAMENTE hechos concretos y relevantes sobre el usuario.

MENSAJE DEL USUARIO:
{user_message}

RESPUESTA DEL ASISTENTE:
{ai_response}

INSTRUCCIONES:
1. Extrae SOLO hechos explícitos mencionados por el usuario (no inferencias)
2. Categoriza cada hecho en uno de estos tipos:
   - "nombre": Nombre del usuario
   - "trabajo": Profesión, cargo o empresa
   - "educacion": Estudios, universidad, carrera
   - "stack_tecnologico": Lenguajes, frameworks, herramientas que usa
   - "preferencias": Preferencias de aprendizaje, temas de interés
   - "ubicacion": Ciudad, país
   - "otro": Otros hechos relevantes

3. Si NO hay hechos relevantes, devuelve una lista vacía: []
4. Responde ÚNICAMENTE con JSON válido, sin texto adicional.

FORMATO DE RESPUESTA (JSON):
[
  {{"tipo": "stack_tecnologico", "valor": "Python", "confianza": 0.9}},
  {{"tipo": "trabajo", "valor": "desarrollador senior", "confianza": 0.8}}
]

RESPUESTA JSON:"""

        try:
            response = llm.invoke(extraction_prompt)
            content = response.content.strip()
            
            # DEBUG: Log raw response
            print(f"DEBUG JSON RAW: {content}")
            
            # Usar regex robusta para extraer el JSON array
            # Buscar el primer '[' y el último ']'
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            else:
                # Intentar limpiar manualmente
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
            
            # Si está vacío o no es JSON válido, retornar lista vacía
            if not content or content == "[]":
                return []
            
            facts = json.loads(content)
            
            # Validar estructura de los hechos
            validated_facts = []
            for fact in facts:
                if isinstance(fact, dict) and "tipo" in fact and "valor" in fact:
                    validated_facts.append({
                        "tipo": fact.get("tipo", "otro"),
                        "valor": fact.get("valor", ""),
                        "confianza": float(fact.get("confianza", 0.8))
                    })
            
            return validated_facts
            
        except json.JSONDecodeError as e:
            print(f"[UserMemory] Error JSON decode: {e}")
            return []
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
    
    def extract_and_save_async(self, session_id: str, user_message: str, ai_response: str):
        """
        Extrae y guarda hechos de forma asíncrona (en un thread separado).
        No bloquea el hilo principal del chat.
        
        Args:
            session_id: ID de la sesión del usuario.
            user_message: Mensaje del usuario.
            ai_response: Respuesta del asistente.
        """
        def _extract_and_save():
            try:
                facts = self.extract_user_facts(user_message, ai_response)
                if facts:
                    saved = self.save_facts(session_id, facts)
                    print(f"[UserMemory] Extraídos y guardados {saved} hechos del usuario")
            except Exception as e:
                print(f"[UserMemory] Error en extracción asíncrona: {e}")
        
        # Ejecutar en un thread separado para no bloquear
        thread = threading.Thread(target=_extract_and_save, daemon=True)
        thread.start()
