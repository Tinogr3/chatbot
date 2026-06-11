"""
Endpoints del Módulo Formador.

POST /trainer/generate-itinerary
    Chat IA de configuración: a partir del prompt del formador, busca
    contexto en la base de conocimientos (RAG) y genera un itinerario
    estructurado (semanas, horas, temas y unidades con peso %) usando
    salida estructurada del LLM.

POST /trainer/save-itinerary
    Persiste el cuadrante validado por el formador. Reemplaza el
    itinerario anterior de la sesión (una sesión mantiene un itinerario
    activo).

GET /trainer/progress/quadrant/{student_session_id}
    Matriz de progreso del alumno: temas → unidades con puntuación 0-10,
    % completado y color de estado.

GET /trainer/progress/unit-details/{student_session_id}/{unit_id}
    Drill-down de una celda: histórico de actividades y desglose del
    cálculo de la nota (media de quizzes, nº de vídeos/preguntas).
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import get_validated_session
from database import get_db
from logger import get_logger
from models import (
    ActivityType,
    Competency,
    CourseItinerary,
    LearningOutcome,
    LearningUnit,
    StudentActivityLog,
    Subcompetency,
    Theme,
    UnitProgress,
)
from schemas import (
    CourseItineraryCreate,
    GeneratedItinerary,
    GenerateItineraryRequest,
    QuadrantResponse,
    QuadrantTheme,
    QuadrantUnit,
    SaveItineraryResponse,
    StudentActivityLogRead,
    TrainerLearningOutcomeOption,
    UnitDetailsQuizStats,
    UnitDetailsResponse,
)
from services.progress_service import compute_color_code
from session_ids import normalize_session_id

logger = get_logger("api.trainer")

router = APIRouter(prefix="/trainer", tags=["Trainer"])

_RAG_CONTEXT_MAX_CHARS = 30000
_RAG_TOP_K = 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _build_rag_context(session_id: str, prompt: str) -> str:
    """Recupera fragmentos relevantes de la base de conocimientos de la sesión.

    Devuelve cadena vacía si no hay documentos indexados — el generador
    funcionará solo con el prompt del formador.
    """
    from rag_engine import initialize_vector_store_async

    try:
        vector_store = await initialize_vector_store_async(
            documents=None, existing_vector_store=None, session_id=session_id
        )
        if not vector_store:
            return ""
        retriever = vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={"k": _RAG_TOP_K, "fetch_k": _RAG_TOP_K * 3, "lambda_mult": 0.6},
        )
        docs = await asyncio.to_thread(retriever.invoke, prompt)
        parts = [
            f"[{d.metadata.get('source', 'Desconocido')}]\n{d.page_content}"
            for d in docs
        ]
        return "\n\n---\n\n".join(parts)[:_RAG_CONTEXT_MAX_CHARS]
    except Exception as e:
        logger.warning("RAG context para itinerario no disponible: %s", e)
        return ""


def _normalize_unit_weights(itinerary: GeneratedItinerary) -> GeneratedItinerary:
    """Reescala los pesos de las unidades para que sumen exactamente 100."""
    total = sum(
        unit.weight for theme in itinerary.themes for unit in theme.learning_units
    )
    if total <= 0:
        # Repartir uniformemente si el LLM no asignó pesos válidos
        unit_count = sum(len(t.learning_units) for t in itinerary.themes)
        if unit_count == 0:
            return itinerary
        uniform = round(100.0 / unit_count, 2)
        for theme in itinerary.themes:
            for unit in theme.learning_units:
                unit.weight = uniform
        return itinerary

    factor = 100.0 / total
    for theme in itinerary.themes:
        for unit in theme.learning_units:
            unit.weight = round(unit.weight * factor, 2)
    return itinerary


def _generate_itinerary_sync(prompt: str, rag_context: str) -> Optional[GeneratedItinerary]:
    """Invoca el LLM con salida estructurada (bloqueante; ejecutar en hilo)."""
    from router import get_model

    llm = get_model(temperature=0.2, max_output_tokens=65535)
    if not llm:
        return None

    context_block = (
        f"BASE DE CONOCIMIENTOS (fragmentos de los documentos del curso):\n---\n{rag_context}\n---\n\n"
        if rag_context
        else "(No hay documentos indexados; usa tu conocimiento general del dominio.)\n\n"
    )
    full_prompt = (
        "Eres un diseñador instruccional senior. Un formador te pide planificar un curso.\n\n"
        f"{context_block}"
        f"PETICIÓN DEL FORMADOR:\n{prompt}\n\n"
        "INSTRUCCIONES:\n"
        "• Respeta las semanas y horas que indique el formador; si no las indica, estímalas.\n"
        "• Divide el curso en temas (bloques) coherentes con la base de conocimientos.\n"
        "• Dentro de cada tema, define unidades de aprendizaje (conceptos concretos) con:\n"
        "  - name: nombre corto del concepto.\n"
        "  - definition: qué debe aprender el alumno (1-3 frases, concreto y evaluable).\n"
        "  - weight: peso porcentual sobre el TOTAL del curso. La suma de TODAS las "
        "unidades de TODOS los temas debe ser 100.\n"
        "• Usa terminología de la base de conocimientos cuando exista.\n"
        "• Redacta en español."
    )

    structured_llm = llm.with_structured_output(GeneratedItinerary)
    return structured_llm.invoke(full_prompt)


# ---------------------------------------------------------------------------
# Competencias disponibles para enlazar celdas del cuadrante
# ---------------------------------------------------------------------------


@router.get(
    "/learning-outcomes",
    response_model=List[TrainerLearningOutcomeOption],
    summary="Lista de resultados de aprendizaje enlazables a celdas del cuadrante",
)
async def list_learning_outcomes(
    session_id: str = Depends(get_validated_session),
    db: AsyncSession = Depends(get_db),
) -> List[TrainerLearningOutcomeOption]:
    """Devuelve los learning outcomes de los documentos de la sesión del formador."""
    from document_registry import load_document_registry

    registry = load_document_registry(session_id)
    doc_keys = list(registry.keys()) if registry else []
    if not doc_keys:
        return []

    try:
        rows = (
            await db.execute(
                select(
                    LearningOutcome.id,
                    LearningOutcome.description,
                    Subcompetency.name,
                    Competency.name,
                    Competency.document_id,
                )
                .join(Subcompetency, LearningOutcome.subcompetency_id == Subcompetency.id)
                .join(Competency, Subcompetency.competency_id == Competency.id)
                .where(Competency.document_id.in_(doc_keys))
                .order_by(Competency.document_id, Competency.name, Subcompetency.name, LearningOutcome.id)
            )
        ).all()
    except SQLAlchemyError as exc:
        logger.exception("Error listando learning outcomes (session=%s)", session_id)
        raise HTTPException(
            status_code=500,
            detail="Error consultando las competencias disponibles.",
        ) from exc

    return [
        TrainerLearningOutcomeOption(
            id=row[0],
            description=row[1],
            subcompetency_name=row[2],
            competency_name=row[3],
            document_id=row[4] or "",
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Fase 2: generación y guardado del itinerario
# ---------------------------------------------------------------------------


@router.post(
    "/generate-itinerary",
    response_model=GeneratedItinerary,
    summary="Genera un itinerario estructurado con IA a partir del prompt del formador",
)
async def generate_itinerary(
    body: GenerateItineraryRequest,
    session_id: str = Depends(get_validated_session),
) -> GeneratedItinerary:
    """Genera la propuesta de cuadrante (NO la persiste; ver /save-itinerary)."""
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt vacío")

    rag_context = await _build_rag_context(session_id, prompt)

    try:
        itinerary = await asyncio.to_thread(_generate_itinerary_sync, prompt, rag_context)
    except Exception as exc:
        logger.exception("Error generando itinerario con LLM")
        raise HTTPException(
            status_code=502,
            detail=f"El generador de itinerarios no está disponible: {exc}",
        ) from exc

    if itinerary is None:
        raise HTTPException(
            status_code=502,
            detail="No hay credenciales de LLM configuradas o el modelo no devolvió un itinerario.",
        )

    return _normalize_unit_weights(itinerary)


@router.post(
    "/save-itinerary",
    response_model=SaveItineraryResponse,
    summary="Guarda el cuadrante validado por el formador (reemplaza el anterior)",
)
async def save_itinerary(
    body: CourseItineraryCreate,
    session_id: str = Depends(get_validated_session),
    db: AsyncSession = Depends(get_db),
) -> SaveItineraryResponse:
    """Persiste itinerario + temas + unidades en BD.

    Los pesos de las unidades llegan como fracciones 0.0–1.0 (el frontend
    convierte el % mostrado). Si la suma no es ≈1.0 se renormaliza aquí para
    mantener el invariante del cuadrante.
    """
    # Renormalizar pesos a suma 1.0 (defensa ante ediciones manuales del formador)
    total_weight = sum(u.weight for t in body.themes for u in t.learning_units)
    factor = (1.0 / total_weight) if total_weight > 0 else 0.0

    try:
        # Reemplazo: una sesión mantiene un único itinerario activo
        existing = (
            await db.execute(
                select(CourseItinerary).where(CourseItinerary.session_id == session_id)
            )
        ).scalars().all()
        for it in existing:
            await db.delete(it)
        await db.flush()

        itinerary = CourseItinerary(
            session_id=session_id,
            title=body.title.strip(),
            total_weeks=body.total_weeks,
            hours_per_week=body.hours_per_week,
        )
        db.add(itinerary)
        await db.flush()

        unit_count = 0
        for t_idx, theme_data in enumerate(body.themes):
            theme = Theme(
                itinerary_id=itinerary.id,
                name=theme_data.name.strip(),
                order_index=theme_data.order_index or t_idx,
            )
            db.add(theme)
            await db.flush()

            for u_idx, unit_data in enumerate(theme_data.learning_units):
                normalized_weight = (
                    round(unit_data.weight * factor, 6) if factor > 0 else 0.0
                )
                db.add(
                    LearningUnit(
                        theme_id=theme.id,
                        name=unit_data.name.strip(),
                        definition=unit_data.definition.strip(),
                        weight=normalized_weight,
                        order_index=unit_data.order_index or u_idx,
                        learning_outcome_id=unit_data.learning_outcome_id,
                    )
                )
                unit_count += 1

        await db.flush()
        itinerary_id = itinerary.id
    except SQLAlchemyError as exc:
        logger.exception("Error guardando itinerario (session=%s)", session_id)
        raise HTTPException(
            status_code=500, detail="Error guardando el itinerario en la base de datos."
        ) from exc

    return SaveItineraryResponse(
        itinerary_id=itinerary_id,
        theme_count=len(body.themes),
        unit_count=unit_count,
        message=f"Itinerario '{body.title}' guardado con {len(body.themes)} temas y {unit_count} unidades.",
    )


# ---------------------------------------------------------------------------
# Fase 4: cuadrante de progreso y drill-down
# ---------------------------------------------------------------------------


@router.get(
    "/progress/quadrant/{student_session_id}",
    response_model=QuadrantResponse,
    summary="Matriz de progreso (temas → unidades con puntuación y color)",
)
async def get_progress_quadrant(
    student_session_id: str,
    _auth_session: str = Depends(get_validated_session),
    db: AsyncSession = Depends(get_db),
) -> QuadrantResponse:
    """Devuelve el itinerario de la sesión con el progreso del alumno por celda."""
    student_session_id = normalize_session_id(student_session_id)

    itinerary = (
        await db.execute(
            select(CourseItinerary)
            .options(
                selectinload(CourseItinerary.themes).selectinload(Theme.learning_units)
            )
            .where(CourseItinerary.session_id == student_session_id)
            .order_by(CourseItinerary.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if itinerary is None:
        raise HTTPException(
            status_code=404,
            detail="No hay itinerario guardado para esta sesión. El formador debe crearlo primero.",
        )

    # Progreso por unidad para la sesión del alumno
    progress_rows = (
        await db.execute(
            select(UnitProgress).where(UnitProgress.session_id == student_session_id)
        )
    ).scalars().all()
    progress_by_unit = {p.learning_unit_id: p for p in progress_rows}

    themes_out: List[QuadrantTheme] = []
    weighted_sum = 0.0
    total_weight = 0.0

    for theme in itinerary.themes:
        units_out: List[QuadrantUnit] = []
        for unit in theme.learning_units:
            progress = progress_by_unit.get(unit.id)
            score = round(float(progress.total_score), 2) if progress else 0.0
            color = progress.color_code if progress else compute_color_code(0.0)
            units_out.append(
                QuadrantUnit(
                    unit_id=unit.id,
                    name=unit.name,
                    definition=unit.definition,
                    weight=unit.weight,
                    score=score,
                    percent_complete=round(score / 10.0 * 100.0, 1),
                    color_code=color,
                )
            )
            weighted_sum += score * unit.weight
            total_weight += unit.weight
        themes_out.append(
            QuadrantTheme(theme_id=theme.id, name=theme.name, units=units_out)
        )

    overall = round(weighted_sum / total_weight, 2) if total_weight > 0 else 0.0

    return QuadrantResponse(
        itinerary_id=itinerary.id,
        title=itinerary.title,
        total_weeks=itinerary.total_weeks,
        hours_per_week=itinerary.hours_per_week,
        themes=themes_out,
        overall_score=max(0.0, min(10.0, overall)),
    )


@router.get(
    "/progress/unit-details/{student_session_id}/{unit_id}",
    response_model=UnitDetailsResponse,
    summary="Drill-down de una celda: histórico de actividades y desglose de la nota",
)
async def get_unit_details(
    student_session_id: str,
    unit_id: int,
    _auth_session: str = Depends(get_validated_session),
    db: AsyncSession = Depends(get_db),
) -> UnitDetailsResponse:
    """Audita de dónde salen los puntos de una celda (vídeos, preguntas, quizzes)."""
    student_session_id = normalize_session_id(student_session_id)

    unit = (
        await db.execute(select(LearningUnit).where(LearningUnit.id == unit_id))
    ).scalar_one_or_none()
    if unit is None:
        raise HTTPException(status_code=404, detail=f"LearningUnit id={unit_id} no existe.")

    activities = (
        await db.execute(
            select(StudentActivityLog)
            .where(
                StudentActivityLog.session_id == student_session_id,
                StudentActivityLog.learning_unit_id == unit_id,
            )
            .order_by(StudentActivityLog.timestamp.desc(), StudentActivityLog.id.desc())
        )
    ).scalars().all()

    quiz_scores = [
        float(a.score_earned or 0.0)
        for a in activities
        if a.activity_type == ActivityType.QUIZ
    ]
    video_count = sum(1 for a in activities if a.activity_type == ActivityType.VIDEO)
    chat_count = sum(
        1 for a in activities if a.activity_type == ActivityType.CHAT_QUESTION
    )
    action_count = video_count + chat_count

    quiz_avg = (sum(quiz_scores) / len(quiz_scores)) if quiz_scores else None
    quiz_points = round((quiz_avg or 0.0) * 0.75, 2)
    action_points = round(min(action_count * 0.5, 2.5), 2)

    progress = (
        await db.execute(
            select(UnitProgress).where(
                UnitProgress.session_id == student_session_id,
                UnitProgress.learning_unit_id == unit_id,
            )
        )
    ).scalar_one_or_none()
    total_score = round(float(progress.total_score), 2) if progress else 0.0
    color = progress.color_code if progress else compute_color_code(0.0)

    return UnitDetailsResponse(
        unit_id=unit.id,
        unit_name=unit.name,
        total_score=total_score,
        color_code=color,
        quiz_stats=UnitDetailsQuizStats(
            count=len(quiz_scores),
            average_score=round(quiz_avg, 2) if quiz_avg is not None else None,
        ),
        video_count=video_count,
        chat_question_count=chat_count,
        quiz_points=min(quiz_points, 7.5),
        action_points=min(action_points, 2.5),
        activities=[StudentActivityLogRead.model_validate(a) for a in activities],
    )
