"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Layers, Send, RotateCcw, Copy, Check, Code2, Search, X, ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { listNetworks, compareModels, compareImages, getMessageStatus, voteArena, APIError } from "@/lib/api/client";
import { MarkdownContent } from "@/components/chat/MarkdownContent";
import { useAuthStore } from "@/lib/stores/auth";
import type { NetworkListItem, WebMessage, CompareItem } from "@/lib/api/types";
import { Trophy, Image as ImageIcon, MessageSquareText } from "lucide-react";

type CompareMode = "text" | "image";

const detectHTML = (s: string) =>
  /<(pre|code|div|p|ul|ol|h[1-6]|blockquote|table|img|br)\b/i.test(s);

// ── Page root ─────────────────────────────────────────────────────────────────
export default function ComparePage() {
  const { setStars } = useAuthStore();
  const [mode, setMode] = useState<CompareMode>("text");
  const [prompt, setPrompt] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [compareItems, setCompareItems] = useState<CompareItem[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isImage = mode === "image";
  const maxSelect = isImage ? 4 : 3;

  const { data: networks = [], isLoading: networksLoading } = useQuery({
    queryKey: ["networks"],
    queryFn: () => listNetworks(),
    staleTime: 5 * 60 * 1000,
  });

  const isImageModel = (n: NetworkListItem) =>
    n.provider === "fal-ai" && !n.handle_video && n.output_type !== "video";

  const filtered = networks.filter((n) => {
    if (!n.name.toLowerCase().includes(search.toLowerCase())) return false;
    return isImage ? isImageModel(n) : n.provider !== "fal-ai";
  });

  const switchMode = (next: CompareMode) => {
    if (next === mode) return;
    setMode(next);
    setSelected([]);
    setSearch("");
    setError(null);
  };

  const toggleModel = (slug: string) => {
    setSelected((prev) =>
      prev.includes(slug)
        ? prev.filter((s) => s !== slug)
        : prev.length < maxSelect
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
      if (isImage) {
        const res = await compareImages({ prompt: prompt.trim(), models: selected });
        setStars(res.new_balance);
        setCompareItems(res.items);
      } else {
        const res = await compareModels({ message: prompt.trim(), network_slugs: selected });
        setStars(res.new_balance);
        setCompareItems(res.items);
      }
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
        isImage={isImage}
        onReset={() => { setCompareItems(null); setError(null); }}
      />
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 text-center">
        <div className="mb-3 flex justify-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-[14px] bg-[rgba(10,124,255,0.10)] text-[#D97757]">
            <Layers size={24} />
          </div>
        </div>
        <h1 className="text-[24px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
          Сравнение моделей
        </h1>
        <p className="mt-1.5 text-[14px] text-[rgba(13,13,13,0.48)] dark:text-[rgba(236,236,236,0.42)]">
          {isImage
            ? "Один промпт — несколько изображений. Выберите 2–4 модели и сравните результат."
            : "Один запрос — несколько ответов. Выберите 2–3 нейросети и сравните результат."}
        </p>
      </div>

      {/* Mode tabs */}
      <div className="mb-5 flex justify-center">
        <div
          className="inline-flex rounded-[12px] p-1"
          style={{ background: "rgba(13,13,13,0.05)" }}
        >
          {([
            { key: "text" as const, label: "Текст", icon: MessageSquareText },
            { key: "image" as const, label: "Изображения", icon: ImageIcon },
          ]).map((tab) => {
            const active = mode === tab.key;
            const Icon = tab.icon;
            return (
              <button
                key={tab.key}
                onClick={() => switchMode(tab.key)}
                className={[
                  "flex items-center gap-1.5 rounded-[9px] px-4 py-1.5 text-[13px] font-medium transition-all",
                  active
                    ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[#2a2a2e] dark:text-[#EDE8E3]"
                    : "text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)]",
                ].join(" ")}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>
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
          placeholder={isImage ? "Опишите изображение для генерации..." : "Введите запрос для сравнения..."}
          rows={4}
          className="block w-full resize-none bg-white px-4 py-3.5 text-[14px] leading-relaxed text-[#1A1A1A] outline-none dark:bg-[#1C1917] dark:text-[#EDE8E3] dark:placeholder:text-[rgba(236,236,236,0.30)]"
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
            <span className="text-[#D97757]">{selected.length}/{maxSelect}</span>
          </span>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск..."
              className="h-7 rounded-[7px] border border-[rgba(13,13,13,0.12)] bg-white pl-7 pr-3 text-[12px] text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:bg-[#1c1c1f] dark:text-[#EDE8E3]"
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
                const isDisabled = !isSelected && selected.length >= maxSelect;
                return (
                  <button
                    key={network.slug}
                    onClick={() => !isDisabled && toggleModel(network.slug)}
                    className={[
                      "flex items-center gap-2.5 rounded-[10px] border px-3 py-2.5 text-left transition-all",
                      isSelected
                        ? "border-[#D97757] bg-[rgba(10,124,255,0.06)]"
                        : "border-[rgba(13,13,13,0.10)] bg-white hover:border-[rgba(13,13,13,0.22)] dark:border-[rgba(255,255,255,0.08)] dark:bg-[#1c1c1f] dark:hover:border-[rgba(255,255,255,0.18)]",
                      isDisabled ? "cursor-not-allowed opacity-35" : "cursor-pointer",
                    ].join(" ")}
                  >
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-[6px]">
                      {network.avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={network.avatar} alt="" width={28} height={28} className="object-cover" />
                      ) : (
                        <div className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-[rgba(10,124,255,0.10)] text-[#D97757]">
                          <Code2 size={13} />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">
                        {network.name}
                      </p>
                      <p className="text-[11px] text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.35)]">
                        {network.cost_per_message} зв.
                      </p>
                    </div>
                    {isSelected && (
                      <Check size={14} className="shrink-0 text-[#D97757]" />
                    )}
                  </button>
                );
              })}
              {filtered.length === 0 && (
                <p className="col-span-3 py-6 text-center text-[13px] text-[rgba(13,13,13,0.4)]">
                  {isImage ? "Image-модели не найдены" : "Модели не найдены"}
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
                className="flex items-center gap-1.5 rounded-full border border-[#D97757] bg-[rgba(10,124,255,0.08)] px-3 py-1 text-[12px] font-medium text-[#D97757]"
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
            : isImage
            ? `~${totalCost} зв. (списывается за каждое изображение)`
            : `Стоимость: ${totalCost} зв.`}
        </p>
        <button
          onClick={handleSubmit}
          disabled={!prompt.trim() || selected.length < 2 || isSubmitting}
          className="flex items-center gap-2 rounded-[10px] px-5 py-2.5 text-[14px] font-medium text-white transition-all disabled:cursor-not-allowed disabled:opacity-35"
          style={{ background: "#1A1A1A" }}
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
  isImage,
  onReset,
}: {
  prompt: string;
  items: CompareItem[];
  isImage?: boolean;
  onReset: () => void;
}) {
  const [doneCount, setDoneCount] = useState(0);
  const [voted, setVoted] = useState<string | null>(null); // winner slug
  const [voteError, setVoteError] = useState<string | null>(null);

  const allDone = doneCount >= items.length;

  const handleVote = async (winnerSlug: string) => {
    if (voted) return;
    const loserSlugs = items.map((i) => i.network_slug).filter((s) => s !== winnerSlug);
    const chatIds = items.map((i) => i.chat_id);
    // Голосуем последовательно: анти-абьюз арены (compare_chat_ids overlap) допускает
    // лишь один матч на сессию сравнения, поэтому параллельные запросы при 3-4 моделях
    // вернули бы 400. Достаточно одного успешного матча, остальные 400 игнорируем.
    let anySuccess = false;
    let lastError: unknown = null;
    for (const loserSlug of loserSlugs) {
      try {
        await voteArena({ winner_slug: winnerSlug, loser_slug: loserSlug, compare_chat_ids: chatIds });
        anySuccess = true;
      } catch (err) {
        lastError = err;
      }
    }
    if (anySuccess) {
      setVoted(winnerSlug);
    } else {
      setVoteError(lastError instanceof APIError ? lastError.message : "Ошибка голосования");
    }
  };

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
            <p className="mt-0.5 line-clamp-2 text-[13px] text-[#1A1A1A] dark:text-[#EDE8E3]">
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

        {/* Arena vote row */}
        {allDone && !voted && (
          <div className="mx-auto mt-3 max-w-7xl">
            <p className="mb-2 flex items-center gap-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
              <Trophy size={12} className="text-[#f4a017]" />
              {isImage ? "Какое изображение лучше?" : "Какой ответ лучший?"} Ваш голос влияет на Elo-рейтинг арены.
            </p>
            <div className="flex flex-wrap gap-2">
              {items.map((item) => (
                <button
                  key={item.network_slug}
                  onClick={() => handleVote(item.network_slug)}
                  className="flex items-center gap-1.5 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.65)] transition-all hover:border-[#f4a017] hover:bg-[rgba(244,160,23,0.07)] hover:text-[#c68a00] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.55)]"
                >
                  <Trophy size={11} />
                  {item.network_name}
                </button>
              ))}
            </div>
            {voteError && <p className="mt-1 text-[12px] text-[#e74c3c]">{voteError}</p>}
          </div>
        )}
        {voted && (
          <p className="mx-auto mt-2 max-w-7xl text-[12px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.42)]">
            Голос засчитан — рейтинг Elo обновлён.
          </p>
        )}
      </div>

      {/* Columns */}
      <div className="flex-1 overflow-y-auto">
        <div
          className="grid h-full divide-x divide-[rgba(13,13,13,0.08)] dark:divide-[rgba(255,255,255,0.06)]"
          style={{ gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))` }}
        >
          {items.map((item) => (
            <CompareColumn
              key={item.network_slug}
              item={item}
              onDone={() => setDoneCount((c) => c + 1)}
              isWinner={voted === item.network_slug}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Single compare column with polling ────────────────────────────────────────
function CompareColumn({
  item,
  onDone,
  isWinner,
}: {
  item: CompareItem;
  onDone?: () => void;
  isWinner?: boolean;
}) {
  const [message, setMessage] = useState<WebMessage | null>(null);
  const [done, setDone] = useState(false);
  const [copied, setCopied] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneReported = useRef(false);

  const poll = useCallback(async () => {
    try {
      const msg = await getMessageStatus(item.assistant_message_id);
      setMessage(msg);
      if (msg.status !== "pending") {
        setDone(true);
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (!doneReported.current) {
          doneReported.current = true;
          onDone?.();
        }
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
    <div className={["flex flex-col", isWinner ? "ring-2 ring-inset ring-[#f4a017]" : ""].join(" ")}>
      {/* Column header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{
          borderBottom: "1px solid rgba(13,13,13,0.08)",
          background: isWinner ? "rgba(244,160,23,0.07)" : "rgba(13,13,13,0.02)",
        }}
      >
        <div className="flex min-w-0 items-center gap-2">
          <ModelAvatar avatar={item.network_avatar} name={item.network_name} size={22} />
          <span className="truncate text-[13px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            {item.network_name}
          </span>
          {isWinner && <Trophy size={13} className="shrink-0 text-[#f4a017]" />}
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
            className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1.5 text-[12px] text-[rgba(13,13,13,0.50)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)] dark:hover:text-[#EDE8E3]"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Скопировано" : "Копировать"}
          </button>
          <Link
            href={`/chat/${item.chat_id}/`}
            className="flex items-center gap-1.5 rounded-[6px] px-2.5 py-1.5 text-[12px] text-[rgba(13,13,13,0.50)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)] dark:hover:text-[#EDE8E3]"
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
      className="flex shrink-0 items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.10)] text-[#D97757]"
      style={{ width: size, height: size }}
    >
      <Code2 size={Math.round(size * 0.55)} />
    </div>
  );
}
