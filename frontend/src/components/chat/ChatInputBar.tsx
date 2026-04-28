"use client";

import { useRef, type FormEvent, type RefObject } from "react";
import { Book, BookOpen, HelpCircle, Send } from "lucide-react";
import { dictionaries } from "@/locales";

const t = dictionaries.mainContent;

export type ChatInputBarProps = {
  onSendMessage?: (text: string) => void;
  inputRef?: RefObject<HTMLInputElement | null>;
  isLearningMode?: boolean;
  onToggleLearningMode?: () => void;
};

export default function ChatInputBar({
  onSendMessage,
  inputRef,
  isLearningMode = false,
  onToggleLearningMode,
}: ChatInputBarProps) {
  const internalRef = useRef<HTMLInputElement>(null);
  const ref = inputRef ?? internalRef;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = ref.current?.value?.trim();
    if (value && onSendMessage) {
      onSendMessage(value);
      ref.current!.value = "";
    }
  };

  const learningModeLabel = isLearningMode
    ? t.learningModeToggle.deactivate
    : t.learningModeToggle.activate;
  const learningModeTitle = isLearningMode
    ? t.learningModeToggle.activeTitle
    : t.learningModeToggle.activate;

  return (
    <form
      onSubmit={handleSubmit}
      className="shrink-0 p-4 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800"
    >
      <div className="flex items-center gap-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 focus-within:ring-2 focus-within:ring-emerald-500/30 focus-within:border-emerald-500">
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onToggleLearningMode}
            aria-label={learningModeLabel}
            aria-pressed={isLearningMode}
            title={learningModeTitle}
            className={`p-2 rounded-lg transition-colors ${
              isLearningMode
                ? "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            {isLearningMode ? <BookOpen className="w-5 h-5" /> : <Book className="w-5 h-5" />}
          </button>
          <button type="button" className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
            <HelpCircle className="w-5 h-5" />
          </button>
        </div>
        <input
          ref={ref}
          type="text"
          placeholder={t.chatInput.placeholder}
          className="flex-1 min-w-0 bg-transparent border-0 py-1.5 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus:ring-0 text-sm"
        />
        <button
          type="submit"
          className="p-2 rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 shrink-0"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </form>
  );
}
