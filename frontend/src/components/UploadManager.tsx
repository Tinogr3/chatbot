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
import { useUser } from "@/context/UserContext";

const POLL_INTERVAL_MS = 1500;

type TabId = "manual" | "nube" | "youtube";

export default function UploadManager() {
  const { sessionId } = useUser();

  const [activeTab, setActiveTab] = useState<TabId>("manual");
  const [file, setFile] = useState<File | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
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

  const handleManualUpload = async () => {
    if (!sessionId) return;
    if (!file) {
      setError("Selecciona un archivo PDF");
      return;
    }
    setError(null);
    try {
      const { task_id } = await uploadPdf(file, sessionId);
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleLoadCloud = async () => {
    if (!sessionId) return;
    setError(null);
    setTaskStatus(null);
    setTaskId(null);
    setNubeLoading(true);
    try {
      const { task_id } = await loadCloudPdfs(sessionId);
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNubeLoading(false);
    }
  };

  const handleProcessVideo = async () => {
    if (!sessionId) return;
    const url = youtubeUrl.trim();
    if (!url) {
      setError("Introduce la URL del video de YouTube");
      return;
    }
    setError(null);
    try {
      const { task_id } = await processVideo(url, sessionId);
      setTaskId(task_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const isTaskDone = taskStatus?.status === "SUCCESS" || taskStatus?.status === "FAILURE";
  const showTaskProgress = taskId && taskStatus && !isTaskDone;
  const showTaskResult = taskId && taskStatus && isTaskDone;

  const tabs: { id: TabId; label: string; icon: typeof Upload }[] = [
    { id: "manual", label: "Manual (Upload)", icon: Upload },
    { id: "nube", label: "Nube", icon: Cloud },
    { id: "youtube", label: "YouTube", icon: Youtube },
  ];

  if (!sessionId) return null;

  return (
    <div className="space-y-4">
      <div className="flex rounded-lg bg-gray-100 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              setActiveTab(tab.id);
              setError(null);
            }}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white text-emerald-700 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
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
              <span className="sr-only">Seleccionar PDF</span>
              <input
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  setFile(f ?? null);
                  setError(null);
                }}
                className="block w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:bg-emerald-50 file:text-emerald-700 file:font-medium file:cursor-pointer hover:file:bg-emerald-100"
              />
            </label>
            <button
              type="button"
              onClick={handleManualUpload}
              disabled={!file || !!taskId}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Subir PDF
            </button>
          </div>
        )}

        {activeTab === "nube" && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Carga todos los PDFs configurados en el bucket para esta sesión.
            </p>
            <button
              type="button"
              onClick={handleLoadCloud}
              disabled={nubeLoading || !!taskId}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {nubeLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Cargando...
                </>
              ) : (
                "Cargar PDFs del bucket"
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
              placeholder="https://www.youtube.com/watch?v=..."
              className="w-full px-3 py-2 rounded-lg border border-gray-200 bg-white text-gray-800 placeholder:text-gray-400 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-500"
            />
            <button
              type="button"
              onClick={handleProcessVideo}
              disabled={!youtubeUrl.trim() || !!taskId}
              className="w-full py-2.5 rounded-lg bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Procesar video
            </button>
          </div>
        )}
      </div>

      {showTaskProgress && taskStatus && (
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-2">
          <div className="h-2 rounded-full bg-emerald-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-300"
              style={{ width: `${Math.round((taskStatus.progress ?? 0) * 100)}%` }}
            />
          </div>
          <p className="text-sm text-gray-600">
            {taskStatus.message || "Procesando..."}
          </p>
        </div>
      )}

      {showTaskResult && taskStatus && (
        <div
          className={`rounded-lg border p-3 text-sm ${
            taskStatus.status === "SUCCESS"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          {taskStatus.status === "SUCCESS" ? (
            <p>{typeof taskStatus.result?.message === "string" ? taskStatus.result.message : "Completado correctamente."}</p>
          ) : (
            <p>{taskStatus.error ?? "Error desconocido."}</p>
          )}
          <button
            type="button"
            onClick={clearTask}
            className="mt-2 text-xs font-medium underline hover:no-underline"
          >
            Cerrar y empezar otra
          </button>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
