"""Resolución de claves canónicas de documentos (registry + proyecto activo)."""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from sqlalchemy import or_

from models import Competency

_YT_URL_RE = re.compile(r"(?:youtube\.com|youtu\.be)", re.IGNORECASE)
_YT_ID_RE = re.compile(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})")


def extract_video_id_from_url(url: str) -> Optional[str]:
    match = _YT_ID_RE.search(url)
    return match.group(1) if match else None


def basename_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    if _YT_URL_RE.search(k):
        video_id = extract_video_id_from_url(k)
        return video_id if video_id else k
    return os.path.basename(k)


def parse_project_document_keys_header(raw: Optional[str]) -> List[str]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(unquote(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item.strip() for item in data if isinstance(item, str) and item.strip()]


def build_document_filenames(
    registry: Dict[str, Any],
    header_keys: List[str],
) -> Tuple[List[str], Dict[str, str]]:
    seen: set[str] = set()
    filenames: List[str] = []
    display_names: Dict[str, str] = {}

    for reg_key, reg_value in registry.items():
        card = reg_value if isinstance(reg_value, dict) else {}
        if card.get("type") == "video":
            video_id = card.get("video_id") or extract_video_id_from_url(reg_key)
            if not video_id:
                continue
            lookup_key = str(video_id)
            display = card.get("title") or reg_key
        else:
            lookup_key = basename_key(reg_key)
            display = lookup_key

        if not lookup_key or lookup_key in seen:
            continue
        seen.add(lookup_key)
        filenames.append(lookup_key)
        display_names[lookup_key] = display

    for key in header_keys:
        lookup_key = basename_key(key) if _YT_URL_RE.search(key) else key.strip()
        if not lookup_key or lookup_key in seen:
            continue
        seen.add(lookup_key)
        filenames.append(lookup_key)
        display_names[lookup_key] = key.strip()

    return filenames, display_names


def competency_document_match(document_filenames: List[str]):
    """Filtro SQL para ``Competency.document_id`` alineado con claves canónicas."""
    conditions = []
    for filename in document_filenames:
        conditions.append(Competency.document_id == filename)
        conditions.append(Competency.document_id.like(f"%/{filename}"))
        conditions.append(Competency.document_id.like(f"%?v={filename}%"))
    if not conditions:
        return None
    return or_(*conditions)


def normalize_competency_document_id(raw_id: str) -> str:
    if _YT_URL_RE.search(raw_id or ""):
        return extract_video_id_from_url(raw_id) or basename_key(raw_id)
    return basename_key(raw_id)
