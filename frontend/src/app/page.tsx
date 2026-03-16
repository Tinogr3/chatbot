"use client";

import { useCallback, useEffect, useState } from "react";
import LeftSidebar from "@/components/LeftSidebar";
import MainContent from "@/components/MainContent";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";
import { Sparkles } from "lucide-react";

const SESSION_STORAGE_KEY = "cotutor_session_id";

function normalizeSessionId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_-]/g, "");
}

function WelcomeScreen({ onSubmit }: { onSubmit: (sessionId: string) => void }) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.querySelector<HTMLInputElement>('input[name="sessionId"]');
    const value = input?.value?.trim() ?? "";
    const normalized = normalizeSessionId(value);
    if (normalized.length > 0) onSubmit(normalized);
  };

  return (
    <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white shadow-xl rounded-2xl p-8 w-full max-w-md border border-gray-100">
        <div className="flex justify-center mb-6">
          <div className="p-3 rounded-xl bg-emerald-500 text-white">
            <Sparkles className="w-10 h-10" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-gray-800 text-center mb-2">
          Bienvenido al Chatbot RAG Educativo
        </h1>
        <p className="text-gray-500 text-center text-sm mb-6">
          Introduce tu nombre de usuario o ID de sesión para continuar. Se guardará tu historial y preferencias.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="sr-only">Nombre de usuario o ID de sesión</span>
            <input
              type="text"
              name="sessionId"
              placeholder="Ej: juan_perez, mi_sesion_123"
              autoComplete="username"
              className="w-full px-4 py-3 rounded-xl border border-gray-200 bg-gray-50 text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
          </label>
          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors"
          >
            Comenzar
          </button>
        </form>
        <p className="text-gray-400 text-xs text-center mt-4">
          Usa siempre el mismo nombre para recuperar tu historial.
        </p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [sessionId, setSessionIdState] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (stored && stored.length > 0) {
      setSessionIdState(stored);
    }
    setHydrated(true);
  }, []);

  const setSessionId = useCallback((id: string | null) => {
    setSessionIdState(id);
    if (typeof window !== "undefined") {
      if (id) sessionStorage.setItem(SESSION_STORAGE_KEY, id);
      else sessionStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, []);

  if (!hydrated) {
    return (
      <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500 text-sm">Cargando...</div>
      </div>
    );
  }

  if (!sessionId) {
    return <WelcomeScreen onSubmit={(id) => setSessionId(id)} />;
  }

  return (
    <DashboardLayoutWithLogout sessionId={sessionId} setSessionId={setSessionId} />
  );
}

function DashboardLayoutWithLogout({
  sessionId,
  setSessionId,
}: {
  sessionId: string;
  setSessionId: (id: string | null) => void;
}) {
  const { messages, isLoading, error, sendMessage } = useChat({ sessionId });
  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden">
      <LeftSidebar sessionId={sessionId} onLogout={() => setSessionId(null)} />
      <MainContent onSendMessage={sendMessage} />
      <ChatPanel messages={messages} isLoading={isLoading} error={error} />
    </div>
  );
}
