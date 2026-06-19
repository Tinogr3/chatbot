import { BACKEND_URL } from "@/lib/config";

export { BACKEND_URL };

export function normalizeSessionId(sessionId: string): string {
  return sessionId.trim().toLowerCase().replace(/\s+/g, "_");
}

export async function parseErrorResponse(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const json = JSON.parse(text) as {
      detail?: string | Array<{ msg?: string; loc?: string[] }>;
    };
    if (typeof json.detail === "string") return json.detail;
    if (Array.isArray(json.detail)) {
      return (
        json.detail
          .map((entry) => {
            const field = (entry.loc ?? []).filter((part) => part !== "body").join(" → ");
            const msg = (entry.msg ?? "Valor inválido").replace(/^Value error,\s*/i, "");
            return field ? `${field}: ${msg}` : msg;
          })
          .join(" | ") || `Error ${res.status}`
      );
    }
  } catch {
    // respuesta no JSON
  }
  return text || res.statusText || `Error ${res.status}`;
}

export function sessionHeaders(
  sessionId: string,
  accessToken?: string | null,
): HeadersInit {
  const headers: Record<string, string> = {
    "X-Session-Id": normalizeSessionId(sessionId),
  };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return headers;
}

export type FetchJsonOptions = RequestInit & {
  sessionId?: string;
  accessToken?: string | null;
};

export async function fetchJson<T>(
  url: string,
  options: FetchJsonOptions = {},
): Promise<T> {
  const { sessionId, accessToken, ...init } = options;
  const headers = new Headers(init.headers as Headers);
  if (sessionId !== undefined) {
    headers.set("X-Session-Id", normalizeSessionId(sessionId));
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, credentials: "include" });
  } catch {
    throw new Error(
      "No se pudo conectar con el servidor. Comprueba que el backend está en marcha y NEXT_PUBLIC_BACKEND_URL.",
    );
  }

  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
