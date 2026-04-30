"use client";

import { useMemo } from "react";
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
  if (msg.role === "assistant") {
    return (
      <div className="flex justify-start">
        <div className="max-w-[92%]">
          <div className="rounded-lg rounded-tl-none px-3 py-2 bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-gray-100 prose prose-sm md:prose-base dark:prose-invert max-w-none">
            <ReactMarkdown>{msg.content}</ReactMarkdown>
          </div>
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

      {isExpanded && (
        <ChatInputBar
          onSendMessage={onSendMessage}
          isLearningMode={isLearningMode}
          onToggleLearningMode={onToggleLearningMode}
        />
      )}
    </aside>
  );
}
