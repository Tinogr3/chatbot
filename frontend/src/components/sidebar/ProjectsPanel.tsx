"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import {
  ChevronDown,
  Cloud,
  FileText,
  Folder,
  Pencil,
  Plus,
  Trash2,
  Youtube,
  type LucideIcon,
} from "lucide-react";
import {
  useProjects,
  type DocumentSource,
  type Project,
} from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.sidebar.projects;
const tMain = dictionaries.mainContent;

const DOCUMENT_ICONS: Record<DocumentSource, LucideIcon> = {
  manual: FileText,
  cloud: Cloud,
  youtube: Youtube,
};

export type ProjectsPanelProps = {
  searchQuery: string;
};

export default function ProjectsPanel({ searchQuery }: ProjectsPanelProps) {
  const {
    projects,
    currentProjectId,
    pendingRenameProjectId,
    consumePendingRename,
    createProject,
    selectProject,
    renameProject,
    deleteProject,
  } = useProjects();

  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState<string>("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!pendingRenameProjectId) return;
    const project = projects.find((p) => p.id === pendingRenameProjectId);
    if (project) {
      setRenamingId(project.id);
      setRenameDraft(project.name);
      setExpandedIds((prev) => {
        if (prev.has(project.id)) return prev;
        const next = new Set(prev);
        next.add(project.id);
        return next;
      });
    }
    consumePendingRename();
  }, [pendingRenameProjectId, projects, consumePendingRename]);

  const trimmedQuery = searchQuery.trim().toLowerCase();
  const filtered = trimmedQuery
    ? projects.filter((p) => p.name.toLowerCase().includes(trimmedQuery))
    : projects;

  const startRename = (project: Project) => {
    setRenamingId(project.id);
    setRenameDraft(project.name);
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameDraft("");
  };

  const commitRename = (projectId: string) => {
    const trimmed = renameDraft.trim();
    if (trimmed) {
      renameProject(projectId, trimmed);
    }
    setRenamingId(null);
    setRenameDraft("");
  };

  const handleRenameKey = (
    event: KeyboardEvent<HTMLInputElement>,
    projectId: string,
  ) => {
    if (event.key === "Enter") {
      event.preventDefault();
      commitRename(projectId);
    } else if (event.key === "Escape") {
      event.preventDefault();
      cancelRename();
    }
  };

  const toggleExpanded = (projectId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) {
        next.delete(projectId);
      } else {
        next.add(projectId);
      }
      return next;
    });
  };

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2 min-h-0">
      <div className="flex items-center justify-between gap-2 px-2 pb-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          {t.sectionTitle}
        </p>
        <button
          type="button"
          onClick={createProject}
          aria-label={t.newProjectAriaLabel}
          title={tMain.newProjectButton}
          className="p-1 rounded text-emerald-700 hover:bg-emerald-50"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {projects.length === 0 ? (
        <p className="px-2 text-xs text-gray-500">{t.emptyState}</p>
      ) : filtered.length === 0 ? (
        <p className="px-2 text-xs text-gray-500">{t.noResults(searchQuery)}</p>
      ) : (
        <ul className="space-y-1">
          {filtered.map((project) => {
            const isActive = project.id === currentProjectId;
            const isRenaming = renamingId === project.id;
            const isExpanded = expandedIds.has(project.id);
            const canDelete = projects.length > 1;
            return (
              <li
                key={project.id}
                className={`rounded-lg ${
                  isActive
                    ? "bg-emerald-50 border border-emerald-200"
                    : "border border-transparent hover:bg-gray-50"
                }`}
              >
                <div className="flex items-center gap-1 px-2 py-1.5">
                  <button
                    type="button"
                    onClick={() => toggleExpanded(project.id)}
                    aria-expanded={isExpanded}
                    aria-label={
                      isExpanded
                        ? t.collapseAriaLabel(project.name)
                        : t.expandAriaLabel(project.name)
                    }
                    className="p-0.5 text-gray-400 hover:text-gray-700 rounded hover:bg-white/60 shrink-0"
                  >
                    <ChevronDown
                      className={`w-3.5 h-3.5 transition-transform ${
                        isExpanded ? "" : "-rotate-90"
                      }`}
                    />
                  </button>
                  <Folder
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? "text-emerald-600" : "text-gray-400"
                    }`}
                    aria-hidden="true"
                  />
                  {isRenaming ? (
                    <input
                      autoFocus
                      type="text"
                      value={renameDraft}
                      onChange={(e) => setRenameDraft(e.target.value)}
                      onBlur={() => commitRename(project.id)}
                      onKeyDown={(e) => handleRenameKey(e, project.id)}
                      aria-label={t.renameAriaLabel(project.name)}
                      className="flex-1 min-w-0 bg-white border border-emerald-300 rounded px-2 py-1 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => selectProject(project.id)}
                      onDoubleClick={() => startRename(project)}
                      aria-label={t.selectAriaLabel(project.name)}
                      aria-pressed={isActive}
                      className={`flex-1 min-w-0 text-left text-sm truncate ${
                        isActive
                          ? "font-medium text-emerald-700"
                          : "text-gray-700 hover:text-gray-900"
                      }`}
                    >
                      {project.name}
                    </button>
                  )}

                  {!isRenaming && (
                    <>
                      <button
                        type="button"
                        onClick={() => startRename(project)}
                        aria-label={t.renameAriaLabel(project.name)}
                        className="p-1 text-gray-400 hover:text-gray-700 rounded hover:bg-white/60"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => deleteProject(project.id)}
                          aria-label={t.deleteAriaLabel(project.name)}
                          className="p-1 text-gray-400 hover:text-red-600 rounded hover:bg-white/60"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </>
                  )}
                </div>

                {isExpanded && (
                  <div className="px-3 pb-2">
                    {project.documents.length === 0 ? (
                      <p className="pl-7 text-xs italic text-gray-500">
                        {t.noDocuments}
                      </p>
                    ) : (
                      <ul className="space-y-0.5">
                        {project.documents.map((doc) => {
                          const Icon = DOCUMENT_ICONS[doc.source];
                          return (
                            <li
                              key={doc.id}
                              title={doc.name}
                              className="flex items-center gap-2 pl-7 pr-1 py-1 text-xs text-gray-600"
                            >
                              <Icon
                                className="w-3 h-3 shrink-0 text-gray-400"
                                aria-hidden="true"
                              />
                              <span className="truncate flex-1 min-w-0">
                                {doc.name}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
