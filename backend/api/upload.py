"""
Endpoints de subida de PDFs - POST /upload (asíncrono), POST /upload/load_cloud
"""
import asyncio
import base64
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from logger import get_logger
from schemas import TaskEnqueuedResponse
from session_ids import normalize_session_id

logger = get_logger("api.upload")
router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=TaskEnqueuedResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    """Encola el procesamiento del PDF y devuelve task_id. Consultar GET /status/{task_id} para progreso."""
    session_id = normalize_session_id(x_session_id)
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    filename = file.filename

    # Flujo manual: NO enviar al bucket. Serializamos a base64 para que el worker
    # procese el archivo directamente en background.
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="El PDF está vacío")
    file_b64 = await asyncio.to_thread(base64.b64encode, file_bytes)
    file_b64_str = file_b64.decode("utf-8")

    from worker import process_pdf_task

    task = process_pdf_task.delay(
        filename=filename,
        session_id=session_id,
        file_b64=file_b64_str,
    )
    return TaskEnqueuedResponse(task_id=task.id, message="PDF encolado. Consulta GET /status/{task_id} para el progreso.")


@router.post("/load_cloud", response_model=TaskEnqueuedResponse)
def load_cloud_pdfs(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    session_id = normalize_session_id(x_session_id)
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    # Validación estricta antes de encolar para que el cliente reciba
    # un error claro (en lugar de fallos silenciosos en background).
    from gcs_utils import validate_gcs_configuration

    validate_gcs_configuration()

    from worker import process_cloud_pdfs_task

    task = process_cloud_pdfs_task.delay(session_id=session_id)
    return TaskEnqueuedResponse(
        task_id=task.id,
        message="PDFs del bucket encolados. Consulta GET /status/{task_id} para el progreso.",
    )
