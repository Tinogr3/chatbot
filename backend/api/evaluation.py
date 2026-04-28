"""
Endpoint de evaluación de respuestas + helpers reutilizables de persistencia.

POST /evaluate
    Recibe `EvaluateLearningRequest` y orquesta:
      1. Carga del `LearningOutcome` por id (con su subcompetencia precargada).
      2. Evaluación con LLM (`EvaluationService.evaluate_student_answer`).
      3. Persistencia (vía `record_learning_progress`) de la evidencia y del
         progreso agregado por subcompetencia.
      4. Devuelve `EvaluateLearningResponse`.

`record_learning_progress` también se reutiliza desde `api/chat.py` cuando el
usuario está en modo aprendizaje y el LLM evalúa su respuesta dentro del
flujo conversacional, manteniendo una única fuente de verdad para la lógica
de "registrar evidencia + recalcular progreso".

Toda la persistencia usa la sesión inyectada por `get_db`. El generador
gestiona automáticamente commit/rollback al cerrarse, así que no se llama
explícitamente a `db.commit()` desde aquí.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from evaluation_engine import EvaluationService
from logger import get_logger
from models import LearningEvidence, LearningOutcome, UserCompetencyProgress
from schemas import EvaluateLearningRequest, EvaluateLearningResponse

logger = get_logger("api.evaluation")

router = APIRouter(tags=["Evaluation"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _compute_weighted_subcompetency_score(
    db: AsyncSession,
    *,
    session_id: str,
    subcompetency_id: int,
    fallback_score: float,
) -> float:
    """Media móvil ponderada de la subcompetencia para una sesión.

    Estrategia: por cada `learning_outcome` de la subcompetencia se toma la
    evidencia con `id` más alto del usuario (la más reciente cronológicamente),
    y se devuelve la media ponderada por `weight` de cada outcome.

    Si no hay pesos válidos (subcompetencia sin outcomes con peso > 0) se
    devuelve `fallback_score` para no producir 0/0.

    El resultado se redondea a 4 decimales y se acota al rango [0.0, 1.0]
    para defenderse de pesos inconsistentes en la BD.
    """
    latest_evidence_subq = (
        select(
            LearningEvidence.learning_outcome_id,
            func.max(LearningEvidence.id).label("max_id"),
        )
        .where(LearningEvidence.session_id == session_id)
        .group_by(LearningEvidence.learning_outcome_id)
        .subquery()
    )

    weighted_stmt = (
        select(
            func.sum(LearningEvidence.score * LearningOutcome.weight).label(
                "weighted_sum"
            ),
            func.sum(LearningOutcome.weight).label("total_weight"),
        )
        .join(
            LearningOutcome,
            LearningEvidence.learning_outcome_id == LearningOutcome.id,
        )
        .join(
            latest_evidence_subq,
            and_(
                LearningEvidence.learning_outcome_id
                == latest_evidence_subq.c.learning_outcome_id,
                LearningEvidence.id == latest_evidence_subq.c.max_id,
            ),
        )
        .where(LearningOutcome.subcompetency_id == subcompetency_id)
    )

    row = (await db.execute(weighted_stmt)).one()
    weighted_sum = float(row.weighted_sum or 0.0)
    total_weight = float(row.total_weight or 0.0)

    if total_weight <= 0.0:
        return max(0.0, min(1.0, round(fallback_score, 4)))

    return max(0.0, min(1.0, round(weighted_sum / total_weight, 4)))


async def record_learning_progress(
    db: AsyncSession,
    *,
    session_id: str,
    learning_outcome_id: int,
    score: float,
    feedback: str,
) -> float:
    """Registra una evidencia de aprendizaje y actualiza el progreso.

    Pasos:
      1. Resuelve el `LearningOutcome` (y su `subcompetency_id`).
      2. Inserta una nueva fila en `learning_evidences`.
      3. Recalcula la media móvil ponderada de la subcompetencia.
      4. UPSERT en `user_competency_progress`.

    Devuelve la nueva puntuación agregada de la subcompetencia.
    Lanza `LookupError` si `learning_outcome_id` no existe (los callers
    deben mapear a 404 si están en un endpoint, o capturar y omitir la
    persistencia silenciosamente cuando se invoque desde otros flujos).

    Esta función NO commitea: el commit lo hace el dependency `get_db` al
    cerrar el generador del request.
    """
    safe_score = max(0.0, min(1.0, float(score)))

    outcome_stmt = (
        select(LearningOutcome)
        .options(selectinload(LearningOutcome.subcompetency))
        .where(LearningOutcome.id == learning_outcome_id)
    )
    outcome: Optional[LearningOutcome] = (
        await db.execute(outcome_stmt)
    ).scalar_one_or_none()

    if outcome is None:
        raise LookupError(
            f"LearningOutcome con id={learning_outcome_id} no existe."
        )

    db.add(
        LearningEvidence(
            session_id=session_id,
            learning_outcome_id=learning_outcome_id,
            score=safe_score,
            feedback=feedback,
        )
    )
    await db.flush()  # asegura que la nueva evidencia entra en el cálculo

    new_subcompetency_score = await _compute_weighted_subcompetency_score(
        db,
        session_id=session_id,
        subcompetency_id=outcome.subcompetency_id,
        fallback_score=safe_score,
    )

    progress_stmt = select(UserCompetencyProgress).where(
        UserCompetencyProgress.session_id == session_id,
        UserCompetencyProgress.subcompetency_id == outcome.subcompetency_id,
    )
    progress: Optional[UserCompetencyProgress] = (
        await db.execute(progress_stmt)
    ).scalar_one_or_none()

    if progress is None:
        db.add(
            UserCompetencyProgress(
                session_id=session_id,
                subcompetency_id=outcome.subcompetency_id,
                score=new_subcompetency_score,
            )
        )
    else:
        progress.score = new_subcompetency_score

    return new_subcompetency_score


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/evaluate",
    response_model=EvaluateLearningResponse,
    summary="Evalúa una respuesta, registra la evidencia y actualiza el progreso",
)
async def evaluate(
    body: EvaluateLearningRequest,
    db: AsyncSession = Depends(get_db),
) -> EvaluateLearningResponse:
    """Evalúa la respuesta de un estudiante y persiste la evidencia + progreso.

    Errores HTTP:
      * 400 si `session_id` queda vacío tras normalizar.
      * 404 si el `learning_outcome_id` no existe.
      * 502 si el LLM evaluador no está disponible (credenciales/red).
      * 500 ante errores inesperados de BD o evaluación.
    """
    session_id = body.session_id.strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="session_id no puede estar vacío.",
        )

    # 1. Validar que el outcome existe (para producir 404 antes del LLM)
    try:
        outcome_check = await db.execute(
            select(LearningOutcome.id).where(
                LearningOutcome.id == body.learning_outcome_id
            )
        )
        if outcome_check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"LearningOutcome con id={body.learning_outcome_id} no existe."
                ),
            )
    except SQLAlchemyError as exc:
        logger.exception(
            "Error consultando LearningOutcome id=%s",
            body.learning_outcome_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Error consultando el resultado de aprendizaje.",
        ) from exc

    # Recuperamos también la descripción para alimentar al LLM.
    description_row = await db.execute(
        select(LearningOutcome.description).where(
            LearningOutcome.id == body.learning_outcome_id
        )
    )
    description = description_row.scalar_one()

    # 2. Evaluación con LLM (bloqueante → hilo separado)
    try:
        evaluation = await asyncio.to_thread(
            EvaluationService.evaluate_student_answer,
            description,
            body.answer,
        )
    except RuntimeError as exc:
        logger.exception("Fallo configurando o invocando el LLM evaluador.")
        raise HTTPException(
            status_code=502,
            detail=f"Servicio de evaluación no disponible: {exc}",
        ) from exc
    except Exception as exc:  # pragma: no cover - red de seguridad
        logger.exception("Error inesperado durante la evaluación con LLM.")
        raise HTTPException(
            status_code=500,
            detail="Error interno al evaluar la respuesta.",
        ) from exc

    score = float(evaluation["score"])
    feedback = str(evaluation["feedback"])

    # 3. Persistir evidencia + actualizar progreso
    try:
        new_subcompetency_score = await record_learning_progress(
            db,
            session_id=session_id,
            learning_outcome_id=body.learning_outcome_id,
            score=score,
            feedback=feedback,
        )
    except LookupError as exc:
        # Carrera muy improbable: el outcome existía al validar pero ya no.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        logger.exception(
            "Error persistiendo evidencia/progreso (session=%s, outcome=%s).",
            session_id,
            body.learning_outcome_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Error guardando la evaluación.",
        ) from exc

    return EvaluateLearningResponse(
        score=score,
        feedback=feedback,
        updated_subcompetency_score=new_subcompetency_score,
    )
