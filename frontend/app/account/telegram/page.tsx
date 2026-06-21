"use client";

import { useState, useEffect, useCallback } from "react";
import { MessageCircle, Link, Unlink, RefreshCw, CheckCircle, Copy } from "lucide-react";
import { request as apiRequest } from "@/lib/api/client";

interface TelegramStatus {
  linked: boolean;
  telegram_id?: number;
  telegram_username?: string;
  telegram_first_name?: string;
  linked_at?: string;
}

interface LinkTokenResponse {
  link: string;
  expires_in: number;
  token: string;
}

export default function TelegramPage() {
  const [status, setStatus] = useState<TelegramStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [linkData, setLinkData] = useState<LinkTokenResponse | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const data = await apiRequest<TelegramStatus>("/telegram/link-token/");
      setStatus(data);
    } catch {
      setStatus({ linked: false });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Обратный отсчёт таймера
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  // Поллинг статуса пока ссылка открыта
  useEffect(() => {
    if (!linkData || countdown <= 0) return;
    const interval = setInterval(async () => {
      const data = await apiRequest<TelegramStatus>("/telegram/link-token/").catch(() => null);
      if (data?.linked) {
        setStatus(data);
        setLinkData(null);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [linkData, countdown]);

  const generateLink = async () => {
    setGenerating(true);
    try {
      const data = await apiRequest<LinkTokenResponse>("/telegram/link-token/", {
        method: "POST",
      });
      setLinkData(data);
      setCountdown(data.expires_in);
    } catch (e) {
      alert("Ошибка генерации ссылки");
    } finally {
      setGenerating(false);
    }
  };

  const unlink = async () => {
    if (!confirm("Отвязать Telegram от аккаунта?")) return;
    setUnlinking(true);
    try {
      await apiRequest("/telegram/link-token/", { method: "DELETE" });
      setStatus({ linked: false });
      setLinkData(null);
    } catch {
      alert("Ошибка отвязки");
    } finally {
      setUnlinking(false);
    }
  };

  const copyLink = () => {
    if (!linkData) return;
    navigator.clipboard.writeText(linkData.link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return (
      <div className="py-8 px-6">
        <div className="h-32 animate-pulse rounded-2xl bg-[rgba(13,13,13,0.06)]" />
      </div>
    );
  }

  return (
    <div className="py-8 px-0 md:px-6">
      <div className="mb-6">
        <h1 className="text-[22px] font-semibold text-[#0d0d0d]">Telegram</h1>
        <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.5)]">
          Привяжи Telegram-аккаунт, чтобы пользоваться AI прямо в мессенджере
        </p>
      </div>

      {status?.linked ? (
        /* Привязан */
        <div className="rounded-2xl border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[rgba(10,124,255,0.1)]">
              <CheckCircle size={24} className="text-[#0a7cff]" />
            </div>
            <div className="flex-1">
              <p className="text-[15px] font-semibold text-[#0d0d0d]">Telegram привязан</p>
              {status.telegram_first_name && (
                <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.55)]">
                  {status.telegram_first_name}
                  {status.telegram_username ? ` (@${status.telegram_username})` : ""}
                </p>
              )}
              {status.linked_at && (
                <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.38)]">
                  Привязан {new Date(status.linked_at).toLocaleDateString("ru-RU")}
                </p>
              )}
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <a
              href="https://t.me/aineron_bot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-[10px] bg-[#0a7cff] px-4 py-2.5 text-[13px] font-medium text-white hover:opacity-90 transition-opacity"
            >
              <MessageCircle size={15} />
              Открыть бота
            </a>
            <button
              onClick={unlink}
              disabled={unlinking}
              className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.12)] px-4 py-2.5 text-[13px] text-[rgba(13,13,13,0.6)] hover:text-[rgba(13,13,13,0.9)] transition-colors disabled:opacity-50"
            >
              <Unlink size={15} />
              {unlinking ? "Отвязываю..." : "Отвязать"}
            </button>
          </div>
        </div>
      ) : linkData && countdown > 0 ? (
        /* Ожидаем привязку */
        <div className="rounded-2xl border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <p className="text-[15px] font-semibold text-[#0d0d0d] mb-1">Подключение...</p>
          <p className="text-[13px] text-[rgba(13,13,13,0.55)] mb-5">
            Ссылка действительна {formatTime(countdown)}. Перейди по ней и нажми Start.
          </p>

          <div className="flex items-center gap-2 rounded-[10px] bg-[rgba(13,13,13,0.04)] px-4 py-3 mb-4">
            <code className="flex-1 truncate text-[12px] text-[rgba(13,13,13,0.7)]">
              {linkData.link}
            </code>
            <button
              onClick={copyLink}
              className="shrink-0 p-1 text-[rgba(13,13,13,0.4)] hover:text-[rgba(13,13,13,0.8)] transition-colors"
            >
              {copied ? <CheckCircle size={15} className="text-green-500" /> : <Copy size={15} />}
            </button>
          </div>

          <div className="flex flex-wrap gap-3">
            <a
              href={linkData.link}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-[10px] bg-[#0a7cff] px-4 py-2.5 text-[13px] font-medium text-white hover:opacity-90 transition-opacity"
            >
              <MessageCircle size={15} />
              Открыть Telegram
            </a>
            <button
              onClick={generateLink}
              disabled={generating}
              className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.12)] px-4 py-2.5 text-[13px] text-[rgba(13,13,13,0.6)] hover:text-[rgba(13,13,13,0.9)] transition-colors"
            >
              <RefreshCw size={15} />
              Новая ссылка
            </button>
          </div>

          <p className="mt-4 text-[12px] text-[rgba(13,13,13,0.38)]">
            Страница автоматически обновится после привязки
          </p>
        </div>
      ) : (
        /* Не привязан */
        <div className="rounded-2xl border border-[rgba(13,13,13,0.10)] bg-white p-6">
          <div className="flex items-start gap-4 mb-6">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[rgba(13,13,13,0.06)]">
              <MessageCircle size={24} className="text-[rgba(13,13,13,0.4)]" />
            </div>
            <div>
              <p className="text-[15px] font-semibold text-[#0d0d0d]">Telegram не привязан</p>
              <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.55)]">
                Привяжи аккаунт, чтобы использовать все AI-модели прямо в Telegram
              </p>
            </div>
          </div>

          <ul className="mb-6 space-y-2">
            {[
              "Текстовый чат с любой моделью",
              "Генерация изображений командой /image",
              "Голосовые сообщения и TTS",
              "Оплата через Telegram Stars",
              "Уведомления о балансе и подписке",
            ].map((f) => (
              <li key={f} className="flex items-center gap-2 text-[13px] text-[rgba(13,13,13,0.65)]">
                <CheckCircle size={14} className="shrink-0 text-[#0a7cff]" />
                {f}
              </li>
            ))}
          </ul>

          <button
            onClick={generateLink}
            disabled={generating}
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#0a7cff] px-5 py-2.5 text-[13px] font-medium text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            <Link size={15} />
            {generating ? "Генерирую ссылку..." : "Подключить Telegram"}
          </button>
        </div>
      )}
    </div>
  );
}
