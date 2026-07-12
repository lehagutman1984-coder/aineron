"use client";

import { useState, useRef } from "react";
import { useTranslations } from "next-intl";
import {
  X,
  Brush,
  Send,
  Loader2,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  Maximize2,
  Check,
} from "lucide-react";
import { MaskEditor } from "@/components/chat/MaskEditor";

export interface EditImagePayload {
  prompt: string;
  image_url: string;
  mask_url?: string;
  outpaint_direction?: "left" | "right" | "up" | "down" | "all";
  target_ratio?: string;
}

interface Props {
  imageUrl: string;
  chatId: number;
  onClose: () => void;
  onSubmit: (payload: EditImagePayload) => void;
}

type Direction = "left" | "right" | "up" | "down" | "all";

const EXPAND_RATIOS = ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9"];

export function EditImageModal({ imageUrl, chatId, onClose, onSubmit }: Props) {
  const t = useTranslations("chat.editImageModal");
  const ASPECT_HINT: Record<Direction, string> = {
    left: t("aspectHintLeft"),
    right: t("aspectHintRight"),
    up: t("aspectHintUp"),
    down: t("aspectHintDown"),
    all: t("aspectHintAll"),
  };
  const OUTPAINT_BTNS: { dir: Direction; icon: typeof ArrowLeft; label: string }[] = [
    { dir: "left", icon: ArrowLeft, label: t("directionLeft") },
    { dir: "up", icon: ArrowUp, label: t("directionUp") },
    { dir: "down", icon: ArrowDown, label: t("directionDown") },
    { dir: "right", icon: ArrowRight, label: t("directionRight") },
    { dir: "all", icon: Maximize2, label: t("directionAll") },
  ];
  const [prompt, setPrompt] = useState("");
  const promptRef = useRef<HTMLTextAreaElement>(null);
  const [maskMode, setMaskMode] = useState(false);
  const [maskUrl, setMaskUrl] = useState<string | null>(null);
  const [outpaint, setOutpaint] = useState<Direction | null>(null);
  const [targetRatio, setTargetRatio] = useState<string | null>(null);

  // Маска и outpaint взаимоисключающие
  const handleMaskApplied = (url: string) => {
    setMaskUrl(url);
    setOutpaint(null);
    setMaskMode(false);
  };

  const toggleOutpaint = (dir: Direction) => {
    setOutpaint((prev) => (prev === dir ? null : dir));
    setMaskUrl(null);
    setMaskMode(false);
    setTargetRatio(null);
  };

  const toggleTargetRatio = (ratio: string) => {
    setTargetRatio((prev) => (prev === ratio ? null : ratio));
    setOutpaint(null);
    setMaskUrl(null);
    setMaskMode(false);
  };

  const toggleMaskMode = () => {
    setMaskMode((v) => !v);
    if (!maskMode) { setOutpaint(null); setTargetRatio(null); }
  };

  const canSubmit = prompt.trim().length > 0 || Boolean(maskUrl) || Boolean(outpaint) || Boolean(targetRatio);

  const submitting = false; // отправка управляется родителем (sendMutation), модалка закрывается сразу

  const handleSubmit = () => {
    if (!canSubmit) return;
    const payload: EditImagePayload = { prompt: prompt.trim(), image_url: imageUrl };
    if (targetRatio) payload.target_ratio = targetRatio;
    else if (outpaint) payload.outpaint_direction = outpaint;
    else if (maskUrl) payload.mask_url = maskUrl;
    onSubmit(payload);
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="relative flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-[16px] bg-white dark:bg-[#1a1a1a]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[rgba(13,13,13,0.08)] px-4 py-3 dark:border-[rgba(255,255,255,0.08)]">
          <p className="text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
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
          {maskMode ? (
            <MaskEditor
              imageUrl={imageUrl}
              chatId={chatId}
              applying={submitting}
              onApply={handleMaskApplied}
            />
          ) : (
            <div className="overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.1)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl}
                alt={t("altSourceImage")}
                className="mx-auto block max-h-[45vh] w-auto object-contain"
              />
            </div>
          )}

          {/* Mask toggle + status */}
          <div className={outpaint ? "opacity-40 pointer-events-none select-none" : ""}>
            {/* Quick presets */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              {[
                { label: t("presetRemoveBackground"), prompt: "Remove background, make it transparent or white" },
                { label: t("presetEnhance"), prompt: "Enhance sharpness, increase brightness and contrast, professional photo editing" },
              ].map(({ label, prompt: p }) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setPrompt(p)}
                  className="h-8 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] hover:border-[rgba(13,13,13,0.25)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                >
                  {label}
                </button>
              ))}
              {/* Добавить текст — несовместимо с outpaint: сбрасываем его */}
              <button
                type="button"
                onClick={() => {
                  setOutpaint(null);
                  setTargetRatio(null);
                  const prefix = t("addCaptionPrefix");
                  if (!prompt.startsWith(prefix)) setPrompt(prefix);
                  setTimeout(() => {
                    const el = promptRef.current;
                    if (!el) return;
                    el.focus();
                    el.selectionStart = el.selectionEnd = el.value.length;
                  }, 0);
                }}
                className="h-8 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] hover:border-[rgba(13,13,13,0.25)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
              >
                {t("addText")}
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={toggleMaskMode}
                className={`flex h-9 items-center gap-1.5 rounded-[8px] border px-3 text-[14px] font-medium transition-colors ${
                  maskMode
                    ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                    : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                }`}
              >
                <Brush size={14} />
                {maskMode ? t("hideMask") : t("drawMask")}
              </button>
              {maskUrl && !maskMode && (
                <span className="flex items-center gap-1 text-[14px] font-medium text-[#D97757]">
                  <Check size={13} />
                  {t("maskReady")}
                </span>
              )}
            </div>
            {outpaint && (
              <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                {t("outpaintDisabledHint")}
              </p>
            )}
          </div>

          {/* Outpaint */}
          <div className={(maskMode || maskUrl || Boolean(targetRatio)) ? "opacity-40 pointer-events-none select-none" : ""}>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("expandCanvasTitle")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {OUTPAINT_BTNS.map(({ dir, icon: Icon, label }) => (
                <button
                  key={dir}
                  type="button"
                  onClick={() => toggleOutpaint(dir)}
                  title={label}
                  className={`flex h-9 items-center gap-1.5 rounded-[8px] border px-2.5 text-[14px] font-medium transition-colors ${
                    outpaint === dir
                      ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  <Icon size={14} />
                  {label}
                  <span className="text-[12px] opacity-60 ms-0.5">{ASPECT_HINT[dir]}</span>
                </button>
              ))}
            </div>
            {(maskMode || maskUrl) && (
              <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                {t("maskActiveHint")}
              </p>
            )}
          </div>

          {/* Generative Expand — расширение до целевого соотношения */}
          <div className={(maskMode || maskUrl || Boolean(outpaint)) ? "opacity-40 pointer-events-none select-none" : ""}>
            <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {t("expandToRatioTitle")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {EXPAND_RATIOS.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => toggleTargetRatio(r)}
                  className={`h-9 rounded-[8px] border px-3 text-[14px] font-medium transition-colors ${
                    targetRatio === r
                      ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
              {t("expandRatioHint")}
            </p>
          </div>

          {/* Prompt */}
          <div>
            <textarea
              ref={promptRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder={
                outpaint || targetRatio
                  ? t("placeholderOutpaint")
                  : maskUrl
                    ? t("placeholderMask")
                    : t("placeholderDefault")
              }
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[15px] text-[#1A1A1A] outline-none transition-all focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.04)] dark:text-[#EDE8E3]"
            />
            {outpaint && (
              <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                {t("outpaintPromptHint")}
              </p>
            )}
          </div>
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
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {t("generate")}
          </button>
        </div>
      </div>
    </div>
  );
}
