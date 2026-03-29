"""
Módulo de configuración y autenticación (backend).
Maneja variables de entorno y credenciales de Google Cloud.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

from dotenv import load_dotenv
from google.oauth2 import service_account
from google.auth.credentials import Credentials

load_dotenv()

BUCKET_NAME: str = os.getenv("BUCKET_NAME", "chatbot-rag-documents")

_DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000,http://localhost:8501"


@dataclass(frozen=True)
class HttpSettings:
    """Parámetros HTTP de la app (p. ej. CORS). No incluye secretos."""

    allowed_origins: tuple[str, ...]


@lru_cache
def get_http_settings() -> HttpSettings:
    """
    Orígenes permitidos para CORS (ALLOWED_ORIGINS, lista separada por comas).
    Con allow_credentials=True en FastAPI no se puede usar '*'; debe ser una lista explícita.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS).strip()
    origins = tuple(o.strip() for o in raw.split(",") if o.strip())
    if not origins:
        origins = tuple(
            o.strip() for o in _DEFAULT_ALLOWED_ORIGINS.split(",") if o.strip()
        )
    return HttpSettings(allowed_origins=origins)


def get_credentials_and_project() -> Tuple[Optional[Credentials], Optional[str]]:
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
