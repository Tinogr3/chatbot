"""
Endpoints de historial de chat - GET /history, DELETE /history
"""
from fastapi import APIRouter, Depends

from auth import get_validated_session
from chat_manager import ChatHistoryManager
from schemas import DeletedCountResponse, HistoryResponse

router = APIRouter(prefix="/history", tags=["history"])
chat_manager = ChatHistoryManager()


@router.get("", response_model=HistoryResponse)
async def get_history(
    session_id: str = Depends(get_validated_session),
) -> HistoryResponse:
    messages = await chat_manager.get_history(session_id)
    return HistoryResponse(messages=messages)


@router.delete("", response_model=DeletedCountResponse)
async def delete_history(
    session_id: str = Depends(get_validated_session),
) -> DeletedCountResponse:
    n = await chat_manager.delete_history(session_id)
    return DeletedCountResponse(deleted=n)
