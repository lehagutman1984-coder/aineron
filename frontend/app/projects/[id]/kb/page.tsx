"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Database,
  FileText,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  XCircle,
  BarChart3,
  MinusCircle,
  ChevronDown,
  ChevronRight,
  Hash,
} from "lucide-react";
import Link from "next/link";
import { getProjectKBStats, reindexProjectFile, getFileChunks } from "@/lib/api/client";
import type { KBFileStat } from "@/lib/api/types";

type EffectiveStatus = "done" | "pending" | "none" | "error" | "skipped";
type FilterKey = "all" | EffectiveStatus;

function formatBytes(bytes: number, t: ReturnType<typeof useTranslations>): string {
  const sizes = [t("unitBytes"), t("unitKb"), t("unitMb"), t("unitGb")];
  if (bytes === 0) return `0 ${sizes[0]}`;
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function getEffectiveStatus(file: KBFileStat): EffectiveStatus {
  if (file.file_size === 0 && file.embed_status === "error") return "skipped";
  return file.embed_status as EffectiveStatus;
}

function StatusBadge({ status }: { status: EffectiveStatus }) {
  const t = useTranslations("projectsKb");
  const STATUS_MAP: Record<EffectiveStatus, { label: string; color: string; icon: React.ReactNode }> = {
    done:    { label: t("statusDone"),    color: "#16a34a", icon: <CheckCircle size={12} /> },
    pending: { label: t("statusPending"), color: "#d97706", icon: <Clock       size={12} /> },
    none:    { label: t("statusNone"),    color: "#6b7280", icon: <Clock       size={12} /> },
    error:   { label: t("statusError"),   color: "#dc2626", icon: <XCircle     size={12} /> },
    skipped: { label: t("statusSkipped"), color: "#9ca3af", icon: <MinusCircle size={12} /> },
  };
  const s = STATUS_MAP[status] ?? STATUS_MAP.none;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-[5px] px-1.5 py-0.5 text-[13px] font-medium"
      style={{ color: s.color, background: `${s.color}18` }}
    >
      {s.icon}
      {s.label}
    </span>
  );
}

