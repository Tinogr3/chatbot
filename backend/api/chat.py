"""
Endpoints de chat - POST /chat
"""
import asyncio
from typing import Any, Iterable, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api.evaluation import record_learning_progress
from auth import get_current_user, get_validated_session
from chat_manager import ChatHistoryManager
from discovery_repo import add_stored_exam, add_stored_summary
from database import get_db
from document_registry import load_document_registry
from logger import get_logger
from evaluation_engine import EvaluationService
from models import Competency, LearningOutcome, LearningUnit, Subcompetency, User
from rag_engine import initialize_agent, initialize_vector_store_async
from router import (
    QueryCategory,
    LearningFlowManager,
    build_context_block,
    get_direct_response,
    get_exam_response,
    get_summary_response,
    route_query,
    RouteResult,
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


def _should_store_discovery_content(answer: str) -> bool:
    """Evita guardar mensajes de error o respuestas triviales en el Discovery Hub."""
    a = (answer or "").strip()
    if len(a) < 30:
        return False
    bad_prefixes = (
        "No hay documentos disponibles",
        "No hay documentos cargados",
        "No puedo generar",
        "Error generando",
        "Error al generar",
    )
    return not any(a.startswith(p) for p in bad_prefixes)


_EXAM_REQUEST_MARKERS = (
    "cuestionario",
    "examen",
    "test",
    "evaluar unidad",
    "genera un examen",
    "hazme un",
    "evaluación escrita",
)


def _is_exam_generation_request(text: str) -> bool:
    """True si el mensaje pide crear un examen/cuestionario (no enviar respuestas)."""
    lowered = (text or "").lower()
    return any(marker in lowered for marker in _EXAM_REQUEST_MARKERS)


def _looks_like_exam_content(text: str) -> bool:
    """Heurística: el último mensaje del asistente parece un examen entregado."""
    content = (text or "").strip()
    if len(content) < 120:
        return False
    lowered = content.lower()
    markers = (
        "pregunta",
        "a)",
        "b)",
        "c)",
        "d)",
        "opción",
        "desarrollo",
        "envía tus respuestas",
        "copiar sus respuestas",
    )
    return sum(1 for marker in markers if marker in lowered) >= 2


def _last_assistant_message(chat_history: List[dict]) -> str:
    for msg in reversed(chat_history):
        if msg.get("role") == "assistant":
            return (msg.get("content") or "").strip()
    return ""


async def _load_learning_unit(
    db: AsyncSession, unit_id: int
) -> Optional[LearningUnit]:
    return (
        await db.execute(select(LearningUnit).where(LearningUnit.id == unit_id))
    ).scalar_one_or_none()


async def _register_unit_quiz_progress(
    db: AsyncSession,
    *,
    session_id: str,
    unit_id: int,
    score: float,
    detail: str,
) -> bool:
    """Registra una actividad quiz en la celda del cuadrante. Devuelve True si tuvo éxito."""
    try:
        from models import ActivityType
        from services.progress_service import ProgressService

        await ProgressService.log_activity_and_update_progress(
            db,
            session_id=session_id,
            unit_id=unit_id,
            activity_type=ActivityType.QUIZ,
            score=score,
            detail=detail,
        )
        return True
    except Exception:
        logger.exception(
            "No se pudo registrar progreso de cuestionario (session=%s, unit=%s).",
            session_id,
            unit_id,
        )
        return False


async def _try_evaluate_quiz_submission(
    db: AsyncSession,
    *,
    session_id: str,
    learning_unit_id: int,
    prompt: str,
    chat_history: List[dict],
    max_tokens: int,
) -> Optional[Tuple[str, bool]]:
    """Evalúa respuestas del alumno a un cuestionario previo de la misma unidad."""
    if _is_exam_generation_request(prompt):
        return None

    last_assistant = _last_assistant_message(chat_history)
    if not _looks_like_exam_content(last_assistant):
        return None

    unit = await _load_learning_unit(db, learning_unit_id)
    if unit is None:
        return None

    try:
        evaluation = await asyncio.to_thread(
            EvaluationService.evaluate_quiz_submission,
            f"{unit.name}: {unit.definition}",
            last_assistant[:12000],
            prompt,
        )
    except Exception:
        logger.exception("Fallo evaluando respuestas del cuestionario (session=%s).", session_id)
        return None

    score_10 = max(0.0, min(10.0, float(evaluation["score"]) * 10.0))
    feedback = str(evaluation["feedback"])
    progress_ok = await _register_unit_quiz_progress(
        db,
        session_id=session_id,
        unit_id=learning_unit_id,
        score=score_10,
        detail="Respuestas evaluadas del cuestionario",
    )

    answer = (
        f"## Corrección del cuestionario — {unit.name}\n\n"
        f"**Nota:** {score_10:.1f} / 10\n\n"
        f"{feedback}\n\n"
        "_Tu progreso en el cuadrante se ha actualizado con esta nota._"
    )
    return answer, progress_ok


async def _log_unit_activity_best_effort(
    db: AsyncSession,
    *,
    session_id: str,
    text: str,
    activity_type: Any,
    score: Optional[float] = None,
    detail: Optional[str] = None,
) -> None:
    """Registra actividad en el cuadrante del Módulo Formador (best-effort).

    Mapea el texto (pregunta, tema…) a la `LearningUnit` más relevante del
    itinerario de la sesión. Si no hay itinerario o no hay match, se omite
    silenciosamente: el chat nunca debe fallar por el seguimiento.
    """
    try:
        from services.progress_service import ProgressService

        unit_id = await ProgressService.find_unit_for_text(
            db, session_id=session_id, text=text
        )
        if unit_id is None:
            return
        await ProgressService.log_activity_and_update_progress(
            db,
            session_id=session_id,
            unit_id=unit_id,
            activity_type=activity_type,
            score=score,
            detail=detail,
        )
    except Exception:
        logger.exception(
            "No se pudo registrar actividad de unidad (session=%s).", session_id
        )


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
    session_id: str = Depends(get_validated_session),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    from services.trainer_project_service import progress_session_for_user

    prompt = (body.message or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="message vacío")

    progress_sid = await progress_session_for_user(
        db, user=current_user, validated_session_id=session_id
    )

    temperature = body.temperature
    max_tokens = body.max_tokens
    answer = ""
    sources: List[str] = []
    learning_mode = body.learning_mode
    learning_topic = body.learning_topic
    last_learning_content = body.last_learning_content or ""
    learning_unit_id = body.learning_unit_id
    progress_updated = False

    # Evaluar respuestas a un cuestionario de una celda del cuadrante
    if learning_unit_id and not learning_mode:
        chat_history_early = await chat_manager.get_history(session_id)
        quiz_result = await _try_evaluate_quiz_submission(
            db,
            session_id=progress_sid,
            learning_unit_id=learning_unit_id,
            prompt=prompt,
            chat_history=chat_history_early,
            max_tokens=max_tokens,
        )
        if quiz_result is not None:
            answer, progress_updated = quiz_result
            await chat_manager.save_message(session_id, "user", prompt)
            await chat_manager.save_message(session_id, "assistant", answer, None)
            user_memory.extract_and_save_async(session_id, prompt, answer, max_tokens=max_tokens)
            return ChatResponse(
                answer=answer,
                sources=[],
                learning_mode=False,
                learning_topic=None,
                progress_updated=progress_updated,
            )

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
            outcome_id: Optional[int] = None
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
            except Exception:  # pragma: no cover
                logger.exception(
                    "Error inesperado registrando progreso (session=%s).",
                    session_id,
                )

            # Módulo Formador: quiz en la celda enlazada por learning_outcome_id
            try:
                from models import ActivityType as _ActivityType
                from services.progress_service import ProgressService

                quiz_score = _score_from_evaluation(
                    is_correct=bool(result.get("is_correct")),
                    is_partial=bool(result.get("is_partial")),
                ) * 10.0
                unit_id = None
                if outcome_id is not None:
                    unit_id = await ProgressService.find_unit_by_outcome_id(
                        db,
                        session_id=session_id,
                        learning_outcome_id=outcome_id,
                    )
                if unit_id is not None:
                    await ProgressService.log_activity_and_update_progress(
                        db,
                        session_id=progress_sid,
                        unit_id=unit_id,
                        activity_type=_ActivityType.QUIZ,
                        score=quiz_score,
                        detail=f"Evaluación en modo aprendizaje (tema: {learning_topic})",
                    )
            except Exception:
                logger.exception(
                    "No se pudo registrar el quiz en el cuadrante (session=%s).",
                    session_id,
                )
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
        # Clasificar con historial + hechos del usuario para extraer también
        # contexto/restricciones acumuladas del chat.
        user_facts = user_memory.get_user_facts_formatted(session_id)
        chat_history = await chat_manager.get_history(session_id)
        route_result = route_query(
            prompt,
            max_tokens=max_tokens,
            chat_history=chat_history,
            user_facts=user_facts,
        )
        category = route_result.category
        route_context = route_result.context
        # Petición desde el cuadrante: forzar EXAMEN si pide cuestionario
        if learning_unit_id and _is_exam_generation_request(prompt):
            category = QueryCategory.EXAMEN.value
            route_result = RouteResult(category=category, context=route_context)
        if route_context:
            logger.info(
                "Router contexto (session=%s, category=%s): %s",
                session_id,
                category,
                route_context[:200],
            )

        vector_store = await initialize_vector_store_async(documents=None, existing_vector_store=None, session_id=session_id)

        if category == QueryCategory.CONVERSACION.value:
            answer = get_direct_response(
                prompt,
                session_id,
                user_facts,
                max_tokens=max_tokens,
                route_context=route_context,
            )
        elif category == QueryCategory.RESUMEN.value and vector_store:
            result = get_summary_response(
                prompt,
                vector_store,
                session_id,
                max_tokens=max_tokens,
                route_context=route_context,
            )
            answer = result.get("answer", "No se pudo generar el resumen.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
            if _should_store_discovery_content(answer):
                try:
                    await add_stored_summary(db, session_id, prompt, answer)
                except Exception as exc:
                    logger.warning("No se pudo guardar resumen en Discovery Hub: %s", exc)
        elif category == QueryCategory.EXAMEN.value and vector_store:
            unit = (
                await _load_learning_unit(db, learning_unit_id)
                if learning_unit_id
                else None
            )
            result = get_exam_response(
                prompt,
                vector_store,
                session_id,
                max_tokens=max_tokens,
                route_context=route_context,
                unit_name=unit.name if unit else None,
                unit_definition=unit.definition if unit else None,
            )
            answer = result.get("answer", "No se pudo generar el examen.")
            sources = list(set(_doc_to_source(d) for d in result.get("source_documents", [])))
            if _should_store_discovery_content(answer):
                try:
                    await add_stored_exam(db, session_id, prompt, answer)
                except Exception as exc:
                    logger.warning("No se pudo guardar examen en Discovery Hub: %s", exc)
        elif category == QueryCategory.APRENDIZAJE.value and vector_store:
            learning_manager = LearningFlowManager(vector_store, session_id, max_tokens=max_tokens)
            result = learning_manager.start_learning_session(
                prompt, route_context=route_context
            )
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
                agent_prompt = prompt
                ctx_block = build_context_block(route_context)
                if ctx_block:
                    agent_prompt = (
                        f"{ctx_block.strip()}\n\nCONSULTA ACTUAL DEL USUARIO:\n{prompt}"
                    )
                agent_result = agent.invoke({"messages": [HMsg(content=agent_prompt)]})
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

                # Módulo Formador: pregunta relevante al chat → +0.5 en la celda
                if category == QueryCategory.PREGUNTA_DOCUMENTO.value:
                    from models import ActivityType as _ActivityType

                    await _log_unit_activity_best_effort(
                        db,
                        session_id=progress_sid,
                        text=prompt,
                        activity_type=_ActivityType.CHAT_QUESTION,
                        detail=prompt[:500],
                    )

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
