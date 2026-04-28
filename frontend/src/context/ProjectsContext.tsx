"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useUser } from "@/context/UserContext";
import { dictionaries } from "@/locales";

const STORAGE_PREFIX = "cotutor_projects_";

export type DocumentSource = "manual" | "cloud" | "youtube";

export type ProjectDocument = {
  id: string;
  name: string;
  source: DocumentSource;
  addedAt: number;
};

export type Project = {
  id: string;
  name: string;
  documents: ProjectDocument[];
  createdAt: number;
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
  projects: Project[];
  currentProject: Project | null;
  currentProjectId: string | null;
  /**
   * Identificador compuesto que se envía al backend como `X-Session-Id`.
   * Une la sesión del usuario y el id del proyecto activo de modo que cada
   * proyecto reciba un espacio aislado de chat, registro de documentos y
   * colección de embeddings en el backend (que ya aísla por session_id).
   */
  effectiveSessionId: string | null;
  pendingRenameProjectId: string | null;
  isHydrated: boolean;
  createProject: () => void;
  renameProject: (projectId: string, name: string) => void;
  selectProject: (projectId: string) => void;
  deleteProject: (projectId: string) => void;
  addDocumentsToCurrent: (inputs: Array<{ name: string; source: DocumentSource }>) => void;
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
  const [state, setState] = useState<PersistedState>(EMPTY_STATE);
  const [pendingRenameProjectId, setPendingRenameProjectId] = useState<string | null>(
    null,
  );
  const [isHydrated, setIsHydrated] = useState(false);

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
      if (!prev.projects.some((p) => p.id === projectId)) return prev;
      return { ...prev, currentProjectId: projectId };
    });
  }, []);

  const deleteProject = useCallback((projectId: string) => {
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
    (inputs: Array<{ name: string; source: DocumentSource }>) => {
      if (inputs.length === 0) return;
      setState((prev) => {
        if (!prev.currentProjectId) return prev;
        const baseTimestamp = Date.now();
        const newDocuments: ProjectDocument[] = inputs.map((input, index) => ({
          id: generateId("doc"),
          name: input.name,
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

  const currentProject = useMemo(
    () => state.projects.find((p) => p.id === state.currentProjectId) ?? null,
    [state.projects, state.currentProjectId],
  );

  const effectiveSessionId = useMemo<string | null>(() => {
    if (!sessionId || !state.currentProjectId) return null;
    return `${sessionId}__${state.currentProjectId}`;
  }, [sessionId, state.currentProjectId]);

  const value = useMemo<ProjectsContextValue>(
    () => ({
      projects: state.projects,
      currentProject,
      currentProjectId: state.currentProjectId,
      effectiveSessionId,
      pendingRenameProjectId,
      isHydrated,
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
      currentProject,
      effectiveSessionId,
      pendingRenameProjectId,
      isHydrated,
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
