#!/usr/bin/env bash
# Arranca backend (en segundo plano) y frontend con un solo comando.
# Al salir (Ctrl+C o cerrar Streamlit), se detiene también el backend.
#
# Para procesamiento asíncrono de PDFs y videos (Celery):
#   1. Inicia Redis: redis-server (o docker run -p 6379:6379 redis)
#   2. En otra terminal, desde la raíz del proyecto: celery -A backend.worker worker --loglevel=info
#   Opcional: CELERY_BROKER_URL=redis://localhost:6379/0 en .env

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d "venv" ]]; then
  echo "No se encuentra venv. Crea uno con: python3 -m venv venv"
  exit 1
fi

source venv/bin/activate

# Asegurar dependencias del backend (celery, redis, etc.) para que uvicorn arranque
if ! python -c "import celery" 2>/dev/null; then
  echo "Instalando dependencias del backend (incl. Celery/Redis)..."
  pip install -q -r backend/requirements.txt
fi

# Puerto del backend (por si quieres cambiarlo)
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${STREAMLIT_SERVER_PORT:-8501}"

# Liberar el puerto si ya está en uso (p. ej. backend anterior)
if command -v lsof >/dev/null 2>&1; then
  OLD_PID=$(lsof -t -i:"${BACKEND_PORT}" 2>/dev/null || true)
  if [[ -n "$OLD_PID" ]]; then
    echo "Liberando puerto ${BACKEND_PORT} (proceso $OLD_PID)..."
    kill $OLD_PID 2>/dev/null || true
    sleep 1
  fi
fi

echo "Iniciando backend en http://localhost:${BACKEND_PORT} ..."
uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# Al salir (Ctrl+C o cierre normal), matar el backend
cleanup() {
  echo ""
  echo "Deteniendo backend (PID $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  exit 0
}
trap cleanup EXIT INT TERM

# Dar tiempo a que el proceso arranque (importaciones pesadas: LangChain, Chroma, etc.)
sleep 5

# Esperar a que el backend responda (hasta 60 s, comprobando cada segundo)
echo -n "Esperando al backend"
for i in $(seq 1 60); do
  if curl -s "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    echo ""
    echo "Backend listo."
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo ""
    echo "El backend no respondió a tiempo (60 s)."
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
  fi
  echo -n "."
  sleep 1
done

# Liberar el puerto del frontend si ya está en uso (p. ej. Streamlit anterior)
if command -v lsof >/dev/null 2>&1; then
  OLD_FRONTEND_PID=$(lsof -t -i:"${FRONTEND_PORT}" 2>/dev/null || true)
  if [[ -n "$OLD_FRONTEND_PID" ]]; then
    echo "Liberando puerto ${FRONTEND_PORT} (proceso $OLD_FRONTEND_PID)..."
    kill $OLD_FRONTEND_PID 2>/dev/null || true
    sleep 1
  fi
fi

echo "Iniciando frontend en http://localhost:${FRONTEND_PORT} ..."
cd frontend
exec streamlit run app.py --server.port "${FRONTEND_PORT}"
