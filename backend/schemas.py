"""
Modelos Pydantic estrictos para inputs/outputs de la API y del RAG.
"""
from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ----- Chat -----
class ChatRequest(BaseModel):
    """Request estricto para POST /chat."""

    message: str = Field(..., min_length=1, description="Mensaje del usuario")
    session_id: Optional[str] = Field(None, description="ID de sesión (alternativa al header)")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperatura del modelo")
    max_tokens: int = Field(65535, ge=1, le=65535, description="Máximo de tokens de respuesta")
    learning_mode: bool = Field(False, description="Si está en modo aprendizaje")
    learning_topic: Optional[str] = Field(None, description="Tema actual en modo aprendizaje")
    last_learning_content: Optional[str] = Field(None, description="Último contenido del tutor en modo aprendizaje")


class ChatResponse(BaseModel):
    """Response estricto de POST /chat."""

    answer: str = Field(..., description="Respuesta del asistente")
    sources: List[str] = Field(default_factory=list, description="Fuentes utilizadas")
    learning_mode: bool = Field(False, description="Si el modo aprendizaje sigue activo")
    learning_topic: Optional[str] = Field(None, description="Tema en modo aprendizaje")


# ----- Upload -----
class UploadResponse(BaseModel):
    """Response de POST /upload."""

    success: bool = Field(..., description="Si el procesamiento fue exitoso")
    gcs_path: Optional[str] = Field(None, description="Ruta en GCS si se subió")
    filename: str = Field(..., description="Nombre del archivo")
    document_count: int = Field(..., ge=0, description="Número de chunks/documentos generados")
    message: str = Field(..., description="Mensaje para el usuario")


class LoadCloudResponse(BaseModel):
    """Response de POST /upload/load_cloud."""

    success: bool = Field(..., description="Si la carga desde nube fue exitosa")
    filenames: List[str] = Field(default_factory=list, description="Nombres de archivos procesados")
    document_count: int = Field(..., ge=0, description="Total de chunks generados")
    message: str = Field(..., description="Mensaje para el usuario")


# ----- Video -----
class ProcessVideoRequest(BaseModel):
    """Request para POST /process_video."""

    url: str = Field(..., min_length=1, description="URL del video de YouTube")
    session_id: Optional[str] = Field(None, description="ID de sesión (alternativa al header)")


class ProcessVideoResponse(BaseModel):
    """Response de POST /process_video."""

    success: bool = Field(..., description="Si el video se procesó correctamente")
    document_count: int = Field(..., ge=0, description="Chunks generados de la transcripción")
    video_id: Optional[str] = Field(None, description="ID del video de YouTube")
    message: str = Field(..., description="Mensaje para el usuario")


# ----- History -----
class ChatMessageSource(BaseModel):
    """Fuente citada en un mensaje (opcional, para tipado)."""

    pass  # Por ahora solo strings en sources; se puede extender


class ChatMessageSchema(BaseModel):
    """Un mensaje del historial de chat."""

    role: str = Field(..., description="user | assistant")
    content: str = Field(..., description="Contenido del mensaje")
    sources: Optional[List[str]] = Field(None, description="Fuentes citadas (solo assistant)")


class HistoryResponse(BaseModel):
    """Response de GET /history."""

    messages: List[ChatMessageSchema] = Field(
        default_factory=list,
        description="Historial de mensajes (role, content, sources opcional)",
    )


# ----- User facts -----
class UserFactItem(BaseModel):
    """Un hecho almacenado sobre el usuario."""

    tipo: str = Field(..., description="Categoría del hecho (nombre, trabajo, etc.)")
    valor: str = Field(..., description="Valor del hecho")
    confianza: float = Field(1.0, ge=0.0, le=1.0, description="Confianza 0-1")


class UserFactsResponse(BaseModel):
    """Response de GET /user_facts."""

    facts: List[UserFactItem] = Field(default_factory=list, description="Lista de hechos")


# ----- Session -----
class ClearSessionResponse(BaseModel):
    """Response de POST /session/clear."""

    message: str = Field(..., description="Mensaje de confirmación")


class DeletedCountResponse(BaseModel):
    """Response genérico para DELETE que devuelve cantidad eliminada."""

    deleted: int = Field(..., ge=0, description="Número de elementos eliminados")


# ----- RAG / Documentos -----
class DocumentCardSchema(BaseModel):
    """Ficha de documento generada por el LLM (resumen, temas, uso, preguntas HyDE)."""

    summary: str = Field(..., description="Resumen ejecutivo del documento en exactamente 2 líneas.")
    topics: List[str] = Field(..., description="Lista de 5 palabras clave del documento.")
    usage_guide: str = Field(..., description="Frase que indica para qué usar este documento.")
    hypothetical_questions: List[str] = Field(
        ..., description="Tres preguntas que este documento responde perfectamente (HyDE)."
    )


class DocumentRegistryEntry(BaseModel):
    """Entrada del registro de documentos por sesión (serializable)."""

    summary: str = Field("", description="Resumen del documento")
    topics: List[str] = Field(default_factory=list, description="Palabras clave")
    usage_guide: str = Field("", description="Guía de uso")
    hypothetical_questions: List[str] = Field(default_factory=list, description="Preguntas HyDE")


class RAGSummaryOutput(BaseModel):
    """Salida tipada de get_summary_response (router) y flujos de resumen."""

    answer: str = Field(..., description="Resumen generado")
    source_documents: List[Any] = Field(default_factory=list, description="Documentos fuente (LangChain Document)")


class LearningSessionOutput(BaseModel):
    """Salida tipada de start_learning_session / evaluate_answer."""

    content: str = Field(..., description="Contenido de la respuesta del tutor")
    is_learning_mode: bool = Field(True, description="Si sigue en modo aprendizaje")
    awaiting_answer: bool = Field(False, description="Si espera respuesta del estudiante")
    topic: Optional[str] = Field(None, description="Tema de la sesión")
    question: Optional[str] = Field(None, description="Pregunta planteada (opcional)")
    is_correct: bool = Field(False, description="Si la respuesta evaluada es correcta")
    is_partial: bool = Field(False, description="Si la respuesta es parcialmente correcta")
    source_documents: List[Any] = Field(default_factory=list, description="Documentos fuente")
