"use client";

import {
  Check,
  Library,
  BookOpen,
  Scale,
  Mic,
  Search,
  Sparkles,
} from "lucide-react";

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

export default function LeftSidebar() {
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

      {/* Pie: Modo seguro */}
      <div className="p-3 border-t border-gray-100">
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-emerald-50 text-emerald-800 text-xs">
          <Check className="w-4 h-4 shrink-0 text-emerald-600" />
          <span className="font-medium">MODO SEGURO - Datos cifrados E2E</span>
        </div>
      </div>
    </aside>
  );
}
