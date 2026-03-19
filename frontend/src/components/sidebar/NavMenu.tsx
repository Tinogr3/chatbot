"use client";

import { navItems } from "@/config/navigation";

export default function NavMenu() {
  return (
    <nav className="flex-1 px-3 overflow-y-auto">
      <ul className="space-y-0.5">
        {navItems.map((item) => (
          <li key={item.label}>
            <button
              type="button"
              className={`w-full flex items-center gap-2 px-3 py-2.5 rounded-lg text-left text-sm transition-colors ${
                item.active ? "bg-emerald-50 text-emerald-700 font-medium" : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <item.icon className="w-4 h-4 shrink-0" />
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
  );
}

