"""
Endpoints de historial de chat - GET /history, DELETE /history
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from chat_manager import ChatHistoryManager

router = APIRouter(prefix="/history", tags=["history"])
chat_manager = ChatHistoryManager()


class HistoryResponse(BaseModel):
    messages: list


@router.get("", response_model=HistoryResponse)
def get_history(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    messages = chat_manager.get_history(session_id)
    return HistoryResponse(messages=messages)


@router.delete("")
def delete_history(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    n = chat_manager.delete_history(session_id)
    return {"deleted": n}
