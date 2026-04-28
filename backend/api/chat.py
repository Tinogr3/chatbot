"""
Endpoints de chat - POST /chat
"""
from typing import Any, Iterable, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api.evaluation import record_learning_progress
from chat_manager import ChatHistoryManager
from database import get_db
from document_registry import load_document_registry
from logger import get_logger
from models import Competency, LearningOutcome, Subcompetency
from rag_engine import extract_text, initialize_agent, initialize_vector_store_async
from router import (
    QueryCategory,
    LearningFlowManager,
    get_direct_response,
    get_summary_response,
    route_query,
)
from schemas import ChatRequest, ChatResponse
from user_memory import UserMemoryManager

logger = get_logger("api.chat")

router = APIRouter(prefix="/chat", tags=["chat"])
chat_manager = ChatHistoryManager()
user_memory = UserMemoryManager()

# Cache de agente por session_id (invalidar en upload/video/clear)
_agent_cache: dict = {}


async def _get_agent(session_id: str, temperature: float, max_tokens: int) -> Optional[Any]:
    if session_id in _agent_cache:
        return _agent_cache[session_id]
    vector_store = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)
    if not vector_store:
        return None
    registry = load_document_registry(session_id)
    history = await chat_manager.get_history(session_id)
    agent = initialize_agent(
        vector_store=vector_store,
        temperature=temperature,
        max_tokens=max_tokens,
        session_id=session_id,
        chat_history=history,
        document_registry=registry,
    )
    if agent:
        _agent_cache[session_id] = agent
    return agent


def invalidate_agent_cache(session_id: str) -> None:
    _agent_cache.pop(session_id, None)


