"use client";

import { useParams, useRouter } from "next/navigation";
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
} from "lucide-react";
import Link from "next/link";
import { getProjectKBStats, reindexProjectFile } from "@/lib/api/client";
import type { KBFileStat } from "@/lib/api/types";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Б";
  const k = 1024;
  const sizes = ["Б", "КБ", "МБ", "ГБ"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function StatusBadge({ embedStatus }: { embedStatus: KBFileStat["embed_status"] }) {
  const map: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
    done: { label: "Проиндексирован", color: "#16a34a", icon: <CheckCircle size={12} /> },
    pending: { label: "В очереди", color: "#d97706", icon: <Clock size={12} /> },
    none: { label: "Не проиндексирован", color: "#6b7280", icon: <Clock size={12} /> },
    error: { label: "Ошибка", color: "#dc2626", icon: <XCircle size={12} /> },
  };
  const s = map[embedStatus] ?? map.none;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-[5px] px-1.5 py-0.5 text-[11px] font-medium"
      style={{ color: s.color, background: `${s.color}18` }}
    >
      {s.icon}
      {s.label}
    </span>
  );
}

function FileRow({ file, projectId }: { file: KBFileStat; projectId: number }) {
  const qc = useQueryClient();
  const reindex = useMutation({
    mutationFn: () => reindexProjectFile(projectId, file.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project-kb-stats", projectId] });
    },
  });

  return (
    <div className="flex items-center gap-3 border-b border-[rgba(13,13,13,0.06)] py-2.5 last:border-0 dark:border-[rgba(255,255,255,0.05)]">
      <FileText size={15} className="shrink-0 text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.35)]" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-[13px] font-medium text-[#0d0d0d] dark:text-[#ececec]">
            {file.filename}
          </span>
          {!file.enabled && (
            <span className="text-[11px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
              (отключён)
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
          <span>{formatBytes(file.file_size)}</span>
          <span>·</span>
          <span>{file.chunk_count} чанков</span>
        </div>
      </div>
      <StatusBadge embedStatus={file.embed_status} />
      <button
        onClick={() => reindex.mutate()}
        disabled={reindex.isPending || file.embed_status === "pending"}
        className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.12)] px-2.5 py-1 text-[12px] text-[rgba(13,13,13,0.55)] transition hover:border-[#0a7cff] hover:text-[#0a7cff] disabled:opacity-40 dark:border-[rgba(255,255,255,0.1)] dark:text-[rgba(236,236,236,0.5)]"
        title="Переиндексировать"
      >
        <RefreshCw size={11} className={reindex.isPending ? "animate-spin" : ""} />
        Переиндекс.
      </button>
    </div>
  );
}

export default function ProjectKBPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id, 10);

  const { data, isLoading, error } = useQuery({
    queryKey: ["project-kb-stats", projectId],
    queryFn: () => getProjectKBStats(projectId),
    staleTime: 30 * 1000,
    refetchInterval: 15 * 1000,
  });

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div
        className="flex shrink-0 items-center gap-3 border-b border-[rgba(13,13,13,0.08)] px-5 py-3 dark:border-[rgba(255,255,255,0.07)]"
        style={{ background: "var(--surface, #fff)" }}
      >
        <Link
          href={`/projects/${id}`}
          className="flex items-center gap-1.5 text-[12px] text-[rgba(13,13,13,0.50)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.45)]"
        >
          <ArrowLeft size={13} />
          Проект
        </Link>
        <span className="text-[rgba(13,13,13,0.25)] dark:text-[rgba(236,236,236,0.2)]">/</span>
        <div className="flex items-center gap-1.5">
          <Database size={14} className="text-[#0a7cff]" />
          <span className="text-[13px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
            База знаний
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-5">
        {isLoading && (
          <div className="flex items-center gap-2 text-[13px] text-[rgba(13,13,13,0.45)]">
            <RefreshCw size={13} className="animate-spin" />
            Загрузка статистики...
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 text-[13px] text-red-500">
            <AlertCircle size={13} />
            Не удалось загрузить данные
          </div>
        )}

        {data && (
          <>
            {/* Summary cards */}
            <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { label: "Файлов", value: data.file_count, icon: <FileText size={16} className="text-[#0a7cff]" /> },
                { label: "Проиндексировано", value: data.indexed_count, icon: <CheckCircle size={16} className="text-[#16a34a]" /> },
                { label: "Ошибки", value: data.error_count, icon: <XCircle size={16} className="text-red-500" /> },
                { label: "Чанков", value: data.total_chunks, icon: <BarChart3 size={16} className="text-[#7c3aed]" /> },
              ].map((c) => (
                <div
                  key={c.label}
                  className="rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-3 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]"
                >
                  <div className="mb-1 flex items-center gap-1.5">
                    {c.icon}
                    <span className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      {c.label}
                    </span>
                  </div>
                  <div className="text-[22px] font-bold text-[#0d0d0d] dark:text-[#ececec]">
                    {c.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Coverage bar */}
            {data.file_count > 0 && (
              <div className="mb-5 rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-4 dark:border-[rgba(255,255,255,0.07)] dark:bg-[rgba(255,255,255,0.03)]">
                <div className="mb-2 flex items-center justify-between text-[12px]">
                  <span className="font-medium text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">
                    Покрытие индексом
                  </span>
                  <span className="font-semibold text-[#0d0d0d] dark:text-[#ececec]">
                    {Math.round((data.indexed_count / data.file_count) * 100)}%
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[rgba(13,13,13,0.08)] dark:bg-[rgba(255,255,255,0.08)]">
                  <div
                    className="h-full rounded-full bg-[#0a7cff] transition-all"
                    style={{ width: `${(data.indexed_count / data.file_count) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* File list */}
            <div className="rounded-[10px] border border-[rgba(13,13,13,0.08)] dark:border-[rgba(255,255,255,0.07)]">
              <div className="border-b border-[rgba(13,13,13,0.08)] px-4 py-2.5 dark:border-[rgba(255,255,255,0.07)]">
                <span className="text-[12px] font-semibold text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.5)]">
                  Файлы ({data.files.length})
                </span>
              </div>
              <div className="px-4">
                {data.files.length === 0 ? (
                  <div className="py-6 text-center text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
                    Нет файлов в базе знаний
                  </div>
                ) : (
                  data.files.map((f) => (
                    <FileRow key={f.id} file={f} projectId={projectId} />
                  ))
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
