"use client";

import { useState, type FormEvent } from "react";
import { Loader2, Send, Sparkles } from "lucide-react";
import { generateItinerary, type GeneratedItinerary } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.trainer.chat;

type ChatEntry = {
  role: "trainer" | "assistant";
  text: string;
};

export type TrainerChatProps = {
  /** Callback con el itinerario generado para que el validador lo muestre. */
  onItineraryGenerated: (itinerary: GeneratedItinerary) => void;
};

/**
 * Chat del formador: envía el prompt a /trainer/generate-itinerary y entrega
 * la respuesta estructurada al QuadrantValidator (panel derecho).
 */
export default function TrainerChat({ onItineraryGenerated }: TrainerChatProps) {
  const { accessToken } = useAuth();
  const { effectiveSessionId } = useProjects();

  const [prompt, setPrompt] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const text = prompt.trim();
    if (!text || !effectiveSessionId || loading) return;

    setError(null);
    setLoading(true);
    setEntries((prev) => [...prev, { role: "trainer", text }]);
    setPrompt("");

    try {
      const itinerary = await generateItinerary(text, effectiveSessionId, accessToken);
      const unitCount = itinerary.themes.reduce(
        (acc, th) => acc + th.learning_units.length,
        0,
      );
      setEntries((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `He generado «${itinerary.title}»: ${itinerary.total_weeks} semanas, ${itinerary.hours_per_week}h/semana, ${itinerary.themes.length} temas y ${unitCount} unidades. Revísalo y valídalo a la derecha.`,
        },
      ]);
      onItineraryGenerated(itinerary);
    } catch (err) {
      const message = err instanceof Error ? err.message : t.error;
      setError(message);
      setEntries((prev) => [...prev, { role: "assistant", text: message }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col rounded-xl border border-gray-100 bg-white dark:border-gray-700 dark:bg-gray-900/50">
      <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-700">
        <Sparkles className="h-4 w-4 text-emerald-500" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
          {t.title}
        </h3>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {entries.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">{t.hint}</p>
        ) : (
          entries.map((entry, i) => (
            <div
              key={i}
              className={`max-w-[90%] rounded-lg px-3 py-2 text-sm ${
                entry.role === "trainer"
                  ? "ml-auto bg-emerald-500 text-white"
                  : "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100"
              }`}
            >
              {entry.text}
            </div>
          ))
        )}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t.generating}
          </div>
        )}
      </div>

      {error && (
        <p className="px-4 pb-1 text-xs text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      )}

      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 border-t border-gray-100 p-3 dark:border-gray-700"
      >
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              e.currentTarget.form?.requestSubmit();
            }
          }}
          placeholder={t.placeholder}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
        />
        <button
          type="submit"
          disabled={!prompt.trim() || loading}
          className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
          {t.send}
        </button>
      </form>
    </div>
  );
}
