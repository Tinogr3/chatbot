"""
Endpoints de sesión - POST /clear_session
"""
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from api.chat import invalidate_agent_cache
from chat_manager import ChatHistoryManager
from document_registry import clear_document_registry
from logger import get_logger
from rag_engine import _chroma_persist_directory
from schemas import ClearSessionResponse

logger = get_logger("api.session")
router = APIRouter(prefix="/session", tags=["session"])
chat_manager = ChatHistoryManager()


@router.post("/clear", response_model=ClearSessionResponse)
async def clear_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> ClearSessionResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    await chat_manager.delete_history(session_id)
    clear_document_registry(session_id)
    invalidate_agent_cache(session_id)

    persist_dir = _chroma_persist_directory(session_id)
    if os.path.exists(persist_dir):
        try:
            shutil.rmtree(persist_dir)
        except OSError as e:
            logger.warning("Error removing chroma dir for %s: %s", session_id, e)

    return ClearSessionResponse(message="Sesión limpiada correctamente.")
