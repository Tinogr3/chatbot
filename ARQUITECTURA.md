# Arquitectura Cliente-Servidor - Chatbot RAG Educativo

El proyecto está dividido en **backend** (API FastAPI) y **frontend** (Streamlit). El frontend solo hace peticiones HTTP al backend y mantiene `st.session_state` para la sesión del usuario, enviando `session_id` en el header `X-Session-Id` (o en el body donde aplique).

## Estructura de carpetas sugerida

```
chatbot-test/
├── backend/                    # API FastAPI
│   ├── main.py                 # App FastAPI, CORS, rutas
│   ├── config.py               # Credenciales y env
│   ├── rag_engine.py            # RAG, embeddings, Chroma, agente (sin Streamlit)
│   ├── router.py                # Router de queries, aprendizaje
│   ├── media_processor.py       # YouTube, transcripciones
│   ├── chat_manager.py          # Historial SQLite
│   ├── user_memory.py           # Memoria de usuario SQLite
│   ├── document_registry.py     # Registry por sesión
│   ├── gcs_utils.py             # Google Cloud Storage
│   ├── api/
│   │   ├── chat.py              # POST /chat
│   │   ├── upload.py            # POST /upload, POST /upload/load_cloud
│   │   ├── video.py             # POST /process_video
│   │   ├── history.py           # GET/DELETE /history
│   │   ├── user_facts.py         # GET/DELETE /user_facts
│   │   └── session.py           # POST /session/clear
│   ├── data/                    # ChromaDB, SQLite, registry (generado)
│   └── requirements.txt
│
├── frontend/                   # Cliente Streamlit
│   ├── app.py                   # UI + st.session_state + llamadas HTTP
│   ├── api_client.py            # Cliente httpx (chat, upload, process_video, etc.)
│   ├── utils.py                 # format_timestamp, extract_video_id, is_youtube_url
│   └── requirements.txt
│
├── app.py                       # (legacy) App monolítica original
├── requirements.txt             # (legacy) Dependencias del monolito
└── ARQUITECTURA.md              # Este archivo
```

## Endpoints del backend

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /health | Salud del servicio |
| POST | /chat | Enviar mensaje (body: message, session_id?, temperature?, max_tokens?, learning_mode?, learning_topic?, last_learning_content?) |
| POST | /upload | Subir PDF (multipart file + header X-Session-Id) |
| POST | /upload/load_cloud | Cargar todos los PDFs del bucket GCS (X-Session-Id) |
| POST | /process_video | Procesar video YouTube (body: url, session_id?) + X-Session-Id |
| GET | /history | Historial de mensajes (X-Session-Id) |
| DELETE | /history | Borrar historial (X-Session-Id) |
| GET | /user_facts | Hechos del usuario (X-Session-Id) |
| DELETE | /user_facts | Borrar hechos (X-Session-Id) |
| POST | /session/clear | Limpiar sesión: historial, registry, Chroma (X-Session-Id) |

En todas las peticiones que requieren sesión se debe enviar **X-Session-Id** con el mismo valor que usa el frontend en `st.session_state.session_id`.

## Cómo ejecutar

1. **Backend** (desde la raíz del proyecto o desde `backend/`):
   ```bash
   cd backend
   pip install -r requirements.txt
   # Configurar .env o GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_API_KEY, etc.
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend** (en otra terminal):
   ```bash
   cd frontend
   pip install -r requirements.txt
   export BACKEND_URL=http://localhost:8000   # opcional, por defecto es localhost:8000
   streamlit run app.py
   ```

El frontend mantiene el manejo de `st.session_state` (session_id, messages, archivos_manuales, archivos_nube, videos_procesados, learning_mode, etc.) y solo delega la lógica pesada al backend mediante peticiones HTTP.
