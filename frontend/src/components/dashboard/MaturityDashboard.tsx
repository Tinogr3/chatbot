"use client";

import { useCallback, useEffect, useState } from "react";

import { useProjects } from "@/context/ProjectsContext";
import {
  getDashboardCompetencies,
  type DashboardCompetencyItem,
} from "@/lib/api";
import { useProgressUpdated } from "@/lib/progressEvents";
import {
  HEATMAP_LEVELS,
  categories,
  type GradeLevel,
  type LearningCriterion,
} from "@/constants/dashboardConfig";
import { dictionaries } from "@/locales";

import LearningCriteriaSection from "./LearningCriteriaSection";

const t = dictionaries.dashboard.maturity;

// ---------------------------------------------------------------------------
// Mapeo backend → frontend
// ---------------------------------------------------------------------------

/**
 * Convierte el `score` del backend (0.0–1.0) en `domainPercent` (0–100)
 * con redondeo entero. Aplica clamp defensivo y trata `NaN`/`Infinity`
 * como 0 para no propagar valores corruptos al UI.
 */
function scoreToDomainPercent(score: number): number {
  const safe = Number.isFinite(score) ? score : 0;
  const clamped = Math.max(0, Math.min(1, safe));
  return Math.round(clamped * 100);
}

/**
 * Asigna grade en base al `domainPercent`:
 *   > 90  → A
 *   > 75  → B
 *   > 60  → C
 *   resto → D
 */
function gradeFromPercent(percent: number): GradeLevel {
  if (percent > 90) return "A";
  if (percent > 75) return "B";
  if (percent > 60) return "C";
  return "D";
}

/**
 * Transforma un `DashboardCompetencyItem` (backend) en `LearningCriterion`
 * (UI). El `id` se compone con el índice + nombre para garantizar unicidad
 * estable dentro de la respuesta y servir como `key` en React.
 */
export function mapCompetencyToCriterion(
  item: DashboardCompetencyItem,
  index: number,
): LearningCriterion {
  const domainPercent = scoreToDomainPercent(item.score);
  return {
    id: `competency-${index}-${item.name}`,
    name: item.name,
    domainPercent,
    grade: gradeFromPercent(domainPercent),
    category: item.name,
  };
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

/**
 * Skeleton minimalista que respeta el grid de `LearningCriteriaSection`
 * (`sm:grid-cols-2 lg:grid-cols-3`) y la silueta de cada tarjeta: badge de
 * grade, título, descripción y barra de progreso. Animación `animate-pulse`
 * y mismas clases de tema que el contenido real para evitar saltos visuales
 * cuando los datos llegan.
 */
function LearningCriteriaSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      role="status"
      aria-live="polite"
      aria-label={t.criteriaLoading}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="flex animate-pulse flex-col gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
          aria-hidden="true"
        >
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 shrink-0 rounded-lg bg-gray-200 dark:bg-gray-700" />
            <div className="min-w-0 flex-1 space-y-2">
              <div className="h-3.5 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
              <div className="h-3 w-full rounded bg-gray-100 dark:bg-gray-700/60" />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 rounded-full bg-gray-100 dark:bg-gray-700" />
            <div className="h-3 w-8 rounded bg-gray-200 dark:bg-gray-700" />
          </div>
        </div>
      ))}
      <span className="sr-only">{t.criteriaLoading}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Componente principal
// ---------------------------------------------------------------------------

export type MaturityDashboardProps = {
  title?: string;
  lastUpdatedText?: string;
  description?: string;
  /**
   * Override opcional para tests/storybook. Si se pasa, se usa tal cual y
   * el componente no realiza fetch al backend.
   */
  criteria?: LearningCriterion[];
};

export default function MaturityDashboard({
  title = t.title,
  lastUpdatedText = t.lastUpdated,
  description = t.description,
  criteria: criteriaOverride,
}: MaturityDashboardProps) {
  const { effectiveSessionId } = useProjects();
  const [fetchedCriteria, setFetchedCriteria] = useState<LearningCriterion[] | null>(
    null,
  );
  const [loading, setLoading] = useState<boolean>(criteriaOverride === undefined);
  const [error, setError] = useState<string | null>(null);
  /**
   * Bumpear este contador re-dispara el `useEffect` de fetch sin invalidar
   * sus otras dependencias. Se incrementa cuando llega un evento global de
   * progreso actualizado (vía `useProgressUpdated`), por ejemplo después de
   * que el usuario responde correctamente en modo aprendizaje y el backend
   * persiste la evidencia.
   */
  const [refreshKey, setRefreshKey] = useState(0);

  const handleProgressUpdated = useCallback(() => {
    setRefreshKey((n) => n + 1);
  }, []);
  useProgressUpdated(handleProgressUpdated);

  /**
   * Fetch dinámico al montar (y al cambiar de proyecto/usuario, ya que
   * `effectiveSessionId` cambia con la combinación user+project, o cuando
   * `refreshKey` se incrementa por un evento de progreso). Se cancela de
   * forma segura con un flag `cancelled` para descartar respuestas
   * pertenecientes a un sessionId previo si el usuario navega rápido.
   */
  useEffect(() => {
    if (criteriaOverride !== undefined) {
      setLoading(false);
      setError(null);
      return;
    }

    if (!effectiveSessionId) {
      setFetchedCriteria([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getDashboardCompetencies(effectiveSessionId)
      .then((response) => {
        if (cancelled) return;
        setFetchedCriteria(response.competencies.map(mapCompetencyToCriterion));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setError(message || t.criteriaError);
        setFetchedCriteria([]);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [criteriaOverride, effectiveSessionId, refreshKey]);

  const criteria = criteriaOverride ?? fetchedCriteria ?? [];

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-4 flex items-start justify-between gap-4">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
          {title}
        </h2>
        <button
          type="button"
          className="shrink-0 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
        >
          {lastUpdatedText}
        </button>
      </div>
      <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
        {description}
      </p>

      <div className="space-y-4">
        {categories.map((cat, catIndex) => (
          <div key={cat.name} className="space-y-1.5">
            <div className="flex justify-between text-sm">
              <span className="text-gray-700 dark:text-gray-300">{cat.name}</span>
              <span className="font-medium text-gray-800 dark:text-gray-100">
                {cat.percent}%
              </span>
            </div>

            <div className="flex gap-0.5">
              {HEATMAP_LEVELS[catIndex % HEATMAP_LEVELS.length].map(
                (level, i) => (
                  <div
                    key={i}
                    className="h-6 w-6 flex-shrink-0 rounded-sm"
                    style={{
                      backgroundColor:
                        level === 5
                          ? "#059669"
                          : level === 4
                            ? "#10b981"
                            : level === 3
                              ? "#34d399"
                              : level === 2
                                ? "#6ee7b7"
                                : "#a7f3d0",
                    }}
                    title={t.heatmapLevelTitle(level)}
                  />
                ),
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 border-t border-gray-100 pt-6 dark:border-gray-700">
        <h3 className="mb-4 text-base font-semibold text-gray-800 dark:text-gray-100">
          {t.criteriaSectionTitle}
        </h3>
        {loading ? (
          <LearningCriteriaSkeleton />
        ) : error ? (
          <p className="text-sm text-red-600 dark:text-red-400" role="alert">
            {error}
          </p>
        ) : criteria.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {t.criteriaEmpty}
          </p>
        ) : (
          <LearningCriteriaSection criteria={criteria} />
        )}
      </div>
    </section>
  );
}
