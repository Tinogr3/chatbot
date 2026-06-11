"""
Infraestructura de base de datos SQLAlchemy (async) para el módulo de competencias.

Mantiene una BD separada de chat_history.db para no interferir con el sistema
de historial/memoria existente.
"""
import os
from typing import AsyncGenerator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from logger import get_logger

logger = get_logger("database")


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


def _apply_schema_patches_sync(connection) -> None:
    """Parches incrementales que ``create_all()`` no aplica a tablas ya existentes.

    SQLAlchemy solo crea tablas nuevas; no añade columnas ni índices en tablas
    desplegadas previamente. Cada parche comprueba si el cambio ya está aplicado
    antes de ejecutar DDL (idempotente en cada arranque).
    """
    insp = inspect(connection)
    if not insp.has_table("learning_units"):
        return

    columns = {col["name"] for col in insp.get_columns("learning_units")}
    if "learning_outcome_id" in columns:
        return

    dialect = connection.dialect.name
    logger.info(
        "Aplicando parche de esquema: añadir learning_units.learning_outcome_id (%s)",
        dialect,
    )
    if dialect == "postgresql":
        # IF NOT EXISTS evita DuplicateColumnError con varios workers de Uvicorn
        # arrancando lifespan en paralelo.
        connection.execute(
            text(
                "ALTER TABLE learning_units "
                "ADD COLUMN IF NOT EXISTS learning_outcome_id INTEGER "
                "REFERENCES learning_outcomes(id) ON DELETE SET NULL"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_learning_units_outcome "
                "ON learning_units (learning_outcome_id)"
            )
        )
    else:
        # SQLite y otros: columna nullable; el FK se valida a nivel ORM.
        connection.execute(
            text(
                "ALTER TABLE learning_units "
                "ADD COLUMN learning_outcome_id INTEGER"
            )
        )


async def init_db() -> None:
    """Crea tablas nuevas y aplica parches de esquema incrementales (idempotente)."""
    import models  # noqa: F401 — registra todas las tablas en Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_apply_schema_patches_sync)
