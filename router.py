"""
Smart Router - Sistema de enrutamiento inteligente de queries.
Clasifica la intención del usuario y dirige al flujo de procesamiento adecuado.
"""
import os
from typing import Optional, Dict, Any, List
from enum import Enum

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

from config import get_credentials_and_project


class QueryCategory(Enum):
    """Categorías de clasificación de queries."""
    CONVERSACION = "CONVERSACION"
    PREGUNTA_DOCUMENTO = "PREGUNTA_DOCUMENTO"
    RESUMEN = "RESUMEN"
    APRENDIZAJE = "APRENDIZAJE"
    OTRO = "OTRO"


def get_model(temperature: float = 0.7):
    """Obtiene el modelo Gemini Flash para clasificación rápida."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=256,
                api_key=api_key
            )
        
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-2.5-pro",
                temperature=temperature,
                max_output_tokens=256,
                vertexai=True,
                project=project_id,
                location="us-central1"
            )
    except Exception as e:
        print(f"Error inicializando modelo Flash: {e}")
    return None


def route_query(query: str) -> str:
    """
    Clasifica la intención del usuario en una categoría.
    
    Args:
        query: Texto de la consulta del usuario.
    
    Returns:
        Categoría de la query: CONVERSACION, PREGUNTA_DOCUMENTO, RESUMEN, APRENDIZAJE, OTRO
    """
    llm = get_model(temperature=0.1)
    if not llm:
        # Si no hay modelo, asumir pregunta de documento por defecto
        return QueryCategory.PREGUNTA_DOCUMENTO.value
    
    classification_prompt = f"""Clasifica la siguiente consulta del usuario en UNA de estas categorías:

CATEGORÍAS:
- CONVERSACION: Saludos, despedidas, charla casual, preguntas personales al asistente, agradecimientos. Incluye cuando el usuario da información sobre sí mismo (ej: "me llamo X", "trabajo en Y", "soy de Z") o da instrucciones sobre cómo comportarse.
- PREGUNTA_DOCUMENTO: Preguntas específicas que requieren buscar información en documentos
- RESUMEN: Solicitudes de resumir, sintetizar o dar una visión general del contenido
- APRENDIZAJE: El usuario quiere aprender, estudiar, practicar, hacer ejercicios o que le enseñen un tema
- OTRO: Cualquier otra cosa que no encaje en las anteriores

CONSULTA DEL USUARIO:
"{query}"

INSTRUCCIONES:
- Responde ÚNICAMENTE con una de estas palabras: CONVERSACION, PREGUNTA_DOCUMENTO, RESUMEN, APRENDIZAJE, OTRO
- No agregues explicaciones ni texto adicional

CATEGORÍA:"""

    try:
        response = llm.invoke(classification_prompt)
        category = response.content.strip().upper()
        
        # Validar que sea una categoría válida
        valid_categories = [c.value for c in QueryCategory]
        if category in valid_categories:
            return category
        
        # Si contiene alguna categoría válida, extraerla
        for valid_cat in valid_categories:
            if valid_cat in category:
                return valid_cat
        
        # Por defecto, asumimos pregunta de documento
        return QueryCategory.PREGUNTA_DOCUMENTO.value
        
    except Exception as e:
        print(f"Error clasificando query: {e}")
        return QueryCategory.PREGUNTA_DOCUMENTO.value


def get_direct_response(query: str, session_id: str = None, user_facts: str = "") -> str:
    """
    Genera una respuesta directa para conversaciones sin usar RAG.
    
    Args:
        query: Consulta del usuario.
        session_id: ID de sesión del usuario.
        user_facts: Hechos conocidos del usuario (formateados).
    
    Returns:
        Respuesta generada.
    """
    llm = get_model(temperature=0.7)
    if not llm:
        return "Lo siento, no puedo responder en este momento."
    
    user_context = ""
    if user_facts:
        user_context = f"\n\nInformación conocida sobre el usuario:\n{user_facts}\n"
    
    prompt = f"""Eres un asistente educativo amigable y servicial.{user_context}

