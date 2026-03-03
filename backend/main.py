"""
API FastAPI - Backend del Chatbot RAG Educativo.
Ejecutar: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import os
import sys
from typing import Any, Dict

# Asegurar que el directorio backend esté en el path al ejecutar desde raíz del proyecto
if __name__ == "__main__" or os.path.basename(os.getcwd()) != "backend":
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

# Cargar .env desde la raíz del proyecto (para GOOGLE_APPLICATION_CREDENTIALS, BUCKET_NAME, etc.)
try:
    from dotenv import load_dotenv
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _env_path = os.path.join(_project_root, ".env")
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except Exception:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from logger import setup_logging
from api.chat import router as chat_router
from api.upload import router as upload_router
from api.video import router as video_router
from api.history import router as history_router
from api.user_facts import router as user_facts_router
from api.session import router as session_router

setup_logging()

app = FastAPI(
    title="Chatbot RAG Educativo API",
    description="API backend para el chatbot RAG educativo (chat, upload, process_video, history, user_facts)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(video_router)
app.include_router(history_router)
app.include_router(user_facts_router)
app.include_router(session_router)


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check del API."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
