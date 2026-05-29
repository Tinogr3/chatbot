# Frontend (Next.js)

Cliente web del proyecto de chat / RAG educativo.

## Documentación y arranque

- Guía principal (variables, despliegue con Docker): **[README.md](../README.md)**
- Arquitectura y API: **[ARQUITECTURA.md](../ARQUITECTURA.md)**

## Desarrollo aislado del frontend

Si necesitas iterar solo en el frontend sin Docker, con Node.js instalado:

```bash
npm ci
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000 npm run dev
```

El backend debe estar corriendo y accesible en la URL indicada.
