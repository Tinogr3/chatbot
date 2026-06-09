# Arquitectura — Chatbot RAG educativo

El proyecto separa **backend** (API FastAPI + Celery + RAG), **frontend** (Next.js) y la infraestructura de datos (**PostgreSQL**, **Redis**, **Chroma**). El frontend solo se comunica con el backend por HTTP; no contiene la lógica de RAG ni acceso directo a bases de datos.

Instrucciones de arranque y configuración: **[README.md](README.md)**.

## Frontend (Next.js)

La aplicación web corre en el navegador (React, App Router de Next.js). El estado de sesión se persiste en **sessionStorage** (por ejemplo el identificador bajo la clave `cotutor_session_id` en `UserContext`). Las peticiones al API incluyen el header **`X-Session-Id`** (y donde aplique `session_id` en el cuerpo) para alinear historial, documentos y hechos con la misma sesión.

La URL del backend en el cliente se configura con **`NEXT_PUBLIC_BACKEND_URL`** (por defecto `http://localhost:8000`). El cliente HTTP centralizado está en `frontend/src/lib/api.ts`.

## Estructura de carpetas (raíz del repositorio)

```
chatbot-test/
├── backend/                      # API FastAPI, worker Celery, RAG
│   ├── Dockerfile                # Imagen del backend y worker
│   ├── requirements.txt          # Dependencias Python
│   ├── main.py                   # App FastAPI, CORS, routers
│   ├── config.py                 # Variables de entorno y ajustes HTTP
│   ├── schemas.py                # Modelos Pydantic
│   ├── database.py               # SQLAlchemy async, sesiones
│   ├── models.py                 # Modelos ORM
│   ├── rag_engine.py             # RAG, embeddings, Chroma, agente
│   ├── router.py                 # Enrutado de consultas
│   ├── evaluation_engine.py      # Evaluación de respuestas (aprendizaje)
│   ├── media_processor.py        # YouTube, transcripciones
│   ├── chat_manager.py           # Historial
│   ├── user_memory.py            # Memoria de usuario
│   ├── document_registry.py      # Registro de documentos por sesión
│   ├── discovery_repo.py         # Datos del hub de descubrimiento
│   ├── gcs_utils.py              # Google Cloud Storage
│   ├── worker.py                 # App Celery
│   ├── logger.py
│   ├── exceptions.py
│   ├── api/                      # Routers por dominio
│   └── data/                     # Datos en runtime (Chroma, SQLite — ignorados por git)
│
├── frontend/                     # Cliente Next.js (TypeScript)
│   ├── Dockerfile                # Build multietapa (builder + runner)
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/                  # App Router (layout, page, estilos)
│   │   ├── components/           # UI: chat, sidebar, upload, dashboard, auth…
│   │   ├── context/              # ProjectsContext, UserContext
│   │   ├── hooks/                # p. ej. useChat
│   │   ├── lib/                  # api.ts, progressEvents.ts
│   │   ├── locales/              # Cadenas (es, index)
│   │   └── constants/            # p. ej. dashboardConfig
│   └── public/                   # Activos estáticos
│
├── docker-compose.yml            # Orquestación de todos los servicios
├── deploy.sh                     # Script de despliegue (valida, construye, arranca)
├── .env                          # Variables reales de entorno (no versionar)
├── .env.example                  # Plantilla para crear .env
├── ARQUITECTURA.md               # Este documento
└── README.md                     # Guía de uso y arranque
```

## Endpoints principales del backend

Prefijos de router salvo donde se indique lo contrario. Donde aplica, enviar **`X-Session-Id`** coherente con el cliente.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Salud del servicio |
| POST | `/chat` | Mensaje de chat (RAG, opciones de aprendizaje, etc.) |
| POST | `/upload` | Subida de PDF (multipart; encola Celery → `task_id`) |
| POST | `/upload/load_cloud` | Encolar PDFs desde GCS |
| POST | `/process_video` | Encolar vídeo de YouTube |
| GET | `/status/{task_id}` | Estado de tareas Celery |
| GET | `/history` | Historial de mensajes |
| DELETE | `/history` | Borrar historial |
| GET | `/user_facts` | Hechos inferidos |
| DELETE | `/user_facts` | Borrar hechos |
| POST | `/session/clear` | Limpiar sesión (historial, registry, Chroma asociado) |
| POST | `/evaluate` | Evaluar respuesta de aprendizaje y persistir progreso |
| GET | `/dashboard/competencies` | Datos agregados del dashboard de competencias |
| GET | `/discovery/stats` | Estadísticas del hub de descubrimiento |
| GET | `/discovery/summaries` | Listado tipo resúmenes |
| GET | `/discovery/exams` | Listado tipo exámenes |
| POST | `/discovery/podcast-audio` | Generación de audio para podcast |

Para el detalle de cuerpos y cabeceras, conviene revisar los routers en `backend/api/` y los esquemas en `schemas.py`.

## Flujo de despliegue

Todo se arranca con un único comando desde la raíz:

```bash
./deploy.sh
```

Esto ejecuta `docker compose --env-file .env up --build -d` tras validar el entorno. Docker Compose levanta los cinco servicios (`db`, `redis`, `backend`, `worker`, `frontend`) con sus healthchecks y dependencias en orden. Ver **[README.md](README.md)** para variables de configuración, operaciones habituales y notas sobre credenciales GCP.
