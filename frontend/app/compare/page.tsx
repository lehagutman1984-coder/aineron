"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Layers, Send, RotateCcw, Copy, Check, Code2, Search, X, ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { listNetworks, compareModels, getMessageStatus, APIError } from "@/lib/api/client";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { useAuthStore } from "@/lib/stores/auth";
import type { NetworkListItem, WebMessage, CompareItem } from "@/lib/api/types";

const detectHTML = (s: string) =>
  /<(pre|code|div|p|ul|ol|h[1-6]|blockquote|table|img|br)\b/i.test(s);

// ── Page root ─────────────────────────────────────────────────────────────────
export default function ComparePage() {
  const { setStars } = useAuthStore();
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [compareItems, setCompareItems] = useState<CompareItem[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: networks = [], isLoading: networksLoading } = useQuery({
    queryKey: ["networks"],
    queryFn: () => listNetworks(),
    staleTime: 5 * 60 * 1000,
  });

  const filtered = networks.filter((n) =>
    n.name.toLowerCase().includes(search.toLowerCase())
  );

  const toggleModel = (slug: string) => {
    setSelected((prev) =>
      prev.includes(slug)
        ? prev.filter((s) => s !== slug)
        : prev.length < 3
        ? [...prev, slug]
        : prev
    );
  };

  const totalCost = selected.reduce((sum, slug) => {
    const n = networks.find((n) => n.slug === slug);
    return sum + (n?.cost_per_message ?? 0);
  }, 0);

  const handleSubmit = async () => {
    if (!prompt.trim() || selected.length < 2 || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await compareModels({ message: prompt.trim(), network_slugs: selected });
      setStars(res.new_balance);
      setCompareItems(res.items);
    } catch (err) {
      setError(err instanceof APIError ? err.message : "Ошибка соединения. Попробуйте ещё раз.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (compareItems) {
    return (
      <ResultsView
        prompt={prompt}
        items={compareItems}
        onReset={() => { setCompareItems(null); setError(null); }}
      />
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-3 flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
            <Layers size={24} />
          </div>
        </div>
        <h1 className="text-[24px] font-bold text-[#0d0d0d] dark:text-[#ececec]">
          Сравнение моделей
        </h1>
        <p className="mt-1.5 text-[14px] text-[rgba(13,13,13,0.48)] dark:text-[rgba(236,236,236,0.42)]">
          Один запрос — несколько ответов. Выберите 2–3 нейросети и сравните результат.
        </p>
      </div>

      {/* Prompt */}
      <div
        className="mb-5 overflow-hidden rounded-[14px]"
        style={{
          border: "1px solid rgba(13,13,13,0.12)",
          boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
        }}
      >
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
          }}
          placeholder="Введите запрос для сравнения..."
          rows={4}
          className="block w-full resize-none bg-white px-4 py-3.5 text-[14px] leading-relaxed text-[#0d0d0d] outline-none dark:bg-[#18181b] dark:text-[#ececec] dark:placeholder:text-[rgba(236,236,236,0.30)]"
        />
      </div>

      {/* Model picker */}
      <div
        className="mb-5 overflow-hidden rounded-[14px]"
        style={{ border: "1px solid rgba(13,13,13,0.10)" }}
      >
        {/* Picker header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: "1px solid rgba(13,13,13,0.08)", background: "rgba(13,13,13,0.02)" }}
        >
          <span className="text-[13px] font-medium text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.55)]">
            Выберите модели{" "}
            <span className="text-[#0a7cff]">{selected.length}/3</span>
          </span>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск..."
              className="h-7 rounded-[7px] border border-[rgba(13,13,13,0.12)] bg-white pl-7 pr-3 text-[12px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] dark:border-[rgba(255,255,255,0.12)] dark:bg-[#1c1c1f] dark:text-[#ececec]"
            />
          </div>
        </div>

        {/* Model grid */}
        <div className="max-h-[280px] overflow-y-auto p-3">
          {networksLoading ? (
            <div className="flex justify-center py-8">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="h-2 w-2 animate-bounce rounded-full bg-[rgba(13,13,13,0.25)]"
                    style={{ animationDelay: `${i * 0.18}s` }}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {filtered.map((network) => {
                const isSelected = selected.includes(network.slug);
                const isDisabled = !isSelected && selected.length >= 3;
                return (
                  <button
                    key={network.slug}
                    onClick={() => !isDisabled && toggleModel(network.slug)}
                    className={[
                      "flex items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-left transition-all",
                      isSelected
                        ? "border-[#0a7cff] bg-[rgba(10,124,255,0.06)]"
                        : "border-[rgba(13,13,13,0.10)] bg-white hover:border-[rgba(13,13,13,0.22)] dark:border-[rgba(255,255,255,0.08)] dark:bg-[#1c1c1f] dark:hover:border-[rgba(255,255,255,0.18)]",
                      isDisabled ? "cursor-not-allowed opacity-35" : "cursor-pointer",
                    ].join(" ")}
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-[6px]">
                      {network.avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={network.avatar} alt="" width={28} height={28} className="object-cover" />
                      ) : (
                        <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
                          <Code2 size={13} />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-[#0d0d0d] dark:text-[#ececec]">
                        {network.name}
                      </p>
                      <p className="text-[11px] text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.35)]">
                        {network.cost_per_message} зв.
                      </p>
                    </div>
                    {isSelected && (
                      <Check size={14} className="shrink-0 text-[#0a7cff]" />
                    )}
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="col-span-3 py-6 text-center text-[13px] text-[rgba(13,13,13,0.4)]">
                  Модели не найдены
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {selected.map((slug) => {
            const n = networks.find((n) => n.slug === slug);
            return (
              <span
                key={slug}
                className="flex items-center gap-1.5 rounded-full border border-[#0a7cff] bg-[rgba(10,124,255,0.08)] px-3 py-1 text-[12px] font-medium text-[#0a7cff]"
              >
                {n?.name ?? slug}
                <button onClick={() => toggleModel(slug)}>
                  <X size={11} />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="mb-3 text-[13px] text-[#e74c3c]">{error}</p>
      )}

      {/* Submit row */}
      <div className="flex items-center justify-between">
        <p className="text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)]">
          {selected.length < 2
            ? "Выберите минимум 2 модели"
            : `Стоимость: ${totalCost} зв.`}
        </p>
        <button
          onClick={handleSubmit}
          disabled={!prompt.trim() || selected.length < 2 || isSubmitting}
          className="flex items-center gap-2 rounded-[10px] px-5 py-2.5 text-[14px] font-medium text-white transition-all disabled:cursor-not-allowed disabled:opacity-35"
          style={{ background: "#0d0d0d" }}
        >
          {isSubmitting ? (
            <span className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="h-1.5 w-1.5 animate-bounce rounded-full bg-white"
                  style={{ animationDelay: `${i * 0.18}s` }}
                />
              ))}
            </span>
          ) : (
            <>
              <Send size={14} />
              Сравнить
            </>
          )}
        </button>
      </div>
    </div>
  );
}

// ── Results view ───────────────────────────────────────────────────────────────
function ResultsView({
  prompt,
  items,
  onReset,
}: {
  prompt: string;
  items: CompareItem[];
  onReset: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div
        className="shrink-0 px-4 py-3"
        style={{ borderBottom: "1px solid rgba(13,13,13,0.08)" }}
      >
        <div className="mx-auto flex max-w-7xl items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
              Запрос
            </p>
            <p className="mt-0.5 line-clamp-2 text-[13px] text-[#0d0d0d] dark:text-[#ececec]">
              {prompt}
            </p>
          </div>
          <button
            onClick={onReset}
            className="flex shrink-0 items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.55)]"
          >
            <RotateCcw size={12} />
            Новое сравнение
          </button>
        </div>
      </div>

      {/* Columns */}
      <div className="flex-1 overflow-y-auto">
        <div
          className="grid h-full divide-x divide-[rgba(13,13,13,0.08)] dark:divide-[rgba(255,255,255,0.06)]"
          style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
        >
          {items.map((item) => (
            <CompareColumn key={item.network_slug} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Single compare column with polling ────────────────────────────────────────
function CompareColumn({ item }: { item: CompareItem }) {
  const [message, setMessage] = useState<WebMessage | null>(null);
  const [done, setDone] = useState(false);
  const [copied, setCopied] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    try {
      const msg = await getMessageStatus(item.assistant_message_id);
      setMessage(msg);
      if (msg.status !== "pending") {
        setDone(true);
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } catch {
      setDone(true);
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  }, [item.assistant_message_id]);

  useEffect(() => {
    poll();
    intervalRef.current = setInterval(poll, 800);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [poll]);

  const handleCopy = () => {
    if (!message) return;
    const text = message.plain_text || message.content.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col">
      {/* Column header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid rgba(13,13,13,0.08)", background: "rgba(13,13,13,0.02)" }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <ModelAvatar avatar={item.network_avatar} name={item.network_name} size={22} />
          <span className="truncate text-[13px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
            {item.network_name}
          </span>
        </div>
        <span className="ml-2 shrink-0 rounded-full bg-[rgba(13,13,13,0.06)] px-2 py-0.5 text-[11px] text-[rgba(13,13,13,0.48)] dark:bg-[rgba(255,255,255,0.06)] dark:text-[rgba(236,236,236,0.40)]">
          {item.cost} зв.
        </span>
      </div>

      {/* Response area */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {!message || message.status === "pending" ? (
          <div className="flex items-center gap-1.5 py-2">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-2 w-2 animate-bounce rounded-full bg-[rgba(13,13,13,0.25)] dark:bg-[rgba(236,236,236,0.25)]"
                style={{ animationDelay: `${i * 0.18}s` }}
              />
            ))}
          </div>
        ) : message.status === "failed" ? (
          <p className="text-[13px] text-[#e74c3c]">
            {message.error_message ?? "Ошибка генерации. Попробуйте ещё раз."}
          </p>
        ) : (
          <MessageContent message={message} />
        )}
      </div>

      {/* Footer actions */}
      {done && message?.status === "completed" && (
        <div
          className="flex items-center gap-2 px-4 py-2"
          style={{ borderTop: "1px solid rgba(13,13,13,0.07)" }}
        >
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1.5 text-[12px] text-[rgba(13,13,13,0.50)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.45)] dark:hover:text-[#ececec]"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Скопировано" : "Копировать"}
          </button>
          <Link
            href={`/chat/${item.chat_id}/`}
            className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1.5 text-[12px] text-[rgba(13,13,13,0.50)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.45)] dark:hover:text-[#ececec]"
          >
            <ExternalLink size={12} />
            Открыть чат
          </Link>
        </div>
      )}
    </div>
  );
}

// ── Message content renderer ───────────────────────────────────────────────────
function MessageContent({ message }: { message: WebMessage }) {
  const { content, plain_text } = message;

  if (plain_text && !detectHTML(plain_text)) {
    return <MarkdownContent content={plain_text} />;
  }

  const htmlSource = detectHTML(content) ? content : (plain_text ?? content);
  if (detectHTML(htmlSource)) {
    return (
      <div
        className="chat-prose"
        dangerouslySetInnerHTML={{ __html: htmlSource }}
      />
    );
  }

  return (
    <p className="whitespace-pre-wrap text-[14px] leading-[1.75] text-[rgba(13,13,13,0.86)] dark:text-[rgba(236,236,236,0.82)]">
      {content}
    </p>
  );
}

// ── Model avatar helper ────────────────────────────────────────────────────────
function ModelAvatar({ avatar, name, size }: { avatar: string | null; name: string; size: number }) {
  if (avatar) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={avatar} alt={name} width={size} height={size} className="rounded-[5px] object-cover" />
    );
  }
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]"
      style={{ width: size, height: size }}
    >
      <Code2 size={Math.round(size * 0.55)} />
    </div>
  );
}
