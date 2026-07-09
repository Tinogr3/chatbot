# Arquitectura — Chatbot RAG educativo

El proyecto separa **backend** (API FastAPI + Celery + RAG), **frontend** (Next.js) e infraestructura (**PostgreSQL**, **Redis**, **Chroma**). El navegador solo habla con el backend por HTTP.

Instrucciones de arranque: **[README.md](README.md)**.

## Frontend (Next.js)

- **Autenticación:** JWT (access token en memoria, refresh en cookie httpOnly). Ver `AuthContext`.
- **Sesión de datos:** el header `X-Session-Id` identifica el proyecto o curso activo (`username__projectId` en proyectos propios; sesión del formador en cursos compartidos).
- **Cliente HTTP:** `frontend/src/lib/http.ts` (fetch, errores) y `frontend/src/lib/api.ts` (endpoints).
- **URL del API:** `NEXT_PUBLIC_BACKEND_URL` (incrustada en build).

## Estructura de carpetas

```
cotutor-ia/
├── backend/
│   ├── api/              # Routers por dominio
│   ├── services/         # Lógica de negocio
│   ├── alembic/          # Migraciones
│   ├── main.py           # App FastAPI
│   ├── models.py, schemas.py, database.py
│   ├── rag_engine.py, router.py, worker.py
│   └── data/             # Runtime (Chroma, SQLite; no versionar)
├── frontend/
│   └── src/
│       ├── app/          # App Router
│       ├── components/
│       ├── context/      # Auth, User, Projects
│       ├── hooks/
│       └── lib/          # api, http, config
├── docker-compose.yml
├── deploy.sh
├── .env.example
└── README.md
```

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/auth/login`, `/auth/register`, `/auth/refresh` | Autenticación |
| POST | `/chat` | Chat con RAG |
| POST | `/upload`, `/upload/load_cloud`, `/process_video` | Ingesta de documentos (Celery) |
| GET | `/status/{task_id}` | Estado de tarea (requiere JWT) |
| GET/DELETE | `/history` | Historial de chat |
| POST | `/session/clear` | Limpieza de sesión |
| GET | `/dashboard/competencies` | Dashboard de competencias |
| GET/POST | `/discovery/*` | Hub de descubrimiento |
| POST/GET | `/trainer/*` | Módulo formador (itinerario, alumnos, progreso) |
| GET | `/student/*` | Cursos compartidos y progreso del alumno |

Detalle de cuerpos y cabeceras: routers en `backend/api/` y `backend/schemas.py`.

## Despliegue

```bash
cp .env.example .env   # rellenar valores
./deploy.sh
```

Docker Compose levanta `db`, `redis`, `backend`, `worker` y `frontend`. El esquema relacional se crea en el arranque (`init_db`); migraciones opcionales con Alembic.
