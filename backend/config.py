"""
Configuración central del backend: variables de entorno y credenciales de Google Cloud.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Tuple

from dotenv import load_dotenv
from google.auth.credentials import Credentials
from google.oauth2 import service_account

load_dotenv()

BUCKET_NAME: str = os.getenv("BUCKET_NAME", "chatbot-rag-documents")

_DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000"


@dataclass(frozen=True)
class AppSettings:
    environment: str
    cookie_secure: bool


@lru_cache
def get_app_settings() -> AppSettings:
    environment = os.getenv("ENVIRONMENT", "development").lower()
    raw_secure = os.getenv("COOKIE_SECURE", "").strip().lower()
    if raw_secure in ("1", "true", "yes"):
        cookie_secure = True
    elif raw_secure in ("0", "false", "no"):
        cookie_secure = False
    else:
        cookie_secure = environment == "production"
    return AppSettings(environment=environment, cookie_secure=cookie_secure)


@dataclass(frozen=True)
class HttpSettings:
    """Parámetros HTTP de la app (CORS). No incluye secretos."""

    allowed_origins: tuple[str, ...]


@lru_cache
def get_http_settings() -> HttpSettings:
    """
    Orígenes permitidos para CORS, leídos de ALLOWED_ORIGINS (lista separada por comas).
    Con allow_credentials=True no se puede usar '*'; debe ser una lista explícita.
    """
    raw = os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS).strip()
    origins = tuple(o.strip() for o in raw.split(",") if o.strip())
    if not origins:
        origins = tuple(o.strip() for o in _DEFAULT_ALLOWED_ORIGINS.split(",") if o.strip())
    return HttpSettings(allowed_origins=origins)


def get_credentials_and_project() -> Tuple[Optional[Credentials], Optional[str]]:
    """Devuelve (credentials, project_id) desde GOOGLE_APPLICATION_CREDENTIALS, o (None, None)."""
    creds_path = (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
    if not creds_path or not os.path.isfile(creds_path):
        return None, None
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return credentials, credentials.project_id
    except Exception:
        return None, None
