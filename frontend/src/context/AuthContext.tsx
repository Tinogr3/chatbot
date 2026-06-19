"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { BACKEND_URL } from "@/lib/config";
import { parseErrorResponse } from "@/lib/http";
import { dictionaries } from "@/locales";

export type UserRole = "formador" | "alumno";

export type AuthUser = {
  id: number;
  username: string;
  email?: string;
  role: UserRole;
};

export type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  isHydrated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, role?: UserRole) => Promise<void>;
  logout: () => Promise<void>;
};

async function postAuth(
  path: string,
  body: Record<string, string>,
): Promise<{ access_token: string; expires_in: number }> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await parseErrorResponse(res));
  }
  return res.json();
}

async function getMe(token: string): Promise<AuthUser> {
  const res = await fetch(`${BACKEND_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("No se pudo obtener el perfil.");
  return res.json();
}

async function refreshToken(): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error("Sesión expirada.");
  const data = await res.json();
  return (data as { access_token: string }).access_token;
}

async function logoutRequest(): Promise<void> {
  await fetch(`${BACKEND_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleRefresh = useCallback((expiresInSeconds: number) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const delay = Math.max((expiresInSeconds - 60) * 1000, 5_000);
    refreshTimerRef.current = setTimeout(async () => {
      try {
        const newToken = await refreshToken();
        setAccessToken(newToken);
        scheduleRefresh(14 * 60);
      } catch {
        setAccessToken(null);
        setUser(null);
      }
    }, delay);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const token = await refreshToken();
        if (cancelled) return;
        const me = await getMe(token);
        if (cancelled) return;
        setAccessToken(token);
        setUser(me);
        scheduleRefresh(14 * 60);
      } catch {
        // sin sesión previa
      } finally {
        if (!cancelled) setIsHydrated(true);
      }
    })();
    return () => {
      cancelled = true;
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, [scheduleRefresh]);

  const login = useCallback(
    async (username: string, password: string) => {
      const data = await postAuth("/auth/login", { username, password });
      const me = await getMe(data.access_token);
      setAccessToken(data.access_token);
      setUser(me);
      scheduleRefresh(data.expires_in);
    },
    [scheduleRefresh],
  );

  const register = useCallback(
    async (username: string, password: string, role: UserRole = "alumno") => {
      const data = await postAuth("/auth/register", { username, password, role });
      const me = await getMe(data.access_token);
      setAccessToken(data.access_token);
      setUser(me);
      scheduleRefresh(data.expires_in);
    },
    [scheduleRefresh],
  );

  const logout = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    try {
      await logoutRequest();
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, accessToken, isHydrated, login, register, logout }),
    [user, accessToken, isHydrated, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error(dictionaries.errors.authContextOutsideProvider);
  return ctx;
}
