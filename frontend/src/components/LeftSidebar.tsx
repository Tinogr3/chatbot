"use client";

import { useState } from "react";
import { Plus, Search, Sparkles, X } from "lucide-react";
import UploadManager from "@/components/UploadManager";
import { useUser } from "@/context/UserContext";
import NavMenu from "@/components/sidebar/NavMenu";
import UserSettings from "@/components/sidebar/UserSettings";

export default function LeftSidebar() {
  const { sessionId, logout } = useUser();
  const [uploadModalOpen, setUploadModalOpen] = useState(false);

  if (!sessionId) return null;

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

      <NavMenu />
      <UserSettings sessionId={sessionId} onLogout={logout} />

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
              <UploadManager />
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
