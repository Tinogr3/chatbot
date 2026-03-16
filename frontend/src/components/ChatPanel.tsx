"use client";

import { Settings, ChevronRight } from "lucide-react";
import type { ChatMessage } from "@/hooks/useChat";

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: "ai-1",
    role: "assistant",
    content:
      "¿Cómo aplicarías el principio de minimización de datos en el nuevo flujo de onboarding?",
  },
  {
    id: "user-1",
    role: "user",
    content: "Solo pediría el correo y nombre para crear la cuenta, y el resto cuando lo necesite el flujo.",
  },
  {
    id: "ai-2",
    role: "assistant",
    content:
      "Excelente enfoque. ¿Qué impacto crees que tendría esto en el tiempo de completado del formulario y en la tasa de abandono?",
  },
];

type ChatPanelProps = {
  messages: ChatMessage[];
  isLoading: boolean;
  error: Error | null;
};

export default function ChatPanel({ messages, isLoading, error }: ChatPanelProps) {
  const displayMessages = messages.length > 0 ? messages : INITIAL_MESSAGES;

  return (
    <aside className="w-[25%] min-w-[280px] h-screen flex flex-col bg-white border-l border-gray-200">
      {/* Cabecera */}
      <header className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800 uppercase tracking-wider">
          Chat Integrado
        </h2>
        <button
          type="button"
          className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-50"
        >
          <Settings className="w-4 h-4" />
        </button>
      </header>

      {/* Widget andamiaje */}
      <div className="shrink-0 mx-4 mt-3 p-3 rounded-lg bg-emerald-50 border border-emerald-100">
        <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-2">
          Andamiaje Pedagógico
        </p>
        <div className="h-2 rounded-full bg-emerald-200 overflow-hidden mb-1.5">
          <div
            className="h-full rounded-full bg-emerald-500 transition-all duration-500"
            style={{ width: "65%" }}
          />
        </div>
        <p className="text-xs text-gray-600">
          La IA está guiando tu razonamiento hacia la Arquitectura de Privacidad.
        </p>
      </div>

      {/* Historial de chat (scrollable) */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {displayMessages.map((msg) =>
          msg.role === "assistant" ? (
            <div
              key={msg.id}
              className="flex justify-start"
            >
              <div className="max-w-[92%] rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 text-gray-800 text-sm">
                {msg.content}
              </div>
            </div>
          ) : (
            <div key={msg.id} className="flex justify-end">
              <div className="max-w-[92%] rounded-lg rounded-tr-none px-3 py-2 bg-emerald-500 text-white text-sm text-right">
                {msg.content}
              </div>
            </div>
          )
        )}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 text-gray-500 text-sm flex items-center gap-2">
              <span className="inline-flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
              </span>
              Cotutor está analizando tu respuesta...
            </div>
          </div>
        )}
        {error && (
          <div className="rounded-lg px-3 py-2 bg-red-50 text-red-700 text-sm">
            {error.message}
          </div>
        )}
      </div>

      {/* Pie */}
      <div className="shrink-0 p-4 border-t border-gray-100">
        <button
          type="button"
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200"
        >
          Ver historial completo
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
