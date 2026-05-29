"""
Infraestructura de base de datos SQLAlchemy (async) para el módulo de competencias.

Mantiene una BD separada de chat_history.db para no interferir con el sistema
de historial/memoria existente.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


def _resolve_database_url() -> str:
    """
    Resuelve la URL de conexión final según el entorno:
    - Si DATABASE_URL apunta a Postgres, normaliza el esquema a postgresql+asyncpg://
      (SQLAlchemy async no acepta los esquemas 'postgres://' ni 'postgresql://').
    - Si DATABASE_URL no está definida, usa SQLite local como fallback y crea
      el directorio necesario.
    """
    raw = os.getenv("DATABASE_URL", "").strip()

    if raw.startswith(("postgres://", "postgresql://")):
        # Garantizar esquema compatible con create_async_engine + asyncpg
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )

    if raw:
        # DATABASE_URL definida con otro esquema (ej. sqlite explícito): usar tal cual
        return raw

    # Fallback local: SQLite + aiosqlite
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(backend_dir, "data", "competency.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


DATABASE_URL: str = _resolve_database_url()

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Clase base declarativa para todos los modelos ORM de competencias."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency de FastAPI que provee una sesión async de BD."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Crea todas las tablas definidas en Base.metadata (idempotente)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
