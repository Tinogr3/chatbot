"use client";

import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, Loader2, RefreshCw } from "lucide-react";
import { getProgressQuadrant, type QuadrantResponse, type QuadrantUnit } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProjects } from "@/context/ProjectsContext";
import ProgressDetailModal from "@/components/trainer/ProgressDetailModal";
import { buildUnitQuizAction, dispatchChatAction, useProgressUpdated } from "@/lib/progressEvents";
import { dictionaries } from "@/locales";

const t = dictionaries.trainer.progress;

export type StudentProgressDashboardProps = {
  /** Cambia para forzar un refetch (ej. tras guardar un itinerario). */
  refreshKey?: number;
};

/**
 * Cuadrante visual de progreso (heatmap): cada celda es una unidad de
 * aprendizaje pintada con su color_code y su puntuación 0-10. Clic en una
 * celda → modal con el detalle del histórico.
 */
export default function StudentProgressDashboard({
  refreshKey = 0,
}: StudentProgressDashboardProps) {
  const { accessToken } = useAuth();
  const { effectiveSessionId } = useProjects();

  const [quadrant, setQuadrant] = useState<QuadrantResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [selectedUnit, setSelectedUnit] = useState<QuadrantUnit | null>(null);
  const [localRefresh, setLocalRefresh] = useState(0);

  useProgressUpdated(() => {
    setLocalRefresh((n) => n + 1);
  });

  const fetchQuadrant = useCallback(() => {
    if (!effectiveSessionId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotFound(false);

    getProgressQuadrant(effectiveSessionId, effectiveSessionId, accessToken)
      .then((res) => {
        if (!cancelled) setQuadrant(res);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : t.error;
        // El backend devuelve 404 con detalle claro si no hay itinerario
        if (message.toLowerCase().includes("no hay itinerario")) {
          setNotFound(true);
        } else {
          setError(message);
        }
        setQuadrant(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [effectiveSessionId, accessToken]);

  useEffect(() => {
    const cancel = fetchQuadrant();
    return cancel;
  }, [fetchQuadrant, refreshKey, localRefresh]);

  if (!effectiveSessionId) return null;

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
            {t.title}
          </h2>
          {quadrant && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {quadrant.title} · {quadrant.total_weeks} sem ·{" "}
              {quadrant.hours_per_week}h/sem · {t.overallLabel}:{" "}
              <span className="font-semibold">{quadrant.overall_score.toFixed(2)}</span>
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setLocalRefresh((n) => n + 1)}
          aria-label={t.refresh}
          title={t.refresh}
          className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-700 dark:hover:text-gray-200"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-gray-500 dark:text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t.loading}
        </div>
      ) : notFound ? (
        <p className="py-6 text-sm text-gray-500 dark:text-gray-400">{t.emptyState}</p>
      ) : error ? (
        <p className="py-6 text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      ) : quadrant ? (
        <div className="space-y-5">
          {quadrant.themes.map((theme) => (
            <div key={theme.theme_id}>
              <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                {theme.name}
              </h3>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
                {theme.units.map((unit) => (
                  <div
                    key={unit.unit_id}
                    className="group flex min-h-[84px] flex-col rounded-lg p-2.5 text-left text-white shadow-sm transition-transform hover:scale-[1.03]"
                    style={{ backgroundColor: unit.color_code }}
                  >
                    <button
                      type="button"
                      onClick={() => setSelectedUnit(unit)}
                      aria-label={t.cellAriaLabel(unit.name, unit.score)}
                      title={unit.definition}
                      className="flex flex-1 flex-col justify-between text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-white/80 rounded"
                    >
                      <span className="line-clamp-2 text-xs font-medium leading-tight drop-shadow-sm">
                        {unit.name}
                      </span>
                      <span className="flex items-baseline justify-between gap-1">
                        <span className="text-lg font-bold drop-shadow-sm">
                          {unit.score.toFixed(1)}
                        </span>
                        <span className="text-[10px] opacity-90">
                          {unit.percent_complete.toFixed(0)}%
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        dispatchChatAction(
                          buildUnitQuizAction(unit.unit_id, unit.name, unit.definition),
                        );
                      }}
                      aria-label={t.generateQuizAriaLabel(unit.name)}
                      className="mt-2 flex w-full items-center justify-center gap-1 rounded bg-white/20 px-2 py-1 text-[10px] font-medium text-white opacity-0 transition-opacity hover:bg-white/30 group-hover:opacity-100 focus:opacity-100"
                    >
                      <BrainCircuit className="h-3 w-3" aria-hidden="true" />
                      {t.generateQuiz}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      <ProgressDetailModal
        studentSessionId={effectiveSessionId}
        unit={selectedUnit}
        onClose={() => setSelectedUnit(null)}
      />
    </section>
  );
}
