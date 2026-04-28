"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronUp, LogOut, Settings, Trash2, X } from "lucide-react";
import { clearSession, deleteUserFacts } from "@/lib/api";
import { useUser } from "@/context/UserContext";
import { useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.sidebar.settings;
const tConfirm = t.confirmClear;

type ToastState = { message: string; type: "success" | "error" } | null;

export default function UserSettings() {
  const { sessionId, logout } = useUser();
  const { projects, effectiveSessionId, clearAllProjects } = useProjects();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [actionLoading, setActionLoading] = useState<"clear" | "facts" | null>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!toast) return;
    const tm = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(tm);
  }, [toast]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  /**
   * Borra todos los datos backend del usuario:
   *  - Para cada proyecto se compone su `${user}__${projectId}` y se invocan en
   *    paralelo `clearSession` (chat history + document registry + chroma) y
   *    `deleteUserFacts` (memoria del usuario).
   *  - Se ignoran fallos individuales para garantizar que el resto de
   *    proyectos también se purgue (Promise.allSettled).
   *  - Tras el borrado backend, se limpia el estado/localStorage del cliente
   *    y se cierra la sesión devolviendo al usuario al WelcomeScreen.
   */
  const handleConfirmClear = useCallback(async () => {
    if (!sessionId) return;
    setActionLoading("clear");
    try {
      const sessionIdsToWipe =
        projects.length > 0
          ? projects.map((project) => `${sessionId}__${project.id}`)
          : effectiveSessionId
            ? [effectiveSessionId]
            : [];

      const operations = sessionIdsToWipe.flatMap((compositeId) => [
        clearSession(compositeId),
        deleteUserFacts(compositeId),
      ]);

      await Promise.allSettled(operations);

      clearAllProjects();
      setConfirmOpen(false);
      setSettingsOpen(false);
      setToast({ message: t.clearSessionSuccess, type: "success" });
      logout();
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : t.clearSessionError,
        type: "error",
      });
    } finally {
      setActionLoading(null);
    }
  }, [sessionId, projects, effectiveSessionId, clearAllProjects, logout]);

  const handleDeleteUserFacts = useCallback(async () => {
    if (!effectiveSessionId) return;
    setActionLoading("facts");
    try {
      const res = await deleteUserFacts(effectiveSessionId);
      setToast({ message: t.forgetDataSuccess(res.deleted), type: "success" });
    } catch (e) {
      setToast({
        message: e instanceof Error ? e.message : t.forgetDataError,
        type: "error",
      });
    } finally {
      setActionLoading(null);
    }
  }, [effectiveSessionId]);

  return (
    <div className="p-3 border-t border-gray-100 space-y-2">
      <div className="relative" ref={settingsRef}>
        <button
          type="button"
          onClick={() => setSettingsOpen((o) => !o)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-gray-700 text-sm font-medium hover:bg-gray-100"
          aria-expanded={settingsOpen}
          aria-haspopup="true"
        >
          <Settings className="w-4 h-4 shrink-0" />
          {t.buttonLabel}
          <ChevronUp className={`w-4 h-4 shrink-0 transition-transform ${settingsOpen ? "" : "rotate-180"}`} />
        </button>

        {settingsOpen && (
          <div className="absolute bottom-full left-0 right-0 mb-1 py-1 rounded-lg border border-gray-200 bg-white shadow-lg z-10">
            <button
              type="button"
              onClick={() => {
                setConfirmOpen(true);
                setSettingsOpen(false);
              }}
              disabled={!!actionLoading}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <LogOut className="w-4 h-4 shrink-0" />
              {actionLoading === "clear" ? t.clearSessionLoading : t.clearSession}
            </button>
            <button
              type="button"
              onClick={handleDeleteUserFacts}
              disabled={!!actionLoading}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4 shrink-0" />
              {actionLoading === "facts" ? t.forgetDataLoading : t.forgetData}
            </button>
          </div>
        )}
      </div>

      {toast && (
        <div
          role="status"
          className={`rounded-lg border px-3 py-2 text-xs shadow-sm ${
            toast.type === "error"
              ? "border-red-200 bg-red-50 text-red-800"
              : "border-emerald-200 bg-emerald-50 text-emerald-800"
          }`}
        >
          {toast.message}
        </div>
      )}

      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-clear-title"
          aria-describedby="confirm-clear-description"
          onClick={(event) => {
            if (event.target === event.currentTarget && actionLoading !== "clear") {
              setConfirmOpen(false);
            }
          }}
        >
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-sm overflow-hidden">
            <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-gray-100">
              <h2 id="confirm-clear-title" className="text-base font-semibold text-gray-800">
                {tConfirm.title}
              </h2>
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                disabled={actionLoading === "clear"}
                aria-label={tConfirm.cancel}
                className="p-1 text-gray-400 hover:text-gray-700 rounded hover:bg-gray-50 disabled:opacity-50"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="px-5 py-4">
              <p id="confirm-clear-description" className="text-sm text-gray-600">
                {tConfirm.description}
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-3 bg-gray-50 border-t border-gray-100">
              <button
                type="button"
                onClick={() => setConfirmOpen(false)}
                disabled={actionLoading === "clear"}
                className="px-3 py-1.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
              >
                {tConfirm.cancel}
              </button>
              <button
                type="button"
                onClick={handleConfirmClear}
                disabled={actionLoading === "clear"}
                className="px-3 py-1.5 rounded-lg bg-red-500 text-white text-sm font-medium hover:bg-red-600 disabled:opacity-50"
              >
                {actionLoading === "clear" ? t.clearSessionLoading : tConfirm.accept}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
