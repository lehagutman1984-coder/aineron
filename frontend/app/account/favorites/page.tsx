"use client";

import { useState } from "react";
import Link from "next/link";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Heart, ImageOff, Video, Wand2, Download, ArrowLeft } from "lucide-react";
import { getFavorites, favoriteGeneration, downloadImageUrl } from "@/lib/api/client";

type Filter = "all" | "image" | "video";
const TABS: { key: Filter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "image", label: "Изображения" },
  { key: "video", label: "Видео" },
];

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function FavoritesPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } = useInfiniteQuery({
    queryKey: ["favorites", filter],
    queryFn: ({ pageParam = 1 }) =>
      getFavorites({ page: pageParam as number, per_page: 24, media_type: filter === "all" ? undefined : filter }),
    getNextPageParam: (last) => (last.has_next ? last.page + 1 : undefined),
    initialPageParam: 1,
  });

  const unfavoriteMut = useMutation({
    mutationFn: (id: number) => favoriteGeneration(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["favorites"] }),
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

  return (
    <div className="min-h-screen bg-[var(--bg-primary,#f7f7f8)]">
      <div className="mx-auto max-w-[1100px] px-4 py-8">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Link
            href="/account/"
            className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[rgba(13,13,13,0.10)] text-[rgba(13,13,13,0.5)] transition-colors hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.10)] dark:text-[rgba(236,236,236,0.5)]"
          >
            <ArrowLeft size={15} />
          </Link>
          <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[rgba(231,76,60,0.10)]">
            <Heart size={20} className="text-[#e74c3c]" />
          </div>
          <div>
            <h1 className="text-[20px] font-bold leading-tight text-[#1A1A1A] dark:text-[#EDE8E3]">Избранное</h1>
            <p className="text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
              Сохранённые изображения и видео{total > 0 ? ` · ${total}` : ""}
            </p>
          </div>
        </div>

        {/* Filter tabs */}
        <div className="mb-5 flex gap-1 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] p-1 w-fit dark:border-[rgba(255,255,255,0.10)] dark:bg-[rgba(255,255,255,0.04)]">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setFilter(t.key)}
              className={`rounded-[7px] px-4 py-1.5 text-[13px] font-medium transition-all ${
                filter === t.key
                  ? "bg-white text-[#1A1A1A] shadow-sm dark:bg-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]"
                  : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.5)] dark:hover:text-[#EDE8E3]"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Grid */}
        {isLoading ? (
          <div className="columns-2 gap-3 sm:columns-3 lg:columns-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="mb-3 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.06)]" style={{ height: `${160 + (i % 3) * 60}px` }} />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[rgba(13,13,13,0.05)]">
              <ImageOff size={28} className="text-[rgba(13,13,13,0.25)]" />
            </div>
            <p className="text-[15px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">Пусто</p>
            <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
              Нажмите «Сохранить» под изображением в чате, чтобы добавить его сюда
            </p>
            <Link
              href="/models/"
              className="mt-4 inline-flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-[#C4623E]"
            >
              <Wand2 size={14} />
              Создать изображение
            </Link>
          </div>
        ) : (
          <>
            <div className="columns-2 gap-3 sm:columns-3 lg:columns-4">
              {items.map((item) => (
                <div key={item.id} className="group mb-3 break-inside-avoid overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white dark:border-[rgba(255,255,255,0.08)] dark:bg-[rgba(255,255,255,0.04)]">
                  <div className="relative w-full overflow-hidden bg-[rgba(13,13,13,0.04)]">
                    {item.media_type === "video" ? (
                      // eslint-disable-next-line jsx-a11y/media-has-caption
                      <video src={item.image_url} className="w-full object-cover" autoPlay muted loop playsInline />
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={item.image_url} alt={item.prompt} className="w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]" loading="lazy" />
                    )}
                    {item.media_type === "video" && (
                      <div className="absolute top-2 left-2">
                        <span className="flex items-center gap-1 rounded-[5px] bg-black/50 px-1.5 py-0.5 text-[10px] text-white">
                          <Video size={9} />
                          Видео
                        </span>
                      </div>
                    )}
                    {/* Hover overlay */}
                    <div className="absolute inset-0 flex items-end justify-end gap-1.5 p-2 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={() => downloadImageUrl(item.image_url, `aineron-${item.id}.${item.media_type === "video" ? "mp4" : "png"}`)}
                        title="Скачать"
                        className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/80 text-[#1A1A1A] shadow-sm backdrop-blur-sm hover:bg-white"
                      >
                        <Download size={13} />
                      </button>
                      <button
                        onClick={() => unfavoriteMut.mutate(item.id)}
                        title="Убрать из избранного"
                        className="flex h-7 w-7 items-center justify-center rounded-[6px] bg-white/80 text-[#e74c3c] shadow-sm backdrop-blur-sm hover:bg-white"
                        disabled={unfavoriteMut.isPending}
                      >
                        <Heart size={13} fill="currentColor" />
                      </button>
                    </div>
                  </div>

                  <div className="p-2.5">
                    {item.prompt && (
                      <p className="line-clamp-2 text-[11px] leading-relaxed text-[rgba(13,13,13,0.6)] dark:text-[rgba(236,236,236,0.55)]">
                        {item.prompt}
                      </p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-1">
                      {item.model_name && (
                        <span className="inline-flex items-center rounded-[4px] bg-[rgba(217,119,87,0.08)] px-1.5 py-0.5 text-[10px] font-medium text-[#D97757]">
                          {item.model_name}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] text-[rgba(13,13,13,0.30)] dark:text-[rgba(236,236,236,0.25)]">
                        {formatDate(item.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {hasNextPage && (
              <div className="flex justify-center pt-4">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="h-10 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-6 text-[13px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50 dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.65)]"
                >
                  {isFetchingNextPage ? "Загрузка..." : "Загрузить ещё"}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
