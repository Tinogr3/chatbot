#!/usr/bin/env bash
# Arranca backend (Uvicorn/FastAPI), frontend (Next.js) y worker (Celery) en background.
# Al salir (Ctrl+C), se detienen absolutamente todos los subprocesos asociados.

set -euo pipefail
IFS=$'\n\t'

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -d "venv" ]]; then
  echo "No se encuentra venv. Crea uno con: python3 -m venv venv" >&2
  exit 1
fi

source venv/bin/activate

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
REDIS_HOST="${REDIS_HOST:-127.0.0.1}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_AUTO_START="${REDIS_AUTO_START:-1}"

free_port_if_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local old_pid
    old_pid="$(lsof -t -i:"$port" 2>/dev/null || true)"
    if [[ -n "${old_pid:-}" ]]; then
      echo "Liberando puerto $port (proceso $old_pid)..." >&2
      kill "$old_pid" 2>/dev/null || true
      sleep 1
    fi
  fi
}

is_redis_running() {
  if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
      return 0
    fi
  fi

  if command -v nc >/dev/null 2>&1; then
    if nc -z -w 1 "$REDIS_HOST" "$REDIS_PORT" >/dev/null 2>&1; then
      return 0
    fi
  fi

  return 1
}

ensure_redis_running() {
  if is_redis_running; then
    return 0
  fi

  if [[ "$REDIS_AUTO_START" != "1" ]]; then
    cat >&2 <<EOF
Redis no está disponible en ${REDIS_HOST}:${REDIS_PORT} y REDIS_AUTO_START=0.
Arranca Redis localmente (ejemplos):
  - redis-server
  - docker run --rm -p ${REDIS_PORT}:${REDIS_PORT} redis
EOF
    exit 1
  fi

  if ! command -v redis-server >/dev/null 2>&1; then
    cat >&2 <<EOF
Redis no está disponible en ${REDIS_HOST}:${REDIS_PORT}, y no se encontró redis-server en PATH.
Instala Redis o usa REDIS_AUTO_START=0 para que falle rápido.
EOF
    exit 1
  fi

  echo "Redis no estaba corriendo; arrancando redis-server (${REDIS_HOST}:${REDIS_PORT})..." >&2
  redis-server --port "$REDIS_PORT" --bind "$REDIS_HOST" --save "" --appendonly no &
  REDIS_PID=$!
  PIDS+=("$REDIS_PID")

  # Esperar a que Redis responda.
  for _ in $(seq 1 20); do
    if is_redis_running; then
      return 0
    fi
    sleep 1
  done

  echo "Timeout arrancando redis-server en ${REDIS_HOST}:${REDIS_PORT}." >&2
  kill "$REDIS_PID" 2>/dev/null || true
  exit 1
}

install_backend_deps_if_needed() {
  if ! python -c "import fastapi" 2>/dev/null; then
    echo "Instalando dependencias del backend en venv..." >&2
    pip install -q -r backend/requirements.txt
  fi
}

start_backend() {
  echo "Iniciando backend en http://localhost:${BACKEND_PORT} ..."
  uvicorn backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
  BACKEND_PID=$!
  PIDS+=("$BACKEND_PID")
}

start_celery_worker() {
  echo "Iniciando worker Celery (Redis: ${REDIS_HOST}:${REDIS_PORT})..."
  # Concurrency: procesos en paralelo (cada tarea puede ser un PDF grande).
  # Prefetch 1: no acumular muchas tareas pesadas en un solo proceso (menos picos de RAM).
  : "${CELERY_WORKER_CONCURRENCY:=2}"
  : "${CELERY_PREFETCH_MULTIPLIER:=1}"
  celery -A backend.worker worker \
    --loglevel=info \
    --concurrency="${CELERY_WORKER_CONCURRENCY}" \
    --prefetch-multiplier="${CELERY_PREFETCH_MULTIPLIER}" &
  CELERY_PID=$!
  PIDS+=("$CELERY_PID")
}

start_frontend() {
  if [[ ! -d "frontend/node_modules" ]]; then
    echo "Instalando dependencias del frontend (npm install)..."
    (cd frontend && npm install)
  fi

  echo "Iniciando frontend en http://localhost:${FRONTEND_PORT} ..."
  cd frontend
  PORT="$FRONTEND_PORT" npm run dev &
  FRONTEND_PID=$!
  PIDS+=("$FRONTEND_PID")
  cd "$PROJECT_ROOT"
}

PIDS=()

# Apaga job control para que los procesos en background hereden el PGID del script.
set +m

PGID="$(ps -o pgid= -p $$ | tr -d ' ')"
CLEANED_UP="${CLEANED_UP:-0}"

cleanup() {
  if [[ "$CLEANED_UP" -eq 1 ]]; then
    return 0
  fi
  CLEANED_UP=1

  set +e
  echo ""
  echo "Limpieza: deteniendo servicios (PGID=$PGID)..."

  # Evita que nuestro propio shell dispare traps de nuevo mientras matamos el PGID.
  trap '' INT TERM

  # Señalamos el grupo completo para evitar procesos huérfanos.
  if [[ -n "${PGID:-}" ]]; then
    kill -TERM -- "-$PGID" 2>/dev/null || true
    sleep 2
    kill -KILL -- "-$PGID" 2>/dev/null || true
  fi

  # Reap de PIDs registrados (evita zombies de hijos directos).
  for pid in "${PIDS[@]:-}"; do
    wait "$pid" 2>/dev/null || true
  done

  # Restaura traps (especialmente útil cuando `cleanup` corre por EXIT).
  trap 'on_signal INT' INT
  trap 'on_signal TERM' TERM
}

on_signal() {
  local sig="$1"
  cleanup
  # 130 es el código estándar para SIGINT.
  if [[ "$sig" == "INT" ]]; then
    exit 130
  fi
  exit 143
}

trap 'on_signal INT' INT
trap 'on_signal TERM' TERM
trap 'cleanup' EXIT

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"

ensure_redis_running
install_backend_deps_if_needed

free_port_if_in_use "$BACKEND_PORT"
free_port_if_in_use "$FRONTEND_PORT"

start_backend
sleep 2

echo -n "Esperando al backend"
for i in $(seq 1 60); do
  if curl -s "http://localhost:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    echo ""
    echo "Backend listo."
    break
  fi
  if [[ $i -eq 60 ]]; then
    echo ""
    echo "El backend no respondió a tiempo (60 s)." >&2
    exit 1
  fi
  echo -n "."
  sleep 1
done

start_celery_worker
start_frontend

echo "Servicios levantados. Ctrl+C para detener."

# Mantener el script vivo hasta que uno de los servicios termine.
while true; do
  if ! wait -n "${PIDS[@]}"; then
    echo "Un servicio terminó con error; cerrando todo..." >&2
    exit 1
  fi
  echo "Un servicio terminó; cerrando todo..." >&2
  exit 0
done
