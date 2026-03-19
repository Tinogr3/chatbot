"use client";

import {
  Filter,
  Plus,
  Camera,
  Mic2,
  HelpCircle,
  Send,
} from "lucide-react";
import { useRef } from "react";
import { useUser } from "@/context/UserContext";
import { contentCards } from "@/constants/dashboardConfig";
import MaturityDashboard from "@/components/dashboard/MaturityDashboard";

type MainContentProps = {
  onSendMessage?: (text: string) => void;
  chatInputRef?: React.RefObject<HTMLInputElement | null>;
};

export default function MainContent({ onSendMessage, chatInputRef }: MainContentProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const ref = chatInputRef ?? inputRef;
  const { username, userInitials } = useUser();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const value = ref.current?.value?.trim();
    if (value && onSendMessage) {
      onSendMessage(value);
      ref.current!.value = "";
    }
  };

  return (
    <main className="w-[55%] min-w-0 h-screen flex flex-col bg-gray-50 overflow-hidden">
      {/* Top Nav compartida */}
      <header className="shrink-0 flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
        <nav className="flex items-center gap-6">
          <a
            href="#"
            className="text-sm font-medium text-emerald-600 border-b-2 border-emerald-600 pb-0.5"
          >
            Micro-Onboarding
          </a>
          <a href="#" className="text-sm text-gray-500 hover:text-gray-800">
            Resumen de Audio
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-700">{username}</span>
          <button
            type="button"
            className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center text-sm font-medium"
          >
            {userInitials}
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Título y acciones */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-800">Discovery Hub</h1>
            <p className="text-gray-500 mt-0.5">
              Explora y fortalece tus competencias críticas
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 bg-white text-gray-700 text-sm font-medium hover:bg-gray-50"
            >
              <Filter className="w-4 h-4" />
              Filtrar
            </button>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600"
            >
              <Plus className="w-4 h-4" />
              Nuevo Proyecto
            </button>
          </div>
        </div>

        <MaturityDashboard />

        {/* Tarjetas de contenido */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {contentCards.map((card) => (
            <div
              key={card.title}
              className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 flex flex-col items-start hover:shadow-md transition-shadow"
            >
              <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600 mb-3">
                <card.icon className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-gray-800">{card.title}</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {card.count} Activos
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Barra de chat inferior */}
      <form
        onSubmit={handleSubmit}
        className="shrink-0 p-4 bg-white border-t border-gray-200"
      >
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 focus-within:ring-2 focus-within:ring-emerald-500/30 focus-within:border-emerald-500">
          <div className="flex items-center gap-1 shrink-0">
            <button type="button" className="p-2 text-gray-500 hover:text-gray-700">
              <Camera className="w-5 h-5" />
            </button>
            <button type="button" className="p-2 text-gray-500 hover:text-gray-700">
              <Mic2 className="w-5 h-5" />
            </button>
            <button type="button" className="p-2 text-gray-500 hover:text-gray-700">
              <HelpCircle className="w-5 h-5" />
            </button>
          </div>
          <input
            ref={ref}
            type="text"
            placeholder="Pregúntale a COTUTOR algo sobre los manuales..."
            className="flex-1 min-w-0 bg-transparent border-0 py-1.5 text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-0 text-sm"
          />
          <button
            type="submit"
            className="p-2 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 shrink-0"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </form>
    </main>
  );
}
