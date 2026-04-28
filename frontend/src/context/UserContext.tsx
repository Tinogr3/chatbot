"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { dictionaries } from "@/locales";

const SESSION_STORAGE_KEY = "cotutor_session_id";

function normalizeSessionId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_-]/g, "");
}

function formatUsername(sessionId: string): string {
  const words = sessionId.split(/[_-]+/).filter(Boolean);
  const formatted = words.map((word) => {
    // Si el segmento tiene letras, lo "titulamos". Si solo son dígitos, lo dejamos igual.
    if (/[a-zA-Z]/.test(word)) {
      const lower = word.toLowerCase();
      return `${lower.charAt(0).toUpperCase()}${lower.slice(1)}`;
    }
    return word;
  });

  return formatted.join(" ").trim();
}

function computeUserInitials(sessionId: string): string {
  const words = sessionId.split(/[_-]+/).filter(Boolean);

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
  login: (id: string) => void;
  logout: () => void;
};

const UserContext = createContext<UserContextValue | undefined>(undefined);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
    const normalized = stored ? normalizeSessionId(stored) : "";
    queueMicrotask(() => {
      setSessionId(normalized.length > 0 ? normalized : null);
      setIsHydrated(true);
    });
  }, []);

  const login = useCallback((id: string) => {
    const normalized = normalizeSessionId(id);
    if (normalized.length === 0) {
      throw new Error(dictionaries.errors.invalidSessionId);
    }

    setSessionId(normalized);
    if (typeof window !== "undefined") {
      sessionStorage.setItem(SESSION_STORAGE_KEY, normalized);
    }
  }, []);

  const logout = useCallback(() => {
    setSessionId(null);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, []);

  const username = useMemo(() => {
    if (!sessionId) return "";
    return formatUsername(sessionId);
  }, [sessionId]);

  const userInitials = useMemo(() => {
    if (!sessionId) return "";
    return computeUserInitials(sessionId);
  }, [sessionId]);

  const value = useMemo<UserContextValue>(
    () => ({
      sessionId,
      username,
      userInitials,
      isHydrated,
      login,
      logout,
    }),
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

