import os
import sys
import tempfile
import base64
from typing import Any, Dict, List, Optional

backend_dir = os.path.dirname(os.path.abspath(__file__))
# Asegura imports "planos" (ej. `from session_ids import ...`) dentro de Celery,
# independientemente del `cwd` con el que arranque el worker.
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from celery import Celery
from celery.result import AsyncResult

from logger import get_logger

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

logger = get_logger("worker")


async def _log_video_activity(
    *,
    session_id: str,
    match_text: str,
    video_title: str,
) -> None:
    """Registra una actividad 'video' en el cuadrante del Módulo Formador.

    Abre su propia sesión de BD (el worker no tiene request scope) y commitea.
    Si no hay itinerario o ninguna unidad hace match, no hace nada.
    """
    from database import AsyncSessionLocal, init_db
    from models import ActivityType
    from services.progress_service import ProgressService

    await init_db()
    async with AsyncSessionLocal() as db:
        unit_id = await ProgressService.find_unit_for_text(
            db, session_id=session_id, text=match_text
        )
        if unit_id is None:
            return
        await ProgressService.log_activity_and_update_progress(
            db,
            session_id=session_id,
            unit_id=unit_id,
            activity_type=ActivityType.VIDEO,
            detail=f"Video procesado: {video_title}"[:500],
        )
        await db.commit()


@app.task(bind=True, name="worker.process_video_task")
def process_video_task(
    self,
    url: str,
    session_id: str,
) -> Dict[str, Any]:
    from session_ids import normalize_session_id

    session_id = normalize_session_id(session_id)

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.05, "message": "Iniciando procesamiento del video..."})
        from api.chat import invalidate_agent_cache
        from exceptions import VideoTranscriptionError
        from media_processor import extract_video_id, get_video_title, process_video as do_process_video
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

        # Obtener el título del video (sin descarga completa).
        self.update_state(state="PROGRESS", meta={"progress": 0.75, "message": "Obteniendo título del video..."})
        video_title = get_video_title(video_id) or url

        # Registrar el video en el document_registry para que el agente RAG
        # pueda crear una herramienta de búsqueda dedicada a este video.
        try:
            from document_registry import load_document_registry, save_document_registry

            registry = load_document_registry(session_id)
            registry[url] = {
                "usage_guide": f"Usa esta herramienta para buscar información en el video de YouTube '{video_title}'. URL: {url}",
                "type": "video",
                "video_id": video_id,
                "title": video_title,
            }
            save_document_registry(session_id, registry)
        except Exception as e:
            logger.warning("Error guardando video en document_registry: %s", e)

        # Extraer y persistir competencias a partir de la transcripción del video.
        # Módulo Formador (best-effort): ver/procesar un video cuenta como
        # realización (+0.5) en la celda más afín del itinerario.
        try:
            import asyncio as _asyncio_act

            _asyncio_act.run(
                _log_video_activity(
                    session_id=session_id,
                    match_text=f"{video_title} " + " ".join(
                        d.page_content for d in documents[:3]
                    ),
                    video_title=video_title,
                )
            )
        except Exception as e:
            logger.warning("No se pudo registrar actividad de video en el cuadrante: %s", e)

        self.update_state(state="PROGRESS", meta={"progress": 0.9, "message": "Extrayendo competencias del video..."})
        try:
            from rag_engine import extract_document_competencies, save_extracted_competencies
            import asyncio as _asyncio

            full_text = "\n".join(doc.page_content for doc in documents)[:60000]
            if full_text.strip():
                tree = extract_document_competencies(full_text)
                if tree:
                    # Usamos video_id (no la URL) como document_id canónico en BD.
                    # La URL puede tener variantes (youtu.be vs youtube.com/watch?v=…)
                    # mientras que el video_id de 11 chars es siempre único y estable.
                    _asyncio.run(save_extracted_competencies(tree, video_id))
                else:
                    logger.warning("No se pudieron extraer competencias (LLM) para el video '%s'", url)
        except Exception as e:
            logger.warning("Error en extracción de competencias para video '%s': %s", url, e)

        return {
            "success": True,
            "document_count": len(documents),
            "video_id": video_id,
            "title": video_title,
            "message": f"Video '{video_title}' procesado correctamente.",
        }
    except VideoTranscriptionError as e:
        return {"success": False, "error": e.message, "document_count": 0}
    except Exception as e:
        return {"success": False, "error": str(e), "document_count": 0}


