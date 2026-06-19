"""
Endpoints de autenticación:
  POST /auth/register  — Crear cuenta
  POST /auth/login     — Iniciar sesión (access token en body + refresh en cookie httpOnly)
  POST /auth/refresh   — Renovar access token usando la cookie de refresco
  POST /auth/logout    — Revocar refresh token y limpiar cookie
  GET  /auth/me        — Datos del usuario autenticado
"""
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_limiter = Limiter(key_func=get_remote_address)

from auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    is_account_locked,
    record_failed_login,
    reset_failed_login,
    revoke_refresh_token,
    save_refresh_token,
    validate_and_rotate_refresh_token,
    verify_password,
)
from config import get_app_settings
from database import get_db
from logger import get_logger
from models import User, UserRole
from schemas import TokenResponse, UserCreate, UserLogin, UserOut

logger = get_logger("api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "rt"
_COOKIE_MAX_AGE = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600


def _set_refresh_cookie(response: Response, token: str) -> None:
    secure = get_app_settings().cookie_secure
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    secure = get_app_settings().cookie_secure
    response.delete_cookie(
        key=_REFRESH_COOKIE,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/auth",
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cuenta nueva",
)
@_limiter.limit("5/hour")
async def register(
    request: Request,
    body: UserCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    existing = await db.execute(
        select(User).where(User.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "El nombre de usuario ya está en uso. "
            ),
        )

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=UserRole(body.role.value),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(sub=user.username)
    raw_rt, rt_hash = create_refresh_token()
    await save_refresh_token(user, rt_hash, db)

    _set_refresh_cookie(response, raw_rt)
    logger.info("Nuevo usuario registrado: %s", user.username)

    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Iniciar sesión",
)
@_limiter.limit("10/minute")
async def login(
    request: Request,
    body: UserLogin,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        # Tiempo constante para no revelar si el usuario existe
        hash_password("dummy_timing_protection")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos.",
        )

    if is_account_locked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=(
                "Cuenta bloqueada temporalmente por exceso de intentos fallidos. "
                "Inténtalo de nuevo en unos minutos."
            ),
        )

    if not verify_password(body.password, user.hashed_password):
        await record_failed_login(user, db)
        remaining = max(0, 5 - (user.failed_login_attempts or 0))
        detail = (
            f"Usuario o contraseña incorrectos. "
            f"Te quedan {remaining} intento(s) antes del bloqueo temporal."
            if remaining > 0
            else "Cuenta bloqueada temporalmente. Inténtalo de nuevo en 30 minutos."
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

    await reset_failed_login(user, db)

    access_token = create_access_token(sub=user.username)
    raw_rt, rt_hash = create_refresh_token()
    await save_refresh_token(user, rt_hash, db)

    _set_refresh_cookie(response, raw_rt)
    logger.info("Login exitoso: %s", user.username)

    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renovar access token",
)
async def refresh(
    response: Response,
    rt: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not rt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token no encontrado.",
        )

    user = await validate_and_rotate_refresh_token(rt, db)

    access_token = create_access_token(sub=user.username)
    raw_rt_new, rt_hash_new = create_refresh_token()
    await save_refresh_token(user, rt_hash_new, db)

    _set_refresh_cookie(response, raw_rt_new)

    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cerrar sesión",
)
async def logout(
    response: Response,
    rt: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> None:
    if rt:
        await revoke_refresh_token(rt, db)
    _clear_refresh_cookie(response)
    logger.info("Logout ejecutado")


@router.get(
    "/me",
    response_model=UserOut,
    summary="Datos del usuario autenticado",
)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)
