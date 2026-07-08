"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Wand2, Check, X, Loader2, RefreshCw } from "lucide-react";
import { enhanceImagePrompt, APIError } from "@/lib/api/client";

const STYLE_KEYS: { value: string; key: string }[] = [
  { value: "", key: "styleAuto" },
  { value: "photorealistic", key: "stylePhotorealistic" },
  { value: "anime", key: "styleAnime" },
  { value: "oil_painting", key: "styleOilPainting" },
  { value: "watercolor", key: "styleWatercolor" },
  { value: "digital_art", key: "styleDigitalArt" },
  { value: "cinematic", key: "styleCinematic" },
  { value: "3d_render", key: "style3dRender" },
  { value: "pixel_art", key: "stylePixelArt" },
  { value: "minimalist", key: "styleMinimalist" },
];

interface PromptEnhancerProps {
  prompt: string;
  onAccept: (enhanced: string) => void;
  disabled?: boolean;
}

export function PromptEnhancer({ prompt, onAccept, disabled }: PromptEnhancerProps) {
  const t = useTranslations("chat.promptEnhancer");
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
      setError(err instanceof APIError ? err.message : t("enhanceError"));
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
        title={t("enhanceTitle")}
        className={[
          "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-medium transition-all disabled:cursor-not-allowed disabled:opacity-40",
          open
            ? "bg-[rgba(217,119,87,0.12)] text-[#D97757] ring-1 ring-[rgba(217,119,87,0.35)]"
            : "text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.38)] dark:hover:text-[#EDE8E3]",
        ].join(" ")}
      >
        {loading ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
        {t("enhanceButton")}
      </button>

      {open && (
        <div
          className="absolute bottom-full left-0 z-30 mb-2 w-[min(440px,calc(100vw-2rem))] rounded-[14px] bg-white p-3.5 shadow-xl dark:bg-[#1c1c1f]"
          style={{ border: "1px solid var(--border-primary)" }}
        >
          <div className="mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-[14px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
              <Wand2 size={13} className="text-[#D97757]" />
              {t("enhancedPromptTitle")}
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
            {STYLE_KEYS.map((s) => (
              <button
                key={s.value}
                type="button"
                disabled={loading}
                onClick={() => {
                  setStyle(s.value);
                  run(s.value);
                }}
                className={[
                  "rounded-full px-2.5 py-1 text-[13px] font-medium transition-all disabled:opacity-50",
                  style === s.value
                    ? "bg-[#D97757] text-white"
                    : "bg-[rgba(13,13,13,0.05)] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.09)] dark:bg-[rgba(255,255,255,0.07)] dark:text-[rgba(236,236,236,0.6)]",
                ].join(" ")}
              >
                {t(s.key)}
              </button>
            ))}
          </div>

          {error ? (
            <p className="py-2 text-[15px] text-[#e74c3c]">{error}</p>
          ) : loading ? (
            <div className="flex items-center gap-2 py-3 text-[15px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
              <Loader2 size={14} className="animate-spin" />
              {t("generating")}
            </div>
          ) : (
            <>
              <div className="mb-2">
                <p className="mb-1 text-[12px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
                  {t("before")}
                </p>
                <p className="rounded-[8px] bg-[rgba(13,13,13,0.04)] px-2.5 py-1.5 text-[14px] leading-relaxed text-[rgba(13,13,13,0.6)] dark:bg-[rgba(255,255,255,0.05)] dark:text-[rgba(236,236,236,0.55)]">
                  {original}
                </p>
              </div>
              <div className="mb-3">
                <p className="mb-1 text-[12px] font-medium uppercase tracking-wide text-[#D97757]">
                  {t("after")}
                </p>
                <p className="max-h-[180px] overflow-y-auto rounded-[8px] bg-[rgba(217,119,87,0.06)] px-2.5 py-1.5 text-[14px] leading-relaxed text-[#1A1A1A] ring-1 ring-[rgba(217,119,87,0.18)] dark:text-[#EDE8E3]">
                  {enhanced}
                </p>
              </div>

              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => run()}
                  className="flex items-center gap-1.5 rounded-[8px] px-2.5 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.5)] dark:hover:bg-[rgba(255,255,255,0.08)]"
                >
                  <RefreshCw size={12} />
                  {t("retry")}
                </button>
                <button
                  type="button"
                  onClick={close}
                  className="rounded-[8px] px-2.5 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.5)] dark:hover:bg-[rgba(255,255,255,0.08)]"
                >
                  {t("cancel")}
                </button>
                <button
                  type="button"
                  disabled={!enhanced}
                  onClick={accept}
                  className="flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-3 py-1.5 text-[14px] font-medium text-white transition-all hover:bg-[#C4623E] disabled:opacity-40"
                >
                  <Check size={12} />
                  {t("apply")}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
