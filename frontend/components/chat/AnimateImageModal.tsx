"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import { X, Film, Loader2, Sparkles } from "lucide-react";
import { listNetworks, createChat } from "@/lib/api/client";
import type { NetworkListItem } from "@/lib/api/types";

interface Props {
  imageUrl: string;
  onClose: () => void;
}

const DURATIONS = [5, 8, 10];

/**
 * "Оживить" (img2video): выбор видео-модели + motion-промт + длительность.
 * Создаёт новый чат с выбранной видео-моделью и image_url в settings,
 * затем переходит в этот чат (генерация идёт через обычный fal-ai pipeline).
 */
export function AnimateImageModal({ imageUrl, onClose }: Props) {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState<number>(5);
  const [slug, setSlug] = useState<string>("");

  const { data: networks, isLoading } = useQuery({
    queryKey: ["networks", "fal-ai"],
    queryFn: () => listNetworks({ provider: "fal-ai" }),
    staleTime: 60_000,
  });

  const videoModels = useMemo(
    () => (networks ?? []).filter((n: NetworkListItem) => n.output_type === "video"),
    [networks]
  );

  // авто-выбор первой модели
  const selectedSlug = slug || videoModels[0]?.slug || "";

  const createMutation = useMutation({
    mutationFn: () =>
      createChat({
        network_slug: selectedSlug,
        message: prompt.trim() || " ",
        settings: {
          image_url: imageUrl,
          duration,
          seconds: String(duration),
        },
      }),
    onSuccess: (res) => {
      onClose();
      router.push(`/chat/${res.chat_id}`);
    },
  });

  const canSubmit = Boolean(selectedSlug) && !createMutation.isPending;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[92vh] w-full max-w-md flex-col overflow-hidden rounded-[16px] bg-white dark:bg-[#1a1a1a]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[rgba(13,13,13,0.08)] px-4 py-3 dark:border-[rgba(255,255,255,0.08)]">
          <p className="flex items-center gap-2 text-[14px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
            <Film size={16} className="text-[#0a7cff]" />
            Оживить изображение
          </p>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-[8px] text-[rgba(13,13,13,0.5)] transition-colors hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.5)] dark:hover:bg-[rgba(255,255,255,0.08)]"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {/* Source preview */}
          <div className="overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.1)]">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={imageUrl}
              alt="Кадр-источник"
              className="mx-auto block max-h-[34vh] w-auto object-contain"
            />
          </div>

          {/* Model picker */}
          <div>
            <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              Видео-модель
            </p>
            {isLoading ? (
              <div className="flex items-center gap-2 py-2 text-[13px] text-[rgba(13,13,13,0.45)]">
                <Loader2 size={14} className="animate-spin" />
                Загрузка моделей...
              </div>
            ) : videoModels.length === 0 ? (
              <p className="py-2 text-[13px] text-[rgba(13,13,13,0.45)]">
                Видео-модели недоступны.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                {videoModels.map((m) => (
                  <button
                    key={m.slug}
                    type="button"
                    onClick={() => setSlug(m.slug)}
                    className={`flex flex-col items-start gap-0.5 rounded-[8px] border px-3 py-2 text-left transition-colors ${
                      selectedSlug === m.slug
                        ? "border-[#0a7cff] bg-[rgba(10,124,255,0.08)]"
                        : "border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)]"
                    }`}
                  >
                    <span className="text-[13px] font-medium text-[#0d0d0d] dark:text-[#ececec]">
                      {m.name}
                    </span>
                    <span className="text-[11px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.45)]">
                      {m.cost_per_message} зв.
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Duration */}
          <div>
            <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              Длительность
            </p>
            <div className="flex gap-1.5">
              {DURATIONS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`h-9 flex-1 rounded-[8px] border text-[13px] font-medium transition-colors ${
                    duration === d
                      ? "border-[#0a7cff] bg-[rgba(10,124,255,0.08)] text-[#0a7cff]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  {d} сек
                </button>
              ))}
            </div>
          </div>

          {/* Motion prompt */}
          <div>
            <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              Описание движения (необязательно)
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Например: плавный наезд камеры, лёгкий ветер, движение облаков..."
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[13px] text-[#0d0d0d] outline-none transition-all focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.04)] dark:text-[#ececec]"
            />
          </div>

          {createMutation.isError && (
            <p className="text-[12px] text-[#e74c3c]">
              Не удалось запустить генерацию. Проверьте баланс и попробуйте снова.
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[rgba(13,13,13,0.08)] px-4 py-3 dark:border-[rgba(255,255,255,0.08)]">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-[8px] px-4 text-[13px] font-medium text-[rgba(13,13,13,0.6)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.6)] dark:hover:bg-[rgba(255,255,255,0.08)]"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={() => canSubmit && createMutation.mutate()}
            disabled={!canSubmit}
            className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#0a7cff] px-4 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {createMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            Оживить
          </button>
        </div>
      </div>
    </div>
  );
}
