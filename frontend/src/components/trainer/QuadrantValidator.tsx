"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, Table2, Trash2 } from "lucide-react";
import {
  getTrainerLearningOutcomes,
  saveItinerary,
  type CourseItineraryCreate,
  type GeneratedItinerary,
  type TrainerLearningOutcomeOption,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.trainer.quadrant;

export type QuadrantValidatorProps = {
  /** Itinerario propuesto por el chat IA; null hasta la primera generación. */
  itinerary: GeneratedItinerary | null;
  /** Notifica al padre que el itinerario quedó guardado en BD. */
  onSaved?: () => void;
};

/** Estado editable plano: el formador puede retocar cualquier campo. */
type EditableUnit = {
  name: string;
  definition: string;
  weight: number;
  learning_outcome_id: number | null;
};
type EditableTheme = { name: string; units: EditableUnit[] };

function toEditable(itinerary: GeneratedItinerary): EditableTheme[] {
  return itinerary.themes.map((theme) => ({
    name: theme.name,
    units: theme.learning_units.map((u) => ({
      name: u.name,
      definition: u.definition,
      weight: u.weight,
      learning_outcome_id: null,
    })),
  }));
}

/**
 * Tabla editable del cuadrante (temas → unidades con definición y peso %).
 * "Validar y Guardar" envía el resultado a POST /trainer/save-itinerary
 * convirtiendo los % mostrados a fracciones 0-1 que espera el backend.
 */
export default function QuadrantValidator({ itinerary, onSaved }: QuadrantValidatorProps) {
  const { accessToken } = useAuth();
  const { effectiveSessionId, currentProject } = useProjects();

  const projectDocumentKeys = useMemo(
    () => currentProject?.documents.map((d) => d.docKey ?? d.name).filter(Boolean) ?? [],
    [currentProject?.documents],
  );
  const hasProjectDocuments = projectDocumentKeys.length > 0;

  const [title, setTitle] = useState("");
  const [weeks, setWeeks] = useState(4);
  const [hoursPerWeek, setHoursPerWeek] = useState(10);
  const [themes, setThemes] = useState<EditableTheme[]>([]);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const [outcomes, setOutcomes] = useState<TrainerLearningOutcomeOption[]>([]);
  const [outcomesLoading, setOutcomesLoading] = useState(false);

  useEffect(() => {
    if (!effectiveSessionId) return;
    let cancelled = false;
    setOutcomesLoading(true);
    getTrainerLearningOutcomes(
      effectiveSessionId,
      projectDocumentKeys.length > 0 ? projectDocumentKeys : undefined,
      accessToken,
    )
      .then((list) => {
        if (!cancelled) setOutcomes(list);
      })
      .catch(() => {
        if (!cancelled) setOutcomes([]);
      })
      .finally(() => {
        if (!cancelled) setOutcomesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveSessionId, accessToken, projectDocumentKeys]);

  useEffect(() => {
    if (!effectiveSessionId || !hasProjectDocuments) return;
    const timer = window.setInterval(() => {
      getTrainerLearningOutcomes(
        effectiveSessionId,
        projectDocumentKeys,
        accessToken,
      )
        .then((list) => {
          if (list.length > 0) setOutcomes(list);
        })
        .catch(() => {});
    }, 8000);
    return () => window.clearInterval(timer);
  }, [effectiveSessionId, accessToken, hasProjectDocuments, projectDocumentKeys]);

  useEffect(() => {
    if (!itinerary) return;
    setTitle(itinerary.title);
    setWeeks(itinerary.total_weeks);
    setHoursPerWeek(itinerary.hours_per_week);
    setThemes(toEditable(itinerary));
    setFeedback(null);
  }, [itinerary]);

  const totalWeight = useMemo(
    () => themes.reduce((acc, th) => acc + th.units.reduce((a, u) => a + u.weight, 0), 0),
    [themes],
  );
  const weightIsValid = Math.abs(totalWeight - 100) < 0.5;

  const updateUnit = (
    themeIdx: number,
    unitIdx: number,
    patch: Partial<EditableUnit>,
  ) => {
    setThemes((prev) =>
      prev.map((theme, ti) =>
        ti !== themeIdx
          ? theme
          : {
              ...theme,
              units: theme.units.map((unit, ui) =>
                ui !== unitIdx ? unit : { ...unit, ...patch },
              ),
            },
      ),
    );
  };

  const updateThemeName = (themeIdx: number, name: string) => {
    setThemes((prev) =>
      prev.map((theme, ti) => (ti !== themeIdx ? theme : { ...theme, name })),
    );
  };

  const removeUnit = (themeIdx: number, unitIdx: number) => {
    setThemes((prev) =>
      prev
        .map((theme, ti) =>
          ti !== themeIdx
            ? theme
            : { ...theme, units: theme.units.filter((_, ui) => ui !== unitIdx) },
        )
        .filter((theme) => theme.units.length > 0),
    );
  };

  const handleSave = async () => {
    if (!effectiveSessionId || saving || themes.length === 0) return;
    setSaving(true);
    setFeedback(null);

    const payload: CourseItineraryCreate = {
      title: title.trim() || "Curso sin título",
      total_weeks: weeks,
      hours_per_week: hoursPerWeek,
      themes: themes.map((theme, ti) => ({
        name: theme.name.trim(),
        order_index: ti,
        learning_units: theme.units.map((unit, ui) => ({
          name: unit.name.trim(),
          definition: unit.definition.trim(),
          // El backend espera fracciones 0-1; la tabla muestra %
          weight: Math.max(0, Math.min(1, unit.weight / 100)),
          order_index: ui,
          learning_outcome_id: unit.learning_outcome_id ?? undefined,
        })),
      })),
    };

    try {
      const res = await saveItinerary(payload, effectiveSessionId, accessToken);
      setFeedback({ ok: true, text: t.saveSuccess(res.message) });
      onSaved?.();
    } catch (err) {
      setFeedback({
        ok: false,
        text: err instanceof Error ? err.message : t.saveError,
      });
    } finally {
      setSaving(false);
    }
  };

  if (!itinerary || themes.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 bg-white p-6 text-center dark:border-gray-700 dark:bg-gray-900/50">
        <Table2 className="mb-2 h-8 w-8 text-gray-300 dark:text-gray-600" aria-hidden="true" />
        <p className="text-sm text-gray-500 dark:text-gray-400">{t.emptyState}</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-gray-100 bg-white dark:border-gray-700 dark:bg-gray-900/50">
      <div className="space-y-2 border-b border-gray-100 px-4 py-3 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Table2 className="h-4 w-4 text-emerald-500" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100">{t.title}</h3>
        </div>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-800 focus:border-emerald-500 focus:outline-none dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
        />
        <div className="flex gap-3 text-sm">
          <label className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            {t.weeksLabel}
            <input
              type="number"
              min={1}
              max={104}
              value={weeks}
              onChange={(e) => setWeeks(Math.max(1, Number(e.target.value) || 1))}
              className="w-16 rounded border border-gray-200 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            />
          </label>
          <label className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            {t.hoursLabel}
            <input
              type="number"
              min={1}
              max={80}
              value={hoursPerWeek}
              onChange={(e) => setHoursPerWeek(Math.max(1, Number(e.target.value) || 1))}
              className="w-16 rounded border border-gray-200 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
            />
          </label>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-3">
        {!outcomesLoading && outcomes.length === 0 && (
          <p className="mb-3 text-xs text-amber-700 dark:text-amber-400">
            {hasProjectDocuments ? t.competenciesProcessing : t.noCompetencies}
          </p>
        )}
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <th className="px-2 py-1.5">{t.unitHeader}</th>
              <th className="px-2 py-1.5">{t.definitionHeader}</th>
              <th className="min-w-[180px] px-2 py-1.5">{t.competencyHeader}</th>
              <th className="w-20 px-2 py-1.5 text-right">{t.weightHeader}</th>
              <th className="w-8 px-1 py-1.5" />
            </tr>
          </thead>
          {themes.map((theme, ti) => (
            <tbody key={ti}>
              <tr>
                <td colSpan={5} className="px-2 pb-1 pt-3">
                  <input
                    type="text"
                    value={theme.name}
                    onChange={(e) => updateThemeName(ti, e.target.value)}
                    aria-label={`${t.themeHeader} ${ti + 1}`}
                    className="w-full rounded border border-transparent bg-emerald-50 px-2 py-1 text-sm font-semibold text-emerald-800 focus:border-emerald-400 focus:outline-none dark:bg-emerald-500/10 dark:text-emerald-300"
                  />
                </td>
              </tr>
              {theme.units.map((unit, ui) => (
                <tr
                  key={ui}
                  className="border-b border-gray-50 align-top dark:border-gray-800"
                >
                  <td className="px-2 py-1.5">
                    <input
                      type="text"
                      value={unit.name}
                      onChange={(e) => updateUnit(ti, ui, { name: e.target.value })}
                      className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-sm text-gray-800 hover:border-gray-200 focus:border-emerald-400 focus:outline-none dark:text-gray-100 dark:hover:border-gray-700"
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <textarea
                      value={unit.definition}
                      onChange={(e) => updateUnit(ti, ui, { definition: e.target.value })}
                      rows={2}
                      className="w-full resize-y rounded border border-transparent bg-transparent px-1 py-0.5 text-xs text-gray-600 hover:border-gray-200 focus:border-emerald-400 focus:outline-none dark:text-gray-300 dark:hover:border-gray-700"
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <select
                      value={unit.learning_outcome_id ?? ""}
                      onChange={(e) =>
                        updateUnit(ti, ui, {
                          learning_outcome_id: e.target.value
                            ? Number(e.target.value)
                            : null,
                        })
                      }
                      disabled={outcomesLoading}
                      aria-label={`${t.competencyHeader} — ${unit.name}`}
                      className="w-full max-w-[220px] rounded border border-gray-200 bg-white px-1.5 py-1 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                    >
                      <option value="">
                        {outcomesLoading ? t.competencyLoading : t.competencyPlaceholder}
                      </option>
                      {outcomes.map((o) => (
                        <option key={o.id} value={o.id}>
                          {o.competency_name} › {o.subcompetency_name}:{" "}
                          {o.description.length > 48
                            ? `${o.description.slice(0, 48)}…`
                            : o.description}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1.5 text-right">
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.5}
                      value={unit.weight}
                      onChange={(e) =>
                        updateUnit(ti, ui, {
                          weight: Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                        })
                      }
                      className="w-16 rounded border border-gray-200 bg-white px-1.5 py-0.5 text-right text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-gray-100"
                    />
                  </td>
                  <td className="px-1 py-1.5">
                    <button
                      type="button"
                      onClick={() => removeUnit(ti, ui)}
                      aria-label={t.deleteUnitAriaLabel(unit.name)}
                      className="rounded p-1 text-gray-300 hover:text-red-500 dark:text-gray-600 dark:hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>

      <div className="space-y-2 border-t border-gray-100 px-4 py-3 dark:border-gray-700">
        <div className="flex items-center justify-between text-sm">
          <span
            className={
              weightIsValid
                ? "text-gray-600 dark:text-gray-300"
                : "font-medium text-amber-600 dark:text-amber-400"
            }
          >
            {t.totalWeight(totalWeight.toFixed(1))}
            {!weightIsValid && ` — ${t.weightWarning}`}
          </span>
        </div>
        {feedback && (
          <p
            role={feedback.ok ? "status" : "alert"}
            className={`text-sm ${
              feedback.ok
                ? "text-emerald-700 dark:text-emerald-300"
                : "text-red-600 dark:text-red-400"
            }`}
          >
            {feedback.text}
          </p>
        )}
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || themes.length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 py-2.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t.saving}
            </>
          ) : (
            <>
              <Check className="h-4 w-4" aria-hidden="true" />
              {t.save}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
