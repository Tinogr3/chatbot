"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useAuth } from "@/context/AuthContext";
import { useUser } from "@/context/UserContext";
import { getSharedProjects } from "@/lib/api";
import { dictionaries } from "@/locales";

const STORAGE_PREFIX = "cotutor_projects_";

export type DocumentSource = "manual" | "cloud" | "youtube";

export type ProjectDocument = {
  id: string;
  /** Nombre para mostrar (título del vídeo, nombre del PDF…). */
  name: string;
  /**
   * Clave de búsqueda usada en el dashboard de competencias.
   * Para vídeos de YouTube: el video_id (11 chars).
   * Para PDFs: igual que `name`.
   * Si el campo no está (datos almacenados antes de esta versión),
   * usar `name` como fallback.
   */
  docKey?: string;
  source: DocumentSource;
  addedAt: number;
};

export type Project = {
  id: string;
  name: string;
  documents: ProjectDocument[];
  createdAt: number;
  /** Curso compartido por el formador (solo lectura para el alumno). */
  isShared?: boolean;
  sharedSessionId?: string;
  trainerUsername?: string;
  readOnly?: boolean;
};

type PersistedState = {
  projects: Project[];
  currentProjectId: string | null;
};

const EMPTY_STATE: PersistedState = { projects: [], currentProjectId: null };

function getStorageKey(sessionId: string): string {
  return `${STORAGE_PREFIX}${sessionId}`;
}

/**
 * Genera el siguiente nombre por defecto siguiendo el patrón "Proyecto N",
 * eligiendo el menor entero positivo que no esté ya en uso.
 */
function generateNextProjectName(existing: Project[]): string {
  const used = new Set<number>();
  for (const project of existing) {
    const match = project.name.match(/^Proyecto\s+(\d+)$/);
    if (match) used.add(Number(match[1]));
  }
  let next = 1;
  while (used.has(next)) next++;
  return dictionaries.sidebar.projects.defaultName(next);
}

function generateId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

function isValidProject(value: unknown): value is Project {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Project;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.name === "string" &&
    Array.isArray(candidate.documents) &&
    typeof candidate.createdAt === "number"
  );
}

function loadPersistedState(sessionId: string): PersistedState {
  if (typeof window === "undefined") return EMPTY_STATE;
  try {
    const raw = window.localStorage.getItem(getStorageKey(sessionId));
    if (!raw) return EMPTY_STATE;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return EMPTY_STATE;
    const candidate = parsed as Partial<PersistedState>;
    const projects: Project[] = Array.isArray(candidate.projects)
      ? candidate.projects.filter(isValidProject)
      : [];
    const stored = candidate.currentProjectId;
    const currentProjectId =
      typeof stored === "string" && projects.some((p) => p.id === stored)
        ? stored
        : projects[0]?.id ?? null;
    return { projects, currentProjectId };
  } catch {
    return EMPTY_STATE;
  }
}

function persistState(sessionId: string, state: PersistedState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(getStorageKey(sessionId), JSON.stringify(state));
  } catch {
    // Cuota agotada o modo privacidad: ignorar silenciosamente.
  }
}

export type ProjectsContextValue = {
  /** Proyectos personales del usuario. */
  projects: Project[];
  /** Cursos compartidos por el formador (solo alumnos). */
  sharedProjects: Project[];
  /** Lista unificada para el sidebar (compartidos primero). */
  allProjects: Project[];
  currentProject: Project | null;
  currentProjectId: string | null;
  effectiveSessionId: string | null;
  /** True si el proyecto activo es un curso compartido del formador. */
  isSharedCourseActive: boolean;
  pendingRenameProjectId: string | null;
  isHydrated: boolean;
  refreshSharedProjects: () => void;
  createProject: () => void;
  renameProject: (projectId: string, name: string) => void;
  selectProject: (projectId: string) => void;
  deleteProject: (projectId: string) => void;
  addDocumentsToCurrent: (inputs: Array<{ name: string; docKey?: string; source: DocumentSource }>) => void;
  /**
   * Borra todos los proyectos del usuario actual del estado y de localStorage.
   * No realiza llamadas de red: la cascada de limpieza backend (chat history,
   * document registry, vector store, user facts) es responsabilidad del caller,
   * que debe iterar sobre los proyectos previos a esta llamada.
   */
  clearAllProjects: () => void;
  consumePendingRename: () => void;
};

