"""
Endpoints de historial de chat - GET /history, DELETE /history
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from chat_manager import ChatHistoryManager
from schemas import DeletedCountResponse, HistoryResponse
from session_ids import normalize_session_id

router = APIRouter(prefix="/history", tags=["history"])
chat_manager = ChatHistoryManager()


@router.get("", response_model=HistoryResponse)
async def get_history(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> HistoryResponse:
    session_id = normalize_session_id(x_session_id)
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    messages = await chat_manager.get_history(session_id)
    return HistoryResponse(messages=messages)


@router.delete("", response_model=DeletedCountResponse)
async def delete_history(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> DeletedCountResponse:
    session_id = normalize_session_id(x_session_id)
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    n = await chat_manager.delete_history(session_id)
    return DeletedCountResponse(deleted=n)
