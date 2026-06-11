"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, HelpCircle, ListChecks, Loader2, MessageSquare, X } from "lucide-react";
import { getUnitDetails, type QuadrantUnit, type UnitDetailsResponse } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProjects } from "@/context/ProjectsContext";
import { buildUnitQuizAction, dispatchChatAction } from "@/lib/progressEvents";
import { dictionaries } from "@/locales";

const t = dictionaries.trainer.detailModal;

const ACTIVITY_ICONS = {
  chat_question: MessageSquare,
  quiz: ListChecks,
} as const;

export type ProgressDetailModalProps = {
  /** Sesión del alumno cuyos logros se auditan. */
  studentSessionId: string;
  /** Unidad (celda) a detallar; null cierra el modal. */
  unit: QuadrantUnit | null;
  onClose: () => void;
};

/**
 * Modal de drill-down de una celda: hace fetch a
 * /trainer/progress/unit-details y muestra el histórico de actividades y
 * el desglose de la nota (cuestionarios 75% + preguntas al chat 25%).
 */
export default function ProgressDetailModal({
  studentSessionId,
  unit,
  onClose,
}: ProgressDetailModalProps) {
  const unitId = unit?.unit_id ?? null;
  const { accessToken } = useAuth();
  const { effectiveSessionId } = useProjects();

  const [details, setDetails] = useState<UnitDetailsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (unitId === null || !effectiveSessionId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetails(null);

    getUnitDetails(studentSessionId, unitId, effectiveSessionId, accessToken)
      .then((res) => {
        if (!cancelled) setDetails(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t.error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [unitId, studentSessionId, effectiveSessionId, accessToken]);

  if (unit === null || unitId === null) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={t.title}
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-gray-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h3 className="text-base font-semibold text-gray-800 dark:text-gray-100">
            {details ? details.unit_name : t.title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            aria-label={t.close}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-800 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-gray-500 dark:text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t.loading}
          </div>
        ) : error ? (
          <p className="py-6 text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        ) : details ? (
          <div className="space-y-4">
            {/* Resumen de puntuación */}
            <div className="flex items-center gap-3 rounded-lg border border-gray-100 p-3 dark:border-gray-700">
              <div
                className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg text-lg font-bold text-white"
                style={{ backgroundColor: details.color_code }}
              >
                {details.total_score.toFixed(1)}
              </div>
              <div className="min-w-0 text-sm">
                <p className="font-medium text-gray-800 dark:text-gray-100">
                  {t.scoreLabel}: {details.total_score.toFixed(2)} / 10
                </p>
                <p className="text-gray-500 dark:text-gray-400">
                  {t.quizPointsLabel}: {details.quiz_points.toFixed(2)}
                </p>
                <p className="text-gray-500 dark:text-gray-400">
                  {t.actionPointsLabel}: {details.action_points.toFixed(2)}
                </p>
              </div>
            </div>

            {unit && (
              <div className="rounded-lg border border-emerald-100 bg-emerald-50/50 p-3 dark:border-emerald-900/40 dark:bg-emerald-500/5">
                <p className="mb-2 text-xs text-gray-600 dark:text-gray-400">
                  {t.generateQuizHint}
                </p>
                <button
                  type="button"
                  onClick={() => {
                    dispatchChatAction(
                      buildUnitQuizAction(unit.unit_id, unit.name, unit.definition),
                    );
                    onClose();
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-600"
                >
                  <BrainCircuit className="h-4 w-4" aria-hidden="true" />
                  {t.generateQuiz}
                </button>
              </div>
            )}

            {/* Desglose de actividades (sin vídeos) */}
            <div className="grid grid-cols-2 gap-2 text-center text-xs">
              <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-800">
                <ListChecks className="mx-auto mb-1 h-4 w-4 text-emerald-500" aria-hidden="true" />
                <p className="font-medium text-gray-800 dark:text-gray-100">
                  {t.quizCount(details.quiz_stats.count)}
                </p>
                <p className="text-gray-500 dark:text-gray-400">
                  {details.quiz_stats.average_score !== null
                    ? t.quizAverage(details.quiz_stats.average_score.toFixed(2))
                    : t.noQuizzes}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-800">
                <MessageSquare className="mx-auto mb-1 h-4 w-4 text-emerald-500" aria-hidden="true" />
                <p className="font-medium text-gray-800 dark:text-gray-100">
                  {t.chatCount(details.chat_question_count)}
                </p>
              </div>
            </div>

            {/* Histórico */}
            <div>
              <h4 className="mb-2 text-sm font-semibold text-gray-800 dark:text-gray-100">
                {t.historyTitle}
              </h4>
              {details.activities.length === 0 ? (
                <p className="text-sm text-gray-500 dark:text-gray-400">{t.emptyHistory}</p>
              ) : (
                <ul className="space-y-1.5">
                  {details.activities
                    .filter(
                      (activity): activity is typeof activity & {
                        activity_type: "chat_question" | "quiz";
                      } => activity.activity_type !== "video",
                    )
                    .map((activity) => {
                    const Icon = ACTIVITY_ICONS[activity.activity_type] ?? HelpCircle;
                    return (
                      <li
                        key={activity.id}
                        className="flex items-start gap-2 rounded-lg border border-gray-100 px-2.5 py-2 text-xs dark:border-gray-800"
                      >
                        <Icon
                          className="mt-0.5 h-3.5 w-3.5 shrink-0 text-gray-400 dark:text-gray-500"
                          aria-hidden="true"
                        />
                        <div className="min-w-0 flex-1">
                          <p className="font-medium text-gray-700 dark:text-gray-200">
                            {t.activityLabels[activity.activity_type]}
                            {activity.score_earned !== null &&
                              ` — ${activity.score_earned.toFixed(1)} pts`}
                          </p>
                          {activity.detail && (
                            <p className="truncate text-gray-500 dark:text-gray-400">
                              {activity.detail}
                            </p>
                          )}
                          <p className="text-gray-400 dark:text-gray-500">
                            {new Date(activity.timestamp).toLocaleString("es-ES")}
                          </p>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
