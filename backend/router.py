"""
Smart Router - Sistema de enrutamiento inteligente de queries (backend).

Clasifica cada consulta y extrae contexto acumulado del chat (preferencias,
restricciones de formato, instrucciones de comportamiento) para inyectarlo en
cada flujo de respuesta downstream.
"""
import os
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

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


class RouteResult(BaseModel):
    """Salida del smart router: categoría + contexto acumulado para la respuesta."""

    category: str = Field(
        ...,
        description="Una de: CONVERSACION, PREGUNTA_DOCUMENTO, RESUMEN, EXAMEN, APRENDIZAJE, OTRO",
    )
    context: str = Field(
        default="",
        description=(
            "Preferencias, restricciones e instrucciones del usuario extraídas del "
            "historial y de la consulta actual (formato, tono, nivel, alcance, etc.). "
            "Vacío si no hay nada relevante."
        ),
    )


def build_context_block(route_context: str) -> str:
    """Bloque de prompt listo para inyectar en los generadores downstream."""
    ctx = (route_context or "").strip()
    if not ctx:
        return ""
    return (
        "\n\nCONTEXTO Y RESTRICCIONES DEL USUARIO "
        "(respeta siempre al redactar la respuesta):\n"
        f"{ctx}\n"
    )


def _format_history_for_routing(
    chat_history: Optional[List[Dict[str, Any]]],
    *,
    max_messages: int = 10,
    max_chars_per_message: int = 400,
) -> str:
    """Resume el historial reciente para la clasificación."""
    if not chat_history:
        return "(sin historial previo)"
    recent = chat_history[-max_messages:]
    lines: List[str] = []
    for msg in recent:
        role = "Usuario" if msg.get("role") == "user" else "Asistente"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if len(content) > max_chars_per_message:
            content = content[:max_chars_per_message] + "…"
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(sin historial previo)"


def _normalize_category(raw: str) -> str:
    """Normaliza la categoría devuelta por el LLM."""
    category = (raw or "").strip().upper()
    valid = [c.value for c in QueryCategory]
    if category in valid:
        return category
    for valid_cat in valid:
        if valid_cat in category:
            return valid_cat
    return QueryCategory.PREGUNTA_DOCUMENTO.value


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


