"""
Servicio de progreso del alumno por unidad de aprendizaje (celda).

Regla de negocio (puntuación máxima por celda: 10 puntos):
  * Cuestionarios (quizzes): aportan el 75% del valor de la celda (máx. 7.5
    puntos). Si hay varios, se usa la MEDIA de sus notas (escala 0-10).
  * Realizaciones (ver un vídeo, preguntar al chat…): suman 0.5 puntos cada
    una hasta cubrir el 25% restante (máx. 2.5 puntos).

El color de estado se materializa en ``UnitProgress.color_code``:
  * score < 5.0      → rojo    (#ef4444)
  * 5.0 ≤ score ≤ 7.5 → amarillo (#eab308)
  * score > 7.5      → verde   (#22c55e)
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logger import get_logger
from models import (
    ActivityType,
    CourseItinerary,
    LearningUnit,
    StudentActivityLog,
    Theme,
    UnitProgress,
)

logger = get_logger("progress_service")

# Constantes de la regla de negocio
MAX_CELL_SCORE = 10.0
QUIZ_WEIGHT_FRACTION = 0.75          # 75% del valor de la celda
MAX_QUIZ_POINTS = MAX_CELL_SCORE * QUIZ_WEIGHT_FRACTION       # 7.5
MAX_ACTION_POINTS = MAX_CELL_SCORE * (1 - QUIZ_WEIGHT_FRACTION)  # 2.5
POINTS_PER_ACTION = 0.5

COLOR_RED = "#ef4444"
COLOR_YELLOW = "#eab308"
COLOR_GREEN = "#22c55e"


def compute_color_code(score: float) -> str:
    """Color de la celda según la puntuación 0-10."""
    if score < 5.0:
        return COLOR_RED
    if score <= 7.5:
        return COLOR_YELLOW
    return COLOR_GREEN


class ProgressService:
    """Lógica de registro de actividades y recálculo de progreso por celda.

    Todas las operaciones reciben una ``AsyncSession`` ya abierta y NO
    commitean: el commit es responsabilidad del caller (en FastAPI lo hace
    el dependency ``get_db`` al cerrar el request; en scripts/workers, el
    contexto que abrió la sesión).
    """

    # ------------------------------------------------------------------
    # Registro + recálculo
    # ------------------------------------------------------------------

    @staticmethod
    async def log_activity_and_update_progress(
        db: AsyncSession,
        *,
        session_id: str,
        unit_id: int,
        activity_type: ActivityType,
        score: Optional[float] = None,
        detail: Optional[str] = None,
    ) -> float:
        """Inserta la actividad en el histórico y recalcula la celda.

        Args:
            db: sesión async abierta (sin commit dentro).
            session_id: sesión del alumno.
            unit_id: id de la ``LearningUnit`` afectada.
            activity_type: tipo de actividad (video / chat_question / quiz).
            score: nota 0-10 si es quiz; ignorado para acciones (se usa 0.5).
            detail: contexto opcional (pregunta realizada, título del vídeo…).

        Returns:
            La nueva puntuación total (0-10) de la celda.

        Raises:
            LookupError: si la unidad no existe.
        """
        unit_exists = (
            await db.execute(select(LearningUnit.id).where(LearningUnit.id == unit_id))
        ).scalar_one_or_none()
        if unit_exists is None:
            raise LookupError(f"LearningUnit con id={unit_id} no existe.")

        if activity_type == ActivityType.QUIZ:
            safe_score = max(0.0, min(MAX_CELL_SCORE, float(score if score is not None else 0.0)))
        else:
            safe_score = POINTS_PER_ACTION

        db.add(
            StudentActivityLog(
                session_id=session_id,
                learning_unit_id=unit_id,
                activity_type=activity_type,
                score_earned=safe_score,
                detail=(detail or None),
            )
        )
        await db.flush()  # la nueva actividad debe entrar en el recálculo

        total = await ProgressService._recompute_unit_score(
            db, session_id=session_id, unit_id=unit_id
        )

        await ProgressService._upsert_unit_progress(
            db, session_id=session_id, unit_id=unit_id, total_score=total
        )
        return total

    # ------------------------------------------------------------------
    # Cálculo de puntuación
    # ------------------------------------------------------------------

    @staticmethod
    async def _recompute_unit_score(
        db: AsyncSession,
        *,
        session_id: str,
        unit_id: int,
    ) -> float:
        """Recalcula la puntuación 0-10 de una celda según la regla 75/25."""
        quiz_count, quiz_avg, action_count = await ProgressService._activity_aggregates(
            db, session_id=session_id, unit_id=unit_id
        )

        quiz_points = (quiz_avg * QUIZ_WEIGHT_FRACTION) if quiz_count > 0 else 0.0
        action_points = min(action_count * POINTS_PER_ACTION, MAX_ACTION_POINTS)

        total = round(min(quiz_points + action_points, MAX_CELL_SCORE), 4)
        return max(0.0, total)

    @staticmethod
    async def _activity_aggregates(
        db: AsyncSession,
        *,
        session_id: str,
        unit_id: int,
    ) -> Tuple[int, float, int]:
        """Agrega el histórico de la celda.

        Returns:
            (nº de quizzes, media de notas de quiz 0-10, nº de acciones).
        """
        quiz_row = (
            await db.execute(
                select(
                    func.count(StudentActivityLog.id),
                    func.coalesce(func.avg(StudentActivityLog.score_earned), 0.0),
                )
                .where(
                    StudentActivityLog.session_id == session_id,
                    StudentActivityLog.learning_unit_id == unit_id,
                    StudentActivityLog.activity_type == ActivityType.QUIZ,
                )
            )
        ).one()
        quiz_count = int(quiz_row[0] or 0)
        quiz_avg = float(quiz_row[1] or 0.0)

        action_count = (
            await db.execute(
                select(func.count(StudentActivityLog.id)).where(
                    StudentActivityLog.session_id == session_id,
                    StudentActivityLog.learning_unit_id == unit_id,
                    StudentActivityLog.activity_type != ActivityType.QUIZ,
                )
            )
        ).scalar_one()

        return quiz_count, quiz_avg, int(action_count or 0)

    @staticmethod
    async def _upsert_unit_progress(
        db: AsyncSession,
        *,
        session_id: str,
        unit_id: int,
        total_score: float,
    ) -> None:
        """Crea o actualiza la fila de resumen ``UnitProgress``."""
        progress = (
            await db.execute(
                select(UnitProgress).where(
                    UnitProgress.session_id == session_id,
                    UnitProgress.learning_unit_id == unit_id,
                )
            )
        ).scalar_one_or_none()

        color = compute_color_code(total_score)
        if progress is None:
            db.add(
                UnitProgress(
                    session_id=session_id,
                    learning_unit_id=unit_id,
                    total_score=total_score,
                    color_code=color,
                )
            )
        else:
            progress.total_score = total_score
            progress.color_code = color

    # ------------------------------------------------------------------
    # Resolución de unidad por enlace fuerte (learning_outcome_id)
    # ------------------------------------------------------------------

    @staticmethod
    async def find_unit_by_outcome_id(
        db: AsyncSession,
        *,
        session_id: str,
        learning_outcome_id: int,
    ) -> Optional[int]:
        """Devuelve el id de la ``LearningUnit`` enlazada a un outcome en el itinerario activo."""
        unit_id = (
            await db.execute(
                select(LearningUnit.id)
                .join(Theme, LearningUnit.theme_id == Theme.id)
                .join(CourseItinerary, Theme.itinerary_id == CourseItinerary.id)
                .where(
                    LearningUnit.learning_outcome_id == learning_outcome_id,
                    CourseItinerary.session_id == session_id,
                )
                .order_by(CourseItinerary.id.desc(), LearningUnit.id.asc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return int(unit_id) if unit_id is not None else None

    # ------------------------------------------------------------------
    # Mapeo texto → unidad (best-effort para hooks de chat/video)
    # ------------------------------------------------------------------

    @staticmethod
    async def find_unit_for_text(
        db: AsyncSession,
        *,
        session_id: str,
        text: str,
    ) -> Optional[int]:
        """Encuentra la unidad de aprendizaje más relevante para un texto libre.

        Heurística de solapamiento de tokens entre el texto (pregunta del chat,
        título de vídeo, tema de aprendizaje…) y el nombre + definición de cada
        unidad del itinerario de la sesión. Devuelve ``None`` si no hay
        itinerario o ningún solapamiento mínimo — los callers deben omitir el
        registro silenciosamente en ese caso.
        """
        clean = (text or "").strip().lower()
        if not clean:
            return None

        units = (
            await db.execute(
                select(LearningUnit.id, LearningUnit.name, LearningUnit.definition)
                .join(Theme, LearningUnit.theme_id == Theme.id)
                .join(CourseItinerary, Theme.itinerary_id == CourseItinerary.id)
                .where(CourseItinerary.session_id == session_id)
            )
        ).all()
        if not units:
            return None

        text_tokens = ProgressService._tokenize(clean)
        if not text_tokens:
            return None

        best_id: Optional[int] = None
        best_overlap = 0
        for unit_id, name, definition in units:
            unit_tokens = ProgressService._tokenize(f"{name} {definition or ''}".lower())
            overlap = len(text_tokens & unit_tokens)
            if overlap > best_overlap:
                best_overlap = overlap
                best_id = unit_id

        # Exigir al menos 1 token significativo en común
        return best_id if best_overlap >= 1 else None

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Tokens alfanuméricos significativos (>3 chars) sin stopwords comunes."""
        stopwords = {
            "para", "como", "este", "esta", "estos", "estas", "sobre", "entre",
            "donde", "cuando", "cual", "cuales", "tiene", "tienen", "hacer",
            "puede", "pueden", "debe", "deben", "desde", "hasta", "muy",
            "the", "and", "for", "with", "that", "this", "from", "what", "how",
        }
        tokens = set(re.findall(r"[a-záéíóúñü0-9]{4,}", text))
        return tokens - stopwords
