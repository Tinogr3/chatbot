# Arquitectura cliente-servidor — Chatbot RAG educativo

El proyecto separa **backend** (API FastAPI) y **frontend** (Next.js). El frontend solo se comunica con el backend por HTTP; no contiene la lógica de RAG ni acceso directo a bases de datos del servidor.

## Frontend (Next.js)

La aplicación web corre en el navegador (React 19, App Router de Next.js). El estado de sesión del usuario se persiste en **sessionStorage** (por ejemplo, el identificador bajo la clave `cotutor_session_id` gestionada en `UserContext`). Las peticiones al API incluyen el header **`X-Session-Id`** (y, donde corresponde, `session_id` en el cuerpo) para alinear historial, documentos y hechos con la misma sesión.

La URL del backend en el cliente se configura con la variable de entorno **`NEXT_PUBLIC_BACKEND_URL`** (por defecto `http://localhost:8000`). El cliente HTTP centralizado vive en `frontend/src/lib/api.ts`.

## Estructura de carpetas sugerida

```
chatbot-test/
├── backend/                         # API FastAPI
│   ├── main.py                      # App FastAPI, CORS, montaje de routers
│   ├── config.py                    # Credenciales y variables de entorno
│   ├── schemas.py                   # Modelos Pydantic compartidos
│   ├── rag_engine.py                # RAG, embeddings, Chroma, agente
│   ├── router.py                    # Enrutado de consultas, aprendizaje
│   ├── media_processor.py           # YouTube, transcripciones
│   ├── chat_manager.py              # Historial SQLite
│   ├── user_memory.py               # Memoria de usuario SQLite
│   ├── document_registry.py         # Registro de documentos por sesión
│   ├── gcs_utils.py                 # Google Cloud Storage
│   ├── worker.py                    # App Celery (tareas asíncronas)
│   ├── logger.py
│   ├── exceptions.py
│   ├── api/
│   │   ├── chat.py                  # POST /chat
│   │   ├── upload.py                # POST /upload, POST /upload/load_cloud
│   │   ├── video.py                 # POST /process_video
│   │   ├── history.py               # GET/DELETE /history
│   │   ├── user_facts.py            # GET/DELETE /user_facts
│   │   ├── session.py               # POST /session/clear
│   │   └── tasks.py                 # GET /status/{task_id}
│   ├── data/                        # ChromaDB, SQLite, registry (generado en runtime)
│   └── requirements.txt
│
├── frontend/                        # Cliente Next.js (TypeScript)
│   ├── package.json                 # Scripts: dev, build, start, lint
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/                     # App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── globals.css
│   │   ├── components/            # UI (chat, sidebar, upload, dashboard, etc.)
│   │   │   ├── sidebar/
│   │   │   └── dashboard/
│   │   ├── context/
│   │   │   └── UserContext.tsx      # Sesión y usuario en cliente
│   │   ├── hooks/
│   │   │   └── useChat.ts
│   │   ├── lib/
│   │   │   └── api.ts               # fetch al backend, headers de sesión
│   │   ├── config/
│   │   │   └── navigation.ts
│   │   └── constants/
│   │       └── dashboardConfig.ts
│   └── public/                      # Activos estáticos (favicon, etc.)
│
├── run.sh                           # Orquestación local: Redis, backend, Celery, Next.js
├── ARQUITECTURA.md                  # Este documento
└── .env                             # Secretos y configuración (no versionar valores reales)
```

## Endpoints del backend

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /health | Salud del servicio |
| POST | /chat | Mensaje de chat (body: `message`, `session_id?`, `temperature?`, `max_tokens?`, `learning_mode?`, `learning_topic?`, `last_learning_content?`) |
| POST | /upload | Subir PDF (multipart + `X-Session-Id`; encola procesamiento vía Celery y devuelve `task_id`) |
| POST | /upload/load_cloud | Encolar carga de PDFs desde GCS (`X-Session-Id`; respuesta con `task_id`) |
| POST | /process_video | Encolar vídeo de YouTube (body: `url`, `session_id?` + `X-Session-Id`; respuesta con `task_id`) |
| GET | /status/{task_id} | Estado de tareas encoladas (Celery), p. ej. upload o vídeo |
| GET | /history | Historial de mensajes (`X-Session-Id`) |
| DELETE | /history | Borrar historial (`X-Session-Id`) |
| GET | /user_facts | Hechos inferidos del usuario (`X-Session-Id`) |
| DELETE | /user_facts | Borrar hechos (`X-Session-Id`) |
| POST | /session/clear | Limpiar sesión: historial, registry, colección Chroma asociada (`X-Session-Id`) |

En las operaciones que requieren sesión, el valor de **`X-Session-Id`** debe coincidir con el identificador que el frontend mantiene para ese usuario en el navegador.

## Cómo ejecutar (desarrollo)

1. **Backend** (desde la raíz del repositorio, con `PYTHONPATH` apuntando al proyecto, o desde un entorno que importe `backend`):

   ```bash
   cd /ruta/al/chatbot-test
   source venv/bin/activate
   pip install -r backend/requirements.txt
   # Configurar .env, GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_API_KEY, etc.
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend** (otra terminal; Node.js y npm instalados):

   ```bash
   cd frontend
   npm install
   # Opcional si el API no está en localhost:8000:
   # export NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
   npm run dev
   ```

   Por defecto Next.js sirve en **http://localhost:3000**.

3. **Pila completa local** (Redis, Uvicorn, worker Celery y Next.js): ejecutar **`./run.sh`** desde la raíz. Requiere `venv`, dependencias de backend y Redis disponible (o arranque automático si está configurado en el script).

En producción, el frontend se construye con `npm run build` y se sirve con `npm run start` (u orquestación equivalente); el backend sigue siendo la API FastAPI expuesta según tu despliegue.
