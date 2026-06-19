"""
Utilidades de autenticación JWT y bcrypt.

Seguridad implementada:
  - Contraseñas hasheadas con bcrypt (cost factor 12)
  - Access token JWT HS256 con vida corta (15 min)
  - Refresh token opaco (SHA-256 en BD) con vida larga (7 días)
  - Bloqueo de cuenta tras 5 intentos fallidos (30 min)
  - Validación de propiedad de sesión: el X-Session-Id debe pertenecer al usuario autenticado
  - Tokens de refresco revocables en BD
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import RefreshToken, User, UserRole
from session_ids import normalize_session_id, owner_username_from_session

# ---------------------------------------------------------------------------
# Configuración (leer siempre de entorno, NUNCA harcodear)
# ---------------------------------------------------------------------------

_SECRET_KEY: str = os.environ.get("JWT_SECRET_KEY", "")
_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 30

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _get_secret() -> str:
    """Falla alto si JWT_SECRET_KEY no está configurada en producción."""
    key = _SECRET_KEY or os.environ.get("JWT_SECRET_KEY", "")
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY no está configurada. "
            "Genera una clave segura y añádela a tu .env."
        )
    return key


# ---------------------------------------------------------------------------
# Contraseñas
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Tokens JWT
# ---------------------------------------------------------------------------

def create_access_token(sub: str) -> str:
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": sub,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, _get_secret(), algorithm=_ALGORITHM)


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token() -> tuple[str, str]:
    """Devuelve (token_raw, token_hash). Solo se guarda el hash en BD."""
    raw = secrets.token_urlsafe(48)
    return raw, _hash_token(raw)


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extrae y valida el Bearer token del header Authorization.
    Devuelve el usuario autenticado o lanza 401.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_error

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[_ALGORITHM])
    except JWTError:
        raise credentials_error

    if payload.get("type") != "access":
        raise credentials_error

    username: str | None = payload.get("sub")
    if not username:
        raise credentials_error

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error

    return user


async def require_formador(
    current_user: User = Depends(get_current_user),
) -> User:
    """Solo permite acceso a usuarios con rol FORMADOR."""
    if current_user.role != UserRole.FORMADOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los formadores pueden acceder a este recurso.",
        )
    return current_user


async def require_alumno(
    current_user: User = Depends(get_current_user),
) -> User:
    """Solo permite acceso a usuarios con rol ALUMNO."""
    if current_user.role != UserRole.ALUMNO:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los alumnos pueden acceder a este recurso.",
        )
    return current_user


async def get_validated_session(
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    Valida que el X-Session-Id pertenece al usuario autenticado o a un curso
    compartido del formador (alumno asignado) y devuelve el session_id normalizado.
    """
    from services.trainer_project_service import user_can_access_session

    session_id = normalize_session_id(x_session_id or "")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Session-Id requerido.",
        )

    if await user_can_access_session(db, user=current_user, session_id=session_id):
        return session_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para acceder a esta sesión.",
    )


# ---------------------------------------------------------------------------
# Lógica de bloqueo de cuenta
# ---------------------------------------------------------------------------

def _utc_now() -> datetime:
    """Devuelve la hora UTC actual como datetime naive (sin tzinfo).
    Las columnas TIMESTAMP WITHOUT TIME ZONE de PostgreSQL requieren naive datetimes.
    Las comparaciones internas del código añaden tzinfo cuando es necesario.
    """
    return datetime.now(tz=timezone.utc).replace(tzinfo=None)


def is_account_locked(user: User) -> bool:
    if user.locked_until is None:
        return False
    locked_until = user.locked_until
    if locked_until.tzinfo is not None:
        locked_until = locked_until.replace(tzinfo=None)
    return _utc_now() < locked_until


async def record_failed_login(user: User, db: AsyncSession) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
        user.locked_until = _utc_now() + timedelta(minutes=LOCKOUT_MINUTES)
    await db.flush()


async def reset_failed_login(user: User, db: AsyncSession) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _utc_now()
    await db.flush()


# ---------------------------------------------------------------------------
# Gestión de refresh tokens
# ---------------------------------------------------------------------------

async def save_refresh_token(
    user: User,
    token_hash: str,
    db: AsyncSession,
) -> None:
    expires_at = _utc_now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(rt)
    await db.flush()


async def validate_and_rotate_refresh_token(
    raw_token: str,
    db: AsyncSession,
) -> User:
    """
    Valida el refresh token, lo revoca (rotación), y devuelve el usuario.
    Lanza 401 si es inválido, expirado o revocado.
    """
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()

    now = _utc_now()
    expires_at = rt.expires_at if rt else None
    if expires_at is not None and expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)

    if rt is None or rt.is_revoked or (expires_at is not None and now > expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    rt.is_revoked = True
    await db.flush()

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )

    return user


async def revoke_refresh_token(raw_token: str, db: AsyncSession) -> None:
    token_hash = _hash_token(raw_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    rt = result.scalar_one_or_none()
    if rt:
        rt.is_revoked = True
        await db.flush()
