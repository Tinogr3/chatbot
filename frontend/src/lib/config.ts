/** URL del API FastAPI. Definir en build con NEXT_PUBLIC_BACKEND_URL. */
export const BACKEND_URL =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";
