"""
IDs de modelos Gemini centralizados (Gemini Developer API / Vertex AI vía LangChain).

Referencias oficiales:
  https://ai.google.dev/gemini-api/docs/models
  https://cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-flash
"""

from __future__ import annotations

import os

# Valores por defecto alineados con la documentación actual de Google (preview puede rotar).
DEFAULT_GEMINI_FLASH = "gemini-3-flash-preview"
DEFAULT_GEMINI_PRO = "gemini-3.1-pro-preview"


def gemini_flash_model_id() -> str:
    """Gemini 3 Flash (rápido / económico): fichas de documento, competencias, visión sobre PDFs, etc."""
    v = os.getenv("GEMINI_AI_MODEL_FLASH")
    if v and str(v).strip():
        return str(v).strip()
    return DEFAULT_GEMINI_FLASH


def gemini_pro_model_id() -> str:
    """Gemini 3.1 Pro (razonamiento fuerte): agente de chat, clasificación de router, etc."""
    v = os.getenv("GEMINI_AI_MODEL_PRO")
    if v and str(v).strip():
        return str(v).strip()
    legacy = os.getenv("VERTEX_AI_MODEL")
    if legacy and str(legacy).strip():
        return str(legacy).strip()
    return DEFAULT_GEMINI_PRO
