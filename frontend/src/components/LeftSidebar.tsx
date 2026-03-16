"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  Library,
  BookOpen,
  Scale,
  Mic,
  Search,
  Sparkles,
  Plus,
  X,
  Settings,
  ChevronUp,
  Trash2,
  LogOut,
} from "lucide-react";
import UploadManager from "@/components/UploadManager";
import { clearSession, deleteUserFacts } from "@/lib/api";

const navItems = [
  {
    label: "BIBLIOTECA DE CONOCIMIENTO",
    active: true,
    badge: null,
  },
  {
    label: "Manuales Internos",
    active: false,
    badge: "OFICIAL",
  },
  {
    label: "Regulaciones Legales",
    active: false,
    badge: "VERIFICADO",
  },
  {
    label: "Grabaciones de Expertos",
    active: false,
    badge: null,
  },
];

type LeftSidebarProps = {
  sessionId: string;
  onLogout?: () => void;
};

export default function LeftSidebar({ sessionId, onLogout }: LeftSidebarProps) {
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const [actionLoading, setActionLoading] = useState<"clear" | "facts" | null>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
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
      onLogout?.();
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
    <aside className="w-[20%] min-w-[220px] h-screen flex flex-col bg-white border-r border-gray-200">
      {/* Cabecera */}
      <header className="p-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500 text-white">
            <Sparkles className="w-5 h-5" />
          </div>
          <span className="font-semibold text-gray-800">COTUTOR IA</span>
        </div>
      </header>

      {/* BIBLIOTECA + buscador */}
      <div className="p-4 space-y-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Biblioteca
        </p>
        <p className="text-sm text-gray-800">Fuentes Verificadas</p>
        <button
          type="button"
          onClick={() => setUploadModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 text-sm font-medium hover:bg-emerald-100 transition-colors"
        >
          <Plus className="w-4 h-4 shrink-0" />
          Nuevo Conocimiento
        </button>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="search"
            placeholder="Buscar..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 bg-gray-50 text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
          />
        </div>
      </div>

      {/* Navegación */}
      <nav className="flex-1 px-3 overflow-y-auto">
        <ul className="space-y-0.5">
          {navItems.map((item) => (
            <li key={item.label}>
              <button
                type="button"
                className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors ${
                  item.active
                    ? "bg-emerald-50 text-emerald-700 font-medium"
                    : "text-gray-700 hover:bg-gray-50"
                }`}
              >
                {item.label === "BIBLIOTECA DE CONOCIMIENTO" && (
                  <Library className="w-4 h-4 shrink-0" />
                )}
                {item.label === "Manuales Internos" && (
                  <BookOpen className="w-4 h-4 shrink-0" />
                )}
                {item.label === "Regulaciones Legales" && (
                  <Scale className="w-4 h-4 shrink-0" />
                )}
                {item.label === "Grabaciones de Expertos" && (
                  <Mic className="w-4 h-4 shrink-0" />
                )}
                <span className="flex-1 truncate">{item.label}</span>
                {item.badge && (
                  <span
                    className={`shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      item.badge === "OFICIAL"
                        ? "bg-gray-200 text-gray-700"
                        : "bg-emerald-100 text-emerald-700"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* Pie: Modo seguro + Configuración */}
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

      {/* Modal: Nuevo Conocimiento */}
      {uploadModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={(e) => e.target === e.currentTarget && setUploadModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="upload-modal-title"
        >
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 id="upload-modal-title" className="text-lg font-semibold text-gray-800">
                Nuevo Conocimiento
              </h2>
              <button
                type="button"
                onClick={() => setUploadModalOpen(false)}
                className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-50"
                aria-label="Cerrar"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5">
              <UploadManager
                sessionId={sessionId}
                onClose={() => setUploadModalOpen(false)}
              />
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
