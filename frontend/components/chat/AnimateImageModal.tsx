"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "@/i18n/navigation";

import { useTranslations } from "next-intl";
import { useQuery, useMutation } from "@tanstack/react-query";
import { X, Film, ImagePlus, Loader2, Sparkles } from "lucide-react";
import { listNetworks, createChat, uploadReferenceImage } from "@/lib/api/client";
import type { NetworkListItem } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";

interface Props {
  imageUrl: string;
  onClose: () => void;
}

/**
 * "Оживить" (img2video): выбор видео-модели + motion-промт + длительность.
 * Создаёт новый чат с выбранной видео-моделью и image_url в settings,
 * затем переходит в этот чат (генерация идёт через обычный fal-ai pipeline).
 */

export function AnimateImageModal({ imageUrl, onClose }: Props) {
  const t = useTranslations("chat.animateImageModal");
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [slug, setSlug] = useState<string>("");
  // Per-model settings
  const [cameraFixed, setCameraFixed] = useState(false);
  const [generateAudio, setGenerateAudio] = useState(false);
  // Длительность/формат кадра — реальные опции конкретной модели
  // (duration_options/aspect_options из ui_settings, см. catalog.py), а не
  // хардкод по названию модели: раньше SORA_DURATIONS=[5,10,20] не совпадал
  // с реальными опциями Sora (4/8/12/16/20) — запрос с дефолтным duration=5
  // гарантированно падал на валидации.
  const [durationOverride, setDurationOverride] = useState<string | null>(null);
  const [aspectOverride, setAspectOverride] = useState<string | null>(null);
  // B14: доп. референсные фото сверх основного imageUrl (первый+последний
  // кадр у Kling/Vidu, набор референсов у Veo/Seedance/Grok) — см. i2v ниже.
  const [extraImages, setExtraImages] = useState<Array<{ url: string; localUrl: string; uploading: boolean; error?: boolean }>>([]);
  const extraInputRef = useRef<HTMLInputElement>(null);

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

  // B14: imageUrl (проп) уже занимает один слот, поэтому доступно max_images-1
  // дополнительных фото. Смена модели на ту, что поддерживает меньше — обрежет лишнее.
  const i2v = selectedModel?.i2v ?? null;
  const maxExtraImages = Math.max((i2v?.max_images ?? 1) - 1, 0);
  const visibleExtraImages = extraImages.slice(0, maxExtraImages);

  // null/[] — у модели фиксированная длительность/формат (напр. Veo: 8 сек
  // всегда) — соответствующий блок вообще не показываем.
  const durationOptions = selectedModel?.duration_options ?? null;
  const aspectOptions = selectedModel?.aspect_options ?? null;
  const durationValue =
    (durationOverride && durationOptions?.some((o) => o.value === durationOverride) ? durationOverride : null) ??
    durationOptions?.[0]?.value ?? "";
  const aspectValue =
    (aspectOverride && aspectOptions?.some((o) => o.value === aspectOverride) ? aspectOverride : null) ??
    aspectOptions?.[0]?.value ?? "";

  const handleAddExtraImage = async (file: File) => {
    const localUrl = URL.createObjectURL(file);
    setExtraImages((prev) => [...prev, { url: "", localUrl, uploading: true }]);
    try {
      const result = await uploadReferenceImage(file);
      setExtraImages((prev) => prev.map((s) => (s.localUrl === localUrl ? { url: result.url, localUrl, uploading: false } : s)));
    } catch {
      setExtraImages((prev) => prev.map((s) => (s.localUrl === localUrl ? { url: "", localUrl, uploading: false, error: true } : s)));
    }
  };
  const handleRemoveExtraImage = (localUrl: string) => {
    setExtraImages((prev) => {
      const target = prev.find((s) => s.localUrl === localUrl);
      if (target?.localUrl?.startsWith("blob:")) URL.revokeObjectURL(target.localUrl);
      return prev.filter((s) => s.localUrl !== localUrl);
    });
  };

  const createMutation = useMutation({
    mutationFn: () => {
      const extra: Record<string, unknown> = {};
      // camera_type/motion_strength/audio_response раньше были здесь, но ни
      // одна модель их не декларирует в ui_settings и backend их нигде не
      // читает (grep fal_utils.py) — были чисто декоративными контролами,
      // которые ничего не делали. Убраны вместе с самими UI-элементами ниже.
      if (isSeedance) { extra.camerafixed = cameraFixed; }
      if (isSeedance || isKling) { extra.audio = generateAudio; }
      if (durationOptions) { extra.duration = durationValue; extra.seconds = durationValue; }
      if (aspectOptions) { extra.aspect_ratio = aspectValue; }
      // B14: image_urls — imageUrl + доп. референсы, только если модель их
      // поддерживает и хотя бы одно доп. фото реально загружено без ошибки.
      const extraUrls = visibleExtraImages.filter((s) => s.url && !s.error).map((s) => s.url);
      if (extraUrls.length > 0) extra.image_urls = [imageUrl, ...extraUrls];
      return createChat({
        network_slug: selectedSlug,
        message: prompt.trim() || " ",
        settings: {
          image_url: imageUrl,
          ...extra,
        },
      });
    },
    onSuccess: (res) => {
      onClose();
      router.push(`/chat/${res.chat_id}`);
    },
  });

  const canSubmit = Boolean(selectedSlug) && !createMutation.isPending && !visibleExtraImages.some((s) => s.uploading);

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
          <p className="flex items-center gap-2 text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            <Film size={16} className="text-[#D97757]" />
            {t("title")}
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
              alt={t("sourceAlt")}
              className="mx-auto block max-h-[34vh] w-auto object-contain"
            />
          </div>

          {/* Model picker */}
          <div>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("videoModelLabel")}
            </p>
            {isLoading ? (
              <div className="flex items-center gap-2 py-2 text-[15px] text-[rgba(13,13,13,0.45)]">
                <Loader2 size={14} className="animate-spin" />
                {t("loadingModels")}
              </div>
            ) : videoModels.length === 0 ? (
              <p className="py-2 text-[15px] text-[rgba(13,13,13,0.45)]">
                {t("noVideoModels")}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                {videoModels.map((m) => (
                  <button
                    key={m.slug}
                    type="button"
                    onClick={() => setSlug(m.slug)}
                    className={`flex flex-col items-start gap-0.5 rounded-[8px] border px-3 py-2 text-start transition-colors ${
                      selectedSlug === m.slug
                        ? "border-[#D97757] bg-[rgba(217,119,87,0.08)]"
                        : "border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)]"
                    }`}
                  >
                    <span className="text-[15px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">
                      {m.name}
                    </span>
                    <span className="text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.45)]">
                      {formatMoney(m.cost_kopecks)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* B14: доп. референсные фото — первый+последний кадр (Kling/Vidu) или
              набор референсов (Veo/Seedance/Grok), поверх основного imageUrl */}
          {maxExtraImages > 0 && (
            <div>
              <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
                {i2v?.mode === "first_last" ? t("lastFrameSectionLabel") : t("extraReferencesLabel")}
              </p>
              <div className="flex flex-wrap gap-2">
                {visibleExtraImages.map((img) => (
                  <div key={img.localUrl} className="relative shrink-0">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={img.localUrl || img.url}
                      alt={t("sourceAlt")}
                      className="h-14 w-14 rounded-[10px] border object-cover dark:border-[rgba(255,255,255,0.12)]"
                    />
                    {img.uploading && (
                      <div className="absolute inset-0 flex items-center justify-center rounded-[10px] bg-black/40">
                        <Loader2 size={16} className="animate-spin text-white" />
                      </div>
                    )}
                    {img.error && (
                      <div className="absolute inset-0 rounded-[10px] bg-red-500/30" title={t("uploadError")} />
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemoveExtraImage(img.localUrl)}
                      className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
                    >
                      <X size={11} className="text-[rgba(13,13,13,0.55)]" />
                    </button>
                  </div>
                ))}
                {visibleExtraImages.length < maxExtraImages && (
                  <button
                    type="button"
                    onClick={() => extraInputRef.current?.click()}
                    title={t("addAnotherPhoto")}
                    className="flex h-14 w-14 items-center justify-center rounded-[10px] border border-dashed border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.35)] transition-colors hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.15)] dark:text-[rgba(236,236,236,0.35)]"
                  >
                    <ImagePlus size={16} />
                  </button>
                )}
              </div>
              <input
                ref={extraInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => { if (e.target.files?.[0]) { void handleAddExtraImage(e.target.files[0]); e.target.value = ""; } }}
              />
            </div>
          )}

          {/* Duration — реальные опции модели, скрыт для моделей с фиксированной длительностью */}
          {durationOptions && durationOptions.length > 0 && <div>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("durationLabel")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {durationOptions.map((d) => (
                <button
                  key={d.value}
                  type="button"
                  onClick={() => setDurationOverride(d.value)}
                  className={`h-9 flex-1 rounded-[8px] border text-[15px] font-medium transition-colors ${
                    durationValue === d.value
                      ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  {t("durationSeconds", { seconds: d.value })}
                  {d.extra_cost ? ` (+${d.extra_cost})` : ""}
                </button>
              ))}
            </div>
          </div>}

          {/* Aspect ratio — реальные опции модели, скрыт если формат фиксирован фото */}
          {aspectOptions && aspectOptions.length > 0 && <div>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("aspectRatioLabel")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {aspectOptions.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setAspectOverride(r.value)}
                  className={`h-9 flex-1 rounded-[8px] border text-[14px] font-medium transition-colors ${
                    aspectValue === r.value
                      ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  {r.value}
                  {r.extra_cost ? ` (+${r.extra_cost})` : ""}
                </button>
              ))}
            </div>
          </div>}

          {/* Per-model settings — только реально работающие на бэкенде поля.
              camera_type/motion_strength/audio_response были декоративными:
              ни одна модель их не декларирует и fal_utils.py их не читает. */}
          {(isKling || isSeedance) && (
            <div className="space-y-3 rounded-[10px] border border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] p-3 dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.03)]">
              <p className="text-[13px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
                {t("modelSettingsTitle")}
              </p>
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
                      <span className={`inline-block h-3.5 w-3.5 rounded-full bg-[#fff] shadow transition-transform ${cameraFixed ? "translate-x-4" : "translate-x-0.5"}`} />
                    </button>
                    <span className="text-[14px] text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">{t("cameraFixedLabel")}</span>
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
                    <span className={`inline-block h-3.5 w-3.5 rounded-full bg-[#fff] shadow transition-transform ${generateAudio ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                  <span className="text-[14px] text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">{t("generateAudioLabel")}</span>
                </label>
              </div>
            </div>
          )}

          {/* Motion prompt */}
          <div>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("motionPromptLabel")}
            </p>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder={t("motionPromptPlaceholder")}
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[15px] text-[#1A1A1A] outline-none transition-all focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.04)] dark:text-[#EDE8E3]"
            />
          </div>

          {createMutation.isError && (
            <p className="text-[14px] text-[#e74c3c]">
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : t("genericError")}
            </p>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 border-t border-[rgba(13,13,13,0.08)] px-4 py-3 dark:border-[rgba(255,255,255,0.08)]">
          <button
            type="button"
            onClick={onClose}
            className="h-9 rounded-[8px] px-4 text-[15px] font-medium text-[rgba(13,13,13,0.6)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.6)] dark:hover:bg-[rgba(255,255,255,0.08)]"
          >
            {t("cancel")}
          </button>
          <button
            type="button"
            onClick={() => canSubmit && createMutation.mutate()}
            disabled={!canSubmit}
            className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {createMutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            {t("animate")}
          </button>
        </div>
      </div>
    </div>
  );
}
