"""
Modelos Pydantic estrictos para inputs/outputs de la API y del RAG.
"""
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    learning_unit_id: Optional[int] = Field(
        None,
        gt=0,
        description="Celda del cuadrante asociada (cuestionario/evaluación de unidad)",
    )


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


# ----- Discovery Hub -----
class DiscoveryItemOut(BaseModel):
    """Un resumen o examen guardado desde el chat."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., ge=1)
    user_prompt: str = Field(..., description="Petición original del usuario")
    content: str = Field(..., description="Texto generado por el asistente")
    created_at: datetime = Field(..., description="Fecha de creación (UTC)")


class DiscoveryStatsOut(BaseModel):
    """Conteos para las tarjetas del Discovery Hub."""

    summaries: int = Field(0, ge=0)
    exams: int = Field(0, ge=0)


class PodcastAudioRequest(BaseModel):
    """Body opcional para POST /discovery/podcast-audio."""

    summary_ids: Optional[List[int]] = Field(
        None,
        description=(
            "IDs de resúmenes a incluir (en ese orden en la narración). "
            "Si se omite o es null, se usan todos los resúmenes de la sesión."
        ),
    )


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
    """Resultado de aprendizaje observable y evaluable (salida LLM)."""

    description: str = Field(
        ...,
        min_length=10,
        max_length=520,
        description=(
            "Redacta un único resultado observable: verbo de acción + objeto + "
            "criterio o producto verificable (qué debe poder hacer o producir el "
            "estudiante). Sin vaguedades tipo 'comprender' o 'conocer' sin objeto."
        ),
    )

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class ExtractedSubcompetency(BaseModel):
    """Subcompetencia concreta del documento, distinta de las demás etiquetas."""

    name: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description=(
            "Nombre corto y específico al contenido del documento (procedimiento, norma, "
            "herramienta, concepto clave o caso). Debe diferenciarse claramente de la "
            "competencia principal y de las demás subcompetencias. Evita títulos genéricos."
        ),
    )
    learning_outcomes: List[ExtractedLearningOutcome] = Field(
        ...,
        min_length=1,
        max_length=2,
        description=(
            "Entre 1 y 2 resultados de aprendizaje evaluables para esta subcompetencia: "
            "uno de tipo conceptual/analítico y otro de tipo práctico/aplicado."
        ),
    )

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class ExtractedCompetencyTree(BaseModel):
    """Árbol de competencias extraído del documento: anclado al texto, sin duplicar etiquetas."""

    competency_name: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description=(
            "Competencia principal alineada al propósito del documento (no genérica). "
            "Debe nombrar el ámbito concreto (p. ej. normativa X, proceso Y, análisis Z). "
            "Las subcompetencias deben ser facetas distintas de esta misma competencia."
        ),
    )
    subcompetencies: List[ExtractedSubcompetency] = Field(
        ...,
        min_length=1,
        max_length=5,
        description=(
            "Entre 3 y 5 subcompetencias específicas y ortogonales entre sí, "
            "cubriendo distintos aspectos del documento (conceptual, procedimental, "
            "analítico, aplicado, crítico). Mínimo 1 si el documento es muy corto."
        ),
    )

    @field_validator("competency_name", mode="before")
    @classmethod
    def strip_competency(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


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


class DashboardDocumentCompetencies(BaseModel):
    """Bloque de competencias asociado a un documento cargado en el proyecto."""

    document_id: str = Field(
        ...,
        description="Clave canónica del documento (video_id para YouTube, basename para PDFs)",
    )
    display_name: Optional[str] = Field(
        None,
        description="Nombre legible para mostrar (título del vídeo, nombre del PDF…)",
    )
    competencies: List[DashboardCompetencyItem] = Field(
        default_factory=list,
        description="Competencias extraídas de ese documento y su puntuación agregada",
    )


class DashboardCompetencyResponse(BaseModel):
    """Competencias agrupadas por documento para el dashboard de aprendizaje."""

    documents: List[DashboardDocumentCompetencies] = Field(
        default_factory=list,
        description="Un bloque por cada documento del proyecto, en orden de registro",
    )


# =====================================================================
# Módulo Formador: itinerarios, unidades de aprendizaje y seguimiento
# =====================================================================


class ActivityTypeEnum(str, Enum):
    """Tipo de actividad registrada para una unidad de aprendizaje."""

    VIDEO = "video"
    CHAT_QUESTION = "chat_question"
    QUIZ = "quiz"


# ----- LearningUnit -----

class LearningUnitBase(BaseModel):
    """Campos compartidos de una unidad de aprendizaje (celda del cuadrante)."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre del concepto")
    definition: str = Field(..., min_length=1, description="Descripción del concepto a aprender")
    weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Peso fraccional sobre el itinerario completo (0.0–1.0)",
    )
    order_index: int = Field(0, ge=0, description="Posición dentro del tema")
    learning_outcome_id: Optional[int] = Field(
        None,
        gt=0,
        description="ID del resultado de aprendizaje (competencia) que evalúa esta celda",
    )


