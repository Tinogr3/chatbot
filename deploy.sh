#!/usr/bin/env bash
# deploy.sh — Despliega la aplicación usando .env.
# Uso: ./deploy.sh [--no-build]

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE=".env"
BUILD_FLAG="--build"

for arg in "$@"; do
  case "$arg" in
    --no-build) BUILD_FLAG="" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 1 ;;
  esac
done

# ── Colores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; RESET='\033[0m'
info()  { echo -e "${GREEN}[deploy]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[deploy]${RESET} $*"; }
error() { echo -e "${RED}[deploy] ERROR:${RESET} $*" >&2; }

# ── 1. Verificar prerrequisitos ────────────────────────────────────────────────
info "Verificando prerrequisitos..."

if ! command -v docker &>/dev/null; then
  error "Docker no encontrado. Instálalo en https://docs.docker.com/get-docker/"
  exit 1
fi
if ! docker compose version &>/dev/null; then
  error "Docker Compose (plugin) no disponible. Actualiza Docker Desktop."
  exit 1
fi

# ── 2. Verificar .env ─────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  error "No existe $ENV_FILE. Cópialo desde .env.example y rellena los valores."
  exit 1
fi

# ── 3. Validar que no queden placeholders sin reemplazar ──────────────────────
info "Validando $ENV_FILE..."

# Cadenas que los usuarios deben cambiar al configurar su .env.
PLACEHOLDERS=(
  "CAMBIA_ESTO"
  "cambia_esta_password"
  "cambia_esto_con"
  "tu-project-id"
  "tu-api-key"
  "tu-bucket-name"
)
for placeholder in "${PLACEHOLDERS[@]}"; do
  # Ignora líneas de comentario; muestra número y contenido de las que fallen.
  matches=$(awk -v p="$placeholder" '!/^\s*#/ && $0 ~ p {print NR": "$0}' "$ENV_FILE")
  if [[ -n "$matches" ]]; then
    error "El archivo $ENV_FILE contiene '$placeholder'. Reemplaza todos los valores antes de desplegar."
    echo "$matches" | while read -r line; do
      echo "  Línea $line" >&2
    done
    exit 1
  fi
done

# Leer variables necesarias del .env para validaciones posteriores
# shellcheck disable=SC2046
export $(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | xargs)

REQUIRED_VARS=(
  POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
  GOOGLE_API_KEY PROJECT_ID BUCKET_NAME
  JWT_SECRET_KEY ALLOWED_ORIGINS
)
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    error "La variable $var está vacía en $ENV_FILE."
    exit 1
  fi
done

# ── 4. Verificar archivo de credenciales GCP ──────────────────────────────────
GCP_CREDS="${GOOGLE_APPLICATION_CREDENTIALS:-}"
if [[ -z "$GCP_CREDS" || ! -f "$GCP_CREDS" ]]; then
  error "GOOGLE_APPLICATION_CREDENTIALS no apunta a un archivo válido: '${GCP_CREDS}'"
  exit 1
fi

# ── 5. Preparar directorio de datos del backend ───────────────────────────────
# El volumen bind-mount ./backend/data debe existir antes de docker compose up
# para que Docker no lo cree como root y el contenedor pueda escribir en él.
mkdir -p backend/data

# ── 6. Construir e iniciar contenedores ───────────────────────────────────────
info "Iniciando despliegue${BUILD_FLAG:+ (con build)}..."
docker compose --env-file "$ENV_FILE" up $BUILD_FLAG -d

# ── 7. Esperar a que los servicios críticos estén healthy ─────────────────────
wait_healthy() {
  local service="$1"
  local max_attempts="${2:-30}"
  local attempt=0

  echo -n "  Esperando a $service"
  while [[ $attempt -lt $max_attempts ]]; do
    # docker inspect es más fiable que parsear el JSON de "docker compose ps",
    # cuyo formato varía entre versiones de Docker Compose.
    local cid
    cid=$(docker compose ps -q "$service" 2>/dev/null | head -1)
    local status=""
    if [[ -n "$cid" ]]; then
      status=$(docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{end}}" "$cid" 2>/dev/null || echo "")
    fi

    if [[ "$status" == "healthy" ]]; then
      echo " ✓"
      return 0
    fi
    echo -n "."
    sleep 2
    (( attempt++ ))
  done

  echo ""
  error "Timeout esperando a que '$service' esté healthy (${max_attempts} intentos)."
  docker compose logs --tail=30 "$service" >&2
  return 1
}

info "Comprobando estado de los servicios..."
wait_healthy "db"      30
wait_healthy "redis"   15
wait_healthy "backend" 40

# ── 8. Esquema de base de datos ───────────────────────────────────────────────
# SQLAlchemy create_all() corre en el lifespan del backend (init_db).
# Las tablas se crean automáticamente en el primer arranque si no existen.
# Si en el futuro se añade Alembic, reemplaza este bloque por:
#   docker compose --env-file "$ENV_FILE" exec backend alembic upgrade head
info "Esquema de base de datos: gestionado por SQLAlchemy en el arranque del backend."

# ── 9. Estado final ───────────────────────────────────────────────────────────
info "Despliegue completado."
echo ""
docker compose ps
echo ""
info "Frontend: http://localhost:3000"
info "Backend:  http://localhost:8000/health"
echo ""
info "Ver logs en tiempo real:"
echo "  docker compose --env-file $ENV_FILE logs -f"
echo ""
info "Detener:"
echo "  docker compose --env-file $ENV_FILE down"
