"use client";

import { useMemo, useState } from "react";
import { Settings, ChevronRight, ChevronDown } from "lucide-react";
import type { ChatMessage } from "@/hooks/useChat";

import { useUser } from "@/context/UserContext";
import PedagogicalScaffold from "@/components/PedagogicalScaffold";

type ChatPanelProps = {
  messages: ChatMessage[];
  isLoading: boolean;
  error: Error | null;
  scaffoldMessage?: string;
};

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const hasSources = msg.role === "assistant" && msg.sources && msg.sources.length > 0;

  if (msg.role === "assistant") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[92%] space-y-0">
          <div className="rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 text-gray-800 text-sm">
            {msg.content}
          </div>
          {hasSources && (
            <div className="mt-1 ml-1">
              <button
                type="button"
                onClick={() => setSourcesOpen((o) => !o)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 rounded px-2 py-1 hover:bg-gray-50 border border-transparent hover:border-gray-100"
              >
                <ChevronDown
                  className={`w-3.5 h-3.5 shrink-0 transition-transform ${sourcesOpen ? "rotate-180" : ""}`}
                />
                <span>Fuentes citadas ({msg.sources!.length})</span>
              </button>
              {sourcesOpen && (
                <ul className="mt-1 pl-4 pr-2 py-1.5 text-xs text-gray-500 list-disc space-y-0.5 border-l border-gray-200 ml-2">
                  {msg.sources!.map((src, i) => (
                    <li key={i}>{src}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-end">
      <div className="max-w-[92%] rounded-lg rounded-tr-none px-3 py-2 bg-emerald-500 text-white text-sm text-right">
        {msg.content}
      </div>
    </div>
  );
}

export default function ChatPanel({ messages, isLoading, error, scaffoldMessage }: ChatPanelProps) {
  const { username, sessionId } = useUser();

  const displayMessages = useMemo<ChatMessage[]>(() => {
    if (messages.length > 0) return messages;

    const safeName = username?.trim() ? username : "Usuario";

    return [
      {
        id: `welcome-assistant-${sessionId ?? "anon"}`,
        role: "assistant",
        content: `Hola ${safeName}, soy COTUTOR IA. ¿En qué puedo ayudarte hoy?`,
      },
    ];
  }, [messages, sessionId, username]);

  return (
    <aside className="w-[25%] min-w-[280px] h-screen flex flex-col bg-white border-l border-gray-200">
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

      {scaffoldMessage ? <PedagogicalScaffold scaffoldMessage={scaffoldMessage} /> : null}

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {displayMessages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
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
