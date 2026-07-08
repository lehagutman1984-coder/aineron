"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { BookMarked, Code2, Globe, BarChart2, Mail, BookOpen, Pencil, FileText, X, Search } from "lucide-react";
import { listPrompts } from "@/lib/api/client";
import type { PromptTemplate } from "@/lib/api/types";

const CAT_KEYS = [
  { key: "all", labelKey: "catAll" },
  { key: "code", labelKey: "catCode" },
  { key: "translate", labelKey: "catTranslate" },
  { key: "analyze", labelKey: "catAnalyze" },
  { key: "email", labelKey: "catEmail" },
  { key: "study", labelKey: "catStudy" },
  { key: "creative", labelKey: "catCreative" },
] as const;

type CatKey = (typeof CAT_KEYS)[number]["key"];

function CatIcon({ category, size = 13 }: { category: string; size?: number }) {
  const cls = "shrink-0 text-[#D97757]";
  switch (category) {
    case "code": return <Code2 size={size} className={cls} />;
    case "translate": return <Globe size={size} className={cls} />;
    case "analyze": return <BarChart2 size={size} className={cls} />;
    case "email": return <Mail size={size} className={cls} />;
    case "study": return <BookOpen size={size} className={cls} />;
    case "creative": return <Pencil size={size} className={cls} />;
    default: return <FileText size={size} className={cls} />;
  }
}

export function PromptPicker({
  onSelect,
  onClose,
}: {
  onSelect: (content: string) => void;
  onClose: () => void;
}) {
  const t = useTranslations("chat.promptPicker");
  const [cat, setCat] = useState<CatKey>("all");
  const [search, setSearch] = useState("");

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => listPrompts(),
    staleTime: 5 * 60 * 1000,
  });

  const filtered = prompts.filter((p) => {
    const matchCat = cat === "all" || p.category === cat;
    const matchSearch =
      !search ||
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.content.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/25 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Sheet */}
      <div
        className="relative flex w-full max-w-xl flex-col rounded-t-[20px] bg-white shadow-2xl dark:bg-[#1C1917] sm:rounded-[20px]"
        style={{
          border: "1px solid var(--border-secondary)",
          maxHeight: "80vh",
        }}
      >
        {/* Header */}
        <div
          className="flex shrink-0 items-center justify-between px-4 py-3.5"
          style={{ borderBottom: "1px solid var(--border-tertiary)" }}
        >
          <div className="flex items-center gap-2">
            <BookMarked size={15} className="text-[#D97757]" />
            <span className="text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
              {t("title")}
            </span>
          </div>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-full text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.40)]"
          >
            <X size={15} />
          </button>
        </div>

        {/* Search */}
        <div className="shrink-0 px-4 pt-3 pb-2">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPlaceholder")}
              className="h-8 w-full rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-transparent pl-7 pr-3 text-[14px] text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]"
            />
          </div>
        </div>

        {/* Category chips */}
        <div className="flex shrink-0 gap-1.5 overflow-x-auto px-4 pb-3 pt-1">
          {CAT_KEYS.map(({ key, labelKey }) => (
            <button
              key={key}
              onClick={() => setCat(key)}
              className={[
                "shrink-0 rounded-full px-3 py-1 text-[13px] font-medium transition-all",
                cat === key
                  ? "bg-[#1A1A1A] text-white"
                  : "border border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.60)] hover:border-[rgba(13,13,13,0.25)] dark:border-[rgba(255,255,255,0.10)] dark:text-[rgba(236,236,236,0.55)]",
              ].join(" ")}
            >
              {t(labelKey)}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-16 animate-pulse rounded-[10px] bg-[rgba(13,13,13,0.05)]" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="py-8 text-center text-[15px] text-[rgba(13,13,13,0.40)]">
              {t("noResults")}
            </p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {filtered.map((p) => (
                <button
                  key={p.id}
                  onClick={() => { onSelect(p.content); onClose(); }}
                  className="flex items-start gap-3 rounded-[10px] px-3 py-3 text-left transition-colors hover:bg-[rgba(13,13,13,0.05)] dark:hover:bg-[rgba(255,255,255,0.05)]"
                >
                  <div className="mt-0.5">
                    <CatIcon category={p.category} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[15px] font-medium text-[#1A1A1A] dark:text-[#EDE8E3]">
                      {p.title}
                    </p>
                    <p className="mt-0.5 line-clamp-1 text-[13px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)]">
                      {p.content}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
