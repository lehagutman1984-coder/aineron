"use client";

import { useState } from "react";
import { Wand2, Check, X, Loader2, RefreshCw } from "lucide-react";
import { enhanceImagePrompt, APIError } from "@/lib/api/client";

const STYLES: { value: string; label: string }[] = [
  { value: "", label: "Авто" },
  { value: "photorealistic", label: "Фотореализм" },
  { value: "anime", label: "Аниме" },
  { value: "oil_painting", label: "Масло" },
  { value: "watercolor", label: "Акварель" },
  { value: "digital_art", label: "Цифровой арт" },
  { value: "cinematic", label: "Кинематограф" },
  { value: "3d_render", label: "3D-рендер" },
  { value: "pixel_art", label: "Пиксель-арт" },
  { value: "minimalist", label: "Минимализм" },
];

interface PromptEnhancerProps {
  prompt: string;
  onAccept: (enhanced: string) => void;
  disabled?: boolean;
}

export function PromptEnhancer({ prompt, onAccept, disabled }: PromptEnhancerProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [style, setStyle] = useState("");
  const [enhanced, setEnhanced] = useState<string | null>(null);
  const [original, setOriginal] = useState("");
  const [error, setError] = useState<string | null>(null);

  const canEnhance = prompt.trim().length > 0 && !disabled;

  const run = async (styleOverride?: string) => {
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await enhanceImagePrompt({
        prompt: prompt.trim(),
        style: styleOverride ?? style,
      });
      setEnhanced(res.enhanced_prompt);
      setOriginal(res.original_prompt);
      setOpen(true);
    } catch (err) {
      setError(err instanceof APIError ? err.message : "Не удалось улучшить промпт.");
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const accept = () => {
    if (enhanced) onAccept(enhanced);
    close();
  };

  const close = () => {
    setOpen(false);
    setEnhanced(null);
    setError(null);
  };

  return (
    <div className="relative inline-block">
      <button
        type="button"
        disabled={!canEnhance || loading}
        onClick={() => (open ? close() : run())}
        title="Улучшить промпт с помощью ИИ"
        className={[
          "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-40",
          open
            ? "bg-[rgba(124,58,237,0.12)] text-[#7c3aed] ring-1 ring-[rgba(124,58,237,0.35)]"
            : "text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#ececec]",
        ].join(" ")}
      >
        {loading ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
        Улучшить
      </button>

      {open && (
        <div
          className="absolute bottom-full left-0 z-30 mb-2 w-[min(440px,calc(100vw-2rem))] rounded-[14px] bg-white p-3.5 shadow-xl dark:bg-[#1c1c1f]"
          style={{ border: "1px solid rgba(13,13,13,0.12)" }}
        >
          <div className="mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[12px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
              <Wand2 size={13} className="text-[#7c3aed]" />
              Улучшенный промпт
            </span>
            <button
              type="button"
              onClick={close}
              className="flex h-6 w-6 items-center justify-center rounded-[7px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.4)] dark:hover:bg-[rgba(255,255,255,0.08)]"
            >
              <X size={13} />
            </button>
          </div>

          {/* Style picker */}
          <div className="mb-2.5 flex flex-wrap gap-1.5">
            {STYLES.map((s) => (
              <button
                key={s.value}
                type="button"
                disabled={loading}
                onClick={() => {
                  setStyle(s.value);
                  run(s.value);
                }}
                className={[
                  "rounded-full px-2.5 py-1 text-[11px] font-medium transition-all disabled:opacity-50",
                  style === s.value
                    ? "bg-[#7c3aed] text-white"
                    : "bg-[rgba(13,13,13,0.05)] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.09)] dark:bg-[rgba(255,255,255,0.07)] dark:text-[rgba(236,236,236,0.6)]",
                ].join(" ")}
              >
                {s.label}
              </button>
            ))}
          </div>

          {error ? (
            <p className="py-2 text-[13px] text-[#e74c3c]">{error}</p>
          ) : loading ? (
            <div className="flex items-center gap-2 py-3 text-[13px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
              <Loader2 size={14} className="animate-spin" />
              Генерируем улучшенный промпт...
            </div>
          ) : (
            <>
              <div className="mb-2">
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
                  Было
                </p>
                <p className="rounded-[8px] bg-[rgba(13,13,13,0.04)] px-2.5 py-1.5 text-[12px] leading-relaxed text-[rgba(13,13,13,0.6)] dark:bg-[rgba(255,255,255,0.05)] dark:text-[rgba(236,236,236,0.55)]">
                  {original}
                </p>
              </div>
              <div className="mb-3">
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-[#7c3aed]">
                  Стало
                </p>
                <p className="max-h-[180px] overflow-y-auto rounded-[8px] bg-[rgba(124,58,237,0.06)] px-2.5 py-1.5 text-[12px] leading-relaxed text-[#0d0d0d] ring-1 ring-[rgba(124,58,237,0.18)] dark:text-[#ececec]">
                  {enhanced}
                </p>
              </div>

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => run()}
                  className="flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.5)] dark:hover:bg-[rgba(255,255,255,0.08)]"
                >
                  <RefreshCw size={12} />
                  Ещё раз
                </button>
                <button
                  type="button"
                  onClick={close}
                  className="rounded-[8px] px-2.5 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.5)] dark:hover:bg-[rgba(255,255,255,0.08)]"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  disabled={!enhanced}
                  onClick={accept}
                  className="flex items-center gap-1.5 rounded-[8px] bg-[#7c3aed] px-3 py-1.5 text-[12px] font-medium text-white transition-all hover:bg-[#6d28d9] disabled:opacity-40"
                >
                  <Check size={12} />
                  Применить
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
