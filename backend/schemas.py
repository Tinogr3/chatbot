"""
Modelos Pydantic estrictos para inputs/outputs de la API y del RAG.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    progress_updated: bool = Field(
        False,
        description=(
            "True si la respuesta evaluada produjo una nueva evidencia y el "
            "progreso de la subcompetencia se actualizó en BD. El frontend "
            "lo usa como señal para refrescar el dashboard de competencias."
        ),
    )


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


# ----- Tareas asíncronas (Celery) -----
class TaskEnqueuedResponse(BaseModel):
    """Response cuando se encola una tarea (upload o process_video)."""

    task_id: str = Field(..., description="ID de la tarea para consultar estado")
    message: str = Field(default="Tarea encolada. Usa GET /status/{task_id} para el progreso.")


class TaskStatusResponse(BaseModel):
    """Response de GET /status/{task_id}."""

    task_id: str = Field(..., description="ID de la tarea")
    status: str = Field(..., description="PENDING | PROGRESS | SUCCESS | FAILURE")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progreso 0.0–1.0")
    message: Optional[str] = Field(None, description="Mensaje de estado o etapa actual")
    result: Optional[Dict[str, Any]] = Field(None, description="Resultado si status=SUCCESS")
    error: Optional[str] = Field(None, description="Error si status=FAILURE")


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


# =====================================================================
# Evaluación por competencias
# =====================================================================


class CompetencyTypeEnum(str, Enum):
    """Tipo de competencia."""

    GENERAL = "general"
    ESPECIFICA = "especifica"


# ----- Competency -----

class CompetencyBase(BaseModel):
    """Campos compartidos para crear/actualizar una competencia."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre de la competencia",
    )
    type: CompetencyTypeEnum = Field(
        ...,
        description="Tipo de competencia: general o específica",
    )
    document_id: Optional[str] = Field(
        None,
        max_length=255,
        description="ID del documento subido asociado a esta competencia",
    )


class CompetencyCreate(CompetencyBase):
    """Schema de creación de competencia (sin id ni timestamps)."""


class CompetencyRead(CompetencyBase):
    """Schema de lectura de competencia (incluye id y timestamps)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único de la competencia")
    created_at: datetime = Field(..., description="Fecha de creación")
    updated_at: datetime = Field(..., description="Fecha de última actualización")


# ----- Subcompetency -----

class SubcompetencyBase(BaseModel):
    """Campos compartidos para crear/actualizar una subcompetencia."""

    competency_id: int = Field(
        ...,
        gt=0,
        description="ID de la competencia padre",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre de la subcompetencia",
    )


class SubcompetencyCreate(SubcompetencyBase):
    """Schema de creación de subcompetencia."""


class SubcompetencyRead(SubcompetencyBase):
    """Schema de lectura de subcompetencia (incluye id y timestamp)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único de la subcompetencia")
    created_at: datetime = Field(..., description="Fecha de creación")


# ----- LearningOutcome -----

class LearningOutcomeBase(BaseModel):
    """Campos compartidos para crear/actualizar un resultado de aprendizaje."""

    subcompetency_id: int = Field(
        ...,
        gt=0,
        description="ID de la subcompetencia asociada",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Descripción del resultado de aprendizaje esperado",
    )
    weight: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Peso ponderado del resultado (0.0–1.0)",
    )


class LearningOutcomeCreate(LearningOutcomeBase):
    """Schema de creación de resultado de aprendizaje."""


class LearningOutcomeRead(LearningOutcomeBase):
    """Schema de lectura de resultado de aprendizaje (incluye id y timestamp)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único del resultado de aprendizaje")
    created_at: datetime = Field(..., description="Fecha de creación")


# ----- LearningEvidence -----

class LearningEvidenceBase(BaseModel):
    """Campos compartidos para crear/actualizar una evidencia de evaluación."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID de sesión del usuario evaluado",
    )
    learning_outcome_id: int = Field(
        ...,
        gt=0,
        description="ID del resultado de aprendizaje evaluado",
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Puntuación obtenida (0.0–1.0)",
    )
    feedback: Optional[str] = Field(
        None,
        description="Retroalimentación textual de la evaluación",
    )


