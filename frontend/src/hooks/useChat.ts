"use client";

import { useCallback, useEffect, useState } from "react";
import { chat as apiChat, getHistory } from "@/lib/api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
};

type UseChatOptions = {
  sessionId?: string;
  onError?: (error: Error) => void;
};

const DEFAULT_SESSION_ID = "usuario_test";

function mapHistoryToMessages(messages: { role: string; content: string; sources?: string[] | null }[]): ChatMessage[] {
  return messages.map((m, i) => ({
    id: `${m.role}-history-${i}-${Date.now()}`,
    role: m.role === "assistant" ? "assistant" : "user",
    content: m.content,
    sources: m.sources && m.sources.length > 0 ? m.sources : undefined,
  }));
}

export function useChat(options: UseChatOptions = {}) {
  const sessionId = options.sessionId ?? DEFAULT_SESSION_ID;
  const onError = options.onError;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [isLearningMode, setIsLearningMode] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHistoryLoaded(false);
    getHistory(sessionId)
      .then((res) => {
        if (cancelled) return;
        setMessages(mapHistoryToMessages(res.messages));
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isLoading) return;

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const data = await apiChat(trimmed, sessionId, { learning_mode: isLearningMode });
        const assistantMessage: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.answer,
          sources: data.sources?.length ? data.sources : undefined,
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        const e = err instanceof Error ? err : new Error(String(err));
        setError(e);
        onError?.(e);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading, isLearningMode, onError]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const toggleLearningMode = useCallback(() => {
    setIsLearningMode((prev) => !prev);
  }, []);

  return { messages, isLoading, error, sendMessage, clearMessages, historyLoaded, isLearningMode, toggleLearningMode };
}
