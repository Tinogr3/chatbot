"""
Motor de evaluación por IA ("IA como evaluador").

Usa el LLM de Gemini con salida estructurada para evaluar respuestas de
estudiantes contra resultados de aprendizaje.
"""
from __future__ import annotations

import os
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import get_credentials_and_project
from gemini_models import gemini_flash_model_id
from logger import get_logger

logger = get_logger("evaluation_engine")


class EvaluationLLMOutput(BaseModel):
    """Respuesta obligatoria del LLM evaluador."""

    score: float = Field(..., ge=0.0, le=1.0, description="Grado de cumplimiento del resultado de aprendizaje (0.0–1.0)")
    feedback: str = Field(..., min_length=1, description="Retroalimentación constructiva y específica para el estudiante")


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
    """Evaluación de respuestas de estudiantes mediante LLM con salida estructurada."""

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