class LearningEvidenceCreate(LearningEvidenceBase):
    """Schema de creación de evidencia de evaluación."""


class LearningEvidenceRead(LearningEvidenceBase):
    """Schema de lectura de evidencia de evaluación (incluye id y timestamp)."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único de la evidencia")
    timestamp: datetime = Field(..., description="Momento en que se registró la evaluación")


# ----- UserCompetencyProgress -----

class UserCompetencyProgressBase(BaseModel):
    """Campos compartidos para el progreso de un usuario en una subcompetencia."""

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="ID de sesión del usuario",
    )
    subcompetency_id: int = Field(
        ...,
        gt=0,
        description="ID de la subcompetencia",
    )
    score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Puntuación acumulada en la subcompetencia (0.0–1.0)",
    )


class UserCompetencyProgressCreate(UserCompetencyProgressBase):
    """Schema de creación/actualización de progreso."""


class UserCompetencyProgressRead(UserCompetencyProgressBase):
    """Schema de lectura de progreso (incluye timestamp)."""

    model_config = ConfigDict(from_attributes=True)

    last_updated: datetime = Field(
        ...,
        description="Fecha de la última actualización del progreso",
    )


# ----- Request / Response de evaluación -----

class EvaluateLearningRequest(BaseModel):
    """Request para evaluar la respuesta de un estudiante a un resultado de aprendizaje."""

    session_id: str = Field(
        ...,
        min_length=1,
        description="ID de sesión del usuario que responde",
    )
    learning_outcome_id: int = Field(
        ...,
        gt=0,
        description="ID del resultado de aprendizaje a evaluar",
    )
    answer: str = Field(
        ...,
        min_length=1,
        description="Respuesta del estudiante a evaluar",
    )


class EvaluateLearningResponse(BaseModel):
    """Response con el resultado de una evaluación de aprendizaje."""

    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Puntuación asignada a la respuesta (0.0–1.0)",
    )
    feedback: str = Field(
        ...,
        description="Retroalimentación descriptiva sobre la respuesta",
    )
    updated_subcompetency_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Puntuación actualizada de la subcompetencia tras la evaluación (0.0–1.0)",
    )


# ----- Extracción automática de competencias (salida LLM) -----


class ExtractedLearningOutcome(BaseModel):
    """Resultado de aprendizaje extraído por el LLM."""

    description: str = Field(
        ...,
        min_length=1,
        description="Descripción del resultado de aprendizaje",
    )


class ExtractedSubcompetency(BaseModel):
    """Subcompetencia extraída por el LLM, con su learning outcome asociado."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre de la subcompetencia",
    )
    learning_outcomes: List[ExtractedLearningOutcome] = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Exactamente un resultado de aprendizaje para esta subcompetencia",
    )


class ExtractedCompetencyTree(BaseModel):
    """Árbol completo de competencias extraído por el LLM desde un documento."""

    competency_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Nombre de la competencia general del documento",
    )
    subcompetencies: List[ExtractedSubcompetency] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Exactamente 2 subcompetencias derivadas de la competencia general",
    )


# ----- Dashboard -----

class DashboardCompetencyItem(BaseModel):
    """Elemento individual del dashboard: competencia con su puntuación."""

    name: str = Field(..., description="Nombre de la competencia")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Puntuación promedio de la competencia (0.0–1.0)",
    )


class DashboardCompetencyResponse(BaseModel):
    """Response con la lista de competencias y sus puntuaciones para el dashboard."""

    competencies: List[DashboardCompetencyItem] = Field(
        default_factory=list,
        description="Lista de competencias con sus puntuaciones agregadas",
    )
