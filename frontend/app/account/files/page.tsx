"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Video,
  Trash2,
  Download,
  X,
  ChevronLeft,
  ChevronRight,
  FolderOpen,
  Pencil,
  Film,
  RotateCcw,
  Copy,
  Check,
  Maximize2,
  Images,
  Palette,
  Share2,
  Link2,
} from "lucide-react";
import { getUserFiles, deleteUserFile, rerunGeneration, upscaleGeneration, createVariations, shareGeneration, unshareGeneration } from "@/lib/api/client";
import type { GeneratedFile } from "@/lib/api/types";
import { AnimateImageModal } from "@/components/chat/AnimateImageModal";
import { useUIStore } from "@/lib/stores/ui";
import { APIError } from "@/lib/api/client";

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

// Бейдж seed с кнопкой копирования
function SeedBadge({ seed }: { seed: number }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard?.writeText(String(seed)).then(
          () => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          },
          () => {}
        );
      }}
      title="Скопировать seed"
      className="inline-flex items-center gap-1 rounded-[5px] bg-[rgba(13,13,13,0.05)] px-1.5 py-0.5 text-[10px] font-medium text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.09)] transition-colors"
    >
      <span>seed {seed}</span>
      {copied ? (
        <Check size={10} className="text-[#1a9d4b]" />
      ) : (
        <Copy size={10} className="text-[rgba(13,13,13,0.4)]" />
      )}
    </button>
  );
}

// Кнопка шеринга: переключатель "Публичное" + копирование ссылки /g/<slug>
function ShareControls({
  isPublic,
  shareSlug,
  sharing,
  onToggle,
}: {
  isPublic: boolean;
  shareSlug: string | null;
  sharing: boolean;
  onToggle: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const copyLink = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!shareSlug) return;
    navigator.clipboard?.writeText(`https://aineron.ru/g/${shareSlug}`).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      },
      () => {}
    );
  };
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      <button
        onClick={(e) => { e.stopPropagation(); onToggle(); }}
        disabled={sharing}
        title={isPublic ? "Убрать из публичной галереи" : "Опубликовать в галерее"}
        className={`inline-flex items-center gap-1 rounded-[6px] border px-1.5 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-50 ${
          isPublic
            ? "border-[rgba(26,157,75,0.25)] bg-[rgba(26,157,75,0.08)] text-[#1a9d4b]"
            : "border-[rgba(13,13,13,0.10)] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)]"
        }`}
      >
        <Share2 size={10} className={isPublic ? "text-[#1a9d4b]" : "text-[#D97757]"} />
        {isPublic ? "Публичное" : "Сделать публичным"}
      </button>
      {isPublic && shareSlug && (
        <button
          onClick={copyLink}
          title="Скопировать публичную ссылку"
          className="inline-flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
        >
          {copied ? <Check size={10} className="text-[#1a9d4b]" /> : <Link2 size={10} className="text-[#D97757]" />}
          {copied ? "Скопировано" : "Скопировать ссылку"}
        </button>
      )}
    </div>
  );
}

