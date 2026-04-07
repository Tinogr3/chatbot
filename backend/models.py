"""
Modelos SQLAlchemy para el sistema de evaluación por competencias.

Define 5 entidades relacionales:
- Competency          (competencia general o específica)
- Subcompetency       (subcompetencia ligada a una competencia)
- LearningOutcome     (resultado de aprendizaje con peso ponderado)
- LearningEvidence    (evidencia de evaluación por sesión)
- UserCompetencyProgress (progreso agregado por sesión y subcompetencia)
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
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
