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

import json
import os
import re
from urllib.parse import unquote
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_validated_session
from database import get_db
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


_YT_URL_RE = re.compile(r"(?:youtube\.com|youtu\.be)", re.IGNORECASE)
_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})")


def _extract_video_id_from_url(url: str) -> Optional[str]:
    """Extrae el video_id de 11 caracteres de una URL de YouTube."""
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def _basename_key(key: str) -> str:
    """Clave canónica para un documento (basename del fichero o video_id)."""
    k = (key or "").strip()
    if not k:
        return ""
    if _YT_URL_RE.search(k):
        # Para URLs de YouTube devolver el video_id (no os.path.basename que
        # daría 'watch?v=…' en YouTube.com o solo el ID en youtu.be)
        vid = _extract_video_id_from_url(k)
        return vid if vid else k
    return os.path.basename(k)


def _parse_project_document_keys_header(raw: Optional[str]) -> List[str]:
    """JSON array de claves de documento enviado por el cliente.

    El cliente codifica el valor con ``encodeURIComponent`` para evitar
    caracteres fuera de ISO-8859-1 en headers HTTP; aquí lo decodificamos.
    """
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(unquote(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    out: List[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _build_document_filenames(
    registry: Dict[str, Any],
    header_keys: List[str],
) -> Tuple[List[str], Dict[str, str]]:
    """Construye la lista de claves canónicas de documentos y su mapa de nombres legibles.

    Para vídeos de YouTube: clave = video_id (11 chars), nombre = título del vídeo.
    Para PDFs u otros: clave = basename, nombre = basename.

    El header es un fallback para PDFs cuyo registry esté en otro servidor/volumen.

    Returns:
        document_filenames: lista de claves canónicas en orden de registro.
        display_names: mapping clave → nombre legible para el frontend.
    """
    seen: set[str] = set()
    filenames: List[str] = []
    display_names: Dict[str, str] = {}

    # 1. Entradas del registry (fuente de verdad para la sesión)
    for reg_key, reg_value in registry.items():
        card = reg_value if isinstance(reg_value, dict) else {}
        if card.get("type") == "video":
            # Clave canónica: video_id almacenado explícitamente o extraído de la URL
            video_id = card.get("video_id") or _extract_video_id_from_url(reg_key)
            if not video_id:
                continue
            lookup_key = video_id
            display = card.get("title") or reg_key
        else:
            lookup_key = _basename_key(reg_key)
            display = lookup_key

        if not lookup_key or lookup_key in seen:
            continue
        seen.add(lookup_key)
        filenames.append(lookup_key)
        display_names[lookup_key] = display

    # 2. Claves del header como fallback (cuando el registry está vacío/desfasado)
    for key in header_keys:
        # El frontend envía video_id (11 chars) para YouTube
        lookup_key = _basename_key(key) if _YT_URL_RE.search(key) else key.strip()
        if not lookup_key or lookup_key in seen:
            continue
        seen.add(lookup_key)
        filenames.append(lookup_key)
        display_names[lookup_key] = key.strip()

    return filenames, display_names


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
    header_keys = _parse_project_document_keys_header(x_project_document_keys)
    document_filenames, display_names = _build_document_filenames(registry, header_keys)

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

    doc_match = []
    for fn in document_filenames:
        doc_match.append(Competency.document_id == fn)
        # Compatibilidad con datos anteriores donde se almacenaba la URL completa
        # en lugar del video_id — el video_id de 11 chars aparece en la URL.
        doc_match.append(Competency.document_id.like(f"%/{fn}"))
        doc_match.append(Competency.document_id.like(f"%?v={fn}%"))

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
        .where(or_(*doc_match))
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
        raw_id = row.document_id or ""
        # Normalizar: si es URL de YouTube (datos antiguos), extraer video_id
        if _YT_URL_RE.search(raw_id):
            doc_key = _extract_video_id_from_url(raw_id) or _basename_key(raw_id)
        else:
            doc_key = _basename_key(raw_id)
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
