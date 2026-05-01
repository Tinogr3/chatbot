"""
Endpoints de sesión - POST /clear_session
"""
import os
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.chat import invalidate_agent_cache
from database import get_db
from discovery_repo import clear_discovery_for_session
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
    db: AsyncSession = Depends(get_db),
) -> ClearSessionResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")

    await clear_discovery_for_session(db, session_id)
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
