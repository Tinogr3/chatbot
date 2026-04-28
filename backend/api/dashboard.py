"""
Endpoints del dashboard de competencias.

GET /dashboard/competencies
    Devuelve la puntuación promedio de cada competencia principal **extraída
    de los documentos del proyecto activo**, hayan sido evaluadas o no.

    Para cada competencia:
      - Si todas sus subcompetencias tienen evidencia (`UserCompetencyProgress`)
        para la sesión, devuelve la media de esas puntuaciones.
      - Si aún no hay progreso, devuelve `score = 0.0`. Esto permite que el
        usuario vea qué competencias se han creado al subir documentos
        incluso antes de hacer ninguna evaluación.

Diseño:
    * Las competencias se persisten globalmente en BD (no llevan session_id),
      pero `Competency.document_id` apunta al filename del PDF original. El
      registro de documentos por sesión (`document_registry/<session>.json`)
      enumera qué filenames pertenecen a esa sesión, así que cruzamos
      `Competency.document_id IN (registry.keys())` para filtrar correctamente
      por proyecto sin filtrar también las que aún no están evaluadas.
    * Se hace LEFT JOIN con `UserCompetencyProgress` filtrado por session_id
      vía subquery, de modo que SOLO se considera el progreso del usuario
      actual (no se mezcla con el de otros).
    * `get_db` proporciona la sesión async; `X-Session-Id` se normaliza igual
      que en el resto de la API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from document_registry import load_document_registry
from logger import get_logger
from models import Competency, Subcompetency, UserCompetencyProgress
from schemas import DashboardCompetencyItem, DashboardCompetencyResponse

logger = get_logger("api.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _normalize_session_id(raw: Optional[str]) -> str:
    """Misma normalización que aplican el resto de endpoints (chat, history…)."""
    return (raw or "").strip().lower().replace(" ", "_")


@router.get(
    "/competencies",
    response_model=DashboardCompetencyResponse,
    summary="Puntuación promedio por competencia para los documentos del proyecto",
)
async def get_dashboard_competencies(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> DashboardCompetencyResponse:
    """Devuelve todas las competencias creadas para la sesión actual.

    Esquema del JOIN:
        Competency (filtrada por `document_id` ∈ docs de la sesión)
            └─► Subcompetency
                    └─► UserCompetencyProgress (LEFT JOIN, scoped por session_id)

    Para evitar mezclar progreso entre sesiones distintas, el progreso se
    materializa primero en una subquery filtrada por `session_id` y luego se
    LEFT-JOIN-ea con la subcompetencia. `COALESCE(AVG(score), 0)` produce 0
    para las competencias todavía sin evaluar.
    """
    session_id = _normalize_session_id(x_session_id)
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Header X-Session-Id requerido",
        )

    # Documentos que pertenecen a esta sesión. Las claves del registry son los
    # filenames originales, idénticos a los persistidos en `Competency.document_id`
    # cuando el worker extrae competencias al ingestar el PDF.
    document_filenames = list(load_document_registry(session_id).keys())
    if not document_filenames:
        return DashboardCompetencyResponse(competencies=[])

    # Subquery: progreso del usuario actual (NO se mezcla con otras sesiones).
    progress_subq = (
        select(
            UserCompetencyProgress.subcompetency_id.label("subcompetency_id"),
            UserCompetencyProgress.score.label("score"),
        )
        .where(UserCompetencyProgress.session_id == session_id)
        .subquery()
    )

    stmt = (
        select(
            Competency.id.label("competency_id"),
            Competency.name.label("name"),
            func.coalesce(func.avg(progress_subq.c.score), 0.0).label("avg_score"),
        )
        .join(Subcompetency, Subcompetency.competency_id == Competency.id)
        .outerjoin(
            progress_subq,
            progress_subq.c.subcompetency_id == Subcompetency.id,
        )
        .where(Competency.document_id.in_(document_filenames))
        .group_by(Competency.id, Competency.name)
        .order_by(Competency.name)
    )

    try:
        rows = (await db.execute(stmt)).all()
    except SQLAlchemyError as exc:
        logger.exception(
            "Error agregando competencias para session=%s", session_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Error consultando el dashboard de competencias.",
        ) from exc

    competencies = [
        DashboardCompetencyItem(
            name=row.name,
            score=round(float(row.avg_score or 0.0), 4),
        )
        for row in rows
    ]

    return DashboardCompetencyResponse(competencies=competencies)