@app.task(bind=True, name="worker.process_pdf_task")
def process_pdf_task(
    self,
    filename: str,
    session_id: str,
    gcs_path: Optional[str] = None,
    file_b64: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tarea asíncrona: procesa PDF (particionado, imágenes) y añade documentos al vector store.
    """
    from session_ids import normalize_session_id

    session_id = normalize_session_id(session_id)

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.05, "message": "Preparando documento..."})
        from api.chat import invalidate_agent_cache
        from document_registry import load_document_registry, save_document_registry
        from exceptions import DocumentProcessingError
        from gcs_utils import GCSDownloadError, download_from_gcs
        from rag_engine import initialize_vector_store, procesar_pdf as do_procesar_pdf
    except Exception as e:
        return {"success": False, "error": str(e), "filename": filename, "document_count": 0}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp_path = tmp.name
        if file_b64:
            try:
                pdf_bytes = base64.b64decode(file_b64)
            except Exception as e:
                raise RuntimeError(f"Archivo PDF inválido en payload: {str(e)}") from e
            with open(tmp_path, "wb") as f:
                f.write(pdf_bytes)
        elif gcs_path:
            # Compatibilidad: si llega gcs_path, usamos flujo bucket.
            ok = download_from_gcs(gcs_path, tmp_path)
            if not ok:
                raise GCSDownloadError(f"No se pudo descargar el PDF desde GCS: {gcs_path}")
        else:
            raise RuntimeError("No se recibió archivo para procesar (file_b64 o gcs_path).")

        self.update_state(state="PROGRESS", meta={"progress": 0.2, "message": "Procesando PDF y extrayendo texto..."})
        registry = load_document_registry(session_id)
        documents, registry = do_procesar_pdf(
            tmp_path,
            extract_images=True,
            max_tokens=65535,
            session_id=session_id,
            document_registry=registry,
            logical_filename=filename,
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

        try:
            from rag_engine import persist_competencies_from_chunk_documents

            persist_competencies_from_chunk_documents(documents)
        except Exception as e:
            logger.warning("Error en extracción de competencias para '%s': %s", filename, e)

        return {
            "success": True,
            "gcs_path": gcs_path,
            "filename": filename,
            "document_count": len(documents),
            "message": f"Archivo '{filename}' procesado correctamente.",
        }
    except GCSDownloadError as e:
        return {"success": False, "error": str(e), "filename": filename, "document_count": 0}
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


@app.task(bind=True, name="worker.process_cloud_pdfs_task")
def process_cloud_pdfs_task(
    self,
    session_id: str,
) -> Dict[str, Any]:
    """
    Tarea asíncrona: descarga y procesa todos los PDFs del bucket GCS para una sesión.
    Replica la lógica del endpoint POST /upload/load_cloud, pero en background.
    """
    from session_ids import normalize_session_id

    session_id = normalize_session_id(session_id)

    self.update_state(state="PROGRESS", meta={"progress": 0.0, "message": "Preparando procesamiento PDFs desde la nube..."})

    # Imports locales para evitar ciclos y mantener carga inicial baja.
    from api.chat import invalidate_agent_cache
    from document_registry import load_document_registry, save_document_registry
    from gcs_utils import procesar_todos_pdfs_nube
    from rag_engine import initialize_vector_store

    def progress_callback(progress: float, message: str) -> None:
        # Celery backend lee `PROGRESS` y usa `meta.progress`/`meta.message`.
        # Mapeamos 0..1 a 0..0.75 para dejar espacio a las fases finales
        # (persistencia de registry / vector store / invalidación de caché).
        mapped_progress = max(0.0, min(0.75, progress * 0.75))
        self.update_state(state="PROGRESS", meta={"progress": mapped_progress, "message": message})

    documents, filenames, pdf_registry, error_message = procesar_todos_pdfs_nube(
        session_id=session_id,
        progress_callback=progress_callback,
    )
    if not documents:
        raise RuntimeError(
            error_message
            or "No se encontraron PDFs en el bucket o hubo errores al procesarlos."
        )

    # En la lógica original el endpoint también guarda el registro y actualiza el vector store.
    self.update_state(state="PROGRESS", meta={"progress": 0.8, "message": "Actualizando vector store..."})

    # Preservar entradas existentes (videos, otros PDFs) y fusionar con las nuevas.
    existing_registry = load_document_registry(session_id)
    merged_registry = {**existing_registry, **pdf_registry}
    save_document_registry(session_id, merged_registry)
    existing_vs = initialize_vector_store(documents=None, session_id=session_id)
    vector_store = initialize_vector_store(
        documents=documents,
        existing_vector_store=existing_vs,
        session_id=session_id,
    )
    if not vector_store:
        raise RuntimeError("Error al crear/actualizar vector store")

    invalidate_agent_cache(session_id)
    self.update_state(state="PROGRESS", meta={"progress": 0.95, "message": "Extrayendo competencias..."})

    try:
        from rag_engine import persist_competencies_from_chunk_documents

        persist_competencies_from_chunk_documents(documents)
    except Exception as e:
        logger.warning("Error extrayendo competencias tras carga en nube: %s", e)

    self.update_state(state="PROGRESS", meta={"progress": 0.98, "message": "Finalizado."})

    return {
        "success": True,
        "filenames": filenames,
        "document_count": len(documents),
        "message": f"{len(filenames)} archivos cargados desde la nube.",
    }


def get_task_result(task_id: str) -> Optional[AsyncResult]:
    """Devuelve el AsyncResult para un task_id (para consultar estado desde la API)."""
    if not task_id:
        return None
    return AsyncResult(task_id, app=app)
