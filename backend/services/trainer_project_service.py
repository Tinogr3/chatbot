"""Proyectos compartidos del formador (curso = session_id + RAG + itinerario)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from document_registry import load_document_registry
from models import (
    CourseItinerary,
    StudentActivityLog,
    TrainerProject,
    UnitProgress,
    User,
    UserRole,
    trainer_project_students_association,
)
from session_ids import (
    normalize_session_id,
    owner_username_from_session,
    student_course_progress_session,
)


async def _replace_project_students(
    db: AsyncSession, *, project_id: int, student_ids: List[int]
) -> None:
    """Sincroniza alumnos del curso sin lazy-load de relaciones (async-safe)."""
    await db.execute(
        delete(trainer_project_students_association).where(
            trainer_project_students_association.c.trainer_project_id == project_id
        )
    )
    if student_ids:
        await db.execute(
            insert(trainer_project_students_association),
            [
                {"trainer_project_id": project_id, "student_id": sid}
                for sid in student_ids
            ],
        )


async def get_trainer_project_by_session(
    db: AsyncSession, session_id: str
) -> Optional[TrainerProject]:
    sid = normalize_session_id(session_id)
    if not sid:
        return None
    return (
        await db.execute(
            select(TrainerProject)
            .options(selectinload(TrainerProject.students))
            .where(TrainerProject.session_id == sid)
        )
    ).scalar_one_or_none()


async def student_has_course_access(
    db: AsyncSession, *, student_id: int, course_session_id: str
) -> bool:
    project = await get_trainer_project_by_session(db, course_session_id)
    if project is None:
        return False
    return any(s.id == student_id for s in project.students)


async def trainer_owns_course_session(
    db: AsyncSession, *, trainer_id: int, course_session_id: str
) -> bool:
    sid = normalize_session_id(course_session_id)
    project = (
        await db.execute(
            select(TrainerProject.id).where(
                TrainerProject.session_id == sid,
                TrainerProject.trainer_id == trainer_id,
            )
        )
    ).scalar_one_or_none()
    return project is not None


async def user_can_access_session(
    db: AsyncSession, *, user: User, session_id: str
) -> bool:
    """True si el usuario es dueño de la sesión o alumno con curso compartido."""
    sid = normalize_session_id(session_id)
    if not sid:
        return False
    owner = owner_username_from_session(sid)
    if owner == user.username:
        return True
    if user.role != UserRole.ALUMNO:
        return False
    return await student_has_course_access(db, student_id=user.id, course_session_id=sid)


async def progress_session_for_user(
    db: AsyncSession, *, user: User, validated_session_id: str
) -> str:
    """Sesión donde persistir progreso/cuadrante para el usuario actual."""
    sid = normalize_session_id(validated_session_id)
    owner = owner_username_from_session(sid)
    if owner == user.username:
        return sid
    if user.role == UserRole.ALUMNO and await student_has_course_access(
        db, student_id=user.id, course_session_id=sid
    ):
        return student_course_progress_session(user.username, sid)
    return sid


async def publish_trainer_project(
    db: AsyncSession,
    *,
    trainer: User,
    session_id: str,
    name: str,
) -> TrainerProject:
    """Registra o actualiza el curso compartido y sincroniza alumnos asignados."""
    sid = normalize_session_id(session_id)
    owner = owner_username_from_session(sid)
    if owner != trainer.username:
        raise ValueError("La sesión del proyecto no pertenece al formador.")

    trainer_full = (
        await db.execute(
            select(User)
            .options(selectinload(User.students))
            .where(User.id == trainer.id)
        )
    ).scalar_one_or_none()
    if trainer_full is None:
        raise ValueError("Formador no encontrado.")

    project = await get_trainer_project_by_session(db, sid)
    student_ids = [s.id for s in trainer_full.students]
    if project is None:
        project = TrainerProject(
            trainer_id=trainer.id,
            name=name.strip() or "Curso compartido",
            session_id=sid,
        )
        db.add(project)
        await db.flush()
    else:
        project.name = name.strip() or project.name

    await _replace_project_students(db, project_id=project.id, student_ids=student_ids)
    await db.flush()
    return project


async def sync_student_to_all_trainer_projects(
    db: AsyncSession, *, trainer_id: int, student_id: int
) -> None:
    """Al asignar un alumno al formador, darle acceso a todos sus cursos publicados."""
    projects = (
        await db.execute(
            select(TrainerProject)
            .options(selectinload(TrainerProject.students))
            .where(TrainerProject.trainer_id == trainer_id)
        )
    ).scalars().all()
    student = (
        await db.execute(select(User).where(User.id == student_id))
    ).scalar_one_or_none()
    if student is None:
        return
    for project in projects:
        linked = (
            await db.execute(
                select(trainer_project_students_association.c.student_id).where(
                    trainer_project_students_association.c.trainer_project_id
                    == project.id,
                    trainer_project_students_association.c.student_id == student_id,
                )
            )
        ).first()
        if linked is None:
            await db.execute(
                insert(trainer_project_students_association).values(
                    trainer_project_id=project.id,
                    student_id=student_id,
                )
            )
    await db.flush()


def registry_documents_for_session(session_id: str) -> List[Dict[str, Any]]:
    """Lista documentos del registry para mostrar en el sidebar del alumno."""
    registry = load_document_registry(session_id)
    docs: List[Dict[str, Any]] = []
    for key, meta in registry.items():
        if not isinstance(meta, dict):
            continue
        doc_type = meta.get("type", "manual")
        if doc_type == "video":
            name = meta.get("title") or key
            doc_key = meta.get("video_id") or key
            source = "youtube"
        else:
            name = meta.get("title") or key
            doc_key = key
            source = "manual" if doc_type != "cloud" else "cloud"
        docs.append({"name": name, "doc_key": doc_key, "source": source})
    return docs


async def list_shared_projects_for_student(
    db: AsyncSession, *, student_id: int
) -> List[TrainerProject]:
    return (
        await db.execute(
            select(TrainerProject)
            .options(selectinload(TrainerProject.trainer))
            .where(TrainerProject.students.any(User.id == student_id))
            .order_by(TrainerProject.name.asc())
        )
    ).scalars().all()


async def teardown_shared_course(
    db: AsyncSession, *, course_session_id: str
) -> None:
    """Quita el curso compartido y el progreso de los alumnos al limpiar la sesión del formador."""
    sid = normalize_session_id(course_session_id)
    if not sid:
        return

    project = await get_trainer_project_by_session(db, sid)
    student_usernames = [s.username for s in project.students] if project else []

    if project is not None:
        await db.delete(project)

    itineraries = (
        await db.execute(select(CourseItinerary).where(CourseItinerary.session_id == sid))
    ).scalars().all()
    for itinerary in itineraries:
        await db.delete(itinerary)

    if student_usernames:
        from chat_manager import ChatHistoryManager
        from discovery_repo import clear_discovery_for_session

        chat_manager = ChatHistoryManager()
        for username in student_usernames:
            progress_sid = student_course_progress_session(username, sid)
            await db.execute(
                delete(StudentActivityLog).where(
                    StudentActivityLog.session_id == progress_sid
                )
            )
            await db.execute(
                delete(UnitProgress).where(UnitProgress.session_id == progress_sid)
            )
            await clear_discovery_for_session(db, progress_sid)
            await chat_manager.delete_history(progress_sid)

    await db.flush()
