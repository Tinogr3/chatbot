"""
Smart Router - Sistema de enrutamiento inteligente de queries (backend).
"""
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI

from config import get_credentials_and_project
from gemini_models import gemini_pro_model_id
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
    EXAMEN = "EXAMEN"
    APRENDIZAJE = "APRENDIZAJE"
    OTRO = "OTRO"


def get_model(temperature: float = 0.7, max_output_tokens: int = 65535) -> Optional[ChatGoogleGenerativeAI]:
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            return ChatGoogleGenerativeAI(
                model=gemini_pro_model_id(),
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                api_key=api_key
            )
        credentials, project_id = get_credentials_and_project()
        if credentials and project_id:
            return ChatGoogleGenerativeAI(
                model=gemini_pro_model_id(),
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
- EXAMEN: Solicitudes de crear un examen, test, cuestionario, evaluación con preguntas o repasar con preguntas tipo examen sobre el material
- APRENDIZAJE: El usuario quiere aprender con tutoría guiada, estudiar con el modo tutor, practicar de forma conversacional o que le enseñen paso a paso un tema (no un examen escrito de una vez)
- OTRO: Cualquier otra cosa que no encaje en las anteriores

CONSULTA DEL USUARIO:
"{query}"

INSTRUCCIONES:
- Responde ÚNICAMENTE con una de estas palabras: CONVERSACION, PREGUNTA_DOCUMENTO, RESUMEN, EXAMEN, APRENDIZAJE, OTRO
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
        search_kwargs={"k": 150, "fetch_k": 450, "lambda_mult": 0.7}
    )
    try:
        docs = retriever.invoke(query)
        if not docs:
            return {"answer": "No hay documentos disponibles para resumir.", "source_documents": []}
        context_parts = [f"[{d.metadata.get('source', 'Desconocido')}]\n{d.page_content}" for d in docs]
        context = "\n\n---\n\n".join(context_parts)
        summary_prompt = f"""Estás recibiendo FRAGMENTOS DESORDENADOS de uno o más documentos más grandes (bloques recuperados por similitud). El orden en que aparecen NO refleja el orden original del documento.

TU LABOR: Sintetizar TODO el contenido recibido en un único resumen coherente. No dejes fuera ideas de ningún bloque: cada fragmento aporta información que debe quedar reflejada en el resumen. Si un tema aparece en varios fragmentos, intégralo en una sola sección; si hay datos, cifras o conceptos en cualquier bloque, inclúyelos.

CONTENIDO (fragmentos desordenados):
{context}

INSTRUCCIONES:
1. Considera todos los bloques por igual; no priorices solo los primeros.
2. Organiza el resumen por temas principales, integrando la información de todos los fragmentos.
3. Usa viñetas y sublistas para mayor claridad.
4. Menciona las fuentes cuando sea relevante.
5. Incluye los conceptos, datos e ideas importantes de TODOS los fragmentos recibidos.
6. El resumen debe ser comprensivo y completo, sin omitir contenido por estar en bloques alejados en la lista.

RESUMEN ESTRUCTURADO (sintetizando todo el contenido recibido):"""
        response = llm.invoke(summary_prompt)
        return {"answer": extract_text(response.content).strip(), "source_documents": docs}
    except Exception as e:
        logger.warning("Error generating summary: %s", e)
        return {"answer": f"Error generando resumen: {str(e)}", "source_documents": []}


def get_exam_response(
    query: str,
    vector_store: Any,
    session_id: Optional[str] = None,
    max_tokens: int = 65535,
) -> Dict[str, Any]:
    """Genera un examen (preguntas con opciones y breve clave) a partir de los documentos."""
    llm = get_model(temperature=0.35, max_output_tokens=max_tokens)
    if not llm:
        return {"answer": "No puedo generar el examen en este momento.", "source_documents": []}
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 150, "fetch_k": 450, "lambda_mult": 0.7},
    )
    try:
        docs = retriever.invoke(query)
        if not docs:
            return {"answer": "No hay documentos disponibles para crear el examen.", "source_documents": []}
        context_parts = [f"[{d.metadata.get('source', 'Desconocido')}]\n{d.page_content}" for d in docs]
        context = "\n\n---\n\n".join(context_parts)
        exam_prompt = f"""Eres un profesor que prepara un examen escrito en español a partir del material de referencia.

CONTENIDO (fragmentos del material; pueden estar desordenados):
{context}

PETICIÓN DEL ESTUDIANTE:
{query}

INSTRUCCIONES:
1. Crea entre 8 y 12 preguntas que cubran los temas principales del material.
2. Mezcla preguntas de opción múltiple (4 opciones: A, B, C, D) y 2-3 preguntas de desarrollo breve.
3. Para cada pregunta tipo test, indica cuál es la respuesta correcta al final de esa pregunta entre paréntesis, ej: (Respuesta correcta: B).
4. No inventes datos que contradigan el material; si algo no aparece, omítelo o dilo explícitamente.
5. Al final del examen, incluye una sección "Clave de respuestas" solo para las de opción múltiple.

EXAMEN:"""
        response = llm.invoke(exam_prompt)
        return {"answer": extract_text(response.content).strip(), "source_documents": docs}
    except Exception as e:
        logger.warning("Error generating exam: %s", e)
        return {"answer": f"Error generando examen: {str(e)}", "source_documents": []}


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