Responde de manera natural y cálida a la siguiente conversación del usuario.
Si te preguntan qué puedes hacer, menciona que puedes:
- Responder preguntas sobre documentos cargados
- Generar resúmenes del contenido
- Crear sesiones de aprendizaje interactivas con preguntas

USUARIO: {query}

RESPUESTA:"""

    try:
        response = llm.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return f"Error al generar respuesta: {str(e)}"


def get_summary_response(query: str, vector_store, session_id: str = None) -> Dict[str, Any]:
    """
    Genera un resumen del contenido de los documentos.
    
    Args:
        query: Consulta del usuario.
        vector_store: Vector store con los documentos.
        session_id: ID de sesión del usuario.
    
    Returns:
        Diccionario con 'answer' y 'source_documents'.
    """
    llm = get_model(temperature=0.3)
    if not llm:
        return {"answer": "No puedo generar el resumen en este momento.", "source_documents": []}
    
    # Recuperar más documentos para el resumen
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 30, "lambda_mult": 0.7}
    )
    
    try:
        docs = retriever.invoke(query)
        
        if not docs:
            return {"answer": "No hay documentos disponibles para resumir.", "source_documents": []}
        
        # Construir contexto con todos los documentos
        context_parts = []
        for doc in docs:
            source = doc.metadata.get("source", "Desconocido")
            context_parts.append(f"[{source}]\n{doc.page_content}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        summary_prompt = f"""Genera un resumen completo y estructurado del siguiente contenido.

CONTENIDO:
{context}

INSTRUCCIONES:
1. Organiza el resumen por temas principales
2. Usa viñetas y sublistas para mayor claridad
3. Menciona las fuentes de donde proviene cada sección
4. Incluye los conceptos más importantes
5. El resumen debe ser comprensivo pero conciso

RESUMEN ESTRUCTURADO:"""

        response = llm.invoke(summary_prompt)
        
        return {
            "answer": response.content.strip(),
            "source_documents": docs
        }
        
    except Exception as e:
        return {"answer": f"Error generando resumen: {str(e)}", "source_documents": []}


class LearningFlowManager:
    """
    Gestor del flujo de aprendizaje interactivo.
    Mantiene el estado de la sesión de aprendizaje.
    """
    
    def __init__(self, vector_store, session_id: str = None):
        self.vector_store = vector_store
        self.session_id = session_id
        self.llm = get_model(temperature=0.3)
    
    def start_learning_session(self, topic_query: str) -> Dict[str, Any]:
        """
        Inicia una nueva sesión de aprendizaje sobre un tema.
        
        Args:
            topic_query: Tema o área que el usuario quiere aprender.
        
        Returns:
            Diccionario con la primera lección y pregunta.
        """
        if not self.llm:
            return {
                "content": "No puedo iniciar la sesión de aprendizaje en este momento.",
                "question": None,
                "topic": None,
                "source_documents": []
            }
        
        # Recuperar documentos relevantes al tema
        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 8, "fetch_k": 20, "lambda_mult": 0.6}
        )
        
        try:
            docs = retriever.invoke(topic_query)
            
            if not docs:
                return {
                    "content": "No encontré información sobre ese tema en los documentos. ¿Podrías especificar otro tema?",
                    "question": None,
                    "topic": None,
                    "source_documents": []
                }
            
            # Construir contexto
            context_parts = []
            for doc in docs:
                source = doc.metadata.get("source", "Desconocido")
                context_parts.append(f"[{source}]\n{doc.page_content}")
            
            context = "\n\n".join(context_parts)
            
            lesson_prompt = f"""Actúa como un Tutor Socrático experto (Método de Aprendizaje Guiado).
Tu objetivo NO es dar una clase magistral, sino guiar al estudiante para que descubra el conocimiento.

CONTENIDO DE REFERENCIA:
{context}

TEMA SOLICITADO: {topic_query}

