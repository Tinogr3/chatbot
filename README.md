# Chatbot RAG educativo

Aplicación web con **FastAPI** (backend), **Next.js** (frontend) y **Celery** (tareas en segundo plano: PDFs, vídeo). El cliente solo habla con el API por HTTP; la lógica de RAG, embeddings y almacenamiento vive en el servidor.

## Requisitos previos

| Herramienta | Uso |
|-------------|-----|
| **Python 3** | Entorno virtual en la raíz (`venv/`) |
| **Node.js** (npm incluido; recomendado LTS) | Dependencias del frontend |
| **Redis** | Cola de Celery (subidas y procesamiento pesado). Si no hay servidor en el puerto configurado, `run.sh` intenta arrancar `redis-server` cuando sea posible |
| **curl** | Comprobación de salud del backend al arrancar |

Opcional: **Google Cloud** (credenciales JSON, bucket, API Gemini) según `backend/config.py` y `.env.example`.

## Arranque rápido (recomendado)

Desde la raíz del repositorio:

```bash
chmod +x run.sh   # solo la primera vez en clones nuevos, si hiciera falta
./run.sh
```

El script:

1. Crea **`venv/`** con `python3 -m venv venv` si no existe y lo activa.
2. Instala dependencias **Python** desde **`requirements.txt`** en la raíz (que delega en `backend/requirements.txt`).
3. Si no existe **`frontend/node_modules/`**, ejecuta **`npm ci`** en `frontend/` (instalación reproducible con `package-lock.json`).
4. Garantiza **Redis**, levanta **Uvicorn**, el **worker Celery** y **`npm run dev`** del frontend.

Puertos por defecto: API **8000**, Next.js **3000**. Variables útiles:

```bash
BACKEND_PORT=9000 FRONTEND_PORT=3001 ./run.sh
```

Si Redis no debe arrancarse automáticamente: `REDIS_AUTO_START=0 ./run.sh` (debes tener Redis ya escuchando).

### Tras un `git pull` que cambie dependencias

- **Python:** `./run.sh` vuelve a ejecutar `pip install -r requirements.txt` en cada arranque (rápido con caché).
- **Node:** si ya tienes `frontend/node_modules/`, el script no reinstala. Si cambian `package.json` / `package-lock.json`, ejecuta:

  ```bash
  rm -rf frontend/node_modules
  ./run.sh
  ```

  o manualmente: `(cd frontend && npm ci)`.

## Configuración

1. Copia el ejemplo de entorno: `cp .env.example .env`
2. Rellena claves, proyecto GCP, bucket y ruta al JSON de credenciales (ver comentarios en `.env.example`).

El frontend usa **`NEXT_PUBLIC_BACKEND_URL`** para la URL del API vista desde el navegador (por defecto `http://localhost:8000`). Defínela antes de `npm run dev` si el backend no está en ese host/puerto.

## Desarrollo por piezas

Sin `run.sh`, desde la raíz con `venv` activado y `export PYTHONPATH="$(pwd):${PYTHONPATH:-}"`:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

En otra terminal, `frontend/`:

```bash
npm ci
npm run dev
```

Para subidas y colas asíncronas necesitas **Redis** y un worker: `celery -A backend.worker worker --loglevel=info` (como hace `run.sh`).

## Documentación de arquitectura

Detalle de capas, carpetas y endpoints: **[ARQUITECTURA.md](ARQUITECTURA.md)**.

## Producción (notas breves)

- Frontend: `cd frontend && npm run build && npm run start` (u orquestación equivalente).
- Backend: exponer la app FastAPI con el proceso/servidor que uses en tu plataforma.
- Variables de entorno y secretos deben configurarse en el entorno de despliegue, no en el código.
