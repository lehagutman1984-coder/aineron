"use client";

import { useState } from "react";
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
}

interface Props {
  imageUrl: string;
  chatId: number;
  onClose: () => void;
  onSubmit: (payload: EditImagePayload) => void;
}

type Direction = "left" | "right" | "up" | "down" | "all";

const OUTPAINT_BTNS: { dir: Direction; icon: typeof ArrowLeft; label: string }[] = [
  { dir: "left", icon: ArrowLeft, label: "Влево" },
  { dir: "up", icon: ArrowUp, label: "Вверх" },
  { dir: "down", icon: ArrowDown, label: "Вниз" },
  { dir: "right", icon: ArrowRight, label: "Вправо" },
  { dir: "all", icon: Maximize2, label: "Со всех сторон" },
];

export function EditImageModal({ imageUrl, chatId, onClose, onSubmit }: Props) {
  const [prompt, setPrompt] = useState("");
  const [maskMode, setMaskMode] = useState(false);
  const [maskUrl, setMaskUrl] = useState<string | null>(null);
  const [outpaint, setOutpaint] = useState<Direction | null>(null);

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
  };

  const toggleMaskMode = () => {
    setMaskMode((v) => !v);
    // Открытие редактора маски снимает выбор outpaint
    if (!maskMode) setOutpaint(null);
  };

  const canSubmit = prompt.trim().length > 0 || Boolean(maskUrl) || Boolean(outpaint);

  const submitting = false; // отправка управляется родителем (sendMutation), модалка закрывается сразу

  const handleSubmit = () => {
    if (!canSubmit) return;
    const payload: EditImagePayload = { prompt: prompt.trim(), image_url: imageUrl };
    if (outpaint) payload.outpaint_direction = outpaint;
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
          <p className="text-[14px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
            Редактирование изображения
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
                alt="Исходное изображение"
                className="mx-auto block max-h-[45vh] w-auto object-contain"
              />
            </div>
          )}

          {/* Mask toggle + status */}
          <div className={outpaint ? "opacity-40 pointer-events-none select-none" : ""}>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={toggleMaskMode}
                className={`flex h-9 items-center gap-1.5 rounded-[8px] border px-3 text-[12px] font-medium transition-colors ${
                  maskMode
                    ? "border-[#0a7cff] bg-[rgba(10,124,255,0.08)] text-[#0a7cff]"
                    : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                }`}
              >
                <Brush size={14} />
                {maskMode ? "Скрыть маску" : "Нарисовать маску"}
              </button>
              {maskUrl && !maskMode && (
                <span className="flex items-center gap-1 text-[12px] font-medium text-[#10a37f]">
                  <Check size={13} />
                  Маска готова
                </span>
              )}
            </div>
            {outpaint && (
              <p className="mt-1 text-[11px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                Недоступно: выбрано расширение холста
              </p>
            )}
          </div>

          {/* Outpaint */}
          <div className={(maskMode || maskUrl) ? "opacity-40 pointer-events-none select-none" : ""}>
            <p className="mb-2 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              Расширить холст (outpaint)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {OUTPAINT_BTNS.map(({ dir, icon: Icon, label }) => (
                <button
                  key={dir}
                  type="button"
                  onClick={() => toggleOutpaint(dir)}
                  title={label}
                  className={`flex h-9 items-center gap-1.5 rounded-[8px] border px-2.5 text-[12px] font-medium transition-colors ${
                    outpaint === dir
                      ? "border-[#0a7cff] bg-[rgba(10,124,255,0.08)] text-[#0a7cff]"
                      : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </button>
              ))}
            </div>
            {(maskMode || maskUrl) && (
              <p className="mt-1 text-[11px] text-[rgba(13,13,13,0.4)] dark:text-[rgba(236,236,236,0.4)]">
                Недоступно: активна маска редактирования
              </p>
            )}
          </div>

          {/* Prompt */}
          <div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder={
                outpaint
                  ? "Опишите, чем заполнить новую область (необязательно)..."
                  : maskUrl
                    ? "Опишите, что разместить в закрашенной области..."
                    : "Опишите, что изменить на изображении..."
              }
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[13px] text-[#0d0d0d] outline-none transition-all focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.04)] dark:text-[#ececec]"
            />
          </div>
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
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="flex h-9 items-center gap-1.5 rounded-[8px] bg-[#0a7cff] px-4 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            Сгенерировать
          </button>
        </div>
      </div>
    </div>
  );
}
