"use client";

import {
  Filter,
  Plus,
  Video,
  Mic,
  MessageSquare,
  FileQuestion,
  Camera,
  Mic2,
  HelpCircle,
  Send,
} from "lucide-react";
import { useRef } from "react";

const HEATMAP_LEVELS = [
  [4, 3, 2, 4, 5, 3, 4, 2, 3, 4],
  [2, 4, 5, 3, 4, 5, 2, 4, 3, 5],
  [3, 2, 4, 5, 3, 4, 5, 2, 4, 3],
  [5, 4, 3, 2, 4, 3, 4, 5, 3, 4],
  [4, 5, 4, 4, 2, 5, 3, 4, 5, 2],
];

const categories = [
  { name: "Soberanía de Datos", percent: 82 },
  { name: "Arquitectura Privacidad", percent: 45 },
  { name: "Ética en IA", percent: 68 },
];

const contentCards = [
  { title: "Video Píldoras", count: 3, icon: Video },
  { title: "Podcasts", count: 5, icon: Mic },
  { title: "Resúmenes", count: 12, icon: MessageSquare },
  { title: "Exámenes", count: 8, icon: FileQuestion },
];

type MainContentProps = {
  onSendMessage?: (text: string) => void;
  chatInputRef?: React.RefObject<HTMLInputElement | null>;
};

export default function MainContent({ onSendMessage, chatInputRef }: MainContentProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const ref = chatInputRef ?? inputRef;

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
          <span className="text-sm text-gray-700">Alex Rivera</span>
          <button
            type="button"
            className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center text-sm font-medium"
          >
            AR
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

        {/* Dashboard de Madurez */}
        <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <h2 className="text-lg font-semibold text-gray-800">
              Dashboard de Madurez de Habilidades
            </h2>
            <button
              type="button"
              className="text-xs text-gray-500 hover:text-gray-700 shrink-0"
            >
              Actualizado hace 2h
            </button>
          </div>
          <p className="text-sm text-gray-500 mb-4">
            Progreso dinámico según tu actividad y evaluaciones.
          </p>
          <div className="space-y-4">
            {categories.map((cat, catIndex) => (
              <div key={cat.name} className="space-y-1.5">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-700">{cat.name}</span>
                  <span className="font-medium text-gray-800">{cat.percent}%</span>
                </div>
                <div className="flex gap-0.5">
                  {HEATMAP_LEVELS[catIndex % HEATMAP_LEVELS.length].map((level, i) => (
                    <div
                      key={i}
                      className="w-6 h-6 rounded-sm flex-shrink-0"
                      style={{
                        backgroundColor:
                          level === 5
                            ? "#059669"
                            : level === 4
                              ? "#10b981"
                              : level === 3
                                ? "#34d399"
                                : level === 2
                                  ? "#6ee7b7"
                                  : "#a7f3d0",
                      }}
                      title={`Nivel ${level}`}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

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
