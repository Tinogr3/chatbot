"""
Smart Router - Sistema de enrutamiento inteligente de queries (backend).
"""
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_credentials_and_project
from logger import get_logger

logger = get_logger("router")


def extract_text(content: Any) -> str:
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts)
    return str(content) if content is not None else ""


class QueryCategory(Enum):
    CONVERSACION = "CONVERSACION"
    PREGUNTA_DOCUMENTO = "PREGUNTA_DOCUMENTO"
    RESUMEN = "RESUMEN"
    APRENDIZAJE = "APRENDIZAJE"
    OTRO = "OTRO"


def get_model(temperature: float = 0.7, max_output_tokens: int = 65535) -> Optional[ChatGoogleGenerativeAI]:
    try:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("VERTEX_AI_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-3-pro-preview",
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                api_key=api_key
            )
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model=os.getenv("VERTEX_AI_MODEL") or "gemini-3-pro-preview",
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                vertexai=True,
                project=project_id,
                location="global",
            )
    except Exception as e:
        logger.warning("Error initializing LLM: %s", e)
        return None


def route_query(query: str, max_tokens: int = 65535) -> str:
    llm = get_model(temperature=0.1, max_output_tokens=max_tokens)
    if not llm:
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
        category = extract_text(response.content).strip().upper()
        valid_categories = [c.value for c in QueryCategory]
        if category in valid_categories:
            return category
        for valid_cat in valid_categories:
            if valid_cat in category:
                return valid_cat
        return QueryCategory.PREGUNTA_DOCUMENTO.value
    except Exception as e:
        logger.warning("Error routing query: %s", e)
        return QueryCategory.PREGUNTA_DOCUMENTO.value


def get_direct_response(query: str, session_id: Optional[str] = None, user_facts: str = "", max_tokens: int = 65535) -> str:
    llm = get_model(temperature=0.7, max_output_tokens=max_tokens)
    if not llm:
        return "Lo siento, no puedo responder en este momento."
    user_context = f"\n\nInformación conocida sobre el usuario:\n{user_facts}\n" if user_facts else ""
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
        return extract_text(response.content).strip()
    except Exception as e:
        logger.warning("Error in get_direct_response: %s", e)
        return f"Error al generar respuesta: {str(e)}"


def get_summary_response(
    query: str,
    vector_store: Any,
    session_id: Optional[str] = None,
    max_tokens: int = 65535,
) -> Dict[str, Any]:
    llm = get_model(temperature=0.3, max_output_tokens=max_tokens)
    if not llm:
        return {"answer": "No puedo generar el resumen en este momento.", "source_documents": []}
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 10, "fetch_k": 30, "lambda_mult": 0.7}
    )
    try:
        docs = retriever.invoke(query)
        if not docs:
            return {"answer": "No hay documentos disponibles para resumir.", "source_documents": []}
        context_parts = [f"[{d.metadata.get('source', 'Desconocido')}]\n{d.page_content}" for d in docs]
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
        return {"answer": extract_text(response.content).strip(), "source_documents": docs}
    except Exception as e:
        logger.warning("Error generating summary: %s", e)
        return {"answer": f"Error generando resumen: {str(e)}", "source_documents": []}


class LearningFlowManager:
    def __init__(self, vector_store: Any, session_id: Optional[str] = None, max_tokens: int = 65535) -> None:
        self.vector_store = vector_store
        self.session_id = session_id
        self.max_tokens = max_tokens
        self.llm = get_model(temperature=0.3, max_output_tokens=max_tokens)

    def start_learning_session(self, topic_query: str) -> Dict[str, Any]:
        """Inicia una sesión de aprendizaje sobre el tema indicado."""
        if not self.llm:
            return {"content": "No puedo iniciar la sesión de aprendizaje en este momento.", "question": None, "topic": None, "source_documents": []}
        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 8, "fetch_k": 20, "lambda_mult": 0.6}
        )
        try:
            docs = retriever.invoke(topic_query)
            if not docs:
                return {"content": "No encontré información sobre ese tema en los documentos. ¿Podrías especificar otro tema?", "question": None, "topic": None, "source_documents": []}
            context_parts = [f"[{d.metadata.get('source', 'Desconocido')}]\n{d.page_content}" for d in docs]
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
                "content": extract_text(response.content).strip(),
                "is_learning_mode": True,
                "awaiting_answer": True,
                "topic": topic_query,
                "source_documents": docs
            }
        except Exception as e:
            logger.warning("Error starting learning session: %s", e)
            return {"content": f"Error iniciando sesión de aprendizaje: {str(e)}", "question": None, "topic": None, "source_documents": []}

    def evaluate_answer(self, user_answer: str, topic: str, previous_content: str) -> Dict[str, Any]:
        if not self.llm:
            return {"content": "No puedo evaluar la respuesta en este momento.", "is_correct": False, "source_documents": []}
        retriever = self.vector_store.as_retriever(search_type="mmr", search_kwargs={"k": 6, "fetch_k": 15})
        try:
            docs = retriever.invoke(topic)
            context = "\n\n".join(d.page_content for d in docs)
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
            content = extract_text(response.content).strip()
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
            logger.warning("Error evaluating answer: %s", e)
            return {"content": f"Error evaluando respuesta: {str(e)}", "is_correct": False, "source_documents": []}

    def end_learning_session(self) -> str:
        return """## 🎓 Sesión de aprendizaje finalizada

¡Buen trabajo! Has completado esta sesión de estudio.

**¿Qué puedes hacer ahora?**
- Escribe "aprender [tema]" para iniciar una nueva sesión
- Hazme preguntas específicas sobre los documentos
- Pídeme un resumen del contenido

¡Sigue aprendiendo! 📚"""
