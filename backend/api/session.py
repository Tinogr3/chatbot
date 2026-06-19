"""
Endpoints de sesión - POST /session/clear
"""
import os
import shutil

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.chat import invalidate_agent_cache
from auth import get_current_user, get_validated_session
from database import get_db
from discovery_repo import clear_discovery_for_session
from chat_manager import ChatHistoryManager
from document_registry import clear_document_registry
from logger import get_logger
from models import User
from rag_engine import _chroma_persist_directory
from schemas import ClearSessionResponse
from services.trainer_project_service import teardown_shared_course
from session_ids import owner_username_from_session

logger = get_logger("api.session")
router = APIRouter(prefix="/session", tags=["session"])
chat_manager = ChatHistoryManager()


@router.post("/clear", response_model=ClearSessionResponse)
async def clear_session(
    session_id: str = Depends(get_validated_session),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClearSessionResponse:

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

    if owner_username_from_session(session_id) == current_user.username:
        await teardown_shared_course(db, course_session_id=session_id)

    return ClearSessionResponse(message="Sesión limpiada correctamente.")
