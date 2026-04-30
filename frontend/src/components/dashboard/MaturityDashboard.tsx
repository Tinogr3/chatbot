"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useProjects } from "@/context/ProjectsContext";
import {
  getDashboardCompetencies,
  type DashboardCompetencyItem,
  type DashboardDocumentCompetencies,
} from "@/lib/api";
import { useProgressUpdated } from "@/lib/progressEvents";
import { dictionaries } from "@/locales";

const t = dictionaries.dashboard.maturity;

// ---------------------------------------------------------------------------
// Puntuación 0–1 (backend) → color del indicador (negro sin práctica → verde claro)
// ---------------------------------------------------------------------------

function clamp01(score: number): number {
  const safe = Number.isFinite(score) ? score : 0;
  return Math.max(0, Math.min(1, safe));
}

/**
 * Interpolación en HSL: sin práctica (t≈0) → negro neutro; con práctica suben
 * saturación y luminosidad hasta un verde claro tipo esmeralda.
 */
function scoreToPracticeColor(score: number): string {
  const t = clamp01(score);
  const hue = 152;
  const sat = t * 72;
  const light = 5 + t * 82;
  return `hsl(${hue} ${sat}% ${light}%)`;
}

function scoreToPracticePercent(score: number): number {
  return Math.round(clamp01(score) * 100);
}

function formatDocumentTitle(documentId: string): string {
  try {
    const base = documentId.split(/[/\\]/).pop() ?? documentId;
    return decodeURIComponent(base);
  } catch {
    return documentId;
  }
}

function CompetencyPracticeSquare({ score }: { score: number }) {
  const pct = scoreToPracticePercent(score);
  const bg = scoreToPracticeColor(score);
  return (
    <div
      className="h-8 w-8 shrink-0 rounded-md border border-black/15 shadow-sm dark:border-white/15"
      style={{ backgroundColor: bg }}
      role="img"
      aria-label={t.practiceLevelAriaLabel(pct)}
      title={t.practiceLevelTitle(pct)}
    />
  );
}

function CompetencyRow({ item }: { item: DashboardCompetencyItem }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2.5 dark:border-gray-700 dark:bg-gray-900/40">
      <span className="min-w-0 flex-1 text-sm font-medium text-gray-800 dark:text-gray-100">
        {item.name}
      </span>
      <div className="flex shrink-0 items-center">
        <CompetencyPracticeSquare score={item.score} />
      </div>
    </li>
  );
}

function DocumentBlock({ block }: { block: DashboardDocumentCompetencies }) {
  const title = formatDocumentTitle(block.document_id);
  return (
    <div className="rounded-xl border border-gray-100 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/50">
      <h3 className="mb-3 text-sm font-semibold text-gray-800 dark:text-gray-100">
        {title}
      </h3>
      {block.competencies.length === 0 ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">{t.noCompetenciesYet}</p>
      ) : (
        <ul className="space-y-2">
          {block.competencies.map((c, i) => (
            <CompetencyRow
              key={`${block.document_id}-${i}-${c.name}`}
              item={c}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div
      className="space-y-4"
      role="status"
      aria-live="polite"
      aria-label={t.loadingLabel}
    >
      {[0, 1].map((i) => (
        <div
          key={i}
          className="animate-pulse rounded-xl border border-gray-100 bg-white p-4 dark:border-gray-700 dark:bg-gray-900/50"
        >
          <div className="mb-3 h-4 w-1/3 rounded bg-gray-200 dark:bg-gray-700" />
          <div className="space-y-2">
            <div className="h-10 rounded-lg bg-gray-100 dark:bg-gray-800" />
            <div className="h-10 rounded-lg bg-gray-100 dark:bg-gray-800" />
          </div>
        </div>
      ))}
      <span className="sr-only">{t.loadingLabel}</span>
    </div>
  );
}

export type MaturityDashboardProps = {
  /**
   * Override para tests: si se pasa, no se hace fetch al backend.
   */
  documentsOverride?: DashboardDocumentCompetencies[] | null;
};

export default function MaturityDashboard({ documentsOverride }: MaturityDashboardProps) {
  const { effectiveSessionId, currentProject } = useProjects();
  const projectDocumentNames = useMemo(
    () => currentProject?.documents.map((d) => d.name).filter(Boolean) ?? [],
    [currentProject?.documents],
  );
  const [fetched, setFetched] = useState<DashboardDocumentCompetencies[] | null>(null);
  const [loading, setLoading] = useState<boolean>(documentsOverride === undefined);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleProgressUpdated = useCallback(() => {
    setRefreshKey((n) => n + 1);
  }, []);
  useProgressUpdated(handleProgressUpdated);

  useEffect(() => {
    if (documentsOverride !== undefined) {
      setLoading(false);
      setError(null);
      return;
    }

    if (!effectiveSessionId) {
      setFetched([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getDashboardCompetencies(
      effectiveSessionId,
      projectDocumentNames.length > 0 ? projectDocumentNames : undefined,
    )
      .then((response) => {
        if (cancelled) return;
        setFetched(response.documents);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : String(err);
        setError(message || t.criteriaError);
        setFetched([]);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [documentsOverride, effectiveSessionId, projectDocumentNames, refreshKey]);

  const documents =
    documentsOverride !== undefined ? documentsOverride ?? [] : fetched ?? [];

  const showEmpty =
    !loading && !error && documents.length === 0;

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-5 text-lg font-semibold text-gray-800 dark:text-gray-100">
        {t.title}
      </h2>

      {loading ? (
        <DashboardSkeleton />
      ) : error ? (
        <p className="text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      ) : showEmpty ? (
        <p className="text-sm text-gray-500 dark:text-gray-400">{t.criteriaEmpty}</p>
      ) : (
        <div className="space-y-4">
          {documents.map((block) => (
            <DocumentBlock key={block.document_id} block={block} />
          ))}
        </div>
      )}
    </section>
  );
}