INSTRUCCIONES ESTRICTAS:
1. NO escribas parrafadas largas. Sé breve y conversacional.
2. Introduce el concepto más básico del tema solicitado muy brevemente.
3. Inmediatamente después, formula una pregunta de reflexión o un pequeño desafío para que el estudiante piense.
4. NUNCA des la respuesta completa de inmediato. Espera a que el estudiante intente responder.

FORMATO DE RESPUESTA:
(Saludo breve y motivador)

(Breve introducción al concepto - Máximo 2 frases)

(Pregunta guía o escenario práctico para que el usuario resuelva)
"""

            response = self.llm.invoke(lesson_prompt)
            
            return {
                "content": response.content.strip(),
                "is_learning_mode": True,
                "awaiting_answer": True,
                "topic": topic_query,
                "source_documents": docs
            }
            
        except Exception as e:
            return {
                "content": f"Error iniciando sesión de aprendizaje: {str(e)}",
                "question": None,
                "topic": None,
                "source_documents": []
            }
    
    def evaluate_answer(
        self, 
        user_answer: str, 
        topic: str,
        previous_content: str
    ) -> Dict[str, Any]:
        """
        Evalúa la respuesta del usuario y decide si reforzar o avanzar.
        
        Args:
            user_answer: Respuesta del usuario.
            topic: Tema de aprendizaje actual.
            previous_content: Contenido de la lección anterior.
        
        Returns:
            Diccionario con retroalimentación y siguiente paso.
        """
        if not self.llm:
            return {
                "content": "No puedo evaluar la respuesta en este momento.",
                "is_correct": False,
                "source_documents": []
            }
        
        # Recuperar más contexto sobre el tema
        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 6, "fetch_k": 15}
        )
        
        try:
            docs = retriever.invoke(topic)
            
            context_parts = []
            for doc in docs:
                context_parts.append(doc.page_content)
            context = "\n\n".join(context_parts)
            
            eval_prompt = f"""Eres un Tutor Socrático evaluando a un estudiante.

CONTEXTO PREVIO: {previous_content}
MATERIAL DE REFERENCIA: {context}
RESPUESTA DEL ESTUDIANTE: {user_answer}

INSTRUCCIONES DE EVALUACIÓN:
1. Analiza la lógica del estudiante.
2. Si la respuesta es INCORRECTA:
   - NO le des la solución correcta.
   - Identifica dónde falló su lógica.
   - Dale una pista o hazle una pregunta más sencilla que le ayude a darse cuenta de su error.
3. Si la respuesta es CORRECTA:
   - Felicítalo brevemente.
   - Profundiza un poco más en el tema o pasa al siguiente concepto lógico.
   - Haz una nueva pregunta para seguir avanzando (Scaffolding).

FORMATO:
- Empieza con un emoji de estado (✅, ⚠️, o ❌).
- Feedback constructivo (sin dar la solución si falló).
- Nueva pregunta o reto.
"""

            response = self.llm.invoke(eval_prompt)
            content = response.content.strip()
            
            # Determinar si fue correcta basándose en el emoji
            is_correct = content.startswith("✅")
            is_partial = content.startswith("⚠️")
            
            return {
                "content": content,
                "is_correct": is_correct,
                "is_partial": is_partial,
                "is_learning_mode": True,
                "awaiting_answer": True,
                "topic": topic,
                "source_documents": docs
            }
            
        except Exception as e:
            return {
                "content": f"Error evaluando respuesta: {str(e)}",
                "is_correct": False,
                "source_documents": []
            }
    
    def end_learning_session(self) -> str:
        """Finaliza la sesión de aprendizaje."""
        return """## 🎓 Sesión de aprendizaje finalizada

¡Buen trabajo! Has completado esta sesión de estudio.

**¿Qué puedes hacer ahora?**
- Escribe "aprender [tema]" para iniciar una nueva sesión
- Hazme preguntas específicas sobre los documentos
- Pídeme un resumen del contenido

¡Sigue aprendiendo! 📚"""
