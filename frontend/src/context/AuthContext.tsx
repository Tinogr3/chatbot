"use client";

/**
 * AuthContext — gestión de autenticación JWT.
 *
 * Estrategia de tokens:
 *  - Access token (15 min): almacenado solo en memoria React para evitar XSS.
 *  - Refresh token (7 días): cookie httpOnly establecida por el backend;
 *    el frontend no puede leerla, pero se envía automáticamente al llamar
 *    a POST /auth/refresh.
 *
 * Al montar el provider intenta auto-refrescar (la cookie puede seguir
 * vigente de una sesión anterior). Si falla, el usuario ve la pantalla de login.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { dictionaries } from "@/locales";

const BACKEND_URL =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_BACKEND_URL) ||
  "http://localhost:8000";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export type AuthUser = {
  id: number;
  username: string;
  email?: string;
};

export type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  isHydrated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

// ---------------------------------------------------------------------------
// Helpers de fetch hacia el backend auth
// ---------------------------------------------------------------------------

async function _parseError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const json = JSON.parse(text) as {
      detail?: string | Array<{ msg?: string; loc?: string[] }>;
    };
    if (typeof json.detail === "string") return json.detail;
    // Pydantic devuelve un array de errores de validación
    if (Array.isArray(json.detail)) {
      const msgs = json.detail.map((e) => {
        const field = (e.loc ?? []).filter((l) => l !== "body").join(" → ");
        const msg = (e.msg ?? "Valor inválido").replace(/^Value error,\s*/i, "");
        return field ? `${field}: ${msg}` : msg;
      });
      return msgs.join(" | ") || `Error ${res.status}`;
    }
  } catch {
    // no es JSON
  }
  return text || `Error ${res.status}`;
}

async function _postAuth(
  path: string,
  body: Record<string, string>
): Promise<{ access_token: string; expires_in: number }> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    credentials: "include", // envía/recibe la cookie de refresco
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const msg = await _parseError(res);
    throw new Error(msg);
  }
  return res.json();
}

async function _getMe(
  token: string
): Promise<AuthUser> {
  const res = await fetch(`${BACKEND_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("No se pudo obtener el perfil.");
  return res.json();
}

async function _refreshToken(): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Sesión expirada.");
  const data = await res.json();
  return (data as { access_token: string }).access_token;
}

async function _logout(): Promise<void> {
  await fetch(`${BACKEND_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ---------------------------------------------------------------------------
  // Auto-refresh: programa la renovación 60 s antes de que expire
  // ---------------------------------------------------------------------------
  const scheduleRefresh = useCallback((expiresInSeconds: number) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const delay = Math.max((expiresInSeconds - 60) * 1000, 5_000);
    refreshTimerRef.current = setTimeout(async () => {
      try {
        const newToken = await _refreshToken();
        setAccessToken(newToken);
        // 15 min por defecto si no conocemos el nuevo expiry
        scheduleRefresh(14 * 60);
      } catch {
        setAccessToken(null);
        setUser(null);
      }
    }, delay);
  }, []);

  // ---------------------------------------------------------------------------
  // Hidratación: intenta refrescar con la cookie de sesión existente
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await _refreshToken();
        if (cancelled) return;
        const me = await _getMe(token);
        if (cancelled) return;
        setAccessToken(token);
        setUser(me);
        scheduleRefresh(14 * 60);
      } catch {
        // Sin sesión previa: mostrar login
      } finally {
        if (!cancelled) setIsHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [scheduleRefresh]);

  // ---------------------------------------------------------------------------
  // login
  // ---------------------------------------------------------------------------
  const login = useCallback(
    async (username: string, password: string) => {
      const data = await _postAuth("/auth/login", { username, password });
      const me = await _getMe(data.access_token);
      setAccessToken(data.access_token);
      setUser(me);
      scheduleRefresh(data.expires_in);
    },
    [scheduleRefresh]
  );

  // ---------------------------------------------------------------------------
  // register
  // ---------------------------------------------------------------------------
  const register = useCallback(
    async (username: string, password: string) => {
      const data = await _postAuth("/auth/register", {
        username,
        password,
      });
      const me = await _getMe(data.access_token);
      setAccessToken(data.access_token);
      setUser(me);
      scheduleRefresh(data.expires_in);
    },
    [scheduleRefresh]
  );

  // ---------------------------------------------------------------------------
  // logout
  // ---------------------------------------------------------------------------
  const logout = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    try {
      await _logout();
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, accessToken, isHydrated, login, register, logout }),
    [user, accessToken, isHydrated, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error(dictionaries.errors.authContextOutsideProvider);
  return ctx;
}