def route_query(
    query: str,
    max_tokens: int = 65535,
    *,
    chat_history: Optional[List[Dict[str, Any]]] = None,
    user_facts: str = "",
) -> RouteResult:
    """Clasifica la consulta y extrae contexto/restricciones del chat.

    El ``context`` devuelto resume preferencias e instrucciones acumuladas
    (formato, tono, nivel, alcance, restricciones explícitas) para que cada
    flujo downstream genere respuestas más alineadas con lo pedido.
    """
    fallback = RouteResult(category=QueryCategory.PREGUNTA_DOCUMENTO.value, context="")
    llm = get_model(temperature=0.1, max_output_tokens=max_tokens)
    if not llm:
        return fallback

    history_block = _format_history_for_routing(chat_history)
    facts_block = (
        f"\nHECHOS CONOCIDOS SOBRE EL USUARIO:\n{user_facts.strip()}\n"
        if (user_facts or "").strip()
        else ""
    )

    classification_prompt = f"""Eres el router de un asistente educativo. Tu tarea tiene DOS partes:

1) CLASIFICAR la consulta actual en UNA categoría.
2) EXTRAER un resumen breve de contexto/restricciones que el asistente debe respetar al responder.

CATEGORÍAS (elige exactamente una):
- CONVERSACION: Saludos, despedidas, charla casual, preguntas personales al asistente, agradecimientos. Incluye cuando el usuario da información sobre sí mismo o instrucciones sobre cómo comportarse.
- PREGUNTA_DOCUMENTO: Preguntas específicas que requieren buscar información en documentos.
- RESUMEN: Solicitudes de resumir, sintetizar o dar una visión general del contenido. ÚNICAMENTE si el usuario pide explícitamente un resumen.
- EXAMEN: Solicitudes de crear un examen, test, cuestionario o evaluación escrita. ÚNICAMENTE si el usuario usa explícitamente esas palabras.
- APRENDIZAJE: Quiere aprender con tutoría guiada, estudiar paso a paso o practicar de forma conversacional (no un examen escrito de una vez).
- OTRO: Instrucciones complejas, tareas multi-paso o cualquier cosa que no encaje; el agente libre la procesará.

Para ``context``, sintetiza en 1-4 frases (o deja vacío) lo relevante de:
- Preferencias de formato, tono, idioma o nivel pedido en el chat.
- Restricciones explícitas (ej: "sin tecnicismos", "máximo 3 párrafos", "solo del capítulo 2", "en viñetas").
- Instrucciones de comportamiento dadas en mensajes anteriores que sigan vigentes.
- Tema o foco acumulado de la conversación si afecta a la consulta actual.
No repitas la consulta literal; extrae solo lo que mejore la calidad de la respuesta.
Si no hay nada útil, devuelve context como cadena vacía.

HISTORIAL RECIENTE DEL CHAT:
{history_block}
{facts_block}
CONSULTA ACTUAL DEL USUARIO:
"{query}"

Reglas:
- Si no estás seguro de la categoría, usa OTRO.
- RESUMEN y EXAMEN solo si el usuario lo pide explícitamente en la consulta actual."""

    try:
        structured_llm = llm.with_structured_output(RouteResult)
        result: Optional[RouteResult] = structured_llm.invoke(classification_prompt)
        if result is None:
            return fallback
        return RouteResult(
            category=_normalize_category(result.category),
            context=(result.context or "").strip(),
        )
    except Exception as e:
        logger.warning("Error routing query (structured): %s", e)
        # Fallback sin structured output por compatibilidad con modelos antiguos
        try:
            response = llm.invoke(
                classification_prompt
                + "\n\nResponde SOLO con la categoría en una línea."
            )
            category = _normalize_category(extract_text(response.content))
            return RouteResult(category=category, context="")
        except Exception as e2:
            logger.warning("Error routing query (fallback): %s", e2)
            return fallback


def get_direct_response(
    query: str,
    session_id: Optional[str] = None,
    user_facts: str = "",
    max_tokens: int = 65535,
    route_context: str = "",
) -> str:
    llm = get_model(temperature=0.7, max_output_tokens=max_tokens)
    if not llm:
        return "Lo siento, no puedo responder en este momento."
    user_context = f"\n\nInformación conocida sobre el usuario:\n{user_facts}\n" if user_facts else ""
    prompt = f"""Eres un asistente educativo amigable y servicial.{user_context}{build_context_block(route_context)}

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
    route_context: str = "",
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
{build_context_block(route_context)}
PETICIÓN DEL USUARIO:
{query}

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
    route_context: str = "",
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
        exam_prompt = f"""Eres un profesor que prepara un examen escrito a partir del material de referencia.

CONTENIDO (fragmentos del material; pueden estar desordenados):
{context}

PETICIÓN DEL ESTUDIANTE:
{query}
{build_context_block(route_context)}
INSTRUCCIONES:
1. Crea entre 8 y 12 preguntas que cubran los temas principales del material.
2. Mezcla preguntas de opción múltiple (4 opciones: A, B, C, D) y 2-3 preguntas de desarrollo breve.
3. No inventes datos que contradigan el material; si algo no aparece, omítelo o dilo explícitamente.
4. Al final del examen, incluye una sección "Clave de respuestas" solo para las de opción múltiple.

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

    def start_learning_session(
        self,
        topic_query: str,
        route_context: str = "",
    ) -> Dict[str, Any]:
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
{build_context_block(route_context)}
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

    def evaluate_answer(
        self,
        user_answer: str,
        topic: str,
        previous_content: str,
        route_context: str = "",
    ) -> Dict[str, Any]:
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
{build_context_block(route_context)}
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
