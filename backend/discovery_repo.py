"""Persistencia del Discovery Hub: resúmenes y exámenes guardados por sesión."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import StoredExam, StoredSummary


async def add_stored_summary(
    db: AsyncSession,
    session_id: str,
    user_prompt: str,
    content: str,
) -> None:
    row = StoredSummary(
        session_id=session_id,
        user_prompt=(user_prompt or "")[:8000],
        content=content or "",
    )
    db.add(row)


async def add_stored_exam(
    db: AsyncSession,
    session_id: str,
    user_prompt: str,
    content: str,
) -> None:
    row = StoredExam(
        session_id=session_id,
        user_prompt=(user_prompt or "")[:8000],
        content=content or "",
    )
    db.add(row)


async def list_summaries(db: AsyncSession, session_id: str) -> list[StoredSummary]:
    stmt = (
        select(StoredSummary)
        .where(StoredSummary.session_id == session_id)
        .order_by(StoredSummary.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_summaries_by_ids_ordered(
    db: AsyncSession,
    session_id: str,
    summary_ids: list[int],
) -> list[StoredSummary]:
    """
    Resúmenes de la sesión con los IDs indicados, en el mismo orden que `summary_ids`
    (duplicados en la lista se ignoran tras la primera aparición).
    """
    deduped = list(dict.fromkeys(summary_ids))
    if not deduped:
        return []
    stmt = select(StoredSummary).where(
        StoredSummary.session_id == session_id,
        StoredSummary.id.in_(deduped),
    )
    result = await db.execute(stmt)
    by_id = {r.id: r for r in result.scalars().all()}
    missing = [i for i in deduped if i not in by_id]
    if missing:
        raise ValueError(f"summary_ids no válidos para esta sesión: {missing}")
    return [by_id[i] for i in deduped]


async def list_exams(db: AsyncSession, session_id: str) -> list[StoredExam]:
    stmt = (
        select(StoredExam)
        .where(StoredExam.session_id == session_id)
        .order_by(StoredExam.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_summaries(db: AsyncSession, session_id: str) -> int:
    stmt = select(func.count()).select_from(StoredSummary).where(StoredSummary.session_id == session_id)
    return int((await db.execute(stmt)).scalar_one() or 0)


async def count_exams(db: AsyncSession, session_id: str) -> int:
    stmt = select(func.count()).select_from(StoredExam).where(StoredExam.session_id == session_id)
    return int((await db.execute(stmt)).scalar_one() or 0)


async def clear_discovery_for_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(delete(StoredSummary).where(StoredSummary.session_id == session_id))
    await db.execute(delete(StoredExam).where(StoredExam.session_id == session_id))
