"""
Motor de evaluación por IA ("IA como evaluador").

Usa el LLM de Gemini con salida estructurada para evaluar respuestas de
estudiantes contra resultados de aprendizaje, persistir evidencias y
recalcular el progreso por subcompetencia.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload

from config import get_credentials_and_project
from gemini_models import gemini_flash_model_id
from logger import get_logger

logger = get_logger("evaluation_engine")


# ---------------------------------------------------------------------------
# Schema interno para la salida estructurada del LLM
# ---------------------------------------------------------------------------

class EvaluationLLMOutput(BaseModel):
    """Respuesta obligatoria del LLM evaluador."""

    score: float = Field(..., ge=0.0, le=1.0, description="Grado de cumplimiento del resultado de aprendizaje (0.0–1.0)")
    feedback: str = Field(..., min_length=1, description="Retroalimentación constructiva y específica para el estudiante")


# ---------------------------------------------------------------------------
# Servicio de evaluación
# ---------------------------------------------------------------------------

_EVALUATION_SYSTEM_PROMPT = (
    "Eres un evaluador educativo estricto y justo. "
    "Tu tarea es evaluar la respuesta de un estudiante respecto a un resultado de aprendizaje esperado.\n\n"
    "Criterios de puntuación:\n"
    "- 0.0: la respuesta no demuestra ningún conocimiento relevante.\n"
    "- 0.1–0.4: la respuesta muestra comprensión parcial pero con errores significativos.\n"
    "- 0.5–0.7: la respuesta es aceptable pero incompleta o con imprecisiones menores.\n"
    "- 0.8–0.9: la respuesta es buena, demuestra dominio con detalles menores por mejorar.\n"
    "- 1.0: la respuesta demuestra dominio completo del resultado de aprendizaje.\n\n"
    "Devuelve siempre una puntuación (score) y retroalimentación (feedback) constructiva."
)


class EvaluationService:
    """Encapsula la lógica de evaluación con IA y persistencia de resultados."""

    # -----------------------------------------------------------------
    # LLM helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _get_llm() -> ChatGoogleGenerativeAI:
        api_key = os.getenv("GOOGLE_API_KEY")
        flash = gemini_flash_model_id()
        if api_key:
            return ChatGoogleGenerativeAI(
                model=flash,
                google_api_key=api_key,
                temperature=0,
            )

        credentials, project_id = get_credentials_and_project()
        if not credentials or not project_id:
            raise RuntimeError(
                "No hay credenciales de LLM disponibles. "
                "Configura GOOGLE_API_KEY o GOOGLE_APPLICATION_CREDENTIALS."
            )
        return ChatGoogleGenerativeAI(
            model=flash,
            credentials=credentials,
            project=project_id,
            location="global",
            temperature=0,
        )

    # -----------------------------------------------------------------
    # evaluate_student_answer  (síncrono – LangChain invoke es bloqueante)
    # -----------------------------------------------------------------

    @staticmethod
    def evaluate_student_answer(learning_outcome: str, student_answer: str) -> dict:
        """Evalúa la respuesta de un estudiante usando el LLM.

        Returns:
            dict con claves ``"score"`` (float 0.0–1.0) y ``"feedback"`` (str).
        """
        llm = EvaluationService._get_llm()
        structured_llm = llm.with_structured_output(EvaluationLLMOutput)

        prompt = (
            f"{_EVALUATION_SYSTEM_PROMPT}\n\n"
            f"RESULTADO DE APRENDIZAJE A EVALUAR:\n{learning_outcome}\n\n"
            f"RESPUESTA DEL ESTUDIANTE:\n{student_answer}"
        )

        result: Optional[EvaluationLLMOutput] = structured_llm.invoke(prompt)
        if result is None:
            raise RuntimeError("El LLM no devolvió una evaluación válida.")

        return {"score": result.score, "feedback": result.feedback}

    # -----------------------------------------------------------------
    # process_evaluation  (async – orquesta BD + LLM)
    # -----------------------------------------------------------------

    @staticmethod
    async def process_evaluation(
        session_id: str,
        learning_outcome_id: int,
        student_answer: str,
    ):
        """Flujo completo: evalúa, persiste evidencia y recalcula progreso.

        Returns:
            ``EvaluateLearningResponse`` con score, feedback y
            updated_subcompetency_score.
        """
        from database import AsyncSessionLocal
        from models import LearningEvidence, LearningOutcome, UserCompetencyProgress
        from schemas import EvaluateLearningResponse

        async with AsyncSessionLocal() as db:
            # 1. Buscar el LearningOutcome
            stmt = (
                select(LearningOutcome)
                .options(selectinload(LearningOutcome.subcompetency))
                .where(LearningOutcome.id == learning_outcome_id)
            )
            row = await db.execute(stmt)
            outcome: Optional[LearningOutcome] = row.scalar_one_or_none()

            if outcome is None:
                raise ValueError(
                    f"LearningOutcome con id={learning_outcome_id} no existe."
                )

            subcompetency_id: int = outcome.subcompetency_id

            # 2. Llamar al LLM (bloqueante → hilo separado)
            evaluation = await asyncio.to_thread(
                EvaluationService.evaluate_student_answer,
                outcome.description,
                student_answer,
            )

            # 3. Guardar evidencia
            evidence = LearningEvidence(
                session_id=session_id,
                learning_outcome_id=learning_outcome_id,
                score=evaluation["score"],
                feedback=evaluation["feedback"],
            )
            db.add(evidence)
            await db.flush()

            # 4. Recalcular media ponderada de la subcompetencia
            #    Toma la última evidencia de cada learning_outcome para esta sesión.
            latest_id_subq = (
                select(
                    LearningEvidence.learning_outcome_id,
                    func.max(LearningEvidence.id).label("max_id"),
                )
                .where(LearningEvidence.session_id == session_id)
                .group_by(LearningEvidence.learning_outcome_id)
                .subquery()
            )

            weighted_query = (
                select(
                    func.sum(LearningEvidence.score * LearningOutcome.weight).label("weighted_sum"),
                    func.sum(LearningOutcome.weight).label("total_weight"),
                )
                .join(
                    LearningOutcome,
                    LearningEvidence.learning_outcome_id == LearningOutcome.id,
                )
                .join(
                    latest_id_subq,
                    and_(
                        LearningEvidence.learning_outcome_id == latest_id_subq.c.learning_outcome_id,
                        LearningEvidence.id == latest_id_subq.c.max_id,
                    ),
                )
                .where(LearningOutcome.subcompetency_id == subcompetency_id)
            )

            result = await db.execute(weighted_query)
            row_calc = result.one()
            weighted_sum = row_calc.weighted_sum or 0.0
            total_weight = row_calc.total_weight or 1.0
            updated_score = round(weighted_sum / total_weight, 4)

            # 5. Upsert UserCompetencyProgress
            progress_stmt = select(UserCompetencyProgress).where(
                UserCompetencyProgress.session_id == session_id,
                UserCompetencyProgress.subcompetency_id == subcompetency_id,
            )
            progress_row = await db.execute(progress_stmt)
            progress: Optional[UserCompetencyProgress] = progress_row.scalar_one_or_none()

            if progress is None:
                progress = UserCompetencyProgress(
                    session_id=session_id,
                    subcompetency_id=subcompetency_id,
                    score=updated_score,
                )
                db.add(progress)
            else:
                progress.score = updated_score

            await db.commit()

            # 6. Devolver respuesta
            return EvaluateLearningResponse(
                score=evaluation["score"],
                feedback=evaluation["feedback"],
                updated_subcompetency_score=updated_score,
            )
