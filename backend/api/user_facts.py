"""
Endpoints de memoria de usuario - GET /user_facts, DELETE /user_facts
"""
from fastapi import APIRouter, Depends

from auth import get_validated_session
from schemas import DeletedCountResponse, UserFactsResponse
from user_memory import UserMemoryManager

router = APIRouter(prefix="/user_facts", tags=["user_facts"])
user_memory = UserMemoryManager()


@router.get("", response_model=UserFactsResponse)
def get_user_facts(
    session_id: str = Depends(get_validated_session),
) -> UserFactsResponse:
    facts = user_memory.get_user_facts(session_id)
    return UserFactsResponse(facts=facts)


@router.delete("", response_model=DeletedCountResponse)
def delete_user_facts(
    session_id: str = Depends(get_validated_session),
) -> DeletedCountResponse:
    n = user_memory.delete_user_facts(session_id)
    return DeletedCountResponse(deleted=n)
