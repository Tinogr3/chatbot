"""
Endpoints de memoria de usuario - GET /user_facts, DELETE /user_facts
"""
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from schemas import DeletedCountResponse, UserFactsResponse
from user_memory import UserMemoryManager

router = APIRouter(prefix="/user_facts", tags=["user_facts"])
user_memory = UserMemoryManager()


@router.get("", response_model=UserFactsResponse)
def get_user_facts(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> UserFactsResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    facts = user_memory.get_user_facts(session_id)
    return UserFactsResponse(facts=facts)


@router.delete("", response_model=DeletedCountResponse)
def delete_user_facts(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
) -> DeletedCountResponse:
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    n = user_memory.delete_user_facts(session_id)
    return DeletedCountResponse(deleted=n)