function FileCard({
  file,
  onPreview,
  onDelete,
  onEdit,
  onAnimate,
  onRerun,
  onUpscale,
  onVariations,
  onStyle,
  onToggleShare,
  isPublic,
  shareSlug,
  sharing,
  deleting,
  rerunning,
  upscaling,
  varying,
}: {
  file: GeneratedFile;
  onPreview: (file: GeneratedFile) => void;
  onDelete: (id: string) => void;
  onEdit: (file: GeneratedFile) => void;
  onAnimate: (file: GeneratedFile) => void;
  onRerun: (file: GeneratedFile) => void;
  onUpscale: (file: GeneratedFile, factor: 2 | 4) => void;
  onVariations: (file: GeneratedFile) => void;
  onStyle: (file: GeneratedFile) => void;
  onToggleShare: (file: GeneratedFile) => void;
  isPublic: boolean;
  shareSlug: string | null;
  sharing: boolean;
  deleting: boolean;
  rerunning: boolean;
  upscaling: boolean;
  varying: boolean;
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
              autoPlay
              muted
              loop
              playsInline
            />
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
        {(file.model_name || file.seed != null || file.parent_id != null) && (
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {file.parent_id != null && (
              <span className="inline-flex items-center gap-0.5 rounded-[5px] bg-[rgba(16,163,127,0.1)] px-1.5 py-0.5 text-[10px] font-medium text-[#10a37f]">
                <Maximize2 size={9} />
                Детализировано
              </span>
            )}
            {file.model_name && (
              <span className="inline-flex items-center rounded-[5px] bg-[rgba(10,124,255,0.08)] px-1.5 py-0.5 text-[10px] font-medium text-[#D97757]">
                {file.model_name}
              </span>
            )}
            {file.seed != null && <SeedBadge seed={file.seed} />}
          </div>
        )}
        <p className="mt-0.5 text-[11px] text-[rgba(13,13,13,0.35)]">
          {formatDate(file.created_at)} · {file.size}
        </p>

        {file.media_type === "image" && (
          <div className="mt-2 flex flex-wrap gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); onUpscale(file, 2); }}
              disabled={upscaling}
              title="Детализировать — усилить резкость и проработку деталей"
              className="inline-flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50 transition-colors"
            >
              <Maximize2 size={10} className="text-[#D97757]" />
              Детализировать
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onVariations(file); }}
              disabled={varying}
              title="Создать 4 вариации"
              className="inline-flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50 transition-colors"
            >
              <Images size={10} className="text-[#D97757]" />
              Варианты
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onStyle(file); }}
              title="Использовать как референс стиля"
              className="inline-flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-1.5 py-0.5 text-[10px] font-medium text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
            >
              <Palette size={10} className="text-[#D97757]" />
              Стиль
            </button>
          </div>
        )}

        <ShareControls
          isPublic={isPublic}
          shareSlug={shareSlug}
          sharing={sharing}
          onToggle={() => onToggleShare(file)}
        />
      </div>

      <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={(e) => { e.stopPropagation(); onRerun(file); }}
          disabled={rerunning}
          title="Повторить генерацию (те же параметры)"
          className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/90 shadow-sm hover:bg-white disabled:opacity-50 transition-colors"
        >
          <RotateCcw size={13} className={rerunning ? "animate-spin text-[#D97757]" : "text-[#D97757]"} />
        </button>
        {file.media_type === "image" && (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(file); }}
              title="Редактировать изображение (img2img)"
              className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/90 shadow-sm hover:bg-white transition-colors"
            >
              <Pencil size={13} className="text-[#D97757]" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onAnimate(file); }}
              title="Оживить изображение (img2video)"
              className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/90 shadow-sm hover:bg-white transition-colors"
            >
              <Film size={13} className="text-[#D97757]" />
            </button>
          </>
        )}
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
  onEdit,
  onAnimate,
  onRerun,
  onUpscale,
  onVariations,
  onStyle,
  deleting,
  rerunning,
  upscaling,
  varying,
}: {
  file: GeneratedFile;
  files: GeneratedFile[];
  onClose: () => void;
  onNavigate: (dir: -1 | 1) => void;
  onDelete: (id: string) => void;
  onEdit: (file: GeneratedFile) => void;
  onAnimate: (file: GeneratedFile) => void;
  onRerun: (file: GeneratedFile) => void;
  onUpscale: (file: GeneratedFile, factor: 2 | 4) => void;
  onVariations: (file: GeneratedFile) => void;
  onStyle: (file: GeneratedFile) => void;
  deleting: boolean;
  rerunning: boolean;
  upscaling: boolean;
  varying: boolean;
}) {
  const idx = files.findIndex((f) => f.id === file.id);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[90vh] max-w-4xl w-full flex-col overflow-hidden rounded-[16px] bg-[#1A1A1A]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3">
          <p className="truncate text-[13px] text-[rgba(255,255,255,0.65)] max-w-md">{file.prompt}</p>
          <div className="flex items-center gap-2 flex-shrink-0 ml-3">
            <button
              onClick={() => onRerun(file)}
              disabled={rerunning}
              title="Повторить генерацию (те же параметры)"
              className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] disabled:opacity-50 transition-colors"
            >
              <RotateCcw size={14} className={rerunning ? "animate-spin text-white" : "text-white"} />
              <span className="text-[12px] font-medium text-white">Повторить</span>
            </button>
            {file.media_type === "image" && (
              <>
                <button
                  onClick={() => onEdit(file)}
                  title="Редактировать изображение (img2img)"
                  className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] transition-colors"
                >
                  <Pencil size={14} className="text-white" />
                  <span className="text-[12px] font-medium text-white">Редактировать</span>
                </button>
                <button
                  onClick={() => onAnimate(file)}
                  title="Оживить изображение (img2video)"
                  className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] transition-colors"
                >
                  <Film size={14} className="text-white" />
                  <span className="text-[12px] font-medium text-white">Оживить</span>
                </button>
              </>
            )}
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

        {/* Sprint 6 toolbar: upscale / variations / style (image only) */}
        {file.media_type === "image" && (
          <div className="flex flex-wrap items-center gap-1.5 px-4 pb-2">
            <button
              onClick={() => onUpscale(file, 2)}
              disabled={upscaling}
              title="Увеличить разрешение в 2 раза"
              className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] disabled:opacity-50 transition-colors"
            >
              <Maximize2 size={14} className="text-white" />
              <span className="text-[12px] font-medium text-white">Апскейл 2×</span>
            </button>
            <button
              onClick={() => onUpscale(file, 4)}
              disabled={upscaling}
              title="Увеличить разрешение в 4 раза"
              className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] disabled:opacity-50 transition-colors"
            >
              <Maximize2 size={14} className="text-white" />
              <span className="text-[12px] font-medium text-white">4×</span>
            </button>
            <button
              onClick={() => onVariations(file)}
              disabled={varying}
              title="Создать 4 вариации"
              className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] disabled:opacity-50 transition-colors"
            >
              <Images size={14} className="text-white" />
              <span className="text-[12px] font-medium text-white">Варианты</span>
            </button>
            <button
              onClick={() => onStyle(file)}
              title="Использовать как референс стиля"
              className="flex h-8 items-center gap-1.5 rounded-[8px] bg-[rgba(255,255,255,0.08)] px-3 hover:bg-[rgba(255,255,255,0.14)] transition-colors"
            >
              <Palette size={14} className="text-white" />
              <span className="text-[12px] font-medium text-white">Стиль</span>
            </button>
          </div>
        )}

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
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 py-2.5 text-[11px] text-[rgba(255,255,255,0.35)]">
          <span>{formatDate(file.created_at)} · {file.size}</span>
          {file.width && file.height ? <span>· {file.width}×{file.height}</span> : null}
          {file.model_name ? (
            <span className="rounded-[5px] bg-[rgba(255,255,255,0.10)] px-1.5 py-0.5 text-[rgba(255,255,255,0.7)]">
              {file.model_name}
            </span>
          ) : null}
          {file.seed != null ? (
            <button
              onClick={() => navigator.clipboard?.writeText(String(file.seed))}
              title="Скопировать seed"
              className="inline-flex items-center gap-1 rounded-[5px] bg-[rgba(255,255,255,0.10)] px-1.5 py-0.5 text-[rgba(255,255,255,0.7)] hover:bg-[rgba(255,255,255,0.16)] transition-colors"
            >
              seed {file.seed}
              <Copy size={10} />
            </button>
          ) : null}
          <span className="ml-auto">{idx + 1} из {files.length}</span>
        </div>
      </div>
    </div>
  );
}

