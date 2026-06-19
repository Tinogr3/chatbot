"""Normalización de identificadores de sesión (alineada con el cliente Next.js)."""

from __future__ import annotations

import re
from typing import Optional


def normalize_session_id(raw: Optional[str]) -> str:
    """Igual que el cliente: trim, minúsculas, cualquier espacio → ``_``."""
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    return re.sub(r"\s+", "_", s)


def owner_username_from_session(session_id: str) -> str:
    """Extrae el username propietario de una sesión (sin sufijo de proyecto)."""
    normalized = normalize_session_id(session_id)
    if "__" in normalized:
        return normalized.split("__", 1)[0]
    return normalized


def student_course_progress_session(student_username: str, course_session_id: str) -> str:
    """Clave de progreso del alumno dentro de un curso/proyecto compartido."""
    student = normalize_session_id(student_username)
    course = normalize_session_id(course_session_id)
    return f"{student}__course__{course}"


def is_course_progress_session(session_id: str) -> bool:
    """True si la sesión es una clave de progreso alumno+curso."""
    return "__course__" in normalize_session_id(session_id)
