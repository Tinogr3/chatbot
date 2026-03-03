"""
Endpoints de subida de PDFs - POST /upload, POST /upload/load_cloud
"""
import os
import tempfile
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Header
from pydantic import BaseModel

from rag_engine import procesar_pdf, initialize_vector_store
from gcs_utils import upload_to_gcs, procesar_todos_pdfs_nube
from document_registry import load_document_registry, save_document_registry
from api.chat import invalidate_agent_cache

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    success: bool
    gcs_path: Optional[str] = None
    filename: str
    document_count: int
    message: str


class LoadCloudResponse(BaseModel):
    success: bool
    filenames: List[str]
    document_count: int
    message: str


@router.post("", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")

    content = await file.read()
    filename = file.filename

    # GCS es opcional: si no hay credenciales simplemente se omite
    gcs_path = upload_to_gcs(content, filename)
    if gcs_path:
        logger.info("Archivo subido a GCS: %s", gcs_path)
    else:
        logger.info("GCS no configurado o no disponible; procesando solo en local.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        registry = load_document_registry(session_id)
        documents, registry = procesar_pdf(
            tmp_path,
            extract_images=True,
            max_tokens=65535,
            session_id=session_id,
            document_registry=registry,
        )
    except Exception as e:
        logger.exception("Error processing PDF: %s", e)
        raise HTTPException(status_code=500, detail=f"Error procesando PDF: {str(e)}")
    finally:
        os.unlink(tmp_path)

    if not documents:
        return UploadResponse(
            success=False,
            gcs_path=gcs_path,
            filename=filename,
            document_count=0,
            message="No se pudieron extraer documentos del PDF.",
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
    return UploadResponse(
        success=True,
        gcs_path=gcs_path,
        filename=filename,
        document_count=len(documents),
        message=f"Archivo '{filename}' procesado correctamente.",
    )


@router.post("/load_cloud", response_model=LoadCloudResponse)
def load_cloud_pdfs(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
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
