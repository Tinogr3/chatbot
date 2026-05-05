"""
Discovery Hub — listado de resúmenes/exámenes guardados y audio tipo podcast (TTS).
"""
from __future__ import annotations

import asyncio
import io
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from discovery_repo import (
    count_exams,
    count_summaries,
    list_exams,
    list_summaries,
    list_summaries_by_ids_ordered,
)
from logger import get_logger
from models import StoredSummary
from schemas import DiscoveryItemOut, DiscoveryStatsOut, PodcastAudioRequest

logger = get_logger("api.discovery")

router = APIRouter(prefix="/discovery", tags=["discovery"])

_MAX_TTS_CHARS = 12_000
# gTTS puede tardar mucho con textos largos o red lenta; evita peticiones colgadas indefinidamente.
_TTS_TIMEOUT_SEC = 240.0


def _normalize_session(x_session_id: Optional[str]) -> str:
    sid = (x_session_id or "").strip().lower().replace(" ", "_")
    if not sid:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    return sid


def _summaries_to_speech_text(rows: list[StoredSummary], *, oldest_first: bool = True) -> str:
    """Une contenidos en uno solo para TTS.

    Si ``oldest_first`` es True se asume que ``rows`` está del más nuevo al más viejo
    (como ``list_summaries``) y se invierte para narrar del más antiguo al más nuevo.
    Si es False se respeta el orden de ``rows`` (p. ej. selección explícita del usuario).
    """
    seq = list(reversed(rows)) if oldest_first else list(rows)
    parts = [(r.content or "").strip() for r in seq if (r.content or "").strip()]
    text = "\n\n".join(parts)
    if len(text) > _MAX_TTS_CHARS:
        text = text[:_MAX_TTS_CHARS] + "\n…"
    return text


async def _synthesize_mp3_es(text: str) -> bytes:
    """Genera MP3 en un hilo para no bloquear el event loop."""

    def _run() -> bytes:
        try:
            from gtts import gTTS  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError("gTTS no instalado; añade gtts al entorno backend.") from e
        buf = io.BytesIO()
        tts = gTTS(text=text, lang="es", slow=False)
        tts.write_to_fp(buf)
        return buf.getvalue()

    return await asyncio.to_thread(_run)


@router.get("/stats", response_model=DiscoveryStatsOut)
async def discovery_stats(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> DiscoveryStatsOut:
    session_id = _normalize_session(x_session_id)
    summaries_n = await count_summaries(db, session_id)
    exams_n = await count_exams(db, session_id)
    return DiscoveryStatsOut(summaries=summaries_n, exams=exams_n)


@router.get("/summaries", response_model=list[DiscoveryItemOut])
async def get_summaries(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryItemOut]:
    session_id = _normalize_session(x_session_id)
    rows = await list_summaries(db, session_id)
    return [
        DiscoveryItemOut(
            id=r.id,
            user_prompt=r.user_prompt,
            content=r.content,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/exams", response_model=list[DiscoveryItemOut])
async def get_exams(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> list[DiscoveryItemOut]:
    session_id = _normalize_session(x_session_id)
    rows = await list_exams(db, session_id)
    return [
        DiscoveryItemOut(
            id=r.id,
            user_prompt=r.user_prompt,
            content=r.content,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/podcast-audio")
async def create_podcast_audio(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    body: PodcastAudioRequest = Body(default_factory=PodcastAudioRequest),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Concatena resúmenes guardados y devuelve audio MP3 (español).

    Si el cuerpo incluye ``summary_ids``, solo esos resúmenes (en ese orden);
    si no se envía cuerpo o ``summary_ids`` es null, se usan todos los de la sesión.
    """
    session_id = _normalize_session(x_session_id)
    rows: list[StoredSummary]
    if body.summary_ids is None:
        rows = await list_summaries(db, session_id)
    elif len(body.summary_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="Selecciona al menos un resumen, u omite el cuerpo de la petición para incluir todos.",
        )
    else:
        try:
            rows = await list_summaries_by_ids_ordered(db, session_id, body.summary_ids)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if not rows:
        raise HTTPException(
            status_code=400,
            detail="No hay resúmenes guardados. Pide un resumen en el chat primero.",
        )
    text = _summaries_to_speech_text(rows, oldest_first=body.summary_ids is None)
    if len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="El texto para audio es demasiado corto.")
    try:
        mp3 = await asyncio.wait_for(_synthesize_mp3_es(text), timeout=_TTS_TIMEOUT_SEC)
    except asyncio.TimeoutError:
        logger.warning("TTS podcast: tiempo de espera agotado (%ss)", _TTS_TIMEOUT_SEC)
        raise HTTPException(
            status_code=504,
            detail="La generación de audio tardó demasiado. Prueba con menos resúmenes o comprueba la red.",
        ) from None
    except Exception as e:
        logger.warning("Fallo TTS podcast: %s", e)
        raise HTTPException(
            status_code=503,
            detail="No se pudo generar el audio. Comprueba la conexión o la instalación de gTTS.",
        ) from e
    return Response(content=mp3, media_type="audio/mpeg")
