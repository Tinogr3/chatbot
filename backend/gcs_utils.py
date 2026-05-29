import os
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException
from google.cloud import storage

from config import BUCKET_NAME
from logger import get_logger
from rag_engine import procesar_pdf

logger = get_logger("gcs_utils")


def validate_gcs_configuration() -> None:
    bucket = (BUCKET_NAME or "").strip()
    if not bucket:
        raise HTTPException(
            status_code=500,
            detail="Configuración GCS inválida: BUCKET_NAME no está definido o está vacío.",
        )

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        raise HTTPException(
            status_code=500,
            detail="Configuración GCS inválida: GOOGLE_APPLICATION_CREDENTIALS no está definido (ruta al JSON).",
        )

    creds_path = creds_path.strip()
    if not os.path.isfile(creds_path):
        raise HTTPException(
            status_code=500,
            detail=f"Configuración GCS inválida: GOOGLE_APPLICATION_CREDENTIALS apunta a un archivo inexistente: {creds_path}",
        )


def get_gcs_client() -> Optional[storage.Client]:
    try:
        from google.oauth2 import service_account

        validate_gcs_configuration()
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return storage.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        logger.warning("GCS client error: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error al inicializar cliente GCS con las credenciales proporcionadas: {str(e)}",
        )


def procesar_todos_pdfs_nube(
    bucket_name: str = BUCKET_NAME,
    session_id: Optional[str] = None,
    document_registry: Optional[Dict[str, Any]] = None,
    max_tokens: int = 65535,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Tuple[List[Any], List[str], Dict[str, Any], Optional[str]]:
    try:
        document_registry = document_registry or {}
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        pdf_files: List[str] = []
        for blob in bucket.list_blobs():
            name = getattr(blob, "name", "")
            if name.lower().endswith(".pdf"):
                pdf_files.append(name)
        if not pdf_files:
            return [], [], document_registry, (
                f"No hay archivos PDF en el bucket '{bucket_name}'. Sube al menos un PDF al bucket."
            )

        total_pdfs = len(pdf_files)
        all_documents = []
        processed_filenames = []

        processed_count = 0
        for idx, pdf_name in enumerate(pdf_files, start=1):
            try:
                blob = bucket.blob(pdf_name)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    blob.download_to_file(tmp)
                    tmp_path = tmp.name
                docs, document_registry = procesar_pdf(
                    tmp_path,
                    extract_images=True,
                    max_tokens=max_tokens,
                    session_id=session_id,
                    document_registry=document_registry,
                    logical_filename=pdf_name,
                )
                os.unlink(tmp_path)
                if docs:
                    all_documents.extend(docs)
                    processed_filenames.append(pdf_name)
                    processed_count += 1

                if progress_callback:
                    progress = min(1.0, max(0.0, idx / total_pdfs))
                    progress_callback(progress, f"Procesando {idx}/{total_pdfs}: {pdf_name}")
            except Exception as e:
                logger.warning("Error processing %s: %s", pdf_name, e)
                if progress_callback:
                    progress = min(1.0, max(0.0, idx / total_pdfs))
                    progress_callback(progress, f"Error en {idx}/{total_pdfs}: {pdf_name}")

        if progress_callback:
            progress_callback(1.0, f"Procesamiento completado ({processed_count}/{total_pdfs} con contenido).")

        return all_documents, processed_filenames, document_registry, None
    except HTTPException:
        # Errores de configuración: deben propagarse (API/worker).
        raise
    except Exception as e:
        logger.exception("Error listing/downloading bucket %s: %s", bucket_name, e)
        return [], [], document_registry, f"Error al acceder al bucket '{bucket_name}': {str(e)}"


class GCSDownloadError(Exception):
    """Error específico cuando falla la descarga de un objeto desde GCS."""


def download_from_gcs(gcs_path: str, local_path: str) -> bool:
    """
    Descarga un objeto en GCS a `local_path`.

    `gcs_path` debe tener formato: `gs://{bucket_name}/{blob_name}`.

    Returns:
        True si la descarga fue exitosa, False si falla.
    """
    try:
        if not isinstance(gcs_path, str) or not gcs_path.strip():
            logger.warning("download_from_gcs: gcs_path inválido (vacío)")
            return False
        if not gcs_path.startswith("gs://"):
            logger.warning("download_from_gcs: gcs_path inválido (debe iniciar con 'gs://'): %s", gcs_path)
            return False
        if not isinstance(local_path, str) or not local_path.strip():
            logger.warning("download_from_gcs: local_path inválido (vacío)")
            return False

        gcs_no_scheme = gcs_path[len("gs://"):]
        bucket_name, _, blob_name = gcs_no_scheme.partition("/")
        if not bucket_name or not blob_name:
            logger.warning("download_from_gcs: gcs_path inválido (falta bucket o blob): %s", gcs_path)
            return False

        logger.info("Descargando desde GCS: %s -> %s", gcs_path, local_path)
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)
        return True
    except Exception as e:
        logger.warning("Error descargando desde GCS (%s): %s", gcs_path, str(e))
        return False
