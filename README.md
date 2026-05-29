# Chatbot RAG educativo

Aplicación web con **FastAPI** (backend), **Next.js** (frontend), **Celery** (tareas asíncronas) y **PostgreSQL + Redis**, orquestada con **Docker Compose**.

## Requisitos previos

| Herramienta | Versión mínima |
|-------------|----------------|
| [Docker Desktop](https://docs.docker.com/get-docker/) | 24+ |
| Docker Compose plugin | incluido con Docker Desktop |

No se necesita Python, Node ni Redis instalados en el host; todo corre dentro de los contenedores.

## Arranque rápido

### 1. Obtener las credenciales de Google Cloud

Descarga el JSON de la service account de GCP y colócalo en una ruta accesible de tu máquina (por ejemplo `/home/usuario/keys/service-account.json`). Necesitas una service account con permisos sobre Vertex AI / Gemini y Cloud Storage.

### 2. Copiar y configurar las variables de entorno

```bash
cp .env.example .env
```

Abre `.env` y rellena los valores obligatorios:

| Variable | Descripción |
|----------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | **Ruta absoluta** al JSON de la service account (p. ej. `/home/usuario/keys/service-account.json`) |
| `GOOGLE_API_KEY` | API key de Gemini (si usas la API de Gemini Developer en lugar de Vertex AI) |
| `PROJECT_ID` / `BUCKET_NAME` | Proyecto y bucket de Google Cloud |
| `POSTGRES_PASSWORD` | Contraseña segura para PostgreSQL |
| `ALLOWED_ORIGINS` | Dominio(s) del frontend separados por comas |
| `NEXT_PUBLIC_BACKEND_URL` | URL del backend vista desde el navegador (por defecto `http://localhost:8000`) |

### 3. Desplegar

```bash
chmod +x deploy.sh   # solo la primera vez
./deploy.sh
```

El script realiza los siguientes pasos:

1. Verifica que Docker y Docker Compose estén disponibles.
2. Valida que `.env` exista y no contenga valores sin reemplazar.
3. Construye las imágenes e inicia los contenedores en segundo plano.
4. Espera a que `db`, `redis` y `backend` superen el healthcheck.
5. Muestra el estado final con `docker compose ps`.

Accesos una vez levantado:

- Frontend: <http://localhost:3000>
- Backend / API: <http://localhost:8000/health>

### Redespliegue sin reconstruir imágenes (tras cambios de código)

```bash
./deploy.sh --no-build
```

## Operaciones habituales

```bash
# Ver logs en tiempo real (todos los servicios)
docker compose --env-file .env logs -f

# Ver logs de un servicio concreto
docker compose --env-file .env logs -f backend

# Detener y eliminar contenedores (los volúmenes de datos se conservan)
docker compose --env-file .env down

# Detener y eliminar también los volúmenes (¡borra la base de datos!)
docker compose --env-file .env down -v

# Reconstruir solo el backend tras cambios en el código
docker compose --env-file .env build backend
./deploy.sh --no-build
```

## Servicios

| Servicio | Imagen / Build | Puerto host | Descripción |
|----------|----------------|-------------|-------------|
| `db` | `postgres:15-alpine` | — | PostgreSQL; datos persistidos en el volumen `postgres_data` |
| `redis` | `redis:alpine` | — | Broker de Celery |
| `backend` | `./backend/Dockerfile` | 8000 | API FastAPI + Uvicorn |
| `worker` | `./backend/Dockerfile` | — | Worker Celery (PDFs, vídeos) |
| `frontend` | `./frontend/Dockerfile` | 3000 | Next.js en modo producción |

## Configuración avanzada

### URL del backend en el frontend

`NEXT_PUBLIC_BACKEND_URL` se fija en tiempo de compilación de Next.js (dentro del build de Docker). Si el backend está en un servidor remoto, actualiza el valor en `.env` **antes** de ejecutar `./deploy.sh` o `docker compose build frontend`.

### Credenciales GCP

El archivo JSON indicado en `GOOGLE_APPLICATION_CREDENTIALS` se monta como solo lectura en `/app/credentials.json` dentro de los contenedores `backend` y `worker`. No se copia a la imagen; debe existir en la ruta indicada cada vez que se arranquen los contenedores.

### Base de datos

Las tablas se crean automáticamente al primer arranque del backend (`SQLAlchemy create_all`). Si en el futuro se incorpora Alembic:

```bash
docker compose --env-file .env exec backend alembic upgrade head
```

## Documentación de arquitectura

Detalle de capas, carpetas y endpoints: **[ARQUITECTURA.md](ARQUITECTURA.md)**.
