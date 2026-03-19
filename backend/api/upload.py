"""
Endpoints de subida de PDFs - POST /upload (asíncrono), POST /upload/load_cloud
"""
import base64
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from gcs_utils import upload_to_gcs
from logger import get_logger
from schemas import TaskEnqueuedResponse

logger = get_logger("api.upload")
router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=TaskEnqueuedResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    """Encola el procesamiento del PDF y devuelve task_id. Consultar GET /status/{task_id} para progreso."""
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = await file.read()
    filename = file.filename

    gcs_path = upload_to_gcs(content, filename)
    if gcs_path:
        logger.info("Archivo subido a GCS: %s", gcs_path)

    from worker import process_pdf_task

    file_content_b64 = base64.b64encode(content).decode("utf-8")
    task = process_pdf_task.delay(
        file_content_b64=file_content_b64,
        filename=filename,
        session_id=session_id,
        gcs_path=gcs_path,
    )
    return TaskEnqueuedResponse(task_id=task.id, message="PDF encolado. Consulta GET /status/{task_id} para el progreso.")


@router.post("/load_cloud", response_model=TaskEnqueuedResponse)
def load_cloud_pdfs(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> TaskEnqueuedResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
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
