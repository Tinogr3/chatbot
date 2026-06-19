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
    sharedProjects,
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
  // IDs de documentos cuyo nombre está expandido (no truncado)
  const [expandedDocNames, setExpandedDocNames] = useState<Set<string>>(new Set());

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
  const filteredShared = trimmedQuery
    ? sharedProjects.filter((p) => p.name.toLowerCase().includes(trimmedQuery))
    : sharedProjects;
  const filteredOwn = trimmedQuery
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

  const toggleDocName = (docId: string) => {
    setExpandedDocNames((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const renderProjectRow = (project: Project, canDelete: boolean) => {
    const isActive = project.id === currentProjectId;
    const isRenaming = renamingId === project.id;
    const isExpanded = expandedIds.has(project.id);
    const isReadOnly = Boolean(project.readOnly);

    return (
      <li
        key={project.id}
        className={`rounded-lg ${
          isActive
            ? "bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-700/50"
            : "border border-transparent hover:bg-gray-50 dark:hover:bg-gray-800"
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
            className="p-0.5 text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 rounded hover:bg-white/60 dark:hover:bg-gray-700 shrink-0"
          >
            <ChevronDown
              className={`w-3.5 h-3.5 transition-transform ${
                isExpanded ? "" : "-rotate-90"
              }`}
            />
          </button>
          <Folder
            className={`w-4 h-4 shrink-0 ${
              isActive
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-gray-400 dark:text-gray-500"
            }`}
            aria-hidden="true"
          />
          {isRenaming && !isReadOnly ? (
            <input
              autoFocus
              type="text"
              value={renameDraft}
              onChange={(e) => setRenameDraft(e.target.value)}
              onBlur={() => commitRename(project.id)}
              onKeyDown={(e) => handleRenameKey(e, project.id)}
              aria-label={t.renameAriaLabel(project.name)}
              className="flex-1 min-w-0 bg-white dark:bg-gray-900 border border-emerald-300 dark:border-emerald-600 rounded px-2 py-1 text-sm text-gray-800 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            />
          ) : (
            <button
              type="button"
              onClick={() => selectProject(project.id)}
              onDoubleClick={() => !isReadOnly && startRename(project)}
              aria-label={t.selectAriaLabel(project.name)}
              aria-pressed={isActive}
              className={`flex-1 min-w-0 text-left text-sm truncate ${
                isActive
                  ? "font-medium text-emerald-700 dark:text-emerald-300"
                  : "text-gray-700 dark:text-gray-200 hover:text-gray-900 dark:hover:text-gray-50"
              }`}
            >
              {project.name}
              {project.trainerUsername && (
                <span className="ml-1 text-[10px] text-gray-400">({project.trainerUsername})</span>
              )}
            </button>
          )}

          {!isRenaming && !isReadOnly && (
            <>
              <button
                type="button"
                onClick={() => startRename(project)}
                aria-label={t.renameAriaLabel(project.name)}
                className="p-1 text-gray-400 dark:text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 rounded hover:bg-white/60 dark:hover:bg-gray-700"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              {canDelete && (
                <button
                  type="button"
                  onClick={() => deleteProject(project.id)}
                  aria-label={t.deleteAriaLabel(project.name)}
                  className="p-1 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 rounded hover:bg-white/60 dark:hover:bg-gray-700"
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
              <p className="pl-7 text-xs italic text-gray-500 dark:text-gray-400">
                {t.noDocuments}
              </p>
            ) : (
              <ul className="space-y-0.5">
                {project.documents.map((doc) => {
                  const Icon = DOCUMENT_ICONS[doc.source];
                  const isDocNameExpanded = expandedDocNames.has(doc.id);
                  return (
                    <li
                      key={doc.id}
                      className="flex items-start gap-2 pl-7 pr-1 py-1 text-xs text-gray-600 dark:text-gray-300"
                    >
                      <Icon
                        className="w-3 h-3 shrink-0 text-gray-400 dark:text-gray-500 mt-0.5"
                        aria-hidden="true"
                      />
                      <button
                        type="button"
                        title={isDocNameExpanded ? undefined : doc.name}
                        aria-label={
                          isDocNameExpanded
                            ? `Contraer nombre: ${doc.name}`
                            : `Ver nombre completo: ${doc.name}`
                        }
                        onClick={() => toggleDocName(doc.id)}
                        className={`flex-1 min-w-0 text-left leading-snug hover:text-gray-900 dark:hover:text-gray-50 ${
                          isDocNameExpanded
                            ? "break-words whitespace-normal"
                            : "truncate"
                        }`}
                      >
                        {doc.name}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </li>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2 min-h-0">
      <div className="flex items-center justify-between gap-2 px-2 pb-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {t.sectionTitle}
        </p>
        <button
          type="button"
          onClick={createProject}
          aria-label={t.newProjectAriaLabel}
          title={tMain.newProjectButton}
          className="p-1 rounded text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-500/10"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {filteredShared.length > 0 && (
        <>
          <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
            {t.sharedSectionTitle}
          </p>
          <ul className="mb-3 space-y-1">
            {filteredShared.map((project) => renderProjectRow(project, false))}
          </ul>
        </>
      )}

      {projects.length === 0 && sharedProjects.length === 0 ? (
        <p className="px-2 text-xs text-gray-500 dark:text-gray-400">{t.emptyState}</p>
      ) : filteredOwn.length === 0 && filteredShared.length === 0 ? (
        <p className="px-2 text-xs text-gray-500 dark:text-gray-400">{t.noResults(searchQuery)}</p>
      ) : filteredOwn.length > 0 ? (
        <>
          {sharedProjects.length > 0 && (
            <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
              {t.ownSectionTitle}
            </p>
          )}
          <ul className="space-y-1">
            {filteredOwn.map((project) => renderProjectRow(project, projects.length > 1))}
          </ul>
        </>
      ) : null}
    </div>
  );
}
