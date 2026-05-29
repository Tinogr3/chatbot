"""
Jerarquía de excepciones de dominio del backend.
"""
from __future__ import annotations


class ChatbotBackendError(Exception):
    """Base para todos los errores de dominio del backend."""

    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        self.message = message
        super().__init__(message, *args, **kwargs)


class DocumentProcessingError(ChatbotBackendError):
    """El documento (PDF, extracción de texto o imágenes) no pudo procesarse."""


class VideoTranscriptionError(ChatbotBackendError):
    """El vídeo no pudo descargarse o transcribirse."""
