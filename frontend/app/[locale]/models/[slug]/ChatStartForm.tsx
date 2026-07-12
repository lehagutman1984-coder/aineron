"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "@/i18n/navigation";

import { useQueryClient } from "@tanstack/react-query";
import { Send, Settings2, ChevronDown, ImagePlus, X, Palette, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { createChat, uploadReferenceImage } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import { APIError } from "@/lib/api/client";
import { MediaSettingsPanel } from "@/components/chat/MediaSettingsPanel";
import type { ModelConfigJson } from "@/lib/api/types";

interface Props {
  networkSlug: string;
  isMedia: boolean;
  /** true — модель генерирует видео (output_type === 'video') */
  isVideo?: boolean;
  configJson?: ModelConfigJson | null;
  projectId?: number;
}

export function ChatStartForm({ networkSlug, isMedia, isVideo, configJson, projectId }: Props) {
  const t = useTranslations("catalog");
  const router = useRouter();
  const qc = useQueryClient();
  const { user, setBalance } = useAuthStore();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const hasSettings = Boolean(configJson?.ui_settings?.sections?.length);
  const [showSettings, setShowSettings] = useState(hasSettings);
  const [mediaSettings, setMediaSettings] = useState<Record<string, unknown>>({});
  // img2img: исходное изображение, переданное из галереи "Мои файлы"
  const [editImageUrl, setEditImageUrl] = useState<string | null>(null);
  // Sprint 6: референс стиля, переданный из галереи кнопкой "Стиль"
  const [styleImageUrl, setStyleImageUrl] = useState<string | null>(null);
  // Прямая загрузка референсного фото со стартового экрана (до создания чата)
  const [uploadingImage, setUploadingImage] = useState(false);
  const sourceInputRef = useRef<HTMLInputElement>(null);

  // Инициализируем настройки из api_defaults при загрузке
  useEffect(() => {
    if (configJson?.api_defaults) {
      setMediaSettings(configJson.api_defaults as Record<string, unknown>);
    }
  }, [configJson]);

  // Префилл промта (из публичной галереи "Попробовать этот промт")
  useEffect(() => {
    try {
      const pre = localStorage.getItem("aineron_prefill_prompt");
      if (pre) {
        setText(pre);
        localStorage.removeItem("aineron_prefill_prompt");
      }
    } catch {}
  }, []);

  // img2img: подхватываем изображение из localStorage только на моделях
  // генерации изображений (не на видео и не на текстовых) — иначе ключ
  // «съедается» не той моделью и редактирование молча не срабатывает.
  useEffect(() => {
    if (!isMedia || isVideo) return;
    try {
      const url = localStorage.getItem("aineron_edit_image");
      if (url) {
        setEditImageUrl(url);
        localStorage.removeItem("aineron_edit_image");
      }
      const styleUrl = localStorage.getItem("aineron_style_image");
      if (styleUrl) {
        setStyleImageUrl(styleUrl);
        localStorage.removeItem("aineron_style_image");
      }
    } catch {}
  }, [isMedia, isVideo]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || loading) return;

    if (!user) {
      router.push(`/login/?next=/models/${networkSlug}/`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const settings: Record<string, unknown> = { ...(hasSettings ? mediaSettings : {}) };
      if (editImageUrl) settings.image_url = editImageUrl;
      if (styleImageUrl) settings.style_image_url = styleImageUrl;
      const res = await createChat({
        network_slug: networkSlug,
        message: text.trim(),
        settings: Object.keys(settings).length > 0 ? settings : undefined,
        project_id: projectId,
      });
      setBalance(res.new_balance_kopecks);
      qc.invalidateQueries({ queryKey: ["chats"] });
      router.push(`/chat/${res.chat_id}/`);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message);
      } else {
        setError(t("genericError"));
      }
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const handlePickImage = async (file: File) => {
    if (!user) return;
    setUploadingImage(true);
    setError(null);
    try {
      const result = await uploadReferenceImage(file);
      setEditImageUrl(result.url);
    } catch (err) {
      setError(err instanceof APIError ? err.message : t("genericError"));
    } finally {
      setUploadingImage(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Settings panel for media models */}
      {hasSettings && (
        <div>
          <button
            type="button"
            onClick={() => setShowSettings((v) => !v)}
            className="mb-2 flex items-center gap-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-colors"
          >
            <Settings2 size={13} />
            {t("generationSettings")}
            <ChevronDown
              size={12}
              className={showSettings ? "rotate-180 transition-transform" : "transition-transform"}
            />
          </button>
          {showSettings && (
            <MediaSettingsPanel
              sections={configJson!.ui_settings!.sections}
              values={mediaSettings}
              onChange={setMediaSettings}
            />
          )}
        </div>
      )}

      {/* img2img: загрузка референсного фото в процессе */}
      {uploadingImage && !editImageUrl && (
        <div className="flex items-center gap-2.5 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.02)] p-2.5">
          <Loader2 size={16} className="animate-spin text-[#D97757]" />
          <p className="text-[14px] text-[rgba(13,13,13,0.5)]">{t("uploading")}</p>
        </div>
      )}

      {/* img2img: исходное изображение (загружено напрямую или из галереи) */}
      {editImageUrl && (
        <div className="flex items-center gap-2.5 rounded-[10px] border border-[rgba(217,119,87,0.20)] bg-[rgba(217,119,87,0.04)] p-2.5">
          <div className="relative shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={editImageUrl}
              alt={t("sourceImageAlt")}
              className="h-14 w-14 rounded-[8px] border border-[rgba(13,13,13,0.10)] object-cover"
            />
            <button
              type="button"
              onClick={() => setEditImageUrl(null)}
              title={t("removeSourceImage")}
              className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
            >
              <X size={11} className="text-[rgba(13,13,13,0.55)]" />
            </button>
          </div>
          <div className="min-w-0">
            <p className="flex items-center gap-1 text-[15px] font-medium text-[#1A1A1A]">
              <ImagePlus size={13} className="text-[#D97757]" />
              {t("editImageTitle")}
            </p>
            <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.5)]">
              {t("editImageFormHint")}
            </p>
          </div>
        </div>
      )}

      {/* Sprint 6: референс стиля из галереи */}
      {styleImageUrl && (
        <div className="flex items-center gap-2.5 rounded-[10px] border border-[rgba(155,89,182,0.25)] bg-[rgba(155,89,182,0.05)] p-2.5">
          <div className="relative shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={styleImageUrl}
              alt={t("styleRefTitle")}
              className="h-14 w-14 rounded-[8px] border border-[rgba(13,13,13,0.10)] object-cover"
            />
            <button
              type="button"
              onClick={() => setStyleImageUrl(null)}
              title={t("removeStyleRef")}
              className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
            >
              <X size={11} className="text-[rgba(13,13,13,0.55)]" />
            </button>
          </div>
          <div className="min-w-0">
            <p className="flex items-center gap-1 text-[15px] font-medium text-[#1A1A1A]">
              <Palette size={13} className="text-[#D97757]" />
              {t("styleRefTitle")}
            </p>
            <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.5)]">
              {t("styleRefFormHint")}
            </p>
          </div>
        </div>
      )}

      {/* Prompt input */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            editImageUrl
              ? t("placeholderEdit")
              : isMedia
                ? t("placeholderMedia")
                : t("placeholderText")
          }
          rows={4}
          className={`w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-4 py-3 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all ${isMedia && !isVideo ? "pe-20" : "pe-12"}`}
        />
        {isMedia && !isVideo && (
          <>
            <input
              ref={sourceInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => { if (e.target.files?.[0]) { handlePickImage(e.target.files[0]); e.target.value = ""; } }}
            />
            <button
              type="button"
              disabled={uploadingImage || !user}
              onClick={() => sourceInputRef.current?.click()}
              title={t("uploadImageTitle")}
              className="absolute bottom-3 right-12 flex h-8 w-8 items-center justify-center rounded-[8px] text-[rgba(13,13,13,0.4)] transition-all hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {uploadingImage ? <Loader2 size={15} className="animate-spin" /> : <ImagePlus size={15} />}
            </button>
          </>
        )}
        <button
          type="submit"
          disabled={!text.trim() || loading || uploadingImage}
          className="absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#D97757] text-white hover:bg-[#C4623E] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <Send size={15} />
        </button>
      </div>

      {error && (
        <p className="text-[15px] text-[#e74c3c]">{error}</p>
      )}
      {!user && (
        <p className="text-[15px] text-[rgba(13,13,13,0.5)]">
          {t("needAuthPrefix")}{" "}
          <a href="/login/" className="text-[#D97757] hover:underline">
            {t("needAuthLink")}
          </a>{" "}
          {t("needAuthSuffix")}
        </p>
      )}
    </form>
  );
}
