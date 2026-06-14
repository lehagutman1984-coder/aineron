"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { createChat } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import { APIError } from "@/lib/api/client";

interface Props {
  networkSlug: string;
  isMedia: boolean;
}

export function ChatStartForm({ networkSlug, isMedia }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const { user, setStars } = useAuthStore();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
      const res = await createChat({ network_slug: networkSlug, message: text.trim() });
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
    <form onSubmit={handleSubmit}>
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isMedia
              ? "Опишите изображение подробно..."
              : "Введите сообщение... (Enter — отправить, Shift+Enter — новая строка)"
          }
          rows={4}
          className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.02)] px-4 py-3 pr-12 text-[14px] text-[#0d0d0d] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
        />
        <button
          type="submit"
          disabled={!text.trim() || loading}
          className="absolute bottom-3 right-3 flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#0a7cff] text-white hover:bg-[#0066cc] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <Send size={15} />
        </button>
      </div>
      {error && (
        <p className="mt-2 text-[13px] text-[#e74c3c]">{error}</p>
      )}
      {!user && (
        <p className="mt-2 text-[13px] text-[rgba(13,13,13,0.5)]">
          Нужна{" "}
          <a href="/login/" className="text-[#0a7cff] hover:underline">
            авторизация
          </a>{" "}
          для отправки сообщения
        </p>
      )}
    </form>
  );
}
