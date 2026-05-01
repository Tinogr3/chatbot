"use client";

import { User } from "lucide-react";
import { useUser } from "@/context/UserContext";
import MaturityDashboard from "@/components/dashboard/MaturityDashboard";
import ChatInputBar from "@/components/chat/ChatInputBar";
import { dictionaries } from "@/locales";
import DiscoveryHubSection from "@/components/DiscoveryHubSection";

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
    <main className={`w-[55%] min-w-0 h-screen flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden${hidden ? " hidden" : ""}`}>
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">{t.pageTitle}</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-0.5">{t.pageSubtitle}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-sm text-gray-700 dark:text-gray-200 truncate max-w-[160px]">
              {username}
            </span>
            <button
              type="button"
              aria-label={t.userMenuLabel(username)}
              className="w-9 h-9 rounded-full bg-emerald-500 text-white flex items-center justify-center shrink-0"
            >
              <User className="w-5 h-5" aria-hidden="true" focusable="false" />
            </button>
          </div>
        </div>

        <MaturityDashboard />

        <DiscoveryHubSection />
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