function ChunkViewer({ projectId, fileId }: { projectId: number; fileId: number }) {
  const t = useTranslations("projectsKb");
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const { data: chunks, isLoading } = useQuery({
    queryKey: ["file-chunks", projectId, fileId],
    queryFn: () => getFileChunks(projectId, fileId),
    staleTime: 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-2 py-3 text-[14px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
        <RefreshCw size={11} className="animate-spin" />
        {t("loadingChunks")}
      </div>
    );
  }

  if (!chunks || chunks.length === 0) {
    return (
      <div className="px-2 py-3 text-[14px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.35)]">
        {t("noChunks")}
      </div>
    );
  }

  return (
    <div className="space-y-1.5 pb-3">
      {chunks.map((chunk) => {
        const isExpanded = expanded[chunk.chunk_index];
        const preview = chunk.content.slice(0, 280);
        const hasMore = chunk.content.length > 280;

        return (
          <div
            key={chunk.id}
            className="rounded-[7px] border border-[rgba(13,13,13,0.07)] bg-[rgba(13,13,13,0.02)] dark:border-[rgba(255,255,255,0.06)] dark:bg-[rgba(255,255,255,0.02)]"
          >
            <button
              className="flex w-full items-center gap-2 px-3 py-2 text-left"
              onClick={() => setExpanded((p) => ({ ...p, [chunk.chunk_index]: !p[chunk.chunk_index] }))}
            >
              <Hash size={11} className="shrink-0 text-[rgba(13,13,13,0.3)] dark:text-[rgba(236,236,236,0.3)]" />
              <span className="text-[13px] font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.5)]">
                {t("chunkLabel", { number: chunk.chunk_index + 1 })}
              </span>
              <span className="text-[12px] text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)]">
                {t("tokensCount", { count: chunk.token_count })}
              </span>
              <span className="ml-auto text-[rgba(13,13,13,0.3)] dark:text-[rgba(236,236,236,0.3)]">
                {isExpanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
              </span>
            </button>
            <div className="px-3 pb-2 text-[13px] leading-relaxed text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">
              <pre className="whitespace-pre-wrap break-words font-mono text-[10.5px]">
                {isExpanded ? chunk.content : preview}
                {!isExpanded && hasMore && (
                  <span className="text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)]">…</span>
                )}
              </pre>
              {hasMore && (
                <button
                  onClick={() => setExpanded((p) => ({ ...p, [chunk.chunk_index]: !p[chunk.chunk_index] }))}
                  className="mt-1 text-[12px] text-[#D97757] hover:underline"
                >
                  {isExpanded ? t("collapse") : t("showFull")}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function FileRow({ file, projectId }: { file: KBFileStat; projectId: number }) {
  const t = useTranslations("projectsKb");
  const qc = useQueryClient();
  const [showChunks, setShowChunks] = useState(false);
  const effectiveStatus = getEffectiveStatus(file);

  const reindex = useMutation({
    mutationFn: () => reindexProjectFile(projectId, file.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project-kb-stats", projectId] });
    },
  });

  const canViewChunks = file.chunk_count > 0 && effectiveStatus === "done";

  return (
    <div className="border-b border-[rgba(13,13,13,0.06)] last:border-0 dark:border-[rgba(255,255,255,0.05)]">
      <div className="flex items-center gap-3 py-2.5">
        <button
          onClick={() => canViewChunks && setShowChunks((v) => !v)}
          disabled={!canViewChunks}
          className="shrink-0 disabled:cursor-default"
          title={canViewChunks ? t("showChunksTitle") : undefined}
        >
          {canViewChunks ? (
            showChunks
              ? <ChevronDown size={15} className="text-[#D97757]" />
              : <ChevronRight size={15} className="text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.35)]" />
          ) : (
            <FileText size={15} className="text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.35)]" />
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`truncate text-[15px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3] ${canViewChunks ? "cursor-pointer hover:text-[#D97757]" : ""}`}
              onClick={() => canViewChunks && setShowChunks((v) => !v)}
            >
              {file.filename}
            </span>
            {!file.enabled && (
              <span className="text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                {t("disabledStatus")}
              </span>
            )}
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
            {file.repo_path && file.repo_path !== file.filename && (
              <>
                <span className="truncate max-w-[260px] text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)]" title={file.repo_path}>
                  {file.repo_path.includes("/")
                    ? file.repo_path.slice(0, file.repo_path.lastIndexOf("/"))
                    : file.repo_path}
                </span>
                <span>·</span>
              </>
            )}
            <span>{formatBytes(file.file_size, t)}</span>
            <span>·</span>
            <span
              className={canViewChunks ? "cursor-pointer text-[#D97757] hover:underline" : ""}
              onClick={() => canViewChunks && setShowChunks((v) => !v)}
            >
              {t("chunksCount", { count: file.chunk_count })}
            </span>
          </div>
        </div>
        <StatusBadge status={effectiveStatus} />
        <button
          onClick={() => reindex.mutate()}
          disabled={reindex.isPending || file.embed_status === "pending" || effectiveStatus === "skipped"}
          className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.12)] px-2.5 py-1 text-[14px] text-[rgba(13,13,13,0.55)] transition hover:border-[#D97757] hover:text-[#D97757] disabled:opacity-40 dark:border-[rgba(255,255,255,0.1)] dark:text-[rgba(236,236,236,0.5)]"
          title={t("reindexTitle")}
        >
          <RefreshCw size={11} className={reindex.isPending ? "animate-spin" : ""} />
          {t("reindexButton")}
        </button>
      </div>

      {showChunks && (
        <div className="pb-1 pl-6">
          <ChunkViewer projectId={projectId} fileId={file.id} />
        </div>
      )}
    </div>
  );
}

const PAGE_SIZE = 20;

export default function ProjectKBPage() {
  const t = useTranslations("projectsKb");
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id, 10);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const FILTERS: { key: FilterKey; label: string }[] = [
    { key: "all",     label: t("filterAll") },
    { key: "done",    label: t("filterDone") },
    { key: "error",   label: t("filterError") },
    { key: "skipped", label: t("filterSkipped") },
    { key: "pending", label: t("filterPending") },
    { key: "none",    label: t("filterNone") },
  ];

  const { data, isLoading, error } = useQuery({
    queryKey: ["project-kb-stats", projectId],
    queryFn: () => getProjectKBStats(projectId),
    staleTime: 30 * 1000,
    refetchInterval: 15 * 1000,
  });

  const counts = data?.files.reduce<Record<string, number>>((acc, f) => {
    const s = getEffectiveStatus(f);
    acc[s] = (acc[s] ?? 0) + 1;
    return acc;
  }, {}) ?? {};

  const filteredFiles = (data?.files ?? []).filter((f) =>
    filter === "all" ? true : getEffectiveStatus(f) === filter
  );

  const visibleFiles = filteredFiles.slice(0, visibleCount);
  const hasMore = visibleCount < filteredFiles.length;
  const isExpanded = visibleCount > PAGE_SIZE;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex shrink-0 items-center gap-3 border-b border-[rgba(13,13,13,0.08)] px-5 py-3 dark:border-[rgba(255,255,255,0.07)]"
        style={{ background: "var(--surface, #fff)" }}
      >
        <Link
          href={`/projects/${id}`}
          className="flex items-center gap-1.5 text-[14px] text-[rgba(13,13,13,0.50)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)]"
        >
          <ArrowLeft size={13} />
          {t("backToProject")}
        </Link>
        <span className="text-[rgba(13,13,13,0.25)] dark:text-[rgba(236,236,236,0.2)]">/</span>
        <div className="flex items-center gap-1.5">
          <Database size={14} className="text-[#D97757]" />
          <span className="text-[15px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            {t("knowledgeBase")}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-5">
        {isLoading && (
          <div className="flex items-center gap-2 text-[15px] text-[rgba(13,13,13,0.45)]">
            <RefreshCw size={13} className="animate-spin" />
            {t("loadingStats")}
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-[15px] text-red-500">
            <AlertCircle size={13} />
            {t("loadError")}
          </div>
        )}

        {data && (
          <>
            {/* Summary cards */}
            <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: t("statFiles"),   value: data.file_count,    icon: <FileText    size={16} className="text-[#D97757]"  /> },
                { label: t("statIndexed"), value: data.indexed_count, icon: <CheckCircle size={16} className="text-[#16a34a]" /> },
                { label: t("statErrors"),  value: data.error_count,   icon: <XCircle     size={16} className="text-red-500"   /> },
                { label: t("statChunks"),  value: data.total_chunks,  icon: <BarChart3   size={16} className="text-[#D97757]" /> },
              ].map((c) => (
                <div
                  key={c.label}
                  className="rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-3 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]"
                >
                  <div className="mb-1 flex items-center gap-1.5">
                    {c.icon}
                    <span className="text-[13px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      {c.label}
                    </span>
                  </div>
                  <div className="text-[22px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
                    {c.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Coverage bar */}
            {data.file_count > 0 && (
              <div className="mb-5 rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-4 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]">
                <div className="mb-2 flex items-center justify-between text-[14px]">
                  <span className="font-medium text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">
                    {t("coverageLabel")}
                  </span>
                  <span className="font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
                    {Math.round((data.indexed_count / data.file_count) * 100)}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[rgba(13,13,13,0.08)] dark:bg-[rgba(255,255,255,0.08)]">
                  <div
                    className="h-full rounded-full bg-[#D97757] transition-all"
                    style={{ width: `${(data.indexed_count / data.file_count) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* File list */}
            <div className="rounded-[10px] border border-[rgba(13,13,13,0.08)] dark:border-[rgba(255,255,255,0.07)]">
              <div className="flex flex-wrap items-center gap-3 border-b border-[rgba(13,13,13,0.08)] px-4 py-2.5 dark:border-[rgba(255,255,255,0.07)]">
                <span className="text-[14px] font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.5)]">
                  {t("filesHeading", { count: filteredFiles.length })}
                </span>
                <div className="flex flex-wrap items-center gap-1">
                  {FILTERS.filter(({ key }) => key === "all" || (counts[key] ?? 0) > 0).map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => { setFilter(key); setVisibleCount(PAGE_SIZE); }}
                      className={`rounded-[5px] px-2 py-0.5 text-[13px] font-medium transition ${
                        filter === key
                          ? "bg-[#D97757] text-white"
                          : "text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.4)] dark:hover:text-[#EDE8E3]"
                      }`}
                    >
                      {label}
                      {key !== "all" && (
                        <span className="ml-1 opacity-70">{counts[key] ?? 0}</span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
              <div className="px-4">
                {filteredFiles.length === 0 ? (
                  <div className="py-6 text-center text-[15px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
                    {filter === "all" ? t("emptyAll") : t("emptyFiltered")}
                  </div>
                ) : (
                  visibleFiles.map((f) => (
                    <FileRow key={f.id} file={f} projectId={projectId} />
                  ))
                )}
              </div>

              {/* Pagination controls */}
              {filteredFiles.length > PAGE_SIZE && (
                <div className="flex items-center justify-between border-t border-[rgba(13,13,13,0.06)] px-4 py-2.5 dark:border-[rgba(255,255,255,0.05)]">
                  <span className="text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.35)]">
                    {t("shownCount", { shown: visibleFiles.length, total: filteredFiles.length })}
                  </span>
                  <div className="flex items-center gap-2">
                    {hasMore && (
                      <button
                        onClick={() => setVisibleCount((v) => v + PAGE_SIZE)}
                        className="rounded-[6px] border border-[rgba(13,13,13,0.12)] px-3 py-1 text-[14px] text-[rgba(13,13,13,0.6)] transition hover:border-[#D97757] hover:text-[#D97757] dark:border-[rgba(255,255,255,0.1)] dark:text-[rgba(236,236,236,0.5)]"
                      >
                        {t("showMore", { count: Math.min(PAGE_SIZE, filteredFiles.length - visibleCount) })}
                      </button>
                    )}
                    {isExpanded && (
                      <button
                        onClick={() => setVisibleCount(PAGE_SIZE)}
                        className="rounded-[6px] border border-[rgba(13,13,13,0.12)] px-3 py-1 text-[14px] text-[rgba(13,13,13,0.6)] transition hover:border-[rgba(13,13,13,0.3)] dark:border-[rgba(255,255,255,0.1)] dark:text-[rgba(236,236,236,0.5)]"
                      >
                        {t("collapse")}
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
