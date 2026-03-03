"""
Módulo de utilidades para Google Cloud Storage.
Maneja la autenticación, subida y descarga de archivos desde GCS.
"""
import os
import tempfile
from typing import List, Optional, Tuple

import streamlit as st
from google.cloud import storage
from google.oauth2 import service_account

from config import BUCKET_NAME, get_credentials_and_project
from rag_engine import procesar_pdf


def get_gcs_client():
    """Obtiene el cliente de Google Cloud Storage usando credenciales desde GOOGLE_APPLICATION_CREDENTIALS."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        st.warning(
            "⚠️ **Variable GOOGLE_APPLICATION_CREDENTIALS no definida**\\n\\n"
            "Para usar Google Cloud Storage debes definir la variable de entorno estándar "
            "**GOOGLE_APPLICATION_CREDENTIALS** con la ruta absoluta al archivo JSON de credenciales de servicio.\\n\\n"
            "Ejemplo en .env: `GOOGLE_APPLICATION_CREDENTIALS=/ruta/absoluta/a/tu-credenciales.json`\\n\\n"
            "Sin esta variable, el chatbot funcionará en modo local sin acceso a GCS."
        )
        return None
    creds_path = creds_path.strip()
    if not os.path.isfile(creds_path):
        st.warning(
            f"⚠️ **Archivo de credenciales no encontrado**\\n\\n"
            f"GOOGLE_APPLICATION_CREDENTIALS apunta a: `{creds_path}`\\n\\n"
            "Comprueba que la ruta sea correcta y que el archivo exista."
        )
        return None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return storage.Client(credentials=credentials, project=credentials.project_id)
    except Exception as e:
        st.warning(
            f"⚠️ **Error de autenticación con Google Cloud**\\n\\n"
            f"Detalles: {str(e)}\\n\\n"
            "Verifica que el archivo de credenciales sea válido y tenga los permisos necesarios."
        )
        return None


def procesar_todos_pdfs_nube(bucket_name: str = BUCKET_NAME) -> Tuple[List, List[str]]:
    """Descarga y procesa todos los PDFs del bucket de GCS.
    
    Returns:
        Tuple con (lista de documentos procesados, lista de nombres de archivos)
    """
    client = get_gcs_client()
    if not client:
        return [], []
    
    try:
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs())
        pdf_files = [blob.name for blob in blobs if blob.name.lower().endswith(".pdf")]
        
        if not pdf_files:
            return [], []
        
        all_documents = []
        processed_filenames = []
        
        with st.spinner(f"Descargando y procesando {len(pdf_files)} archivos del bucket..."):
            for pdf_name in pdf_files:
                try:
                    blob = bucket.blob(pdf_name)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        blob.download_to_file(tmp_file)
                        tmp_path = tmp_file.name
                    
                    documents = procesar_pdf(tmp_path)
                    os.unlink(tmp_path)
                    
                    if documents:
                        all_documents.extend(documents)
                        processed_filenames.append(pdf_name)
                except Exception as e:
                    st.warning(f"Error al procesar {pdf_name}: {str(e)}")
                    continue
        
        return all_documents, processed_filenames
    except Exception as e:
        st.error(f"Error al listar o descargar archivos del bucket: {str(e)}")
        return [], []


def upload_to_gcs(file_content: bytes, filename: str, bucket_name: str = BUCKET_NAME) -> Optional[str]:
    """Sube un archivo a Google Cloud Storage."""
    client = get_gcs_client()
    if not client:
        return None
    
    try:
        # Crear bucket si no existe
        try:
            bucket = client.bucket(bucket_name)
            bucket.create()
        except Exception:
            bucket = client.bucket(bucket_name)
        
        # Subir archivo
        blob = bucket.blob(filename)
        blob.upload_from_string(file_content, content_type="application/pdf")
        
        return f"gs://{bucket_name}/{filename}"
    except Exception as e:
        st.error(f"Error al subir archivo a GCS: {str(e)}")
        return None
