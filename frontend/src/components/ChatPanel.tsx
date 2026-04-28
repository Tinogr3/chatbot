"use client";

import { useMemo, useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "@/hooks/useChat";

import { useUser } from "@/context/UserContext";
import { useProjects } from "@/context/ProjectsContext";
import ExpandToggleButton from "@/components/chat/ExpandToggleButton";
import ChatInputBar from "@/components/chat/ChatInputBar";
import { dictionaries } from "@/locales";

const t = dictionaries.chatPanel;
const tUser = dictionaries.user;

type ChatPanelProps = {
  messages: ChatMessage[];
  isLoading: boolean;
  error: Error | null;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
  onSendMessage?: (text: string) => void;
  isLearningMode?: boolean;
  onToggleLearningMode?: () => void;
};

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const hasSources = msg.role === "assistant" && msg.sources && msg.sources.length > 0;

  if (msg.role === "assistant") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[92%] space-y-0">
          <div className="rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 prose prose-sm md:prose-base dark:prose-invert max-w-none">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
          {hasSources && (
            <div className="mt-1 ml-1">
              <button
                type="button"
                onClick={() => setSourcesOpen((o) => !o)}
                className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded px-2 py-1 hover:bg-gray-50 dark:hover:bg-gray-800 border border-transparent hover:border-gray-100 dark:hover:border-gray-700"
              >
                <ChevronDown
                  className={`w-3.5 h-3.5 shrink-0 transition-transform ${sourcesOpen ? "rotate-180" : ""}`}
                />
                <span>{t.sourcesLabel(msg.sources!.length)}</span>
              </button>
              {sourcesOpen && (
                <ul className="mt-1 pl-4 pr-2 py-1.5 text-xs text-gray-500 dark:text-gray-400 list-disc space-y-0.5 border-l border-gray-200 dark:border-gray-700 ml-2">
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

export default function ChatPanel({
  messages,
  isLoading,
  error,
  isExpanded = false,
  onToggleExpand,
  onSendMessage,
  isLearningMode = false,
  onToggleLearningMode,
}: ChatPanelProps) {
  const { username } = useUser();
  const { currentProjectId } = useProjects();

  const displayMessages = useMemo<ChatMessage[]>(() => {
    if (messages.length > 0) return messages;

    const safeName = username?.trim() ? username : tUser.defaultUsername;

    return [
      {
        id: `welcome-assistant-${currentProjectId ?? "anon"}`,
        role: "assistant",
        content: t.welcomeMessage(safeName),
      },
    ];
  }, [messages, currentProjectId, username]);

  return (
    <aside
      className={`${
        isExpanded ? "w-full" : "w-[25%] min-w-[280px]"
      } h-screen flex flex-col bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 transition-all duration-300`}
    >
      <header className="shrink-0 flex items-center justify-between px-4 py-3 border-b border-gray-100 dark:border-gray-800">
        <h2 className="text-sm font-semibold text-gray-800 dark:text-gray-100 uppercase tracking-wider">
          {t.title}
        </h2>
        <div className="flex items-center gap-1">
          {onToggleExpand && (
            <ExpandToggleButton isExpanded={isExpanded} onToggle={onToggleExpand} />
          )}
        </div>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
        {displayMessages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-sm flex items-center gap-2">
              <span className="inline-flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400 dark:bg-gray-500 animate-bounce [animation-delay:300ms]" />
              </span>
              {t.loadingMessage}
            </div>
          </div>
        )}
        {error && (
          <div className="rounded-lg px-3 py-2 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
            {error.message}
          </div>
        )}
      </div>

      {isExpanded ? (
        <ChatInputBar
          onSendMessage={onSendMessage}
          isLearningMode={isLearningMode}
          onToggleLearningMode={onToggleLearningMode}
        />
      ) : (
        <div className="shrink-0 p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            type="button"
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 text-sm font-medium hover:bg-gray-200 dark:hover:bg-gray-700"
          >
            {t.historyButton}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </aside>
  );
}
