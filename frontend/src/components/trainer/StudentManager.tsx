"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, Search, UserMinus, UserPlus } from "lucide-react";
import {
  assignStudent,
  getAvailableStudents,
  getMyStudents,
  removeStudent,
  type UserOut,
} from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.trainer.studentManager;

function StudentRow({
  student,
  action,
  actionLabel,
  onAction,
  busy,
}: {
  student: UserOut;
  action: "assign" | "remove";
  actionLabel: string;
  onAction: () => void;
  busy: boolean;
}) {
  const Icon = action === "assign" ? UserPlus : UserMinus;
  return (
    <li className="flex items-center justify-between gap-2 rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-700">
      <span className="min-w-0 truncate text-sm font-medium text-gray-800 dark:text-gray-100">
        {student.username}
      </span>
      <button
        type="button"
        onClick={onAction}
        disabled={busy}
        className={`flex shrink-0 items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-white disabled:opacity-60 ${
          action === "assign"
            ? "bg-emerald-500 hover:bg-emerald-600"
            : "bg-gray-500 hover:bg-gray-600"
        }`}
      >
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {actionLabel}
      </button>
    </li>
  );
}

/**
 * Panel del formador: alumnos disponibles y asignados.
 */
export default function StudentManager() {
  const { accessToken } = useAuth();
  const { effectiveSessionId } = useProjects();

  const [available, setAvailable] = useState<UserOut[]>([]);
  const [mine, setMine] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredAvailable = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return available;
    return available.filter((s) => s.username.toLowerCase().includes(q));
  }, [available, searchQuery]);

  const loadLists = useCallback(() => {
    if (!effectiveSessionId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      getAvailableStudents(effectiveSessionId, accessToken),
      getMyStudents(effectiveSessionId, accessToken),
    ])
      .then(([avail, assigned]) => {
        if (!cancelled) {
          setAvailable(avail.students);
          setMine(assigned.students);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t.error);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [effectiveSessionId, accessToken]);

  useEffect(() => {
    const cancel = loadLists();
    return cancel;
  }, [loadLists]);

  const handleAssign = async (student: UserOut) => {
    if (!effectiveSessionId) return;
    setBusyId(student.id);
    try {
      await assignStudent({ student_id: student.id }, effectiveSessionId, accessToken);
      loadLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.assignError);
    } finally {
      setBusyId(null);
    }
  };

  const handleRemove = async (student: UserOut) => {
    if (!effectiveSessionId) return;
    setBusyId(student.id);
    try {
      await removeStudent(student.username, effectiveSessionId, accessToken);
      loadLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.removeError);
    } finally {
      setBusyId(null);
    }
  };

  if (!effectiveSessionId) return null;

  return (
    <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <h2 className="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-100">
        {t.title}
      </h2>

      {loading ? (
        <div className="flex items-center gap-2 py-8 text-sm text-gray-500 dark:text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t.loading}
        </div>
      ) : error ? (
        <p className="py-4 text-sm text-red-600 dark:text-red-400" role="alert">
          {error}
        </p>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
              {t.availableTitle}
            </h3>
            <div className="relative mb-3">
              <Search
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
                aria-hidden="true"
              />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t.searchPlaceholder}
                aria-label={t.searchAriaLabel}
                className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2 pl-9 pr-3 text-sm text-gray-800 placeholder:text-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500"
              />
            </div>
            {available.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.emptyAvailable}</p>
            ) : filteredAvailable.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.noSearchResults}</p>
            ) : (
              <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
                {filteredAvailable.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    action="assign"
                    actionLabel={t.assign}
                    onAction={() => handleAssign(student)}
                    busy={busyId === student.id}
                  />
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
              {t.mineTitle}
            </h3>
            {mine.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">{t.emptyMine}</p>
            ) : (
              <ul className="space-y-2">
                {mine.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    action="remove"
                    actionLabel={t.remove}
                    onAction={() => handleRemove(student)}
                    busy={busyId === student.id}
                  />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