const ProjectsContext = createContext<ProjectsContextValue | undefined>(undefined);

export function ProjectsProvider({ children }: { children: React.ReactNode }) {
  const { sessionId, isHydrated: userHydrated } = useUser();
  const { user, accessToken } = useAuth();
  const [state, setState] = useState<PersistedState>(EMPTY_STATE);
  const [sharedProjects, setSharedProjects] = useState<Project[]>([]);
  const [sharedRefresh, setSharedRefresh] = useState(0);
  const [pendingRenameProjectId, setPendingRenameProjectId] = useState<string | null>(
    null,
  );
  const [isHydrated, setIsHydrated] = useState(false);

  const refreshSharedProjects = useCallback(() => {
    setSharedRefresh((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!userHydrated || user?.role !== "alumno" || !sessionId) {
      setSharedProjects([]);
      return;
    }
    let cancelled = false;
    getSharedProjects(sessionId, accessToken)
      .then((res) => {
        if (cancelled) return;
        const mapped: Project[] = res.projects.map((p) => ({
          id: `shared-${p.id}`,
          name: p.name,
          documents: p.documents.map((d, i) => ({
            id: `shared-doc-${p.id}-${i}`,
            name: d.name,
            docKey: d.doc_key,
            source: d.source as DocumentSource,
            addedAt: Date.now(),
          })),
          createdAt: Date.now(),
          isShared: true,
          sharedSessionId: p.session_id,
          trainerUsername: p.trainer_username,
          readOnly: true,
        }));
        setSharedProjects(mapped);
        if (mapped.length > 0) {
          setState((prev) => {
            if (prev.currentProjectId?.startsWith("shared-")) {
              const stillValid = mapped.some((p) => p.id === prev.currentProjectId);
              if (stillValid) return prev;
            }
            return { ...prev, currentProjectId: mapped[0].id };
          });
        }
      })
      .catch(() => {
        if (!cancelled) setSharedProjects([]);
      });
    return () => {
      cancelled = true;
    };
  }, [userHydrated, user?.role, sessionId, accessToken, sharedRefresh]);

  useEffect(() => {
    if (!userHydrated) return;
    setIsHydrated(false);
    setPendingRenameProjectId(null);

    if (!sessionId) {
      setState(EMPTY_STATE);
      setIsHydrated(true);
      return;
    }

    const loaded = loadPersistedState(sessionId);
    if (loaded.projects.length === 0) {
      const project: Project = {
        id: generateId("project"),
        name: generateNextProjectName([]),
        documents: [],
        createdAt: Date.now(),
      };
      const initial: PersistedState = {
        projects: [project],
        currentProjectId: project.id,
      };
      setState(initial);
      persistState(sessionId, initial);
    } else {
      setState(loaded);
    }
    setIsHydrated(true);
  }, [sessionId, userHydrated]);

  useEffect(() => {
    if (!isHydrated || !sessionId) return;
    persistState(sessionId, state);
  }, [state, sessionId, isHydrated]);

  const createProject = useCallback(() => {
    setState((prev) => {
      const project: Project = {
        id: generateId("project"),
        name: generateNextProjectName(prev.projects),
        documents: [],
        createdAt: Date.now(),
      };
      setPendingRenameProjectId(project.id);
      return {
        projects: [...prev.projects, project],
        currentProjectId: project.id,
      };
    });
  }, []);

  const renameProject = useCallback((projectId: string, rawName: string) => {
    const trimmed = rawName.trim();
    if (!trimmed) return;
    if (projectId.startsWith("shared-")) return;
    setState((prev) => ({
      ...prev,
      projects: prev.projects.map((p) =>
        p.id === projectId ? { ...p, name: trimmed } : p,
      ),
    }));
  }, []);

  const selectProject = useCallback((projectId: string) => {
    setState((prev) => {
      if (prev.currentProjectId === projectId) return prev;
      return { ...prev, currentProjectId: projectId };
    });
  }, []);

  const deleteProject = useCallback((projectId: string) => {
    if (projectId.startsWith("shared-")) return;
    setState((prev) => {
      const projects = prev.projects.filter((p) => p.id !== projectId);
      const currentProjectId =
        prev.currentProjectId === projectId
          ? projects[0]?.id ?? null
          : prev.currentProjectId;
      return { projects, currentProjectId };
    });
  }, []);

  const addDocumentsToCurrent = useCallback(
    (inputs: Array<{ name: string; docKey?: string; source: DocumentSource }>) => {
      if (inputs.length === 0) return;
      setState((prev) => {
        if (!prev.currentProjectId) return prev;
        const baseTimestamp = Date.now();
        const newDocuments: ProjectDocument[] = inputs.map((input, index) => ({
          id: generateId("doc"),
          name: input.name,
          docKey: input.docKey ?? input.name,
          source: input.source,
          addedAt: baseTimestamp + index,
        }));
        return {
          ...prev,
          projects: prev.projects.map((p) =>
            p.id === prev.currentProjectId
              ? { ...p, documents: [...p.documents, ...newDocuments] }
              : p,
          ),
        };
      });
    },
    [],
  );

  const consumePendingRename = useCallback(() => {
    setPendingRenameProjectId(null);
  }, []);

  const clearAllProjects = useCallback(() => {
    setState(EMPTY_STATE);
    setPendingRenameProjectId(null);
    if (sessionId && typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(getStorageKey(sessionId));
      } catch {
        // Cuota agotada o modo privacidad: ignorar.
      }
    }
  }, [sessionId]);

  const allProjects = useMemo(
    () => [...sharedProjects, ...state.projects],
    [sharedProjects, state.projects],
  );

  const currentProject = useMemo(
    () => allProjects.find((p) => p.id === state.currentProjectId) ?? null,
    [allProjects, state.currentProjectId],
  );

  const isSharedCourseActive = Boolean(
    currentProject?.isShared && currentProject.sharedSessionId,
  );

  const effectiveSessionId = useMemo<string | null>(() => {
    if (!sessionId || !state.currentProjectId || !currentProject) return null;
    if (currentProject.isShared && currentProject.sharedSessionId) {
      return currentProject.sharedSessionId;
    }
    return `${sessionId}__${state.currentProjectId}`;
  }, [sessionId, state.currentProjectId, currentProject]);

  const value = useMemo<ProjectsContextValue>(
    () => ({
      projects: state.projects,
      sharedProjects,
      allProjects,
      currentProject,
      currentProjectId: state.currentProjectId,
      effectiveSessionId,
      isSharedCourseActive,
      pendingRenameProjectId,
      isHydrated,
      refreshSharedProjects,
      createProject,
      renameProject,
      selectProject,
      deleteProject,
      addDocumentsToCurrent,
      clearAllProjects,
      consumePendingRename,
    }),
    [
      state.projects,
      state.currentProjectId,
      sharedProjects,
      allProjects,
      currentProject,
      effectiveSessionId,
      isSharedCourseActive,
      pendingRenameProjectId,
      isHydrated,
      refreshSharedProjects,
      createProject,
      renameProject,
      selectProject,
      deleteProject,
      addDocumentsToCurrent,
      clearAllProjects,
      consumePendingRename,
    ],
  );

  return <ProjectsContext.Provider value={value}>{children}</ProjectsContext.Provider>;
}

export function useProjects(): ProjectsContextValue {
  const ctx = useContext(ProjectsContext);
  if (!ctx) {
    throw new Error(dictionaries.errors.projectsContextOutsideProvider);
  }
  return ctx;
}
