"""
Endpoints del Módulo Alumno — cursos compartidos y progreso por proyecto.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.trainer import _build_quadrant_response
from auth import get_validated_session, require_alumno
from database import get_db
from models import User
from schemas import QuadrantResponse, SharedProjectDocument, SharedProjectRead, SharedProjectsResponse
from services.trainer_project_service import (
    list_shared_projects_for_student,
    progress_session_for_user,
    registry_documents_for_session,
)
from session_ids import owner_username_from_session

router = APIRouter(prefix="/student", tags=["Student"])


@router.get(
    "/projects/shared",
    response_model=SharedProjectsResponse,
    summary="Cursos/proyectos del formador asignados al alumno",
)
async def list_shared_projects(
    alumno: User = Depends(require_alumno),
    db: AsyncSession = Depends(get_db),
) -> SharedProjectsResponse:
    """Devuelve proyectos compartidos con documentos del registry listos para RAG."""
    projects = await list_shared_projects_for_student(db, student_id=alumno.id)
    items: List[SharedProjectRead] = []
    for project in projects:
        docs_raw = registry_documents_for_session(project.session_id)
        items.append(
            SharedProjectRead(
                id=project.id,
                name=project.name,
                session_id=project.session_id,
                trainer_username=project.trainer.username if project.trainer else "",
                documents=[
                    SharedProjectDocument(
                        name=d["name"],
                        doc_key=d["doc_key"],
                        source=d["source"],
                    )
                    for d in docs_raw
                ],
            )
        )
    return SharedProjectsResponse(projects=items)


@router.get(
    "/progress/quadrant/me",
    response_model=QuadrantResponse,
    summary="Cuadrante de progreso del alumno en el curso/proyecto activo",
)
async def get_my_progress_quadrant(
    course_session_id: str = Depends(get_validated_session),
    alumno: User = Depends(require_alumno),
    db: AsyncSession = Depends(get_db),
) -> QuadrantResponse:
    """Itinerario del proyecto seleccionado + métricas del alumno en ese curso."""
    owner = owner_username_from_session(course_session_id)
    if owner == alumno.username:
        raise HTTPException(
            status_code=404,
            detail=(
                "Selecciona un curso compartido de tu formador para ver el cuadrante. "
                "En proyectos personales no hay itinerario de curso."
            ),
        )

    progress_sid = await progress_session_for_user(
        db, user=alumno, validated_session_id=course_session_id
    )

    return await _build_quadrant_response(
        db,
        course_session_id=course_session_id,
        student_progress_session_id=progress_sid,
    )
