# Frontend (Next.js)

Cliente web del proyecto de chat / RAG educativo.

## Documentación y arranque

- Guía principal del repositorio (entorno, `./run.sh`, variables): **[README.md](../README.md)**
- Arquitectura y API: **[ARQUITECTURA.md](../ARQUITECTURA.md)**

## Solo frontend en desarrollo

Desde esta carpeta, con Node.js instalado:

```bash
npm ci
npm run dev
```

La URL del backend en el navegador se configura con **`NEXT_PUBLIC_BACKEND_URL`** (por defecto suele ser `http://localhost:8000`).
