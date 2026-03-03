"""
Endpoints de memoria de usuario - GET /user_facts, DELETE /user_facts
"""
from typing import Optional, List, Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from user_memory import UserMemoryManager

router = APIRouter(prefix="/user_facts", tags=["user_facts"])
user_memory = UserMemoryManager()


class UserFactsResponse(BaseModel):
    facts: List[Any]


@router.get("", response_model=UserFactsResponse)
def get_user_facts(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    facts = user_memory.get_user_facts(session_id)
    return UserFactsResponse(facts=facts)


@router.delete("")
def delete_user_facts(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
):
    session_id = (x_session_id or "").strip().lower().replace(" ", "_")
    if not session_id:
        raise HTTPException(status_code=400, detail="Header X-Session-Id requerido")
    n = user_memory.delete_user_facts(session_id)
    return {"deleted": n}
