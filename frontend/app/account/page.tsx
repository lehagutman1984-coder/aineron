"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Wallet,
  Code2,
  User,
  Copy,
  MessageSquare,
  ExternalLink,
  Key,
  Brain,
  Folder,
  Images,
} from "lucide-react";
import { getMe, listChats } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import { formatMoney } from "@/lib/money";
import type { ChatListItem } from "@/lib/api/types";

export default function AccountPage() {
  const { user, isLoading, setUser } = useAuthStore();

  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    retry: 0,
  });

  const { data: chats } = useQuery<ChatListItem[]>({
    queryKey: ["chats"],
    queryFn: () => listChats(),
    enabled: !!user,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (me) setUser(me);
  }, [me, setUser]);


  const profile = me ?? user;
  if (!profile) {
    return (
      <div className="flex h-[calc(100vh-56px)] items-center justify-center text-[16px] text-[rgba(13,13,13,0.45)]">
        Загрузка...
      </div>
    );
  }

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      <h1 className="mb-8 text-[24px] font-bold text-[#1A1A1A]">Личный кабинет</h1>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {/* Balance card */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <Wallet size={14} className="text-[#D97757]" />
            Баланс
          </div>
          <p className="mb-4 text-[36px] font-bold text-[#1A1A1A]">{formatMoney(profile.balance_kopecks)}</p>
          <Link
            href="/account/billing/"
            className="inline-flex h-9 items-center gap-2 rounded-[8px] bg-[#D97757] px-4 text-[15px] font-medium text-white hover:bg-[#C4623E] transition-colors"
          >
            Пополнить
          </Link>
        </div>

        {/* Profile card */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <User size={14} />
            Профиль
          </div>
          <p className="mb-1 truncate text-[17px] font-medium text-[#1A1A1A]">{profile.email}</p>
          <p className="mb-4 text-[15px] text-[rgba(13,13,13,0.5)]">
            {"tariff_name" in profile ? profile.tariff_name : "Бесплатный тариф"}
          </p>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/account/billing/"
              className="inline-flex h-9 items-center rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
            >
              Тарифы и платежи
            </Link>
          </div>
        </div>

        {/* Referral card */}
        {"referral_code" in profile && (
          <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
            <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
              <ExternalLink size={14} />
              Реферальная программа
            </div>
            <p className="mb-2 text-[15px] text-[rgba(13,13,13,0.6)]">Ваша реферальная ссылка:</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-[6px] bg-[rgba(13,13,13,0.05)] px-3 py-2 text-[14px] text-[#1A1A1A]">
                {typeof window !== "undefined"
                  ? `${window.location.origin}/?ref=${profile.referral_code}`
                  : `https://aineron.ru/?ref=${profile.referral_code}`}
              </code>
              <button
                onClick={() =>
                  handleCopy(
                    typeof window !== "undefined"
                      ? `${window.location.origin}/?ref=${profile.referral_code}`
                      : `https://aineron.ru/?ref=${profile.referral_code}`
                  )
                }
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.5)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A] transition-all"
              >
                <Copy size={13} />
              </button>
            </div>
          </div>
        )}

        {/* Memory card */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <Brain size={14} className="text-[#D97757]" />
            Память
          </div>
          <p className="mb-4 text-[15px] text-[rgba(13,13,13,0.6)]">
            Факты о вас и история сессий.
          </p>
          <Link
            href="/account/memory/"
            className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            <Brain size={13} />
            Открыть память
          </Link>
        </div>

        {/* Projects card */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <Folder size={14} className="text-[#D97757]" />
            Проекты
          </div>
          <p className="mb-4 text-[15px] text-[rgba(13,13,13,0.6)]">
            Организуйте чаты по папкам с общим контекстом.
          </p>
          <Link
            href="/projects/"
            className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            <Folder size={13} />
            Открыть проекты
          </Link>
        </div>

        {/* Gallery card */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <Images size={14} className="text-[#D97757]" />
            Галерея
          </div>
          <p className="mb-4 text-[15px] text-[rgba(13,13,13,0.6)]">
            Витрина работ сообщества — изображения и видео.
          </p>
          <Link
            href="/gallery/"
            className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            <Images size={13} />
            Открыть галерею
          </Link>
        </div>

        {/* API keys shortcut */}
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="mb-4 flex items-center gap-2 text-[15px] font-medium text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
            <Key size={14} />
            Для разработчиков
          </div>
          <p className="mb-4 text-[15px] text-[rgba(13,13,13,0.6)]">
            OpenAI-совместимый API. Подключите к Cursor, VS Code, Continue.
          </p>
          <div className="flex gap-2">
            <Link
              href="/account/keys/"
              className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
            >
              <Key size={13} />
              API-ключи
            </Link>
            <Link
              href="/api-docs/"
              className="inline-flex h-9 items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
            >
              <ExternalLink size={13} />
              Документация
            </Link>
          </div>
        </div>
      </div>

      {/* Recent chats */}
      {chats && chats.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-4 text-[18px] font-semibold text-[#1A1A1A]">Последние чаты</h2>
          <div className="flex flex-col gap-2">
            {chats.slice(0, 10).map((chat) => (
              <Link
                key={chat.id}
                href={`/chat/${chat.id}/`}
                className="flex items-center gap-3 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3 hover:border-[rgba(217,119,87,0.4)] hover:bg-[rgba(217,119,87,0.02)] transition-all"
              >
                {chat.network.avatar ? (
                  <img src={chat.network.avatar} alt={chat.network.name} width={28} height={28} className="rounded-[6px]" />
                ) : (
                  <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
                    <MessageSquare size={13} />
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-[#1A1A1A]">{chat.title}</p>
                  {chat.last_message && (
                    <p className="truncate text-[14px] text-[rgba(13,13,13,0.5)]">
                      {chat.last_message.preview}
                    </p>
                  )}
                </div>
                <p className="shrink-0 text-[13px] text-[rgba(13,13,13,0.35)]">
                  {new Date(chat.updated_at).toLocaleDateString("ru-RU")}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
