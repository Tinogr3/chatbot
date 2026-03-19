"""
Utilidades para Google Cloud Storage (backend) - Sin Streamlit.
"""
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
    """
    Valida la configuración necesaria para usar GCS.

    Si falta algo, lanza `HTTPException(status_code=500)` para evitar fallos silenciosos
    y comunicar el problema claramente desde la API.

    Formato exacto recomendado en `.env` (en la raíz del proyecto):

      GOOGLE_APPLICATION_CREDENTIALS=/ruta/absoluta/a/tu-service-account.json
      BUCKET_NAME=tu-nombre-del-bucket

    Requisitos:
    - `GOOGLE_APPLICATION_CREDENTIALS` debe apuntar a un JSON de Service Account válido
      (la ruta debe existir en la máquina donde corre el backend/worker).
    - `BUCKET_NAME` no puede estar vacío.
    """

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
        # Si el JSON es inválido o la configuración existe pero GCS no se inicializa,
        # lo devolvemos como error 500 explícito (no silencioso).
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
    """
    Descarga y procesa todos los PDFs del bucket.
    Returns: (documents, filenames, document_registry, error_message)
    error_message es None si todo fue bien; si no, texto para mostrar al usuario.
    """
    try:
        document_registry = document_registry or {}
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        pdf_files = [b.name for b in blobs if b.name.lower().endswith(".pdf")]
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
                )
                os.unlink(tmp_path)
                if docs:
                    all_documents.extend(docs)
                    processed_filenames.append(pdf_name)
                    processed_count += 1

                if progress_callback:
                    # Progreso basado en archivos iterados (aunque un PDF falle, seguimos avanzando).
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


def upload_to_gcs(
    file_content: bytes,
    filename: str,
    bucket_name: str = BUCKET_NAME,
) -> Optional[str]:
    try:
        client = get_gcs_client()
    except HTTPException:
        # En el flujo de subida manual, permitir seguir procesando aunque falle
        # el upload a GCS (el `gcs_path` quedará en None).
        return None
    try:
        bucket = client.bucket(bucket_name)
        try:
            bucket.create()
        except Exception:
            pass
        blob = bucket.blob(filename)
        blob.upload_from_string(file_content, content_type="application/pdf")
        return f"gs://{bucket_name}/{filename}"
    except Exception as e:
        logger.warning("Error uploading to GCS: %s", e)
        return None
