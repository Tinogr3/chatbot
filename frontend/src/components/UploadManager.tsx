"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Upload, Cloud, Youtube, Loader2 } from "lucide-react";
import {
  uploadPdf,
  loadCloudPdfs,
  processVideo,
  getTaskStatus,
  type TaskStatusResponse,
} from "@/lib/api";
import { useProjects, type DocumentSource } from "@/context/ProjectsContext";
import { dictionaries } from "@/locales";

const t = dictionaries.uploadManager;

const POLL_INTERVAL_MS = 1500;

type TabId = "manual" | "nube" | "youtube";

type TabDefinition = {
  id: TabId;
  label: string;
  icon: typeof Upload;
};

const TABS: readonly TabDefinition[] = [
  { id: "manual", label: t.tabs.manual, icon: Upload },
  { id: "nube", label: t.tabs.cloud, icon: Cloud },
  { id: "youtube", label: t.tabs.youtube, icon: Youtube },
];

type PendingDoc = { name: string; source: DocumentSource };

/**
 * Contexto de la tarea encolada que necesitamos para construir, en el momento
 * SUCCESS, el listado real de documentos a registrar en el proyecto activo.
 *
 *  - manual / youtube: el nombre lo conocemos en el cliente (file.name / url).
 *  - cloud: los nombres los aporta el backend en `result.filenames` (el bucket
 *    puede contener N PDFs y queremos una entrada por archivo, no un genérico).
 */
type PendingTaskContext =
  | { kind: "manual"; filename: string }
  | { kind: "cloud" }
  | { kind: "youtube"; url: string };

function resolveDocumentsFromTask(
  context: PendingTaskContext,
  result: TaskStatusResponse["result"],
): PendingDoc[] {
  if (context.kind === "manual") {
    return [{ name: context.filename, source: "manual" }];
  }
  if (context.kind === "youtube") {
    return [{ name: context.url, source: "youtube" }];
  }
  const filenames = (result as { filenames?: unknown } | null | undefined)?.filenames;
  if (!Array.isArray(filenames)) return [];
  return filenames
    .filter((name): name is string => typeof name === "string" && name.trim().length > 0)
    .map((name) => ({ name, source: "cloud" as const }));
}

