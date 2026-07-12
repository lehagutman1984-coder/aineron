"use client";

import { useEffect, useState } from "react";
import { Link, useRouter } from "@/i18n/navigation";

import { useInfiniteQuery } from "@tanstack/react-query";
import { Video, Sparkles, ImageOff, Wand2, Search, Copy, Check, Heart } from "lucide-react";
import { useTranslations, useLocale } from "next-intl";
import { getGallery, likeGeneration } from "@/lib/api/client";
import type { GalleryItem } from "@/lib/api/types";

type Filter = "all" | "image" | "video";

const TAB_KEYS: { key: Filter; labelKey: "tabAll" | "tabImages" | "tabVideo" }[] = [
  { key: "all", labelKey: "tabAll" },
  { key: "image", labelKey: "tabImages" },
  { key: "video", labelKey: "tabVideo" },
];

const PER_PAGE = 24;
const PREFILL_KEY = "aineron_prefill_prompt";

const MODEL_CHIPS = ["Flux 2 Pro", "GPT Image 1", "Flux Kontext Pro", "Sora 2", "Kling v2.6"];

function formatDate(iso: string, locale: string) {
  return new Date(iso).toLocaleDateString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function GalleryCard({
  t, item, onTry,
}: {
  t: ReturnType<typeof useTranslations>;
  item: GalleryItem;
  onTry: (prompt: string) => void;
}) {
  const locale = useLocale();
  const [copied, setCopied] = useState(false);
  const [likes, setLikes] = useState(item.likes ?? 0);
  const [liked, setLiked] = useState(false);

  const handleLike = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (liked) return;
    try {
      const res = await likeGeneration(item.id);
      setLikes(res.likes);
      setLiked(true);
    } catch {}
  };

  return (
    <div className="group relative mb-3 break-inside-avoid overflow-hidden rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
      <Link href={item.share_slug ? `/g/${item.share_slug}` : "#"} className="block">
        <div className="relative w-full overflow-hidden bg-[rgba(13,13,13,0.04)]">
          {item.media_type === "video" || item.video_url ? (
            // eslint-disable-next-line jsx-a11y/media-has-caption
            <video
              src={item.video_url || item.image_url}
              className="w-full object-cover"
              autoPlay
              muted
              loop
              playsInline
            />
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
        <p className="line-clamp-2 text-[14px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {item.prompt || t("noDescription")}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          {item.model_name && (
            <span className="inline-flex items-center rounded-[5px] bg-[rgba(217,119,87,0.08)] px-1.5 py-0.5 text-[12px] font-medium text-[#D97757]">
              {item.model_name}
            </span>
          )}
          <span className="text-[12px] text-[rgba(13,13,13,0.35)]">{item.username}</span>
          <span className="text-[12px] text-[rgba(13,13,13,0.30)]">· {formatDate(item.created_at, locale)}</span>
          {item.prompt && (
            <button
              onClick={(e) => {
                e.preventDefault();
                navigator.clipboard.writeText(item.prompt);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              }}
              className="ms-auto flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.35)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A]"
              title={t("copyPrompt")}
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
            </button>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2">
          {item.prompt && (
            <button
              onClick={() => onTry(item.prompt)}
              className="inline-flex items-center gap-1.5 rounded-[7px] bg-[rgba(217,119,87,0.08)] px-2.5 py-1.5 text-[14px] font-medium text-[#D97757] transition-colors hover:bg-[rgba(217,119,87,0.14)]"
            >
              <Wand2 size={12} />
              {t("tryPrompt")}
            </button>
          )}
          <button
            onClick={handleLike}
            title={liked ? t("alreadyLiked") : t("like")}
            className={`ms-auto flex items-center gap-1 rounded-[7px] px-2 py-1.5 text-[14px] font-medium transition-colors ${
              liked ? "text-[#e74c3c]" : "text-[rgba(13,13,13,0.38)] hover:text-[#e74c3c]"
            }`}
          >
            <Heart size={12} fill={liked ? "currentColor" : "none"} />
            {likes > 0 && <span>{likes}</span>}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function GalleryPage() {
  const t = useTranslations("gallery");
  const router = useRouter();
  const [filter, setFilter] = useState<Filter>("all");
  const [model, setModel] = useState<string>("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timeoutId = setTimeout(() => setDebouncedSearch(search), 500);
    return () => clearTimeout(timeoutId);
  }, [search]);

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey: ["gallery", filter, model, debouncedSearch],
      queryFn: ({ pageParam = 1 }) =>
        getGallery({
          page: pageParam as number,
          per_page: PER_PAGE,
          media_type: filter === "all" ? undefined : filter,
          model_name: model || undefined,
          search: debouncedSearch || undefined,
        }),
      getNextPageParam: (last) => (last.has_next ? last.page + 1 : undefined),
      initialPageParam: 1,
    });

  const items = data?.pages.flatMap((p) => p.items) ?? [];
  const total = data?.pages[0]?.total ?? 0;

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
          <Link href="/" className="text-[15px] font-semibold tracking-tight text-[#1A1A1A]">
            Aineron.ru
          </Link>
          <Link
            href="/models/"
            className="rounded-[8px] bg-[#D97757] px-4 py-1.5 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            {t("createOwn")}
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-4 py-8">
        <div className="mb-5 flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[rgba(217,119,87,0.10)]">
            <Sparkles size={20} className="text-[#D97757]" />
          </div>
          <div>
            <h1 className="text-[22px] font-bold leading-tight text-[#1A1A1A]">{t("title")}</h1>
            <p className="text-[15px] text-[rgba(13,13,13,0.45)]">
              {t("subtitle")}{total > 0 ? ` · ${total}` : ""}
            </p>
          </div>
        </div>

        {/* Search */}
        <div className="relative mb-4 max-w-md">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="w-full rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-white px-4 py-2 ps-10 text-[15px] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] dark:border-[rgba(255,255,255,0.1)] dark:bg-[rgba(255,255,255,0.06)] dark:text-[#EDE8E3]"
          />
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]" />
        </div>

        {/* Filter bar */}
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] p-1">
            {TAB_KEYS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key)}
                className={`rounded-[7px] px-4 py-1.5 text-[15px] font-medium transition-all ${
                  filter === tab.key
                    ? "bg-white text-[#1A1A1A] shadow-sm"
                    : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A]"
                }`}
              >
                {t(tab.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Model chips */}
        <div className="mb-5 mt-2 flex flex-wrap gap-1.5">
          <button
            onClick={() => setModel("")}
            className={`h-7 rounded-[6px] border px-2.5 text-[13px] font-medium transition-colors ${
              !model
                ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]"
            }`}
          >
            {t("allModels")}
          </button>
          {MODEL_CHIPS.map((m) => (
            <button
              key={m}
              onClick={() => setModel(model === m ? "" : m)}
              className={`h-7 rounded-[6px] border px-2.5 text-[13px] font-medium transition-colors ${
                model === m
                  ? "border-[#D97757] bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                  : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:border-[rgba(13,13,13,0.25)]"
              }`}
            >
              {m}
            </button>
          ))}
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
            <p className="text-[17px] font-medium text-[#1A1A1A]">{t("emptyTitle")}</p>
            <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.45)]">
              {t("emptyDescription")}
            </p>
          </div>
        ) : (
          <>
            <div className="columns-2 gap-3 sm:columns-3 lg:columns-4">
              {items.map((item) => (
                <GalleryCard key={item.id} t={t} item={item} onTry={handleTry} />
              ))}
            </div>

            {hasNextPage && (
              <div className="flex justify-center pt-4">
                <button
                  onClick={() => fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="h-10 rounded-[8px] border border-[rgba(13,13,13,0.12)] px-6 text-[15px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:bg-[rgba(13,13,13,0.04)] disabled:opacity-50"
                >
                  {isFetchingNextPage ? t("loadingMore") : t("loadMore")}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
