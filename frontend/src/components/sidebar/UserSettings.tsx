"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, ChevronUp, LogOut, Settings, Trash2 } from "lucide-react";
import { clearSession, deleteUserFacts } from "@/lib/api";

export type UserSettingsProps = {
  sessionId: string;
  onLogout: () => void;
};

export default function UserSettings({ sessionId, onLogout }: UserSettingsProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [actionLoading, setActionLoading] = useState<"clear" | "facts" | null>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(t);
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

  const handleClearSession = useCallback(async () => {
    setActionLoading("clear");
    try {
      await clearSession(sessionId);
      setToast({ message: "Sesión limpiada correctamente.", type: "success" });
      setSettingsOpen(false);
      onLogout();
    } catch (e) {
      setToast({ message: e instanceof Error ? e.message : "Error al limpiar sesión.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  }, [sessionId, onLogout]);

  const handleDeleteUserFacts = useCallback(async () => {
    setActionLoading("facts");
    try {
      const res = await deleteUserFacts(sessionId);
      setToast({ message: `Se eliminaron ${res.deleted} datos sobre ti.`, type: "success" });
      setSettingsOpen(false);
    } catch (e) {
      setToast({ message: e instanceof Error ? e.message : "Error al eliminar datos.", type: "error" });
    } finally {
      setActionLoading(null);
    }
  }, [sessionId]);

  return (
    <div className="p-3 border-t border-gray-100 space-y-2">
      <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-emerald-50 text-emerald-800 text-xs">
        <Check className="w-4 h-4 shrink-0 text-emerald-600" />
        <span className="font-medium">MODO SEGURO - Datos cifrados E2E</span>
      </div>

      <div className="relative" ref={settingsRef}>
        <button
          type="button"
          onClick={() => setSettingsOpen((o) => !o)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-gray-200 bg-gray-50 text-gray-700 text-sm font-medium hover:bg-gray-100"
          aria-expanded={settingsOpen}
          aria-haspopup="true"
        >
          <Settings className="w-4 h-4 shrink-0" />
          Configuración
          <ChevronUp className={`w-4 h-4 shrink-0 transition-transform ${settingsOpen ? "" : "rotate-180"}`} />
        </button>

        {settingsOpen && (
          <div className="absolute bottom-full left-0 right-0 mb-1 py-1 rounded-lg border border-gray-200 bg-white shadow-lg z-10">
            <button
              type="button"
              onClick={handleClearSession}
              disabled={!!actionLoading}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <LogOut className="w-4 h-4 shrink-0" />
              {actionLoading === "clear" ? "Limpiando..." : "Limpiar sesión"}
            </button>
            <button
              type="button"
              onClick={handleDeleteUserFacts}
              disabled={!!actionLoading}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              <Trash2 className="w-4 h-4 shrink-0" />
              {actionLoading === "facts" ? "Eliminando..." : "Olvidar datos sobre mí"}
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
    </div>
  );
}

