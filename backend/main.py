import os
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Dict

backend_dir = os.path.dirname(os.path.abspath(__file__))
# Garantiza imports planos (p. ej. `from session_ids import ...`)
# independientemente del cwd con el que Uvicorn arranque.
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(backend_dir), ".env")
if os.path.isfile(_env_path):
    load_dotenv(_env_path)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import get_http_settings
from logger import setup_logging
from rag_engine import set_rag_thread_pool
from api.auth import router as auth_router
from api.chat import router as chat_router
from api.upload import router as upload_router
from api.video import router as video_router
from api.history import router as history_router
from api.user_facts import router as user_facts_router
from api.session import router as session_router
from api.tasks import router as tasks_router
from api.evaluation import router as evaluation_router
from api.dashboard import router as dashboard_router
from api.discovery import router as discovery_router

limiter = Limiter(key_func=get_remote_address)

setup_logging()

_http = get_http_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from database import init_db
    await init_db()

    workers = max(1, int(os.getenv("RAG_THREAD_POOL_WORKERS", "4")))
    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rag_pool")
    set_rag_thread_pool(executor)
    yield
    set_rag_thread_pool(None)
    executor.shutdown(wait=True)


app = FastAPI(
    title="Chatbot RAG Educativo API",
    description="API backend para el chatbot RAG educativo (chat, upload, process_video, history, user_facts)",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Convierte los errores de validación de Pydantic en mensajes legibles."""
    messages: list[str] = []
    for error in exc.errors():
        field = " → ".join(str(loc) for loc in error.get("loc", []) if loc != "body")
        msg = error.get("msg", "Valor inválido")
        # Limpiar el prefijo genérico "Value error, " que añade Pydantic
        msg = msg.removeprefix("Value error, ")
        if field:
            messages.append(f"{field}: {msg}")
        else:
            messages.append(msg)
    detail = " | ".join(messages) if messages else "Datos de entrada inválidos."
    return JSONResponse(
        status_code=422,
        content={"detail": detail},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_http.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(video_router)
app.include_router(history_router)
app.include_router(user_facts_router)
app.include_router(session_router)
app.include_router(tasks_router)
app.include_router(evaluation_router)
app.include_router(dashboard_router)
app.include_router(discovery_router)


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