class LearningUnitCreate(LearningUnitBase):
    """Creación de unidad de aprendizaje (anidada en SaveItineraryRequest)."""


class LearningUnitUpdate(BaseModel):
    """Actualización parcial de una unidad de aprendizaje."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    definition: Optional[str] = Field(None, min_length=1)
    weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    order_index: Optional[int] = Field(None, ge=0)
    learning_outcome_id: Optional[int] = Field(None, gt=0)


class LearningUnitRead(LearningUnitBase):
    """Lectura de unidad de aprendizaje."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID de la unidad")
    theme_id: int = Field(..., description="ID del tema padre")
    created_at: datetime


# ----- Theme -----

class ThemeBase(BaseModel):
    """Campos compartidos de un tema del itinerario."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre del tema")
    order_index: int = Field(0, ge=0, description="Posición dentro del itinerario")


class ThemeCreate(ThemeBase):
    """Creación de tema con sus unidades anidadas."""

    learning_units: List[LearningUnitCreate] = Field(
        default_factory=list, description="Unidades de aprendizaje del tema"
    )


class ThemeUpdate(BaseModel):
    """Actualización parcial de un tema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    order_index: Optional[int] = Field(None, ge=0)


class ThemeRead(ThemeBase):
    """Lectura de tema con unidades."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    itinerary_id: int
    learning_units: List[LearningUnitRead] = Field(default_factory=list)
    created_at: datetime


# ----- CourseItinerary -----

class CourseItineraryBase(BaseModel):
    """Campos compartidos de un itinerario formativo."""

    title: str = Field(..., min_length=1, max_length=255, description="Título del curso")
    total_weeks: int = Field(..., ge=1, le=104, description="Semanas totales del curso")
    hours_per_week: float = Field(..., gt=0.0, le=80.0, description="Horas por semana")


class CourseItineraryCreate(CourseItineraryBase):
    """Creación de itinerario completo (con temas y unidades anidados)."""

    themes: List[ThemeCreate] = Field(..., min_length=1, description="Temas del curso")


class CourseItineraryUpdate(BaseModel):
    """Actualización parcial de un itinerario."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    total_weeks: Optional[int] = Field(None, ge=1, le=104)
    hours_per_week: Optional[float] = Field(None, gt=0.0, le=80.0)


class CourseItineraryRead(CourseItineraryBase):
    """Lectura de itinerario completo."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    themes: List[ThemeRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# ----- StudentActivityLog -----

class StudentActivityLogCreate(BaseModel):
    """Creación de un registro de actividad del alumno."""

    session_id: str = Field(..., min_length=1, max_length=255)
    learning_unit_id: int = Field(..., gt=0)
    activity_type: ActivityTypeEnum = Field(..., description="video | chat_question | quiz")
    score_earned: Optional[float] = Field(
        None,
        ge=0.0,
        le=10.0,
        description="Nota 0-10 si es quiz; 0.5 por acción; None si no aplica",
    )
    detail: Optional[str] = Field(None, description="Contexto opcional de la actividad")


class StudentActivityLogRead(BaseModel):
    """Lectura de un registro de actividad."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    learning_unit_id: int
    activity_type: ActivityTypeEnum
    score_earned: Optional[float] = None
    detail: Optional[str] = None
    timestamp: datetime


# ----- UnitProgress -----

class UnitProgressRead(BaseModel):
    """Lectura del resumen de progreso de una celda."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    learning_unit_id: int
    total_score: float = Field(..., ge=0.0, le=10.0)
    color_code: str = Field(..., pattern=r"^#[0-9a-fA-F]{6}$")
    last_updated: datetime


# ----- Generación de itinerario con LLM (salida estructurada) -----

class GeneratedLearningUnit(BaseModel):
    """Unidad de aprendizaje propuesta por el LLM."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre corto del concepto")
    definition: str = Field(
        ...,
        min_length=1,
        description="Descripción de qué debe aprender el alumno en esta unidad",
    )
    weight: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Peso porcentual sugerido sobre el total del curso (la suma de todas las unidades debe ser 100)",
    )


class GeneratedTheme(BaseModel):
    """Tema propuesto por el LLM con sus unidades."""

    name: str = Field(..., min_length=1, max_length=255, description="Nombre del tema")
    learning_units: List[GeneratedLearningUnit] = Field(
        ..., min_length=1, description="Unidades de aprendizaje del tema"
    )


