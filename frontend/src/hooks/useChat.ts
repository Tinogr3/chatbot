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
  /**
   * Identificador de sesión que se envía al backend (`X-Session-Id`).
   * Si es `undefined` el hook permanece inactivo: no carga historial ni acepta envíos.
   * Cuando cambia, los mensajes se vacían y se vuelve a leer el historial correspondiente.
   */
  sessionId?: string;
  onError?: (error: Error) => void;
};

function mapHistoryToMessages(
  messages: { role: string; content: string; sources?: string[] | null }[],
): ChatMessage[] {
  return messages.map((m, i) => ({
    id: `${m.role}-history-${i}-${Date.now()}`,
    role: m.role === "assistant" ? "assistant" : "user",
    content: m.content,
    sources: m.sources && m.sources.length > 0 ? m.sources : undefined,
  }));
}

export function useChat(options: UseChatOptions = {}) {
  const { sessionId, onError } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [isLearningMode, setIsLearningMode] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setMessages([]);
    setError(null);
    setHistoryLoaded(false);

    if (!sessionId) {
      setHistoryLoaded(true);
      return;
    }

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
      if (!trimmed || isLoading || !sessionId) return;

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
    [sessionId, isLoading, isLearningMode, onError],
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  const toggleLearningMode = useCallback(() => {
    setIsLearningMode((prev) => !prev);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    historyLoaded,
    isLearningMode,
    toggleLearningMode,
  };
}
