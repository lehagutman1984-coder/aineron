"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Send, Settings2, ChevronDown, ImagePlus, X, Palette } from "lucide-react";
import { createChat } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import { APIError } from "@/lib/api/client";
import { MediaSettingsPanel } from "@/components/chat/MediaSettingsPanel";
import type { ModelConfigJson } from "@/lib/api/types";

interface Props {
  networkSlug: string;
  isMedia: boolean;
  configJson?: ModelConfigJson | null;
  projectId?: number;
}

export function ChatStartForm({ networkSlug, isMedia, configJson, projectId }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, setStars } = useAuthStore();
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

  // img2img: подхватываем изображение из localStorage (только для медиа-моделей)
  useEffect(() => {
    if (!isMedia) return;
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
  }, [isMedia]);

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
      setStars(res.new_balance);
      qc.invalidateQueries({ queryKey: ["chats"] });
      router.push(`/chat/${res.chat_id}/`);
    } catch (err) {
      if (err instanceof APIError) {
        setError(err.message);
      } else {
        setError("Что-то пошло не так. Попробуйте ещё раз.");
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
            Настройки генерации
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

      {/* img2img: исходное изображение из галереи */}
      {editImageUrl && (
        <div className="flex items-center gap-2.5 rounded-[10px] border border-[rgba(217,119,87,0.20)] bg-[rgba(217,119,87,0.04)] p-2.5">
          <div className="relative shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={editImageUrl}
              alt="Исходное изображение"
              className="h-14 w-14 rounded-[8px] border border-[rgba(13,13,13,0.10)] object-cover"
            />
            <button
              type="button"
              onClick={() => setEditImageUrl(null)}
              title="Убрать исходное изображение"
              className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
            >
              <X size={11} className="text-[rgba(13,13,13,0.55)]" />
            </button>
          </div>
          <div className="min-w-0">
            <p className="flex items-center gap-1 text-[15px] font-medium text-[#1A1A1A]">
              <ImagePlus size={13} className="text-[#D97757]" />
              Редактирование изображения
            </p>
            <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.5)]">
              Опишите изменения — модель применит их к этому изображению
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
              alt="Референс стиля"
              className="h-14 w-14 rounded-[8px] border border-[rgba(13,13,13,0.10)] object-cover"
            />
            <button
              type="button"
              onClick={() => setStyleImageUrl(null)}
              title="Убрать референс стиля"
              className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full border border-[rgba(13,13,13,0.10)] bg-white shadow-sm transition-colors hover:bg-[rgba(13,13,13,0.06)]"
            >
              <X size={11} className="text-[rgba(13,13,13,0.55)]" />
            </button>
          </div>
          <div className="min-w-0">
            <p className="flex items-center gap-1 text-[15px] font-medium text-[#1A1A1A]">
              <Palette size={13} className="text-[#D97757]" />
              Референс стиля
            </p>
            <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.5)]">
              Новые изображения переймут стиль этого референса
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
              ? "Опишите, что изменить на изображении..."
              : isMedia
                ? "Опишите, что нужно сгенерировать..."
                : "Введите сообщение... (Enter — отправить, Shift+Enter — новая строка)"
          }
          rows={4}
          className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-4 py-3 pr-12 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
        <button
          type="submit"
          disabled={!text.trim() || loading}
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
          Нужна{" "}
          <a href="/login/" className="text-[#D97757] hover:underline">
            авторизация
          </a>{" "}
          для отправки сообщения
        </p>
      )}
    </form>
  );
}
