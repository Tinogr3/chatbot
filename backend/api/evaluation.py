"""
Endpoints de evaluación de competencias – POST /evaluate-learning, GET /dashboard/competencies
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from evaluation_engine import EvaluationService
from models import Competency, Subcompetency, UserCompetencyProgress
from schemas import (
    DashboardCompetencyItem,
    DashboardCompetencyResponse,
    EvaluateLearningRequest,
    EvaluateLearningResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.post("/evaluate-learning", response_model=EvaluateLearningResponse)
async def evaluate_learning(body: EvaluateLearningRequest) -> EvaluateLearningResponse:
    """Evalúa la respuesta de un estudiante a un resultado de aprendizaje."""
    try:
        return await EvaluationService.process_evaluation(
            session_id=body.session_id,
            learning_outcome_id=body.learning_outcome_id,
            student_answer=body.answer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error inesperado en evaluate_learning")
        raise HTTPException(status_code=500, detail="Error interno al evaluar") from exc


@router.get("/dashboard/competencies", response_model=DashboardCompetencyResponse)
async def dashboard_competencies(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> DashboardCompetencyResponse:
    """Devuelve las competencias con su puntuación agregada para el dashboard."""
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    stmt = (
        select(
            Competency.name,
            func.avg(UserCompetencyProgress.score).label("score"),
        )
        .join(Subcompetency, UserCompetencyProgress.subcompetency_id == Subcompetency.id)
        .join(Competency, Subcompetency.competency_id == Competency.id)
        .where(UserCompetencyProgress.session_id == session_id)
        .group_by(Competency.id, Competency.name)
    )

    result = await db.execute(stmt)
    rows = result.all()

    competencies = [
        DashboardCompetencyItem(name=row.name, score=round(row.score, 2))
        for row in rows
    ]

    return DashboardCompetencyResponse(competencies=competencies)
