"""
Endpoints de procesamiento de video - POST /process_video (asíncrono)
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from logger import get_logger
from media_processor import extract_video_id, is_youtube_url
from schemas import ProcessVideoRequest, TaskEnqueuedResponse
from worker import process_video_task

logger = get_logger("api.video")
router = APIRouter(prefix="/process_video", tags=["video"])


@router.post("", response_model=TaskEnqueuedResponse)
def process_video_endpoint(
    body: ProcessVideoRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    """Encola el procesamiento del video (transcripción/Whisper) y devuelve task_id. Consultar GET /status/{task_id} para progreso."""
    session_id = (body.session_id or x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id requerido (header X-Session-Id o body)")
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url vacía")
    if not is_youtube_url(url):
        raise HTTPException(status_code=400, detail="URL no válida de YouTube")

    task = process_video_task.delay(url=url, session_id=session_id)
    return TaskEnqueuedResponse(task_id=task.id, message="Video encolado. Consulta GET /status/{task_id} para el progreso.")
