"""
Modelos SQLAlchemy para el sistema de evaluación por competencias.

Módulo Alumno (sistema original):
- Competency          (competencia general o específica)
- Subcompetency       (subcompetencia ligada a una competencia)
- LearningOutcome     (resultado de aprendizaje con peso ponderado)
- LearningEvidence    (evidencia de evaluación por sesión)
- UserCompetencyProgress (progreso agregado por sesión y subcompetencia)

Módulo Formador (itinerarios y seguimiento detallado):
- CourseItinerary     (planificación: semanas totales, horas/semana)
- Theme               (tema dentro de un itinerario)
- LearningUnit        (unidad de aprendizaje / celda con peso porcentual)
- StudentActivityLog  (histórico de actividades del alumno por unidad)
- UnitProgress        (resumen de puntuación 0-10 por alumno y unidad)
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# Usuarios y tokens de refresco (autenticación JWT)
# ---------------------------------------------------------------------------

class User(Base):
    """Cuenta de usuario. La contraseña se almacena hasheada con bcrypt."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class RefreshToken(Base):
    """Token de refresco persistido (hash SHA-256) para poder revocarlo."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    __table_args__ = (Index("ix_refresh_tokens_user_id", "user_id"),)

    def __repr__(self) -> str:
        return f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.is_revoked}>"


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------

class CompetencyType(str, enum.Enum):
    """Tipo de competencia: general o específica."""

    GENERAL = "general"
    ESPECIFICA = "especifica"


# ---------------------------------------------------------------------------
# Competency
# ---------------------------------------------------------------------------

class Competency(Base):
    __tablename__ = "competencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[CompetencyType] = mapped_column(
        Enum(CompetencyType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    document_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Referencia al documento subido asociado a esta competencia",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subcompetencies: Mapped[list[Subcompetency]] = relationship(
        back_populates="competency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Competency id={self.id} name={self.name!r} type={self.type.value}>"


# ---------------------------------------------------------------------------
# Subcompetency
# ---------------------------------------------------------------------------

class Subcompetency(Base):
    __tablename__ = "subcompetencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("competencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    competency: Mapped[Competency] = relationship(back_populates="subcompetencies")
    learning_outcomes: Mapped[list[LearningOutcome]] = relationship(
        back_populates="subcompetency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    progress_records: Mapped[list[UserCompetencyProgress]] = relationship(
        back_populates="subcompetency",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Subcompetency id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# LearningOutcome
# ---------------------------------------------------------------------------

class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subcompetency_id: Mapped[int] = mapped_column(
        ForeignKey("subcompetencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    subcompetency: Mapped[Subcompetency] = relationship(back_populates="learning_outcomes")
    evidences: Mapped[list[LearningEvidence]] = relationship(
        back_populates="learning_outcome",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    linked_units: Mapped[list[LearningUnit]] = relationship(
        "LearningUnit",
        back_populates="outcome_link",
        foreign_keys="LearningUnit.learning_outcome_id",
    )

    def __repr__(self) -> str:
        return f"<LearningOutcome id={self.id} weight={self.weight}>"


# ---------------------------------------------------------------------------
# LearningEvidence
# ---------------------------------------------------------------------------

class LearningEvidence(Base):
    __tablename__ = "learning_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    learning_outcome_id: Mapped[int] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    learning_outcome: Mapped[LearningOutcome] = relationship(back_populates="evidences")

    __table_args__ = (
        Index("ix_evidence_session_outcome", "session_id", "learning_outcome_id"),
    )

    def __repr__(self) -> str:
        return f"<LearningEvidence id={self.id} score={self.score}>"


# ---------------------------------------------------------------------------
# UserCompetencyProgress
# ---------------------------------------------------------------------------

class UserCompetencyProgress(Base):
    """Progreso agregado de un usuario/sesión en una subcompetencia."""

    __tablename__ = "user_competency_progress"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    subcompetency_id: Mapped[int] = mapped_column(
        ForeignKey("subcompetencies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subcompetency: Mapped[Subcompetency] = relationship(back_populates="progress_records")

    __table_args__ = (
        Index("ix_progress_session", "session_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserCompetencyProgress session={self.session_id!r} "
            f"subcompetency={self.subcompetency_id} score={self.score}>"
        )


# ---------------------------------------------------------------------------
# Discovery Hub (resúmenes y exámenes generados por chat)
# ---------------------------------------------------------------------------


class StoredSummary(Base):
    """Resumen generado cuando el usuario pide un resumen al asistente."""

    __tablename__ = "stored_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_stored_summary_session_created", "session_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<StoredSummary id={self.id} session={self.session_id!r}>"


class StoredExam(Base):
    """Examen generado cuando el usuario pide un examen o test sobre los documentos."""

    __tablename__ = "stored_exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (Index("ix_stored_exam_session_created", "session_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<StoredExam id={self.id} session={self.session_id!r}>"


# ===========================================================================
# Módulo Formador: itinerarios, unidades de aprendizaje y seguimiento
# ===========================================================================


class ActivityType(str, enum.Enum):
    """Tipo de actividad registrada en el histórico del alumno."""

    VIDEO = "video"
    CHAT_QUESTION = "chat_question"
    QUIZ = "quiz"


class CourseItinerary(Base):
    """Planificación de un curso creada por el formador.

    Una sesión (formador) mantiene un itinerario activo; al guardar uno nuevo
    se reemplaza el anterior (ver `api/trainer.py`).
    """

    __tablename__ = "course_itineraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        doc="Sesión del formador propietario del itinerario",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    hours_per_week: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    themes: Mapped[list[Theme]] = relationship(
        back_populates="itinerary",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Theme.order_index",
    )

    def __repr__(self) -> str:
        return (
            f"<CourseItinerary id={self.id} title={self.title!r} "
            f"weeks={self.total_weeks} h/week={self.hours_per_week}>"
        )


class Theme(Base):
    """Tema (bloque temático) dentro de un itinerario."""

    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    itinerary_id: Mapped[int] = mapped_column(
        ForeignKey("course_itineraries.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    itinerary: Mapped[CourseItinerary] = relationship(back_populates="themes")
    learning_units: Mapped[list[LearningUnit]] = relationship(
        back_populates="theme",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LearningUnit.order_index",
    )

    __table_args__ = (Index("ix_themes_itinerary", "itinerary_id"),)

    def __repr__(self) -> str:
        return f"<Theme id={self.id} name={self.name!r}>"


class LearningUnit(Base):
    """Unidad de aprendizaje (celda del cuadrante) dentro de un tema.

    ``weight`` es la fracción (0.0–1.0) del peso de esta unidad sobre el
    total del itinerario; la suma de todas las unidades debería ser ≈ 1.0.
    """

    __tablename__ = "learning_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(
        Text, nullable=False, doc="Descripción/definición del concepto a aprender"
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        doc="Peso fraccional de la unidad sobre el itinerario completo (0.0–1.0)",
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    learning_outcome_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_outcomes.id", ondelete="SET NULL"),
        nullable=True,
        doc="Enlace fuerte con el sistema de competencias",
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    theme: Mapped[Theme] = relationship(back_populates="learning_units")
    outcome_link: Mapped[LearningOutcome | None] = relationship(
        "LearningOutcome",
        back_populates="linked_units",
        foreign_keys=[learning_outcome_id],
        lazy="selectin",
    )
    activity_logs: Mapped[list[StudentActivityLog]] = relationship(
        back_populates="learning_unit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    progress_records: Mapped[list[UnitProgress]] = relationship(
        back_populates="learning_unit",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_learning_units_theme", "theme_id"),
        Index("ix_learning_units_outcome", "learning_outcome_id"),
    )

    def __repr__(self) -> str:
        return f"<LearningUnit id={self.id} name={self.name!r} weight={self.weight}>"


class StudentActivityLog(Base):
    """Histórico de actividades del alumno sobre una unidad de aprendizaje.

    ``score_earned``:
      - quiz: nota del cuestionario en escala 0–10.
      - video / chat_question: puntos de "realización" (0.5 por defecto).
    """

    __tablename__ = "student_activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    learning_unit_id: Mapped[int] = mapped_column(
        ForeignKey("learning_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_type: Mapped[ActivityType] = mapped_column(
        Enum(ActivityType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    score_earned: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Nota 0-10 si es quiz; 0.5 por acción (video/chat); NULL si no aplica",
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Contexto opcional (pregunta, título del video…)"
    )
    timestamp: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    learning_unit: Mapped[LearningUnit] = relationship(back_populates="activity_logs")

    __table_args__ = (
        Index("ix_activity_session_unit", "session_id", "learning_unit_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<StudentActivityLog id={self.id} type={self.activity_type.value} "
            f"score={self.score_earned}>"
        )


class UnitProgress(Base):
    """Resumen de progreso de un alumno en una unidad de aprendizaje (celda).

    ``total_score`` está en escala 0–10:
      - 75% del valor proviene de la media de los quizzes.
      - 25% restante de las realizaciones (+0.5 por acción, máx. 2.5).
    ``color_code`` se materializa para el frontend: rojo (<5), amarillo
    (5–7.5), verde (>7.5).
    """

    __tablename__ = "unit_progress"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    learning_unit_id: Mapped[int] = mapped_column(
        ForeignKey("learning_units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    color_code: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#ef4444"
    )
    last_updated: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    learning_unit: Mapped[LearningUnit] = relationship(back_populates="progress_records")

    __table_args__ = (Index("ix_unit_progress_session", "session_id"),)

    def __repr__(self) -> str:
        return (
            f"<UnitProgress session={self.session_id!r} "
            f"unit={self.learning_unit_id} score={self.total_score}>"
        )
