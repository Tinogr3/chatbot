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
    """Obtiene las credenciales de servicio y el project_id."""
    try:
        creds_path = None
        for file in os.listdir("."):
            if file.endswith(".json") and "client" in file.lower():
                creds_path = file
                break
        
        if not creds_path:
            return None, None
        
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return credentials, credentials.project_id
    except Exception as e:
        return None, None
