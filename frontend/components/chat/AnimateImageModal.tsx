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
const SORA_DURATIONS = [5, 10, 20];
const SORA_ASPECTS = ["16:9", "9:16", "1:1"] as const;

/**
 * "Оживить" (img2video): выбор видео-модели + motion-промт + длительность.
 * Создаёт новый чат с выбранной видео-моделью и image_url в settings,
 * затем переходит в этот чат (генерация идёт через обычный fal-ai pipeline).
 */
const CAMERA_TYPES = [
  { value: "close_up", label: "Крупный план" },
  { value: "medium", label: "Средний" },
  { value: "wide_angle", label: "Широкий" },
];

export function AnimateImageModal({ imageUrl, onClose }: Props) {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState<number>(5);
  const [slug, setSlug] = useState<string>("");
  // Per-model settings
  const [cameraType, setCameraType] = useState("medium");
  const [motionStrength, setMotionStrength] = useState(0.6);
  const [cameraFixed, setCameraFixed] = useState(false);
  const [generateAudio, setGenerateAudio] = useState(false);
  const [soraDuration, setSoraDuration] = useState<5 | 10 | 20>(5);
  const [soraAspect, setSoraAspect] = useState<string>("16:9");

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

  const selectedModel = videoModels.find((m) => m.slug === selectedSlug);
  const modelName = (selectedModel?.name ?? "").toLowerCase();
  const isKling = modelName.includes("kling");
  const isSeedance = modelName.includes("seedance");
  const isSora = modelName.includes("sora");
  const isVeo = modelName.includes("veo");

  const createMutation = useMutation({
    mutationFn: () => {
      const extra: Record<string, unknown> = {};
      if (isKling) { extra.camera_type = cameraType; extra.motion_strength = motionStrength; }
      if (isSeedance) { extra.camerafixed = cameraFixed; extra.audio = generateAudio; }
      if (isVeo) { extra.audio_response = generateAudio; }
      if (isSora) { extra.aspect_ratio = soraAspect; }
      const activeDuration = isSora ? soraDuration : duration;
      return createChat({
        network_slug: selectedSlug,
        message: prompt.trim() || " ",
        settings: {
          image_url: imageUrl,
          duration: activeDuration,
          seconds: String(activeDuration),
          ...extra,
        },
      });
    },
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
          <p className="flex items-center gap-2 text-[14px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            <Film size={16} className="text-[#D97757]" />
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
                        ? "border-[#D97757] bg-[rgba(10,124,255,0.08)]"
                        : "border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)]"
                    }`}
                  >
                    <span className="text-[13px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">
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

          {/* Duration (hidden for Sora — uses its own duration in per-model settings) */}
          {!isSora && <div>
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
                      ? "border-[#D97757] bg-[rgba(10,124,255,0.08)] text-[#D97757]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  {d} сек
                </button>
              ))}
            </div>
          </div>}

          {/* Per-model settings */}
          {(isKling || isSeedance || isSora || isVeo) && (
            <div className="space-y-3 rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-3 dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.03)]">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
                Настройки модели
              </p>
              {isKling && (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">Камера</label>
                    <div className="flex gap-1.5">
                      {CAMERA_TYPES.map((ct) => (
                        <button
                          key={ct.value}
                          type="button"
                          onClick={() => setCameraType(ct.value)}
                          className={`flex-1 h-8 rounded-[8px] border text-[11px] font-medium transition-colors ${
                            cameraType === ct.value
                              ? "border-[#D97757] bg-[rgba(10,124,255,0.08)] text-[#D97757]"
                              : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                          }`}
                        >
                          {ct.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="flex items-center justify-between text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      <span>Интенсивность движения</span>
                      <span className="font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">{motionStrength.toFixed(1)}</span>
                    </label>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.1}
                      value={motionStrength}
                      onChange={(e) => setMotionStrength(Number(e.target.value))}
                      className="w-full accent-[#D97757]"
                    />
                  </div>
                </>
              )}
              {isSora && (
                <>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">Длительность</label>
                    <div className="flex gap-1.5">
                      {SORA_DURATIONS.map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setSoraDuration(d as 5 | 10 | 20)}
                          className={`h-8 flex-1 rounded-[8px] border text-[12px] font-medium transition-colors ${
                            soraDuration === d
                              ? "border-[#D97757] bg-[rgba(10,124,255,0.08)] text-[#D97757]"
                              : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                          }`}
                        >
                          {d} сек
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">Соотношение сторон</label>
                    <div className="flex gap-1.5">
                      {SORA_ASPECTS.map((r) => (
                        <button
                          key={r}
                          type="button"
                          onClick={() => setSoraAspect(r)}
                          className={`h-8 flex-1 rounded-[8px] border text-[12px] font-medium transition-colors ${
                            soraAspect === r
                              ? "border-[#D97757] bg-[rgba(10,124,255,0.08)] text-[#D97757]"
                              : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                          }`}
                        >
                          {r}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}
              {(isSeedance || isVeo) && (
                <div className="flex flex-wrap gap-4">
                  {isSeedance && (
                    <label className="flex items-center gap-2 cursor-pointer">
                      <button
                        type="button"
                        role="switch"
                        aria-checked={cameraFixed}
                        onClick={() => setCameraFixed((v) => !v)}
                        className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${cameraFixed ? "bg-[#D97757]" : "bg-[rgba(13,13,13,0.15)] dark:bg-[rgba(255,255,255,0.15)]"}`}
                      >
                        <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${cameraFixed ? "translate-x-4" : "translate-x-0.5"}`} />
                      </button>
                      <span className="text-[12px] text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">Камера фиксирована</span>
                    </label>
                  )}
                  <label className="flex items-center gap-2 cursor-pointer">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={generateAudio}
                      onClick={() => setGenerateAudio((v) => !v)}
                      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${generateAudio ? "bg-[#D97757]" : "bg-[rgba(13,13,13,0.15)] dark:bg-[rgba(255,255,255,0.15)]"}`}
                    >
                      <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${generateAudio ? "translate-x-4" : "translate-x-0.5"}`} />
                    </button>
                    <span className="text-[12px] text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">Генерировать аудио</span>
                  </label>
                </div>
              )}
            </div>
          )}

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
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[13px] text-[#1A1A1A] outline-none transition-all focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.04)] dark:text-[#EDE8E3]"
            />
          </div>

          {createMutation.isError && (
            <p className="text-[12px] text-[#e74c3c]">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Не удалось запустить генерацию. Попробуйте снова."}
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
            className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc] disabled:cursor-not-allowed disabled:opacity-40"
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
