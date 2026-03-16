"use client";

import { useCallback, useState } from "react";

const CHAT_API_URL = process.env.NEXT_PUBLIC_CHAT_API_URL ?? "http://localhost:8000/chat";
const DEFAULT_SESSION_ID = "alex_rivera";

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

export function useChat(options: UseChatOptions = {}) {
  const { sessionId = DEFAULT_SESSION_ID, onError } = options;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

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
        const res = await fetch(CHAT_API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionId,
          }),
        });

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(
            (errBody.detail as string) || `Error ${res.status}: ${res.statusText}`
          );
        }

        const data = (await res.json()) as {
          answer: string;
          sources?: string[];
          learning_mode?: boolean;
          learning_topic?: string | null;
        };

        const assistantMessage: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.answer,
          sources: data.sources,
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
    [sessionId, isLoading, onError]
  );

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isLoading, error, sendMessage, clearMessages };
}
