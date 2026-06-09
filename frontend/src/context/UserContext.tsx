"use client";

/**
 * UserContext — adaptador de compatibilidad sobre AuthContext.
 *
 * Expone la misma interfaz que antes (sessionId, username, login, logout…)
 * pero ahora el `sessionId` y el `username` provienen del JWT autenticado,
 * no del string libre introducido por el usuario.
 *
 * `login` y `logout` delegan en AuthContext.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
} from "react";
import { useAuth } from "@/context/AuthContext";
import { dictionaries } from "@/locales";

function formatUsername(username: string): string {
  const words = username.split(/[_-]+/).filter(Boolean);
  return words
    .map((word) => {
      if (/[a-zA-Z]/.test(word)) {
        const lower = word.toLowerCase();
        return `${lower.charAt(0).toUpperCase()}${lower.slice(1)}`;
      }
      return word;
    })
    .join(" ")
    .trim();
}

function computeUserInitials(username: string): string {
  const words = username.split(/[_-]+/).filter(Boolean);
  if (words.length === 1) {
    const letters = words[0].match(/[a-zA-Z]/g) ?? [];
    return letters.slice(0, 2).join("").toUpperCase();
  }
  const initials: string[] = [];
  for (const word of words) {
    const match = word.match(/[a-zA-Z]/);
    if (!match) continue;
    initials.push(match[0].toUpperCase());
    if (initials.length >= 2) break;
  }
  return initials.join("");
}

export type UserContextValue = {
  sessionId: string | null;
  username: string;
  userInitials: string;
  isHydrated: boolean;
  /** @deprecated usar useAuth().login directamente */
  login: (id: string) => void;
  logout: () => void;
};

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const { user, isHydrated, logout: authLogout } = useAuth();

  const sessionId = user?.username ?? null;

  const username = useMemo(
    () => (sessionId ? formatUsername(sessionId) : ""),
    [sessionId]
  );

  const userInitials = useMemo(
    () => (sessionId ? computeUserInitials(sessionId) : ""),
    [sessionId]
  );

  const login = useCallback((_id: string) => {
    // No-op: el login real ocurre en WelcomeScreen → AuthContext.login
  }, []);

  const logout = useCallback(() => {
    authLogout();
  }, [authLogout]);

  const value = useMemo<UserContextValue>(
    () => ({ sessionId, username, userInitials, isHydrated, login, logout }),
    [sessionId, username, userInitials, isHydrated, login, logout]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error(dictionaries.errors.userContextOutsideProvider);
  }
  return ctx;
}
