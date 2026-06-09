# Frontend (Next.js)

Cliente web del proyecto de chat / RAG educativo.

Para la guía completa de arranque, variables de entorno y despliegue con Docker consulta **[README.md](../README.md)**.

## Desarrollo local sin Docker

Requiere Node.js 20+.

```bash
npm ci
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

El backend debe estar corriendo y accesible en la URL indicada. La app queda disponible en <http://localhost:3000>.
