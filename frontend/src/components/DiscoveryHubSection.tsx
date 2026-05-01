"use client";

import { useCallback, useEffect, useState } from "react";
import { FileQuestion, MessageSquare, Mic, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { useProjects } from "@/context/ProjectsContext";
import {
  createPodcastAudio,
  getDiscoveryExams,
  getDiscoveryStats,
  getDiscoverySummaries,
  type DiscoveryItem,
  type DiscoveryStats,
} from "@/lib/api";
import { dictionaries } from "@/locales";

const t = dictionaries.mainContent;
const d = dictionaries.mainContent.discoveryHub;

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("es-ES", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

type ModalProps = {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  titleId?: string;
};

function LargeModal({ title, onClose, children, titleId = "discovery-modal-title" }: ModalProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-4xl max-h-[min(90vh,920px)] flex flex-col rounded-2xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 px-5 py-4 border-b border-gray-100 dark:border-gray-800 shrink-0">
          <h2 id={titleId} className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label={dictionaries.common.close}
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

export default function DiscoveryHubSection() {
  const { effectiveSessionId } = useProjects();
  const [stats, setStats] = useState<DiscoveryStats>({ summaries: 0, exams: 0 });
  const [summariesOpen, setSummariesOpen] = useState(false);
  const [examsOpen, setExamsOpen] = useState(false);
  const [summariesList, setSummariesList] = useState<DiscoveryItem[]>([]);
  const [examsList, setExamsList] = useState<DiscoveryItem[]>([]);
  const [summariesLoading, setSummariesLoading] = useState(false);
  const [examsLoading, setExamsLoading] = useState(false);
  const [audioBlobUrl, setAudioBlobUrl] = useState<string | null>(null);
  const [audioLoading, setAudioLoading] = useState(false);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [podcastModalOpen, setPodcastModalOpen] = useState(false);
  const [podcastPickLoading, setPodcastPickLoading] = useState(false);
  const [podcastPickList, setPodcastPickList] = useState<DiscoveryItem[]>([]);
  const [selectedForPodcast, setSelectedForPodcast] = useState<Set<number>>(() => new Set());

  const refreshStats = useCallback(async () => {
    if (!effectiveSessionId) return;
    try {
      const s = await getDiscoveryStats(effectiveSessionId);
      setStats(s);
    } catch {
      setStats({ summaries: 0, exams: 0 });
    }
  }, [effectiveSessionId]);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  useEffect(() => {
    function onFocus() {
      refreshStats();
    }
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refreshStats]);

  useEffect(() => {
    return () => {
      if (audioBlobUrl) URL.revokeObjectURL(audioBlobUrl);
    };
  }, [audioBlobUrl]);

  const openSummaries = async () => {
    if (!effectiveSessionId) return;
    setSummariesOpen(true);
    setSummariesLoading(true);
    try {
      const list = await getDiscoverySummaries(effectiveSessionId);
      setSummariesList(list);
      await refreshStats();
    } finally {
      setSummariesLoading(false);
    }
  };

  const openExams = async () => {
    if (!effectiveSessionId) return;
    setExamsOpen(true);
    setExamsLoading(true);
    try {
      const list = await getDiscoveryExams(effectiveSessionId);
      setExamsList(list);
      await refreshStats();
    } finally {
      setExamsLoading(false);
    }
  };

  const openPodcastPicker = async () => {
    if (!effectiveSessionId || stats.summaries === 0) return;
    setPodcastModalOpen(true);
    setPodcastPickLoading(true);
    setAudioError(null);
    try {
      const list = await getDiscoverySummaries(effectiveSessionId);
      const asc = [...list].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );
      setPodcastPickList(asc);
      setSelectedForPodcast(new Set(asc.map((x) => x.id)));
      await refreshStats();
    } catch {
      setPodcastPickList([]);
      setSelectedForPodcast(new Set());
      setAudioError(d.podcastListError);
    } finally {
      setPodcastPickLoading(false);
    }
  };

  const togglePodcastSelection = (id: number) => {
    setSelectedForPodcast((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllPodcast = () => {
    setSelectedForPodcast(new Set(podcastPickList.map((x) => x.id)));
  };

  const selectNonePodcast = () => {
    setSelectedForPodcast(new Set());
  };

  const handleGeneratePodcast = async () => {
    if (!effectiveSessionId) return;
    const ids = podcastPickList.filter((x) => selectedForPodcast.has(x.id)).map((x) => x.id);
    if (ids.length === 0) {
      setAudioError(d.podcastNeedSelection);
      return;
    }
    setAudioLoading(true);
    setAudioError(null);
    setAudioBlobUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    try {
      const blob = await createPodcastAudio(effectiveSessionId, ids);
      setAudioBlobUrl(URL.createObjectURL(blob));
      setPodcastModalOpen(false);
    } catch (e) {
      setAudioError(e instanceof Error ? e.message : d.audioError);
    } finally {
      setAudioLoading(false);
    }
  };

  const closePodcastModal = () => {
    if (!audioLoading) setPodcastModalOpen(false);
  };

  if (!effectiveSessionId) return null;

  const cardBase =
    "bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-100 dark:border-gray-800 p-5 flex flex-col items-stretch gap-3 hover:shadow-md transition-shadow";
  const iconWrap =
    "p-2 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 w-fit";
  const btnPrimary =
    "w-full text-center text-sm font-medium py-2.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-60 disabled:pointer-events-none";

  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div className={cardBase}>
          <div className={iconWrap}>
            <Mic className="w-5 h-5" aria-hidden="true" />
          </div>
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">{t.contentCards.podcasts}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {stats.summaries > 0 ? d.podcastReadyHint(stats.summaries) : d.podcastNeedSummaries}
          </p>
          <button
            type="button"
            onClick={openPodcastPicker}
            disabled={audioLoading || stats.summaries === 0}
            className={btnPrimary}
          >
            {audioLoading ? d.audioLoading : d.createAudio}
          </button>
          {audioError && <p className="text-xs text-red-600 dark:text-red-400">{audioError}</p>}
          {audioBlobUrl && (
            <audio src={audioBlobUrl} controls className="w-full mt-1" preload="metadata" />
          )}
        </div>

        <div className={cardBase}>
          <div className={iconWrap}>
            <MessageSquare className="w-5 h-5" aria-hidden="true" />
          </div>
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">{t.contentCards.summaries}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t.activesLabel(stats.summaries)}</p>
          <button type="button" onClick={openSummaries} className={btnPrimary}>
            {d.openSummaries}
          </button>
        </div>

        <div className={cardBase}>
          <div className={iconWrap}>
            <FileQuestion className="w-5 h-5" aria-hidden="true" />
          </div>
          <h3 className="font-semibold text-gray-800 dark:text-gray-100">{t.contentCards.exams}</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">{t.activesLabel(stats.exams)}</p>
          <button type="button" onClick={openExams} className={btnPrimary}>
            {d.openExams}
          </button>
        </div>
      </div>

      {podcastModalOpen && (
        <LargeModal title={d.modalPodcastTitle} titleId="podcast-picker-modal-title" onClose={closePodcastModal}>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{d.podcastPickHint}</p>
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              type="button"
              onClick={selectAllPodcast}
              className="text-sm font-medium text-emerald-600 hover:underline dark:text-emerald-400"
            >
              {d.podcastSelectAll}
            </button>
            <span className="text-gray-300 dark:text-gray-600">·</span>
            <button
              type="button"
              onClick={selectNonePodcast}
              className="text-sm font-medium text-gray-600 hover:underline dark:text-gray-400"
            >
              {d.podcastSelectNone}
            </button>
          </div>
          {podcastPickLoading ? (
            <p className="text-gray-500">{d.podcastLoadingSummaries}</p>
          ) : podcastPickList.length === 0 ? (
            <p className="text-gray-600 dark:text-gray-300">{d.emptySummaries}</p>
          ) : (
            <ul className="space-y-3 max-h-[min(52vh,480px)] overflow-y-auto pr-1">
              {podcastPickList.map((item) => (
                <li key={item.id}>
                  <label className="flex gap-3 cursor-pointer rounded-lg border border-gray-100 dark:border-gray-800 p-3 hover:bg-gray-50 dark:hover:bg-gray-800/60">
                    <input
                      type="checkbox"
                      checked={selectedForPodcast.has(item.id)}
                      onChange={() => togglePodcastSelection(item.id)}
                      className="mt-1 h-4 w-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-gray-500 dark:text-gray-400">{formatDate(item.created_at)}</p>
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-100 line-clamp-2 mt-0.5">
                        {item.user_prompt || "—"}
                      </p>
                    </div>
                  </label>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col sm:flex-row gap-2 mt-6 pt-4 border-t border-gray-100 dark:border-gray-800">
            <button
              type="button"
              onClick={closePodcastModal}
              disabled={audioLoading}
              className="sm:flex-1 text-center text-sm font-medium py-2.5 px-3 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-60"
            >
              {d.podcastCancel}
            </button>
            <button
              type="button"
              onClick={handleGeneratePodcast}
              disabled={
                audioLoading ||
                podcastPickLoading ||
                podcastPickList.length === 0 ||
                selectedForPodcast.size === 0
              }
              className={`${btnPrimary} sm:flex-1`}
            >
              {audioLoading ? d.audioLoading : d.createAudio}
            </button>
          </div>
        </LargeModal>
      )}

      {summariesOpen && (
        <LargeModal title={d.modalSummariesTitle} onClose={() => setSummariesOpen(false)}>
          {summariesLoading ? (
            <p className="text-gray-500">{d.listLoading}</p>
          ) : summariesList.length === 0 ? (
            <p className="text-gray-600 dark:text-gray-300">{d.emptySummaries}</p>
          ) : (
            <ul className="space-y-8">
              {summariesList.map((item) => (
                <li key={item.id} className="border-b border-gray-100 dark:border-gray-800 pb-8 last:border-0 last:pb-0">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{formatDate(item.created_at)}</p>
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mt-1">{d.promptLabel}</p>
                  <p className="text-sm text-gray-800 dark:text-gray-100 mb-3">{item.user_prompt}</p>
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown>{item.content}</ReactMarkdown>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </LargeModal>
      )}

      {examsOpen && (
        <LargeModal title={d.modalExamsTitle} onClose={() => setExamsOpen(false)}>
          {examsLoading ? (
            <p className="text-gray-500">{d.listLoading}</p>
          ) : examsList.length === 0 ? (
            <p className="text-gray-600 dark:text-gray-300">{d.emptyExams}</p>
          ) : (
            <ul className="space-y-8">
              {examsList.map((item) => (
                <li key={item.id} className="border-b border-gray-100 dark:border-gray-800 pb-8 last:border-0 last:pb-0">
                  <p className="text-xs text-gray-500 dark:text-gray-400">{formatDate(item.created_at)}</p>
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-300 mt-1">{d.promptLabel}</p>
                  <p className="text-sm text-gray-800 dark:text-gray-100 mb-3">{item.user_prompt}</p>
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown>{item.content}</ReactMarkdown>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </LargeModal>
      )}
    </>
  );
}
