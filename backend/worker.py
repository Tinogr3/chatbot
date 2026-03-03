"""
Worker Celery - Procesamiento asíncrono de videos (YouTube/Whisper) y PDFs.
Broker y backend: Redis. Ejecutar: celery -A worker worker --loglevel=info
"""
import base64
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

# Asegurar path del backend
if __name__ == "__main__" or os.path.basename(os.getcwd()) != "backend":
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

from celery import Celery
from celery.result import AsyncResult

# Configuración desde entorno (por defecto Redis local)
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

app = Celery(
    "chatbot_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    result_expires=3600 * 24,  # 24 h
    timezone="UTC",
    enable_utc=True,
)


@app.task(bind=True, name="worker.process_video_task")
def process_video_task(
    self,
    url: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Tarea asíncrona: descarga/transcribe video YouTube y añade documentos al vector store.
    """
    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.05, "message": "Iniciando procesamiento del video..."})
        from api.chat import invalidate_agent_cache
        from document_registry import load_document_registry, save_document_registry
        from exceptions import VideoTranscriptionError
        from media_processor import extract_video_id, process_video as do_process_video
        from rag_engine import initialize_vector_store
    except Exception as e:
        return {"success": False, "error": str(e), "document_count": 0}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.2, "message": "Obteniendo transcripción..."})
        documents = do_process_video(url)
        if not documents:
            return {"success": False, "error": "No se pudo extraer contenido del video.", "document_count": 0}

        self.update_state(state="PROGRESS", meta={"progress": 0.7, "message": "Añadiendo al índice de búsqueda..."})
        existing_vs = initialize_vector_store(documents=None, existing_vector_store=None, session_id=session_id)
        vector_store = initialize_vector_store(
            documents=documents,
            existing_vector_store=existing_vs,
            session_id=session_id,
        )
        if not vector_store:
            return {"success": False, "error": "Error al agregar video al vector store", "document_count": 0}

        invalidate_agent_cache(session_id)
        video_id = extract_video_id(url)
        return {
            "success": True,
            "document_count": len(documents),
            "video_id": video_id,
            "message": "Video procesado correctamente.",
        }
    except VideoTranscriptionError as e:
        return {"success": False, "error": e.message, "document_count": 0}
    except Exception as e:
        return {"success": False, "error": str(e), "document_count": 0}


@app.task(bind=True, name="worker.process_pdf_task")
def process_pdf_task(
    self,
    file_content_b64: str,
    filename: str,
    session_id: str,
    gcs_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tarea asíncrona: procesa PDF (particionado, imágenes) y añade documentos al vector store.
    file_content_b64: contenido del PDF en base64.
    """
    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.05, "message": "Preparando documento..."})
        from api.chat import invalidate_agent_cache
        from document_registry import load_document_registry, save_document_registry
        from exceptions import DocumentProcessingError
        from gcs_utils import upload_to_gcs
        from rag_engine import initialize_vector_store, procesar_pdf as do_procesar_pdf
    except Exception as e:
        return {"success": False, "error": str(e), "filename": filename, "document_count": 0}

    tmp_path = None
    try:
        content = base64.b64decode(file_content_b64)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        self.update_state(state="PROGRESS", meta={"progress": 0.2, "message": "Procesando PDF y extrayendo texto..."})
        registry = load_document_registry(session_id)
        documents, registry = do_procesar_pdf(
            tmp_path,
            extract_images=True,
            max_tokens=65535,
            session_id=session_id,
            document_registry=registry,
        )

        if not documents:
            return {
                "success": False,
                "gcs_path": gcs_path,
                "filename": filename,
                "document_count": 0,
                "message": "No se pudieron extraer documentos del PDF.",
            }

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "message": "Añadiendo al índice de búsqueda..."})
        save_document_registry(session_id, registry)
        existing_vs = initialize_vector_store(documents=None, session_id=session_id)
        vector_store = initialize_vector_store(
            documents=documents,
            existing_vector_store=existing_vs,
            session_id=session_id,
        )
        if not vector_store:
            return {"success": False, "error": "Error al crear/actualizar vector store", "filename": filename, "document_count": 0}

        invalidate_agent_cache(session_id)
        return {
            "success": True,
            "gcs_path": gcs_path,
            "filename": filename,
            "document_count": len(documents),
            "message": f"Archivo '{filename}' procesado correctamente.",
        }
    except DocumentProcessingError as e:
        return {"success": False, "error": e.message, "filename": filename, "document_count": 0}
    except Exception as e:
        return {"success": False, "error": str(e), "filename": filename, "document_count": 0}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def get_task_result(task_id: str) -> Optional[AsyncResult]:
    """Devuelve el AsyncResult para un task_id (para consultar estado desde la API)."""
    if not task_id:
        return None
    return AsyncResult(task_id, app=app)
