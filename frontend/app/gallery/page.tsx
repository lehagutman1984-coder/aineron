"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Video, Sparkles, ImageOff, Wand2 } from "lucide-react";
import { getGallery } from "@/lib/api/client";
import type { GalleryItem } from "@/lib/api/types";

type Filter = "all" | "image" | "video";

const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "image", label: "Изображения" },
  { key: "video", label: "Видео" },
];

const PER_PAGE = 24;
const PREFILL_KEY = "aineron_prefill_prompt";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function GalleryCard({ item, onTry }: { item: GalleryItem; onTry: (prompt: string) => void }) {
  return (
    <div className="group relative mb-3 break-inside-avoid overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
      <Link href={item.share_slug ? `/g/${item.share_slug}` : "#"} className="block">
        <div className="relative w-full overflow-hidden bg-[rgba(13,13,13,0.04)]">
          {item.media_type === "video" ? (
            <div className="relative bg-black">
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video src={item.image_url} className="w-full object-cover" preload="metadata" muted />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-black/50">
                  <Video size={16} className="text-white" />
                </div>
              </div>
            </div>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.image_url}
              alt={item.prompt}
              className="w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
              loading="lazy"
            />
          )}
        </div>
      </Link>

      <div className="p-3">
        <p className="line-clamp-2 text-[12px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {item.prompt || "Без описания"}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          {item.model_name && (
            <span className="inline-flex items-center rounded-[5px] bg-[rgba(10,124,255,0.08)] px-1.5 py-0.5 text-[10px] font-medium text-[#0a7cff]">
              {item.model_name}
            </span>
          )}
          <span className="text-[10px] text-[rgba(13,13,13,0.35)]">{item.username}</span>
          <span className="text-[10px] text-[rgba(13,13,13,0.30)]">· {formatDate(item.created_at)}</span>
        </div>
        {item.prompt && (
          <button
            onClick={() => onTry(item.prompt)}
            className="mt-2 inline-flex items-center gap-1.5 rounded-[7px] bg-[rgba(10,124,255,0.08)] px-2.5 py-1.5 text-[12px] font-medium text-[#0a7cff] transition-colors hover:bg-[rgba(10,124,255,0.14)]"
          >
            <Wand2 size={12} />
            Попробовать
          </button>
        )}
      </div>
    </div>
  );
}

export default function GalleryPage() {
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("all");
  const [model, setModel] = useState<string>("");

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey: ["gallery", filter, model],
      queryFn: ({ pageParam = 1 }) =>
        getGallery({
          page: pageParam as number,
          per_page: PER_PAGE,
          media_type: filter === "all" ? undefined : filter,
          model_name: model || undefined,
        }),
      getNextPageParam: (last) => (last.has_next ? last.page + 1 : undefined),
      initialPageParam: 1,
    });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  // Уникальные модели из загруженных элементов — для дропдауна фильтра
  const models = useMemo(() => {
    const set = new Set<string>();
    items.forEach((i) => i.model_name && set.add(i.model_name));
    return Array.from(set).sort();
  }, [items]);

  const handleTry = (prompt: string) => {
    try {
      localStorage.setItem(PREFILL_KEY, prompt);
    } catch {}
    router.push("/models/");
  };

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      {/* Header */}
      <header className="border-b border-[rgba(13,13,13,0.08)] bg-white">
        <div className="mx-auto flex max-w-[1100px] items-center justify-between px-4 py-3">
          <Link href="/" className="text-[13px] font-semibold tracking-tight text-[#0d0d0d]">
            Aineron.ru
          </Link>
          <Link
            href="/models/"
            className="rounded-[8px] bg-[#0a7cff] px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-[#0068e0]"
          >
            Создать своё
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-4 py-8">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[rgba(10,124,255,0.10)]">
            <Sparkles size={20} className="text-[#0a7cff]" />
          </div>
          <div>
            <h1 className="text-[22px] font-bold leading-tight text-[#0d0d0d]">Публичная галерея</h1>
            <p className="text-[13px] text-[rgba(13,13,13,0.45)]">
              Работы пользователей Aineron{total > 0 ? ` · ${total}` : ""}
            </p>
          </div>
        </div>

        {/* Filter bar */}
        <div className="mb-5 flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] p-1">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setFilter(t.key)}
                className={`rounded-[7px] px-4 py-1.5 text-[13px] font-medium transition-all ${
                  filter === t.key
                    ? "bg-white text-[#0d0d0d] shadow-sm"
                    : "text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          {models.length > 0 && (
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="h-9 rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-white px-3 text-[13px] text-[rgba(13,13,13,0.65)] outline-none focus:border-[#0a7cff]"
            >
              <option value="">Все модели</option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Grid (masonry via CSS columns) */}
        {isLoading ? (
          <div className="columns-2 gap-3 sm:columns-3 lg:columns-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="mb-3 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.06)]"
                style={{ height: `${160 + (i % 3) * 60}px` }}
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[rgba(13,13,13,0.05)]">
              <ImageOff size={28} className="text-[rgba(13,13,13,0.25)]" />
            </div>
            <p className="text-[15px] font-medium text-[#0d0d0d]">Пока пусто</p>
            <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.45)]">
              Здесь появятся публичные работы пользователей
            </p>
          </div>
        ) : (
          <>
            <div className="columns-2 gap-3 sm:columns-3 lg:columns-4">
              {items.map((item) => (
                <GalleryCard key={item.id} item={item} onTry={handleTry} />
              ))}
            </div>

            {hasNextPage && (
              <div className="flex justify-center pt-4">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="h-10 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-6 text-[13px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50"
                >
                  {isFetchingNextPage ? "Загрузка..." : "Загрузить ещё"}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
