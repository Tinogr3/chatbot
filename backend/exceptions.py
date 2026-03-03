"""
Excepciones personalizadas del backend para un manejo de errores consistente.
"""


class ChatbotBackendError(Exception):
    """Base para todas las excepciones del backend del chatbot."""

    def __init__(self, message: str, *args: object, **kwargs: object) -> None:
        self.message = message
        super().__init__(message, *args, **kwargs)


class DocumentProcessingError(ChatbotBackendError):
    """Error al procesar un documento (PDF, extracción de texto/imágenes, etc.)."""

    pass


class LLMAPIError(ChatbotBackendError):
    """Error al invocar la API del LLM (Gemini/Vertex, timeouts, cuotas, etc.)."""

    pass


class VideoTranscriptionError(ChatbotBackendError):
    """Error al transcribir o procesar un video (YouTube, Whisper, etc.)."""

    pass


class VectorStoreError(ChatbotBackendError):
    """Error al inicializar o actualizar el vector store (Chroma, embeddings)."""

    pass


class ConfigurationError(ChatbotBackendError):
    """Error de configuración (credenciales, variables de entorno)."""

    pass


class SessionError(ChatbotBackendError):
    """Error relacionado con sesión (session_id inválido, recurso no encontrado)."""

    pass