def _message_content_to_str(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(item["text"])
                elif "parts" in item:
                    for p in (item["parts"] if isinstance(item["parts"], list) else []):
                        if isinstance(p, str):
                            parts.append(p)
                        elif isinstance(p, dict) and "text" in p:
                            parts.append(p["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def _doc_to_source(doc: Any) -> str:
    return doc.metadata.get("source", "Desconocido") if hasattr(doc, "metadata") else "Desconocido"


def _score_from_evaluation(*, is_correct: bool, is_partial: bool) -> float:
    """Mapea la evaluación cualitativa del LLM a una nota numérica [0..1]."""
    if is_correct:
        return 1.0
    if is_partial:
        return 0.5
    return 0.0


async def _find_learning_outcome_for_sources(
    db: AsyncSession,
    sources: Iterable[str],
) -> Optional[int]:
    """Resuelve el `learning_outcome_id` más probable a partir de las fuentes.

    Cada `Competency` se persiste con `document_id = filename` cuando se
    extrae automáticamente al subir un PDF (ver `worker.process_pdf_task` →
    `save_extracted_competencies`). Las `metadata.source` de los chunks
    recuperados por el RAG también almacenan ese `filename`. Buscamos el
    primer `LearningOutcome` (por `id` ascendente) cuya competencia raíz
    apunte a alguno de los documentos involucrados en la respuesta del LLM.

    Devuelve `None` si no hay competencias asociadas o las fuentes están
    vacías. Los callers usan `None` como señal para omitir la persistencia
    silenciosamente sin romper el flujo del chat.
    """
    valid_sources = [s for s in sources if s]
    if not valid_sources:
        return None

    stmt = (
        select(LearningOutcome.id)
        .join(Subcompetency, LearningOutcome.subcompetency_id == Subcompetency.id)
        .join(Competency, Subcompetency.competency_id == Competency.id)
        .where(Competency.document_id.in_(valid_sources))
        .order_by(LearningOutcome.id.asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    session_id = (body.session_id or x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido (header X-Session-Id o body)")
    prompt = (body.message or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="message vacío")

    temperature = body.temperature
    max_tokens = body.max_tokens
    answer = ""
    sources: List[str] = []
    learning_mode = body.learning_mode
    learning_topic = body.learning_topic
    last_learning_content = body.last_learning_content or ""
    progress_updated = False

    # Salir del modo aprendizaje
    if learning_mode and prompt.lower().strip() in ["salir", "exit", "terminar", "fin"]:
        vs_exit = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)
        learning_manager = LearningFlowManager(
            vs_exit,
            session_id,
            max_tokens=max_tokens,
        )
        answer = learning_manager.end_learning_session()
        learning_mode = False
        learning_topic = None
    # Evaluar respuesta en modo aprendizaje (tema ya establecido)
    elif learning_mode and learning_topic:
        vs = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)
        if not vs:
            answer = "No hay documentos cargados para esta sesión."
        else:
            learning_manager = LearningFlowManager(vs, session_id, max_tokens=max_tokens)
            result = learning_manager.evaluate_answer(prompt, learning_topic, last_learning_content)
            answer = result.get("content", "No se pudo evaluar.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
            last_learning_content = answer

            # Persistencia silenciosa de la evidencia + actualización de
            # `UserCompetencyProgress`. Si algo falla, lo logeamos pero NO
            # lo propagamos: el usuario debe seguir viendo la respuesta
            # del tutor aunque el progreso no se haya podido registrar.
            try:
                score = _score_from_evaluation(
                    is_correct=bool(result.get("is_correct")),
                    is_partial=bool(result.get("is_partial")),
                )
                outcome_id = await _find_learning_outcome_for_sources(db, sources)
                if outcome_id is not None:
                    await record_learning_progress(
                        db,
                        session_id=session_id,
                        learning_outcome_id=outcome_id,
                        score=score,
                        feedback=answer,
                    )
                    progress_updated = True
                else:
                    logger.info(
                        "Sin learning_outcome asociado a las fuentes %s; "
                        "omito persistencia de evidencia para session=%s.",
                        sources,
                        session_id,
                    )
            except (LookupError, SQLAlchemyError) as exc:
                logger.warning(
                    "No se pudo registrar el progreso (session=%s, topic=%r): %s",
                    session_id,
                    learning_topic,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - red de seguridad
                logger.exception(
                    "Error inesperado registrando progreso (session=%s).",
                    session_id,
                )
                _ = exc  # silencia linters sobre variable no usada
    # Modo aprendizaje activado pero sin tema: el mensaje actual es el tema (iniciar sesión)
    elif learning_mode and not (learning_topic or "").strip():
        vector_store = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)
        if not vector_store:
            answer = "No hay documentos cargados para esta sesión."
        else:
            learning_manager = LearningFlowManager(vector_store, session_id, max_tokens=max_tokens)
            result = learning_manager.start_learning_session(prompt)
            answer = result.get("content", "No se pudo iniciar la sesión.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
            if result.get("is_learning_mode"):
                learning_topic = result.get("topic", prompt)
                last_learning_content = answer
    else:
        # Clasificar y ejecutar flujo normal
        category = route_query(prompt, max_tokens=max_tokens)
        vector_store = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)

        if category == QueryCategory.CONVERSACION.value:
            user_facts = user_memory.get_user_facts_formatted(session_id)
            answer = get_direct_response(prompt, session_id, user_facts, max_tokens=max_tokens)
        elif category == QueryCategory.RESUMEN.value and vector_store:
            result = get_summary_response(prompt, vector_store, session_id, max_tokens=max_tokens)
            answer = result.get("answer", "No se pudo generar el resumen.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
        elif category == QueryCategory.APRENDIZAJE.value and vector_store:
            learning_manager = LearningFlowManager(vector_store, session_id, max_tokens=max_tokens)
            result = learning_manager.start_learning_session(prompt)
            answer = result.get("content", "No se pudo iniciar la sesión.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
            if result.get("is_learning_mode"):
                learning_mode = True
                learning_topic = result.get("topic", prompt)
                last_learning_content = answer
        else:
            # PREGUNTA_DOCUMENTO / OTRO: agente
            agent = await _get_agent(session_id, temperature, max_tokens)
            if not agent:
                answer = "No hay documentos cargados. Sube o procesa al menos un PDF o video."
            else:
                from langchain_core.messages import HumanMessage as HMsg
                agent_result = agent.invoke({"messages": [HMsg(content=prompt)]})
                agent_messages = agent_result.get("messages", [])
                for msg in reversed(agent_messages):
                    if getattr(msg, "type", None) == "ai" and getattr(msg, "content", None):
                        answer = _message_content_to_str(msg.content)
                        break
                if not answer:
                    answer = "No se pudo generar una respuesta."
                for msg in agent_messages:
                    if getattr(msg, "type", None) == "tool" and getattr(msg, "content", None):
                        name = getattr(msg, "name", "")
                        src = name.replace("search_document_", "").replace("_", " ") if "search_document_" in name else "Todos los documentos"
                        if src not in sources:
                            sources.append(src)

    # Persistir mensajes
    await chat_manager.save_message(session_id, "user", prompt)
    await chat_manager.save_message(session_id, "assistant", answer, sources if sources else None)
    user_memory.extract_and_save_async(session_id, prompt, answer, max_tokens=max_tokens)

    return ChatResponse(
        answer=answer,
        sources=sources,
        learning_mode=learning_mode,
        learning_topic=learning_topic,
        progress_updated=progress_updated,
    )
