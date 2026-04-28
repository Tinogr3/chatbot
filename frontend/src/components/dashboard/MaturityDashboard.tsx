"use client";

import {
  HEATMAP_LEVELS,
  categories,
  learningCriteria,
} from "@/constants/dashboardConfig";
import type { LearningCriterion } from "@/constants/dashboardConfig";
import LearningCriteriaSection from "./LearningCriteriaSection";

export type MaturityDashboardProps = {
  title?: string;
  lastUpdatedText?: string;
  description?: string;
  criteria?: LearningCriterion[];
};

export default function MaturityDashboard({
  title = "Dashboard de Madurez de Habilidades",
  lastUpdatedText = "Actualizado hace 2h",
  description = "Progreso dinámico según tu actividad y evaluaciones.",
  criteria = learningCriteria,
}: MaturityDashboardProps) {
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
              <span className="text-gray-700 dark:text-gray-300">
                {cat.name}
              </span>
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
                    title={`Nivel ${level}`}
                  />
                ),
              )}
            </div>
          </div>
        ))}
      </div>

      {criteria.length > 0 && (
        <div className="mt-6 border-t border-gray-100 pt-6 dark:border-gray-700">
          <h3 className="mb-4 text-base font-semibold text-gray-800 dark:text-gray-100">
            Criterios de Aprendizaje y Calificaciones
          </h3>
          <LearningCriteriaSection criteria={criteria} />
        </div>
      )}
    </section>
  );
}

