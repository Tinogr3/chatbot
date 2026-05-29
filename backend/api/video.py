"""
Endpoints de procesamiento de vídeo - POST /process_video
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from media_processor import is_youtube_url
from schemas import ProcessVideoRequest, TaskEnqueuedResponse
from session_ids import normalize_session_id
from worker import process_video_task

router = APIRouter(prefix="/process_video", tags=["video"])


@router.post("", response_model=TaskEnqueuedResponse)
def process_video_endpoint(
    body: ProcessVideoRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    """Encola el procesamiento del vídeo (transcripción/Whisper) y devuelve task_id."""
    session_id = normalize_session_id(body.session_id or x_session_id)
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido (header X-Session-Id o body)")
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url vacía")
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="URL no válida de YouTube")

    task = process_video_task.delay(url=url, session_id=session_id)
    return TaskEnqueuedResponse(
        task_id=task.id,
        message="Vídeo encolado. Consulta GET /status/{task_id} para el progreso.",
    )
