"""
Endpoints de subida de PDFs - POST /upload (asíncrono), POST /upload/load_cloud
"""
import base64
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from api.chat import invalidate_agent_cache
from document_registry import load_document_registry, save_document_registry
from gcs_utils import procesar_todos_pdfs_nube, upload_to_gcs
from logger import get_logger
from rag_engine import initialize_vector_store
from schemas import LoadCloudResponse, TaskEnqueuedResponse

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


@router.post("/load_cloud", response_model=LoadCloudResponse)
def load_cloud_pdfs(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> LoadCloudResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    documents, filenames, registry, error_message = procesar_todos_pdfs_nube(session_id=session_id)
    if not documents:
        return LoadCloudResponse(
            success=False,
            filenames=[],
            document_count=0,
            message=error_message or "No se encontraron PDFs en el bucket o hubo errores al procesarlos.",
        )

    save_document_registry(session_id, registry)
    existing_vs = initialize_vector_store(documents=None, session_id=session_id)
    vector_store = initialize_vector_store(
        documents=documents,
        existing_vector_store=existing_vs,
        session_id=session_id,
    )
    if not vector_store:
        raise HTTPException(status_code=500, detail="Error al crear/actualizar vector store")

    invalidate_agent_cache(session_id)
    return LoadCloudResponse(
        success=True,
        filenames=filenames,
        document_count=len(documents),
        message=f"{len(filenames)} archivos cargados desde la nube.",
    )
