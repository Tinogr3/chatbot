"""
Persistencia del document_registry por sesión (backend).
"""
import os
import json
import logging

logger = logging.getLogger(__name__)


def _registry_dir() -> str:
    d = os.path.join(os.path.dirname(__file__), "data", "registry")
    os.makedirs(d, exist_ok=True)
    return d


def get_registry_path(session_id: str) -> str:
    return os.path.join(_registry_dir(), f"document_registry_{session_id}.json")


def load_document_registry(session_id: str) -> dict:
    path = get_registry_path(session_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Error loading document_registry for %s: %s", session_id, e)
        return {}


def save_document_registry(session_id: str, registry: dict) -> None:
    if not registry:
        return
    path = get_registry_path(session_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(registry, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.warning("Error saving document_registry for %s: %s", session_id, e)


def clear_document_registry(session_id: str) -> None:
    path = get_registry_path(session_id)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError as e:
            logger.warning("Error removing document_registry for %s: %s", session_id, e)
