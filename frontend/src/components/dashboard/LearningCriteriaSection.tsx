"use client";

import type { GradeLevel, LearningCriterion } from "@/constants/dashboardConfig";

const GRADE_STYLES: Record<GradeLevel, { badge: string; bar: string }> = {
  A: {
    badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    bar: "bg-emerald-500",
  },
  B: {
    badge: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    bar: "bg-amber-500",
  },
  C: {
    badge: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
    bar: "bg-orange-500",
  },
  D: {
    badge: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
    bar: "bg-red-500",
  },
};

type LearningCriteriaSectionProps = {
  criteria: LearningCriterion[];
};

export default function LearningCriteriaSection({
  criteria,
}: LearningCriteriaSectionProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {criteria.map((criterion) => {
        const style = GRADE_STYLES[criterion.grade];
        return (
          <div
            key={criterion.id}
            className="flex flex-col gap-3 rounded-xl border border-gray-100 bg-white p-4 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
          >
            <div className="flex items-start gap-3">
              <span
                className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold ${style.badge}`}
              >
                {criterion.grade}
              </span>
              <div className="min-w-0">
                <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100">
                  {criterion.name}
                </h4>
                <p className="mt-0.5 line-clamp-2 text-xs text-gray-500 dark:text-gray-400">
                  {criterion.description}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-700">
                <div
                  className={`h-full rounded-full transition-all ${style.bar}`}
                  style={{ width: `${criterion.domainPercent}%` }}
                />
              </div>
              <span className="shrink-0 text-xs font-medium text-gray-600 dark:text-gray-300">
                {criterion.domainPercent}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
