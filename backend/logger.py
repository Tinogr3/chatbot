"""
Logger centralizado del backend.
Reemplaza print() y asegura un formato consistente en toda la aplicación.
"""
import logging
import sys
from typing import Optional, TextIO

# Nombre del logger raíz del backend
BACKEND_LOGGER_NAME = "chatbot_backend"


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Obtiene un logger configurado. Si se pasa name, el logger será hijo del raíz (ej: chatbot_backend.rag_engine).
    """
    logger_name = f"{BACKEND_LOGGER_NAME}.{name}" if name else BACKEND_LOGGER_NAME
    return logging.getLogger(logger_name)


def setup_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    stream: Optional[TextIO] = None,
) -> None:
    """
    Configura el logging global del backend. Llamar al arranque de la aplicación (opcional).
    """
    if format_string is None:
        format_string = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    if stream is None:
        stream = sys.stderr

    root = logging.getLogger(BACKEND_LOGGER_NAME)
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(stream)
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(format_string))
        root.addHandler(handler)


# Logger raíz para importar en módulos: from logger import get_logger; logger = get_logger(__name__)
