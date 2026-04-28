"use client";

import { useState } from "react";
import { Plus, Search, Sparkles, X } from "lucide-react";
import UploadManager from "@/components/UploadManager";
import ProjectsPanel from "@/components/sidebar/ProjectsPanel";
import UserSettings from "@/components/sidebar/UserSettings";
import { useUser } from "@/context/UserContext";
import { useProjects } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.sidebar;
const tCommon = dictionaries.common;

export default function LeftSidebar() {
  const { sessionId } = useUser();
  const { currentProject, effectiveSessionId } = useProjects();
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  if (!sessionId || !effectiveSessionId) return null;

  return (
    <aside className="w-[20%] min-w-[220px] h-screen flex flex-col bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800">
      <header className="p-4 border-b border-gray-100 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-500 text-white">
            <Sparkles className="w-5 h-5" />
          </div>
          <span className="font-semibold text-gray-800 dark:text-gray-100">{tCommon.appName}</span>
        </div>
      </header>

      <div className="p-4 space-y-3 border-b border-gray-100 dark:border-gray-800">
        <button
          type="button"
          onClick={() => setUploadModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg border border-emerald-200 dark:border-emerald-700/50 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 text-sm font-medium hover:bg-emerald-100 dark:hover:bg-emerald-500/20 transition-colors"
        >
          <Plus className="w-4 h-4 shrink-0" />
          {t.newKnowledgeButton}
        </button>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 dark:text-gray-500" />
          <input
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t.searchPlaceholder}
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
          />
        </div>
      </div>

      <ProjectsPanel searchQuery={searchQuery} />
      <UserSettings />

      {uploadModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={(e) => e.target === e.currentTarget && setUploadModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="upload-modal-title"
        >
          <div className="bg-white dark:bg-gray-900 rounded-xl shadow-xl border border-gray-200 dark:border-gray-800 w-full max-w-md overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-800">
              <div className="min-w-0">
                <h2 id="upload-modal-title" className="text-lg font-semibold text-gray-800 dark:text-gray-100">
                  {t.uploadModalTitle}
                </h2>
                {currentProject && (
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400 truncate">
                    {t.uploadModalCurrentProject(currentProject.name)}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setUploadModalOpen(false)}
                className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 shrink-0"
                aria-label={t.closeUploadModal}
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
