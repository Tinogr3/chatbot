"""
Endpoints del dashboard de competencias.

GET /dashboard/competencies
    Devuelve, **por cada documento cargado en el proyecto**, la lista de
    competencias extraídas y la puntuación promedio (0.0–1.0) asociada a
    la práctica en modo aprendizaje vía `UserCompetencyProgress`.

    Para cada competencia:
      - Si todas sus subcompetencias tienen evidencia (`UserCompetencyProgress`)
        para la sesión, devuelve la media de esas puntuaciones.
      - Si aún no hay progreso, devuelve `score = 0.0`. Esto permite que el
        usuario vea qué competencias se han creado al subir documentos
        incluso antes de hacer ninguna evaluación.

Diseño:
    * Las competencias se persisten globalmente en BD (no llevan session_id),
      pero `Competency.document_id` apunta al filename del PDF original. El
      registro por sesión (`document_registry_<session>.json`) lista los
      archivos del proyecto; el cliente puede enviar además el header opcional
      ``X-Project-Document-Keys`` (JSON array) con los nombres del proyecto activo
      para cubrir registro vacío, desfases o API/worker sin disco compartido.
    * Se hace LEFT JOIN con `UserCompetencyProgress` filtrado por session_id
      vía subquery, de modo que SOLO se considera el progreso del usuario
      actual (no se mezcla con el de otros).
    * `get_db` proporciona la sesión async; `X-Session-Id` se normaliza igual
      que en el resto de la API.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_validated_session
from database import get_db
from document_keys import (
    build_document_filenames,
    competency_document_match,
    normalize_competency_document_id,
    parse_project_document_keys_header,
)
from document_registry import load_document_registry
from logger import get_logger
from models import Competency, Subcompetency, UserCompetencyProgress

from schemas import (
    DashboardCompetencyItem,
    DashboardCompetencyResponse,
    DashboardDocumentCompetencies,
)

logger = get_logger("api.dashboard")

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/competencies",
    response_model=DashboardCompetencyResponse,
    summary="Puntuación promedio por competencia para los documentos del proyecto",
)
async def get_dashboard_competencies(
    session_id: str = Depends(get_validated_session),
    x_project_document_keys: Optional[str] = Header(
        None,
        alias="X-Project-Document-Keys",
        description="JSON array con nombres de documentos del proyecto (fallback si el registro en disco está vacío o desfasado).",
    ),
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
    registry = load_document_registry(session_id)
    header_keys = parse_project_document_keys_header(x_project_document_keys)
    document_filenames, display_names = build_document_filenames(registry, header_keys)

    if not document_filenames:
        return DashboardCompetencyResponse(documents=[])

    # Subquery: progreso del usuario actual (NO se mezcla con otras sesiones).
    progress_subq = (
        select(
            UserCompetencyProgress.subcompetency_id.label("subcompetency_id"),
            UserCompetencyProgress.score.label("score"),
        )
        .where(UserCompetencyProgress.session_id == session_id)
        .subquery()
    )

    doc_match = competency_document_match(document_filenames)
    if doc_match is None:
        return DashboardCompetencyResponse(documents=[])

    stmt = (
        select(
            Competency.document_id.label("document_id"),
            Competency.id.label("competency_id"),
            Competency.name.label("name"),
            func.coalesce(func.avg(progress_subq.c.score), 0.0).label("avg_score"),
        )
        .join(Subcompetency, Subcompetency.competency_id == Competency.id)
        .outerjoin(
            progress_subq,
            progress_subq.c.subcompetency_id == Subcompetency.id,
        )
        .where(doc_match)
        .group_by(Competency.document_id, Competency.id, Competency.name)
        .order_by(Competency.document_id, Competency.name)
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

    by_document: dict[str, list[DashboardCompetencyItem]] = defaultdict(list)
    for row in rows:
        doc_key = normalize_competency_document_id(row.document_id or "")
        if not doc_key:
            continue
        by_document[doc_key].append(
            DashboardCompetencyItem(
                name=row.name,
                score=round(float(row.avg_score or 0.0), 4),
            )
        )

    documents = [
        DashboardDocumentCompetencies(
            document_id=fn,
            display_name=display_names.get(fn),
            competencies=by_document.get(fn, []),
        )
        for fn in document_filenames
    ]

    return DashboardCompetencyResponse(documents=documents)
