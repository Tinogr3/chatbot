"""
Cliente HTTP para la API del backend.
Todas las peticiones envían X-Session-Id cuando hay session_id.
"""
import os
from typing import Any, Dict, List, Optional

import httpx

BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
DEFAULT_TIMEOUT: float = 120.0


def _headers(session_id: Optional[str] = None) -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if session_id:
        h["X-Session-Id"] = session_id
    return h


def chat(
    message: str,
    session_id: str,
    temperature: float = 0.7,
    max_tokens: int = 65535,
    learning_mode: bool = False,
    learning_topic: Optional[str] = None,
    last_learning_content: Optional[str] = None,
) -> Dict[str, Any]:
    """POST /chat"""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.post(
            f"{BACKEND_URL}/chat",
            json={
                "message": message,
                "session_id": session_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "learning_mode": learning_mode,
                "learning_topic": learning_topic,
                "last_learning_content": last_learning_content,
            },
            headers=_headers(session_id),
        )
        r.raise_for_status()
        return r.json()


def upload_pdf(file_content: bytes, filename: str, session_id: str) -> Dict[str, Any]:
    """POST /upload (multipart). Devuelve { task_id, message } (procesamiento asíncrono)."""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.post(
            f"{BACKEND_URL}/upload",
            files={"file": (filename, file_content, "application/pdf")},
            headers={"X-Session-Id": session_id},
        )
        r.raise_for_status()
        return r.json()


def get_task_status(task_id: str) -> Dict[str, Any]:
    """GET /status/{task_id}. Devuelve status, progress (0–1), message, result o error."""
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BACKEND_URL}/status/{task_id}")
        r.raise_for_status()
        return r.json()


def load_cloud_pdfs(session_id: str) -> Dict[str, Any]:
    """POST /upload/load_cloud"""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.post(
            f"{BACKEND_URL}/upload/load_cloud",
            headers=_headers(session_id),
        )
        r.raise_for_status()
        return r.json()


def process_video(url: str, session_id: str) -> Dict[str, Any]:
    """POST /process_video. Devuelve { task_id, message } (procesamiento asíncrono)."""
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.post(
            f"{BACKEND_URL}/process_video",
            json={"url": url, "session_id": session_id},
            headers=_headers(session_id),
        )
        r.raise_for_status()
        return r.json()


def get_history(session_id: str) -> List[Dict[str, Any]]:
    """GET /history"""
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BACKEND_URL}/history", headers=_headers(session_id))
        r.raise_for_status()
        return r.json().get("messages", [])


def delete_history(session_id: str) -> int:
    """DELETE /history"""
    with httpx.Client(timeout=30.0) as client:
        r = client.delete(f"{BACKEND_URL}/history", headers=_headers(session_id))
        r.raise_for_status()
        return r.json().get("deleted", 0)


def get_user_facts(session_id: str) -> List[Dict[str, Any]]:
    """GET /user_facts"""
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{BACKEND_URL}/user_facts", headers=_headers(session_id))
        r.raise_for_status()
        return r.json().get("facts", [])


def delete_user_facts(session_id: str) -> int:
    """DELETE /user_facts"""
    with httpx.Client(timeout=30.0) as client:
        r = client.delete(f"{BACKEND_URL}/user_facts", headers=_headers(session_id))
        r.raise_for_status()
        return r.json().get("deleted", 0)


def clear_session(session_id: str) -> None:
    """POST /session/clear"""
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{BACKEND_URL}/session/clear", headers=_headers(session_id))
        r.raise_for_status()
