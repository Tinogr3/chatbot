FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300

WORKDIR /app

# ffmpeg: openai-whisper, yt-dlp
# libmagic1, poppler-utils, tesseract-ocr: unstructured[pdf]
# build-essential: compilación nativa de chromadb y similares
# curl: healthcheck en docker-compose
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libmagic1 \
        poppler-utils \
        tesseract-ocr \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Capa 1: paquetes ligeros del servidor y BD (cambian poco, cachean bien) ───
RUN pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    python-multipart>=0.0.6 \
    httpx>=0.26.0 \
    python-dotenv>=1.0.0 \
    pydantic>=2.0.0 \
    sqlalchemy>=2.0.0 \
    aiosqlite>=0.20.0 \
    asyncpg>=0.29.0 \
    psycopg2-binary>=2.9.0 \
    celery[redis]>=5.3.0 \
    redis>=5.0.0

# ── Capa 2: LangChain y Google Cloud (actualizaciones frecuentes) ─────────────
RUN pip install --no-cache-dir \
    langchain>=0.3.0 \
    langchain-community>=0.3.0 \
    langchain-google-genai>=1.0.0 \
    langchain-text-splitters>=0.2.0 \
    langchain-chroma>=0.1.2 \
    langchain-core>=0.2.0 \
    langgraph>=0.0.10 \
    google-cloud-storage>=2.14.0 \
    google-auth>=2.27.0 \
    gTTS>=2.5.0

# ── Capa 3: PDF y Chroma (compilación nativa, tarda pero cachea) ──────────────
RUN pip install --no-cache-dir \
    chromadb>=0.4.22 \
    pypdf>=4.0.0 \
    pymupdf>=1.23.0 \
    pillow>=10.0.0 \
    unstructured[pdf]>=0.12.0

# ── Capa 4: PyTorch CPU-only explícito antes de Whisper ───────────────────────
# Sin esto, pip instala la versión CUDA (~2 GB extra innecesarios en servidor).
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# ── Capa 5: Whisper y YouTube (dependen de torch de la capa anterior) ─────────
RUN pip install --no-cache-dir \
    openai-whisper>=20231117 \
    youtube-transcript-api>=0.6.0 \
    yt-dlp>=2024.1.0

COPY . .

RUN addgroup --system --gid 1001 appgroup \
 && adduser  --system --uid 1001 --ingroup appgroup appuser \
 && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
