"""
Módulo de configuración y autenticación.
Maneja variables de entorno y credenciales de Google Cloud.
"""
import os
from dotenv import load_dotenv
from google.oauth2 import service_account

# Cargar variables de entorno
load_dotenv()

# Nombre por defecto del bucket de documentos
BUCKET_NAME = "chatbot-rag-documents"


def get_credentials_and_project():
    """Obtiene las credenciales de servicio y el project_id desde GOOGLE_APPLICATION_CREDENTIALS."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        print(
            "[Config] Error: La variable de entorno GOOGLE_APPLICATION_CREDENTIALS no está definida. "
            "Defínela con la ruta absoluta al archivo JSON de credenciales de servicio (ej: export GOOGLE_APPLICATION_CREDENTIALS=/ruta/a/credenciales.json)."
        )
        return None, None
    creds_path = creds_path.strip()
    if not os.path.isfile(creds_path):
        print(f"[Config] Error: El archivo de credenciales no existe: {creds_path}")
        return None, None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials, credentials.project_id
    except Exception as e:
        print(f"[Config] Error cargando credenciales desde {creds_path}: {e}")
        return None, None
