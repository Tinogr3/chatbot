"""
Endpoints de sesión - POST /clear_session
"""
import os
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header

from chat_manager import ChatHistoryManager
from document_registry import clear_document_registry
from api.chat import invalidate_agent_cache
from rag_engine import _chroma_persist_directory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])
chat_manager = ChatHistoryManager()


@router.post("/clear")
def clear_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    chat_manager.delete_history(session_id)
    clear_document_registry(session_id)
    invalidate_agent_cache(session_id)

    persist_dir = _chroma_persist_directory(session_id)
    if os.path.exists(persist_dir):
        try:
            import shutil
            shutil.rmtree(persist_dir)
        except Exception as e:
            logger.warning("Error removing chroma dir for %s: %s", session_id, e)

    return {"message": "Sesión limpiada correctamente."}
