"use client";

import { useState, useCallback } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ImageIcon,
  Video,
  Trash2,
  Download,
  X,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
} from "lucide-react";
import { getUserFiles, deleteUserFile } from "@/lib/api/client";
import type { GeneratedFile } from "@/lib/api/types";

type Category = "all" | "images" | "videos";

const TABS: { key: Category; label: string }[] = [
  { key: "all", label: "Все файлы" },
  { key: "images", label: "Изображения" },
  { key: "videos", label: "Видео" },
];

const PER_PAGE = 24;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function FileCard({
  file,
  onPreview,
  onDelete,
  deleting,
}: {
  file: GeneratedFile;
  onPreview: (file: GeneratedFile) => void;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  return (
    <div className="group relative overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
      <button
        onClick={() => onPreview(file)}
        className="relative block w-full overflow-hidden bg-[rgba(13,13,13,0.04)]"
        style={{ aspectRatio: "1 / 1" }}
      >
        {file.media_type === "video" ? (
          <div className="relative h-full w-full bg-black">
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <video
              src={file.url}
              className="h-full w-full object-cover"
              preload="metadata"
              muted
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-black/50">
                <Video size={16} className="text-white" />
              </div>
            </div>
          </div>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={file.url}
            alt={file.prompt}
            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-105"
            loading="lazy"
          />
        )}
        <div className="absolute inset-0 bg-black/0 transition-colors duration-200 group-hover:bg-black/10" />
      </button>

      <div className="p-3">
        <p className="truncate text-[12px] text-[rgba(13,13,13,0.65)]">{file.prompt}</p>
        <p className="mt-0.5 text-[11px] text-[rgba(13,13,13,0.35)]">
          {formatDate(file.created_at)} · {file.size}
        </p>
      </div>

      <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <a
          href={file.url}
          download
          onClick={(e) => e.stopPropagation()}
          className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/90 shadow-sm hover:bg-white transition-colors"
        >
          <Download size={13} className="text-[rgba(13,13,13,0.65)]" />
        </a>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(file.id); }}
          disabled={deleting}
          className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/90 shadow-sm hover:bg-white disabled:opacity-50 transition-colors"
        >
          <Trash2 size={13} className="text-[#e74c3c]" />
        </button>
      </div>
    </div>
  );
}

function PreviewModal({
  file,
  files,
  onClose,
  onNavigate,
  onDelete,
  deleting,
}: {
  file: GeneratedFile;
  files: GeneratedFile[];
  onClose: () => void;
  onNavigate: (dir: -1 | 1) => void;
  onDelete: (id: string) => void;
  deleting: boolean;
}) {
  const idx = files.findIndex((f) => f.id === file.id);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] max-w-4xl w-full flex-col overflow-hidden rounded-[16px] bg-[#0d0d0d]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3">
          <p className="truncate text-[13px] text-[rgba(255,255,255,0.65)] max-w-md">{file.prompt}</p>
          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
            <a
              href={file.url}
              download
              className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.14)] transition-colors"
            >
              <Download size={15} className="text-white" />
            </a>
            <button
              onClick={() => onDelete(file.id)}
              disabled={deleting}
              className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[rgba(231,76,60,0.15)] hover:bg-[rgba(231,76,60,0.25)] disabled:opacity-50 transition-colors"
            >
              <Trash2 size={15} className="text-[#e74c3c]" />
            </button>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.14)] transition-colors"
            >
              <X size={15} className="text-white" />
            </button>
          </div>
        </div>

        {/* Media */}
        <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-black min-h-0">
          {file.media_type === "video" ? (
            <video
              src={file.url}
              controls
              autoPlay
              className="max-h-[70vh] max-w-full object-contain"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={file.url}
              alt={file.prompt}
              className="max-h-[70vh] max-w-full object-contain"
            />
          )}

          {idx > 0 && (
            <button
              onClick={() => onNavigate(-1)}
              className="absolute left-2 flex h-9 w-9 items-center justify-center rounded-full bg-black/50 hover:bg-black/70 transition-colors"
            >
              <ChevronLeft size={20} className="text-white" />
            </button>
          )}
          {idx < files.length - 1 && (
            <button
              onClick={() => onNavigate(1)}
              className="absolute right-2 flex h-9 w-9 items-center justify-center rounded-full bg-black/50 hover:bg-black/70 transition-colors"
            >
              <ChevronRight size={20} className="text-white" />
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2.5 text-[11px] text-[rgba(255,255,255,0.35)]">
          {formatDate(file.created_at)} · {file.size}
          {file.width && file.height ? ` · ${file.width}×${file.height}` : ""}
          {" · "}{idx + 1} из {files.length}
        </div>
      </div>
    </div>
  );
}

export default function FilesPage() {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<Category>("all");
  const [preview, setPreview] = useState<GeneratedFile | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey: ["user-files", category],
      queryFn: ({ pageParam = 1 }) =>
        getUserFiles({ page: pageParam as number, per_page: PER_PAGE, category }),
      getNextPageParam: (last) => (last.has_next ? last.page + 1 : undefined),
      initialPageParam: 1,
    });

  const allFiles = data?.pages.flatMap((p) => p.files) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  const deleteMutation = useMutation({
    mutationFn: deleteUserFile,
    onMutate: (id) => setDeletingId(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ["user-files"] });
      if (preview?.id === id) setPreview(null);
    },
    onSettled: () => setDeletingId(null),
  });

  const handleNavigate = useCallback(
    (dir: -1 | 1) => {
      if (!preview) return;
      const idx = allFiles.findIndex((f) => f.id === preview.id);
      const next = allFiles[idx + dir];
      if (next) setPreview(next);
    },
    [preview, allFiles]
  );

  const handleCategoryChange = (cat: Category) => {
    setCategory(cat);
    setPreview(null);
  };

  return (
    <div className="px-4 py-10 sm:px-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-[#0d0d0d]">Мои файлы</h1>
          {total > 0 && (
            <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.45)]">
              {total} {total === 1 ? "файл" : total < 5 ? "файла" : "файлов"}
            </p>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => handleCategoryChange(t.key)}
            className={`rounded-[7px] px-4 py-1.5 text-[13px] font-medium transition-all ${
              category === t.key
                ? "bg-white text-[#0d0d0d] shadow-sm"
                : "text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.06)]"
              style={{ aspectRatio: "1 / 1" }}
            />
          ))}
        </div>
      ) : allFiles.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[rgba(13,13,13,0.05)]">
            <FolderOpen size={28} className="text-[rgba(13,13,13,0.25)]" />
          </div>
          <p className="text-[15px] font-medium text-[#0d0d0d]">Файлов пока нет</p>
          <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.45)]">
            Сгенерированные изображения и видео будут здесь
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {allFiles.map((file) => (
              <FileCard
                key={file.id}
                file={file}
                onPreview={setPreview}
                onDelete={(id) => deleteMutation.mutate(id)}
                deleting={deletingId === file.id}
              />
            ))}
          </div>

          {hasNextPage && (
            <div className="flex justify-center pt-2">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="h-10 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-6 text-[13px] font-medium text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50 transition-colors"
              >
                {isFetchingNextPage ? "Загрузка..." : "Загрузить ещё"}
              </button>
            </div>
          )}
        </>
      )}

      {/* Preview modal */}
      {preview && (
        <PreviewModal
          file={preview}
          files={allFiles}
          onClose={() => setPreview(null)}
          onNavigate={handleNavigate}
          onDelete={(id) => deleteMutation.mutate(id)}
          deleting={deletingId === preview.id}
        />
      )}
    </div>
  );
}
