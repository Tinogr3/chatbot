"""
Endpoints de procesamiento de vídeo - POST /process_video
"""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_validated_session
from media_processor import is_youtube_url
from schemas import ProcessVideoRequest, TaskEnqueuedResponse
from worker import process_video_task

router = APIRouter(prefix="/process_video", tags=["video"])


@router.post("", response_model=TaskEnqueuedResponse)
def process_video_endpoint(
    body: ProcessVideoRequest,
    session_id: str = Depends(get_validated_session),
) -> TaskEnqueuedResponse:
    """Encola el procesamiento del vídeo (transcripción/Whisper) y devuelve task_id."""
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
