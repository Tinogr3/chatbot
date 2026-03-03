"""
Utilidades para Google Cloud Storage (backend) - Sin Streamlit.
"""
import os
import tempfile
import logging
from typing import List, Optional, Tuple

from google.cloud import storage
from config import BUCKET_NAME
from rag_engine import procesar_pdf

logger = logging.getLogger(__name__)


def get_gcs_client():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        return None
    creds_path = creds_path.strip()
    if not os.path.isfile(creds_path):
        return None
    try:
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return storage.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        logger.warning("GCS client error: %s", e)
        return None


def procesar_todos_pdfs_nube(
    bucket_name: str = BUCKET_NAME,
    session_id: Optional[str] = None,
    document_registry: Optional[dict] = None,
    max_tokens: int = 65535,
) -> Tuple[List, List[str], dict, Optional[str]]:
    """
    Descarga y procesa todos los PDFs del bucket.
    Returns: (documents, filenames, document_registry, error_message)
    error_message es None si todo fue bien; si no, texto para mostrar al usuario.
    """
    document_registry = document_registry or {}
    client = get_gcs_client()
    if not client:
        return [], [], document_registry, (
            "GCS no configurado. Configure GOOGLE_APPLICATION_CREDENTIALS (ruta al JSON de cuenta de servicio) "
            "y BUCKET_NAME en el archivo .env de la raíz del proyecto."
        )
    try:
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        pdf_files = [b.name for b in blobs if b.name.lower().endswith(".pdf")]
        if not pdf_files:
            return [], [], document_registry, (
                f"No hay archivos PDF en el bucket '{bucket_name}'. Sube al menos un PDF al bucket."
            )
        all_documents = []
        processed_filenames = []
        for pdf_name in pdf_files:
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
            except Exception as e:
                logger.warning("Error processing %s: %s", pdf_name, e)
        return all_documents, processed_filenames, document_registry, None
    except Exception as e:
        logger.exception("Error listing/downloading bucket %s: %s", bucket_name, e)
        return [], [], document_registry, f"Error al acceder al bucket '{bucket_name}': {str(e)}"


def upload_to_gcs(
    file_content: bytes,
    filename: str,
    bucket_name: str = BUCKET_NAME,
) -> Optional[str]:
    client = get_gcs_client()
    if not client:
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
