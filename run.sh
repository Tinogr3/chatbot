#!/usr/bin/env bash
# Arranca backend (FastAPI) y frontend (Next.js) con un solo comando.
# Usa el entorno virtual venv para el backend.
# Al salir (Ctrl+C), se detienen ambos.
#
# Para procesamiento asíncrono de PDFs y videos (Celery):
#   1. Inicia Redis: redis-server (o docker run -p 6379:6379 redis)
#   2. En otra terminal, desde la raíz: source venv/bin/activate && celery -A backend.worker worker --loglevel=info

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d "venv" ]]; then
  echo "No se encuentra venv. Crea uno con: python3 -m venv venv"
  exit 1
fi

source venv/bin/activate

# Dependencias del backend con venv
if ! python -c "import fastapi" 2>/dev/null; then
  echo "Instalando dependencias del backend en venv..."
  pip install -q -r backend/requirements.txt
fi

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Liberar puerto del backend si está en uso
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

cleanup() {
  echo ""
  echo "Deteniendo backend (PID $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  if [[ -n "$FRONTEND_PID" ]]; then
    echo "Deteniendo frontend (PID $FRONTEND_PID)..."
    kill "$FRONTEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
  fi
  exit 0
}
trap cleanup EXIT INT TERM

sleep 5
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

# Frontend Next.js (frontend/): instalar deps si hace falta y arrancar
if [[ ! -d "frontend/node_modules" ]]; then
  echo "Instalando dependencias del frontend (npm install)..."
  (cd frontend && npm install)
fi

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
PORT="$FRONTEND_PORT" npm run dev &
FRONTEND_PID=$!
cd "$PROJECT_ROOT"
wait $FRONTEND_PID