export default function UploadManager() {
  const { effectiveSessionId, addDocumentsToCurrent } = useProjects();

  const [activeTab, setActiveTab] = useState<TabId>("manual");
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [pendingTask, setPendingTask] = useState<PendingTaskContext | null>(null);
  const [nubeLoading, setNubeLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTask = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setTaskId(null);
    setTaskStatus(null);
    setPendingTask(null);
  }, []);

  useEffect(() => {
    if (!taskId) return;
    const poll = async () => {
      try {
        const status = await getTaskStatus(taskId);
        setTaskStatus(status);
        if (status.status === "SUCCESS" || status.status === "FAILURE") {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    };
    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId]);

  useEffect(() => {
    if (!pendingTask || !taskStatus) return;
    if (taskStatus.status === "SUCCESS") {
      const docs = resolveDocumentsFromTask(pendingTask, taskStatus.result);
      if (docs.length > 0) {
        addDocumentsToCurrent(docs);
      }
      setPendingTask(null);
    } else if (taskStatus.status === "FAILURE") {
      setPendingTask(null);
    }
  }, [taskStatus, pendingTask, addDocumentsToCurrent]);

  const handleManualUpload = async () => {
    if (!effectiveSessionId) return;
    if (!file) {
      setError(t.manual.missingFileError);
      return;
    }
    setError(null);
    try {
      const { task_id } = await uploadPdf(file, effectiveSessionId);
      setPendingTask({ kind: "manual", filename: file.name });
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleLoadCloud = async () => {
    if (!effectiveSessionId) return;
    setError(null);
    setTaskStatus(null);
    setTaskId(null);
    setNubeLoading(true);
    try {
      const { task_id } = await loadCloudPdfs(effectiveSessionId);
      setPendingTask({ kind: "cloud" });
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNubeLoading(false);
    }
  };

  const handleProcessVideo = async () => {
    if (!effectiveSessionId) return;
    const url = youtubeUrl.trim();
    if (!url) {
      setError(t.youtube.missingUrlError);
      return;
    }
    setError(null);
    try {
      const { task_id } = await processVideo(url, effectiveSessionId);
      setPendingTask({ kind: "youtube", url });
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const isTaskDone = taskStatus?.status === "SUCCESS" || taskStatus?.status === "FAILURE";
  const isTaskRunning = !!taskId && !isTaskDone;
  const showTaskProgress = taskId && taskStatus && !isTaskDone;
  const showTaskResult = taskId && taskStatus && isTaskDone;

  if (!effectiveSessionId) return null;

  return (
    <div className="space-y-4">
      <div className="flex rounded-lg bg-gray-100 dark:bg-gray-800 p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              setActiveTab(tab.id);
              setError(null);
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white dark:bg-gray-900 text-emerald-700 dark:text-emerald-300 shadow-sm"
                : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
            }`}
          >
            <tab.icon className="w-4 h-4 shrink-0" />
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-[140px]">
        {activeTab === "manual" && (
          <div className="space-y-3">
            <label className="block">
              <span className="sr-only">{t.manual.selectLabel}</span>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  setFile(f ?? null);
                  setError(null);
                }}
                className="block w-full text-sm text-gray-600 dark:text-gray-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-emerald-50 dark:file:bg-emerald-500/10 file:text-emerald-700 dark:file:text-emerald-300 file:font-medium file:cursor-pointer hover:file:bg-emerald-100 dark:hover:file:bg-emerald-500/20"
              />
            </label>
            <button
              type="button"
              onClick={handleManualUpload}
              disabled={!file || isTaskRunning}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t.manual.submit}
            </button>
          </div>
        )}

        {activeTab === "nube" && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t.cloud.description}
            </p>
            <button
              type="button"
              onClick={handleLoadCloud}
              disabled={nubeLoading || isTaskRunning}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {nubeLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t.cloud.loading}
                </>
              ) : (
                t.cloud.submit
              )}
            </button>
          </div>
        )}

        {activeTab === "youtube" && (
          <div className="space-y-3">
            <input
              type="url"
              value={youtubeUrl}
              onChange={(e) => {
                setYoutubeUrl(e.target.value);
                setError(null);
              }}
              placeholder={t.youtube.placeholder}
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-800 dark:text-gray-100 placeholder:text-gray-400 dark:placeholder:text-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
            <button
              type="button"
              onClick={handleProcessVideo}
              disabled={!youtubeUrl.trim() || isTaskRunning}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t.youtube.submit}
            </button>
          </div>
        )}
      </div>

      {showTaskProgress && taskStatus && (
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 p-3 space-y-2">
          <div className="h-2 rounded-full bg-emerald-200 dark:bg-emerald-700 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-300"
              style={{ width: `${Math.round((taskStatus.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-300">
            {taskStatus.message || t.progress.fallbackMessage}
          </p>
        </div>
      )}

      {showTaskResult && taskStatus && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            taskStatus.status === "SUCCESS"
              ? "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-700/50 text-emerald-800 dark:text-emerald-200"
              : "bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800 text-red-800 dark:text-red-200"
          }`}
        >
          {taskStatus.status === "SUCCESS" ? (
            <p>{typeof taskStatus.result?.message === "string" ? taskStatus.result.message : t.result.successFallback}</p>
          ) : (
            <p>{taskStatus.error ?? t.result.errorFallback}</p>
          )}
          <button
            type="button"
            onClick={clearTask}
            className="mt-2 text-xs font-medium underline hover:no-underline"
          >
            {t.result.closeAndStartOver}
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 px-3 py-2 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}
