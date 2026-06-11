"use client";

import { useState } from "react";
import { GraduationCap, User, Users } from "lucide-react";
import { useUser } from "@/context/UserContext";
import MaturityDashboard from "@/components/dashboard/MaturityDashboard";
import ChatInputBar from "@/components/chat/ChatInputBar";
import TrainerConfigView from "@/components/trainer/TrainerConfigView";
import StudentProgressDashboard from "@/components/trainer/StudentProgressDashboard";
import { dictionaries } from "@/locales";
import DiscoveryHubSection from "@/components/DiscoveryHubSection";

const t = dictionaries.mainContent;
const tTrainer = dictionaries.trainer;

type MainContentProps = {
  onSendMessage?: (text: string) => void;
  chatInputRef?: React.RefObject<HTMLInputElement | null>;
  hidden?: boolean;
  isLearningMode?: boolean;
  onToggleLearningMode?: () => void;
};

type TrainerTab = "config" | "progress";

export default function MainContent({
  onSendMessage,
  chatInputRef,
  hidden,
  isLearningMode = false,
  onToggleLearningMode,
}: MainContentProps) {
  const { username } = useUser();
  const [isTrainerMode, setIsTrainerMode] = useState(false);
  const [trainerTab, setTrainerTab] = useState<TrainerTab>("config");
  const [progressRefreshKey, setProgressRefreshKey] = useState(0);

  return (
    <main className={`w-[55%] min-w-0 h-screen flex flex-col bg-gray-50 dark:bg-gray-950 overflow-hidden${hidden ? " hidden" : ""}`}>
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">{t.pageTitle}</h1>
            <p className="text-gray-500 dark:text-gray-400 mt-0.5">{t.pageSubtitle}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setIsTrainerMode((prev) => !prev)}
              aria-pressed={isTrainerMode}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                isTrainerMode
                  ? "bg-emerald-500 text-white hover:bg-emerald-600"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
              }`}
            >
              {isTrainerMode ? (
                <>
                  <GraduationCap className="h-4 w-4" aria-hidden="true" />
                  {tTrainer.modeToggle.toStudent}
                </>
              ) : (
                <>
                  <Users className="h-4 w-4" aria-hidden="true" />
                  {tTrainer.modeToggle.toTrainer}
                </>
              )}
            </button>
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

        {isTrainerMode ? (
          <div className="space-y-4">
            <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1 max-w-md">
              {(
                [
                  { id: "config", label: tTrainer.tabs.config },
                  { id: "progress", label: tTrainer.tabs.progress },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setTrainerTab(tab.id)}
                  className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                    trainerTab === tab.id
                      ? "bg-white dark:bg-gray-900 text-emerald-700 dark:text-emerald-300 shadow-sm"
                      : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {trainerTab === "config" ? (
              <TrainerConfigView
                onItinerarySaved={() => setProgressRefreshKey((n) => n + 1)}
              />
            ) : (
              <StudentProgressDashboard refreshKey={progressRefreshKey} />
            )}
          </div>
        ) : (
          <>
            <MaturityDashboard />
            <DiscoveryHubSection />
          </>
        )}
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
