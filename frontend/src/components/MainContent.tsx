"use client";

import { User } from "lucide-react";
import { useUser } from "@/context/UserContext";
import { contentCards } from "@/constants/dashboardConfig";
import MaturityDashboard from "@/components/dashboard/MaturityDashboard";
import ChatInputBar from "@/components/chat/ChatInputBar";
import { dictionaries } from "@/locales";

const t = dictionaries.mainContent;

type MainContentProps = {
  onSendMessage?: (text: string) => void;
  chatInputRef?: React.RefObject<HTMLInputElement | null>;
  hidden?: boolean;
  isLearningMode?: boolean;
  onToggleLearningMode?: () => void;
};

export default function MainContent({
  onSendMessage,
  chatInputRef,
  hidden,
  isLearningMode = false,
  onToggleLearningMode,
}: MainContentProps) {
  const { username } = useUser();

  return (
    <main className={`w-[55%] min-w-0 h-screen flex flex-col bg-gray-50 overflow-hidden${hidden ? " hidden" : ""}`}>
      {/* Top Nav compartida */}
      <header className="shrink-0 flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200">
        <nav className="flex items-center gap-6">
          <a
            href="#"
            className="text-sm font-medium text-emerald-600 border-b-2 border-emerald-600 pb-0.5"
          >
            {t.nav.microOnboarding}
          </a>
          <a href="#" className="text-sm text-gray-500 hover:text-gray-800">
            {t.nav.audioSummary}
          </a>
        </nav>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-700">{username}</span>
          <button
            type="button"
            aria-label={t.userMenuLabel(username)}
            className="w-8 h-8 rounded-full bg-emerald-500 text-white flex items-center justify-center"
          >
            <User className="w-5 h-5" aria-hidden="true" focusable="false" />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{t.pageTitle}</h1>
          <p className="text-gray-500 mt-0.5">{t.pageSubtitle}</p>
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
                {t.activesLabel(card.count)}
              </p>
            </div>
          ))}
        </div>
      </div>

      <ChatInputBar
        onSendMessage={onSendMessage}
        inputRef={chatInputRef}
        isLearningMode={isLearningMode}
        onToggleLearningMode={onToggleLearningMode}
      />
    </main>
  );
}
