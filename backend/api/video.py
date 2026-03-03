"""
Endpoints de procesamiento de video - POST /process_video
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from media_processor import process_video, is_youtube_url, extract_video_id
from rag_engine import initialize_vector_store
from api.chat import invalidate_agent_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/process_video", tags=["video"])


class ProcessVideoRequest(BaseModel):
    url: str
    session_id: Optional[str] = None


class ProcessVideoResponse(BaseModel):
    success: bool
    document_count: int
    video_id: Optional[str] = None
    message: str


@router.post("", response_model=ProcessVideoResponse)
def process_video_endpoint(
    body: ProcessVideoRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (body.session_id or x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido (header X-Session-Id o body)")
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url vacía")
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="URL no válida de YouTube")

    try:
        documents = process_video(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error processing video: %s", e)
        raise HTTPException(status_code=500, detail=f"Error al procesar video: {str(e)}")

    if not documents:
        return ProcessVideoResponse(
            success=False,
            document_count=0,
            message="No se pudo extraer contenido del video.",
        )

    existing_vs = initialize_vector_store(documents=None, existing_vector_store=None, session_id=session_id)
    vector_store = initialize_vector_store(
        documents=documents,
        existing_vector_store=existing_vs,
        session_id=session_id,
    )
    if not vector_store:
        raise HTTPException(status_code=500, detail="Error al agregar video al vector store")

    invalidate_agent_cache(session_id)
    video_id = extract_video_id(url)
    return ProcessVideoResponse(
        success=True,
        document_count=len(documents),
        video_id=video_id,
        message="Video procesado correctamente.",
    )
