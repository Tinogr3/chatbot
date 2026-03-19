"use client";

import { HEATMAP_LEVELS, categories } from "@/constants/dashboardConfig";

export type MaturityDashboardProps = {
  title?: string;
  lastUpdatedText?: string;
  description?: string;
};

export default function MaturityDashboard({
  title = "Dashboard de Madurez de Habilidades",
  lastUpdatedText = "Actualizado hace 2h",
  description = "Progreso dinámico según tu actividad y evaluaciones.",
}: MaturityDashboardProps) {
  return (
    <section className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <h2 className="text-lg font-semibold text-gray-800">{title}</h2>
        <button
          type="button"
          className="text-xs text-gray-500 hover:text-gray-700 shrink-0"
        >
          {lastUpdatedText}
        </button>
      </div>
      <p className="text-sm text-gray-500 mb-4">{description}</p>

      <div className="space-y-4">
        {categories.map((cat, catIndex) => (
          <div key={cat.name} className="space-y-1.5">
            <div className="flex justify-between text-sm">
              <span className="text-gray-700">{cat.name}</span>
              <span className="font-medium text-gray-800">{cat.percent}%</span>
            </div>

            <div className="flex gap-0.5">
              {HEATMAP_LEVELS[catIndex % HEATMAP_LEVELS.length].map((level, i) => (
                <div
                  key={i}
                  className="w-6 h-6 rounded-sm flex-shrink-0"
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
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