// localStorage-ключ, по которому ChatStartForm подхватывает изображение для редактирования
const EDIT_IMAGE_KEY = "aineron_edit_image";
// localStorage-ключ для референса стиля (Sprint 6)
const STYLE_IMAGE_KEY = "aineron_style_image";

export default function FilesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const addToast = useUIStore((s) => s.addToast);
  const [category, setCategory] = useState<Category>("all");
  const [preview, setPreview] = useState<GeneratedFile | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [upscalingId, setUpscalingId] = useState<string | null>(null);
  const [varyingId, setVaryingId] = useState<string | null>(null);
  const [animateUrl, setAnimateUrl] = useState<string | null>(null);
  const [sharingId, setSharingId] = useState<string | null>(null);
  // Локальные оверрайды состояния публикации (мгновенный отклик без рефетча)
  const [shareOverrides, setShareOverrides] = useState<
    Record<string, { is_public: boolean; share_slug: string | null }>
  >({});

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

  const rerunMutation = useMutation({
    mutationFn: rerunGeneration,
    onMutate: (id) => setRerunningId(id),
    onSuccess: (res) => {
      router.push(`/chat/${res.chat_id}/`);
    },
    onSettled: () => setRerunningId(null),
  });

  const handleRerun = useCallback(
    (file: GeneratedFile) => {
      if (rerunningId) return;
      rerunMutation.mutate(file.id);
    },
    [rerunMutation, rerunningId]
  );

  const upscaleMutation = useMutation({
    mutationFn: ({ id, factor }: { id: string; factor: 2 | 4 }) =>
      upscaleGeneration(id, factor),
    onMutate: ({ id }) => setUpscalingId(id),
    onSuccess: (res) => {
      addToast({
        type: "success",
        message: `Апскейл ×${res.factor} запущен. Результат появится в галерее через минуту.`,
      });
      // Результат генерируется асинхронно — обновляем галерею с задержкой
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["user-files"] }), 8000);
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["user-files"] }), 25000);
    },
    onError: (err) => {
      addToast({
        type: "error",
        message: err instanceof APIError ? err.message : "Не удалось запустить апскейл.",
      });
    },
    onSettled: () => setUpscalingId(null),
  });

  const variationsMutation = useMutation({
    mutationFn: (id: string) => createVariations(id, 4),
    onMutate: (id) => setVaryingId(id),
    onSuccess: (res) => {
      router.push(`/chat/${res.chat_id}/`);
    },
    onError: (err) => {
      addToast({
        type: "error",
        message: err instanceof APIError ? err.message : "Не удалось создать вариации.",
      });
    },
    onSettled: () => setVaryingId(null),
  });

  const handleUpscale = useCallback(
    (file: GeneratedFile, factor: 2 | 4) => {
      if (upscalingId) return;
      upscaleMutation.mutate({ id: file.id, factor });
    },
    [upscaleMutation, upscalingId]
  );

  const handleVariations = useCallback(
    (file: GeneratedFile) => {
      if (varyingId) return;
      variationsMutation.mutate(file.id);
    },
    [variationsMutation, varyingId]
  );

  const handleStyle = useCallback(
    (file: GeneratedFile) => {
      try {
        localStorage.setItem(STYLE_IMAGE_KEY, file.url);
      } catch {}
      router.push("/models/");
    },
    [router]
  );

  const shareMutation = useMutation({
    mutationFn: ({ id, makePublic }: { id: string; makePublic: boolean }) =>
      makePublic ? shareGeneration(id) : unshareGeneration(id),
    onMutate: ({ id }) => setSharingId(id),
    onSuccess: (res) => {
      setShareOverrides((prev) => ({
        ...prev,
        [String(res.id)]: { is_public: res.is_public, share_slug: res.share_slug },
      }));
      addToast({
        type: "success",
        message: res.is_public
          ? "Опубликовано в галерее."
          : "Убрано из публичной галереи.",
      });
    },
    onError: (err) => {
      addToast({
        type: "error",
        message: err instanceof APIError ? err.message : "Не удалось изменить публикацию.",
      });
    },
    onSettled: () => setSharingId(null),
  });

  const effectiveShare = useCallback(
    (file: GeneratedFile) =>
      shareOverrides[file.id] ?? { is_public: file.is_public, share_slug: file.share_slug },
    [shareOverrides]
  );

  const handleToggleShare = useCallback(
    (file: GeneratedFile) => {
      if (sharingId) return;
      const currentlyPublic = effectiveShare(file).is_public;
      shareMutation.mutate({ id: file.id, makePublic: !currentlyPublic });
    },
    [shareMutation, sharingId, effectiveShare]
  );

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

  // img2img: сохранить URL изображения и перейти к выбору модели генерации
  const handleEdit = useCallback(
    (file: GeneratedFile) => {
      try {
        localStorage.setItem(EDIT_IMAGE_KEY, file.url);
      } catch {}
      router.push("/models/");
    },
    [router]
  );

  // img2video: открыть модалку "Оживить" (создаёт новый чат с видео-моделью)
  const handleAnimate = useCallback((file: GeneratedFile) => {
    setAnimateUrl(file.url);
  }, []);

  return (
    <div className="px-4 py-10 sm:px-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-[#1A1A1A]">Мои файлы</h1>
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
                ? "bg-white text-[#1A1A1A] shadow-sm"
                : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A]"
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
          <p className="text-[15px] font-medium text-[#1A1A1A]">Файлов пока нет</p>
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
                onEdit={handleEdit}
                onAnimate={handleAnimate}
                onRerun={handleRerun}
                onUpscale={handleUpscale}
                onVariations={handleVariations}
                onStyle={handleStyle}
                onToggleShare={handleToggleShare}
                isPublic={effectiveShare(file).is_public}
                shareSlug={effectiveShare(file).share_slug}
                sharing={sharingId === file.id}
                deleting={deletingId === file.id}
                rerunning={rerunningId === file.id}
                upscaling={upscalingId === file.id}
                varying={varyingId === file.id}
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
          onEdit={handleEdit}
          onAnimate={handleAnimate}
          onRerun={handleRerun}
          onUpscale={handleUpscale}
          onVariations={handleVariations}
          onStyle={handleStyle}
          deleting={deletingId === preview.id}
          rerunning={rerunningId === preview.id}
          upscaling={upscalingId === preview.id}
          varying={varyingId === preview.id}
        />
      )}

      {/* img2video "Оживить" modal */}
      {animateUrl && (
        <AnimateImageModal
          imageUrl={animateUrl}
          onClose={() => setAnimateUrl(null)}
        />
      )}
    </div>
  );
}