class GeneratedItinerary(BaseModel):
    """Itinerario completo propuesto por el LLM (respuesta de /trainer/generate-itinerary)."""

    title: str = Field(..., min_length=1, max_length=255, description="Título del curso")
    total_weeks: int = Field(..., ge=1, le=104, description="Semanas totales estimadas")
    hours_per_week: float = Field(..., gt=0.0, le=80.0, description="Horas semanales estimadas")
    themes: List[GeneratedTheme] = Field(..., min_length=1, description="Temas del curso")


class GenerateItineraryRequest(BaseModel):
    """Body de POST /trainer/generate-itinerary."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="Petición del formador (ej: 'Curso de Python de 4 semanas, 10h/semana')",
    )


class SaveItineraryResponse(BaseModel):
    """Respuesta de POST /trainer/save-itinerary."""

    itinerary_id: int = Field(..., description="ID del itinerario guardado")
    theme_count: int = Field(..., ge=0)
    unit_count: int = Field(..., ge=0)
    message: str


class TrainerLearningOutcomeOption(BaseModel):
    """Opción de competencia para enlazar una celda del cuadrante."""

    id: int = Field(..., description="ID del learning outcome")
    description: str = Field(..., description="Descripción del resultado de aprendizaje")
    competency_name: str = Field(..., description="Competencia raíz")
    subcompetency_name: str = Field(..., description="Subcompetencia")
    document_id: str = Field(..., description="Documento de origen")


# ----- Cuadrante de progreso (dashboard formador) -----

class QuadrantUnit(BaseModel):
    """Celda del cuadrante: unidad con puntuación, % completado y color."""

    unit_id: int
    name: str
    definition: str
    weight: float = Field(..., ge=0.0, le=1.0, description="Peso fraccional en el itinerario")
    score: float = Field(..., ge=0.0, le=10.0, description="Puntuación actual 0-10")
    percent_complete: float = Field(
        ..., ge=0.0, le=100.0, description="Porcentaje completado de la celda (score/10)"
    )
    color_code: str = Field(..., description="Color hex para pintar la celda")


class QuadrantTheme(BaseModel):
    """Tema del cuadrante con sus celdas."""

    theme_id: int
    name: str
    units: List[QuadrantUnit] = Field(default_factory=list)


class QuadrantResponse(BaseModel):
    """Respuesta de GET /trainer/progress/quadrant/{session_id}."""

    itinerary_id: int
    title: str
    total_weeks: int
    hours_per_week: float
    themes: List[QuadrantTheme] = Field(default_factory=list)
    overall_score: float = Field(
        0.0, ge=0.0, le=10.0, description="Media ponderada por peso de todas las celdas"
    )


class UnitDetailsQuizStats(BaseModel):
    """Estadísticas de cuestionarios de una celda."""

    count: int = Field(0, ge=0)
    average_score: Optional[float] = Field(None, ge=0.0, le=10.0)


class UnitDetailsResponse(BaseModel):
    """Respuesta de GET /trainer/progress/unit-details/{session_id}/{unit_id}."""

    unit_id: int
    unit_name: str
    total_score: float = Field(..., ge=0.0, le=10.0)
    color_code: str
    quiz_stats: UnitDetailsQuizStats
    video_count: int = Field(0, ge=0)
    chat_question_count: int = Field(0, ge=0)
    quiz_points: float = Field(0.0, ge=0.0, le=7.5, description="Puntos aportados por quizzes (máx 7.5)")
    action_points: float = Field(0.0, ge=0.0, le=2.5, description="Puntos aportados por acciones (máx 2.5)")
    activities: List[StudentActivityLogRead] = Field(default_factory=list)


# =====================================================================
# Autenticación JWT
# =====================================================================

_PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d]).{8,}$"
)
_USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,50}$")


class UserCreate(BaseModel):
    """Body de POST /auth/register."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Solo minúsculas, dígitos, guion o guion bajo (3–50 caracteres)",
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Mínimo 8 caracteres con mayúscula, minúscula, dígito y carácter especial",
    )

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("username")
    @classmethod
    def validate_username_pattern(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "El nombre de usuario solo puede contener letras minúsculas, números, "
                "guion (-) o guion bajo (_), con entre 3 y 50 caracteres. "
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not _PASSWORD_RE.match(v):
            raise ValueError(
                "La contraseña debe tener al menos 8 caracteres e incluir: "
                "una mayúscula (A-Z), una minúscula (a-z), un dígito (0-9) y "
                "un carácter especial (!@#$%...). "
            )
        return v


class UserLogin(BaseModel):
    """Body de POST /auth/login."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class TokenResponse(BaseModel):
    """Respuesta de login/registro/refresh con el access token JWT."""

    access_token: str = Field(..., description="JWT de acceso (Bearer)")
    token_type: str = Field("bearer", description="Tipo de token")
    expires_in: int = Field(..., description="Vida útil del access token en segundos")


class UserOut(BaseModel):
    """Datos públicos del usuario autenticado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    created_at: datetime
