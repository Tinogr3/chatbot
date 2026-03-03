"""
Módulo de configuración y autenticación (backend).
Maneja variables de entorno y credenciales de Google Cloud.
"""
import os
from dotenv import load_dotenv
from google.oauth2 import service_account

load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME", "chatbot-rag-documents")


def get_credentials_and_project():
    """Obtiene las credenciales de servicio y el project_id desde GOOGLE_APPLICATION_CREDENTIALS."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        return None, None
    creds_path = creds_path.strip()
    if not os.path.isfile(creds_path):
        return None, None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials, credentials.project_id
    except Exception:
        return None, None
