"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import LeftSidebar from "@/components/LeftSidebar";
import MainContent from "@/components/MainContent";
import ChatPanel from "@/components/ChatPanel";
import { useChat } from "@/hooks/useChat";
import { UserProvider, useUser } from "@/context/UserContext";

function WelcomeScreen() {
  const { login } = useUser();
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.querySelector<HTMLInputElement>('input[name="sessionId"]');
    const value = input?.value?.trim() ?? "";

    try {
      login(value);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al iniciar sesión.");
    }
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
          {error && (
            <div
              role="alert"
              className="rounded-lg border border-red-200 bg-red-50 text-red-800 px-3 py-2 text-xs"
            >
              {error}
            </div>
          )}
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
  return (
    <UserProvider>
      <DashboardGate />
    </UserProvider>
  );
}

function DashboardGate() {
  const { sessionId, isHydrated } = useUser();

  if (!isHydrated) {
    return (
      <div className="min-h-screen w-full bg-gray-50 flex items-center justify-center">
        <div className="text-gray-500 text-sm">Cargando...</div>
      </div>
    );
  }

  if (!sessionId) return <WelcomeScreen />;

  return <DashboardLayoutWithLogout />;
}

function DashboardLayoutWithLogout() {
  const { sessionId } = useUser();
  const { messages, isLoading, error, sendMessage } = useChat({
    sessionId: sessionId ?? undefined,
  });

  if (!sessionId) return null;

  return (
    <div className="flex h-screen w-full bg-gray-50 overflow-hidden">
      <LeftSidebar />
      <MainContent onSendMessage={sendMessage} />
      <ChatPanel
        messages={messages}
        isLoading={isLoading}
        error={error}
        scaffoldMessage="La IA está guiando tu razonamiento hacia la Arquitectura de Privacidad."
      />
    </div>
  );
}
