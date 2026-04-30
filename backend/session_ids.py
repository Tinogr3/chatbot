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
