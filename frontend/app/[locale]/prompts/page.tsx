"use client";

import { useState } from "react";
import { Link } from "@/i18n/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookMarked, Code2, Globe, BarChart2, Mail, BookOpen, Pencil, FileText,
  Search, Plus, Trash2, Copy, Check, X,
} from "lucide-react";

import { useTranslations } from "next-intl";
import { listPrompts, createPrompt, deletePrompt } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { PromptTemplate } from "@/lib/api/types";

const CATEGORIES = [
  { key: "all", labelKey: "categoryAll", Icon: BookMarked },
  { key: "code", labelKey: "categoryCode", Icon: Code2 },
  { key: "translate", labelKey: "categoryTranslate", Icon: Globe },
  { key: "analyze", labelKey: "categoryAnalyze", Icon: BarChart2 },
  { key: "email", labelKey: "categoryEmail", Icon: Mail },
  { key: "study", labelKey: "categoryStudy", Icon: BookOpen },
  { key: "creative", labelKey: "categoryCreative", Icon: Pencil },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];

export default function PromptsPage() {
  const t = useTranslations("prompts");
  const { user } = useAuthStore();
  const qc = useQueryClient();
  const [activeCategory, setActiveCategory] = useState<CategoryKey>("all");
  const [search, setSearch] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const { data: prompts = [], isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => listPrompts(),
  });

  const deleteMutation = useMutation({
    mutationFn: deletePrompt,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });

  const filtered = prompts.filter((p) => {
    const matchCat = activeCategory === "all" || p.category === activeCategory;
    const matchSearch =
      !search ||
      p.title.toLowerCase().includes(search.toLowerCase()) ||
      p.content.toLowerCase().includes(search.toLowerCase());
    return matchCat && matchSearch;
  });

  const handleCopy = (p: PromptTemplate) => {
    navigator.clipboard.writeText(p.content).catch(() => {});
    setCopiedId(p.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-[24px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
          {t("title")}
        </h1>
        <p className="mt-1 text-[16px] text-[rgba(13,13,13,0.48)] dark:text-[rgba(236,236,236,0.42)]">
          {t("subtitle", { count: prompts.length })}
        </p>
      </div>

      {/* Toolbar */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {/* Search */}
        <div className="relative w-full max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.30)]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchPlaceholder")}
            className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-white ps-8 pe-3 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.10)] dark:bg-[#1c1c1f] dark:text-[#EDE8E3]"
          />
        </div>

        {user && (
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-[9px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            <Plus size={14} />
            {t("addPrompt")}
          </button>
        )}
      </div>

      {/* Category tabs */}
      <div className="mb-6 flex gap-1.5 overflow-x-auto pb-1">
        {CATEGORIES.map(({ key, labelKey, Icon }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={[
              "flex shrink-0 items-center gap-1.5 rounded-[8px] px-3.5 py-1.5 text-[15px] font-medium transition-all",
              activeCategory === key
                ? "bg-[#1A1A1A] text-white"
                : "text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.55)] dark:hover:bg-[rgba(255,255,255,0.07)]",
            ].join(" ")}
          >
            <Icon size={13} />
            {t(labelKey)}
          </button>
        ))}
      </div>

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-[140px] animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)] dark:bg-[rgba(255,255,255,0.04)]" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center py-20 text-center">
          <BookMarked size={40} className="mb-3 text-[rgba(13,13,13,0.15)] dark:text-[rgba(236,236,236,0.12)]" />
          <p className="text-[16px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)]">
            {search ? t("emptySearch") : t("emptyCategory")}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <PromptCard
              key={p.id}
              t={t}
              prompt={p}
              copied={copiedId === p.id}
              onCopy={() => handleCopy(p)}
              onDelete={p.is_own ? () => deleteMutation.mutate(p.id) : undefined}
            />
          ))}
        </div>
      )}

      {/* Add prompt modal */}
      {showAdd && <AddPromptModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}

// ── Prompt card ────────────────────────────────────────────────────────────────
function PromptCard({
  t, prompt, copied, onCopy, onDelete,
}: {
  t: ReturnType<typeof useTranslations>;
  prompt: PromptTemplate;
  copied: boolean;
  onCopy: () => void;
  onDelete?: () => void;
}) {
  return (
    <div
      className="group flex flex-col rounded-[12px] border p-4 transition-all hover:shadow-[0_2px_12px_rgba(0,0,0,0.08)]"
      style={{ borderColor: "var(--border-secondary)" }}
    >
      {/* Top row */}
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <CategoryIcon category={prompt.category} />
          <p className="text-[15px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            {prompt.title}
          </p>
        </div>
        {onDelete && (
          <button
            onClick={onDelete}
            className="shrink-0 text-[rgba(13,13,13,0.25)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-[#e74c3c]"
          >
            <Trash2 size={13} />
          </button>
        )}
      </div>

      {/* Preview */}
      <p className="mb-4 line-clamp-3 flex-1 text-[14px] leading-relaxed text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.40)]">
        {prompt.content}
      </p>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onCopy}
          className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.10)] px-2.5 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.60)] transition-colors hover:border-[rgba(13,13,13,0.20)] hover:text-[#1A1A1A] dark:border-[rgba(255,255,255,0.10)] dark:text-[rgba(236,236,236,0.50)]"
        >
          {copied ? <Check size={12} className="text-[#D97757]" /> : <Copy size={12} />}
          {copied ? t("copied") : t("copy")}
        </button>
        <Link
          href={`/models/`}
          className="flex items-center gap-1.5 rounded-[7px] bg-[rgba(217,119,87,0.08)] px-2.5 py-1.5 text-[14px] font-medium text-[#D97757] transition-colors hover:bg-[rgba(217,119,87,0.14)]"
        >
          {t("use")}
        </Link>
      </div>
    </div>
  );
}

// ── Add prompt modal ───────────────────────────────────────────────────────────
function AddPromptModal({ onClose }: { onClose: () => void }) {
  const t = useTranslations("prompts");
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("other");

  const mutation = useMutation({
    mutationFn: createPrompt,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts"] });
      onClose();
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;
    mutation.mutate({ title: title.trim(), content: content.trim(), category });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-lg rounded-[16px] bg-white p-6 shadow-2xl dark:bg-[#1C1917]"
        style={{ border: "1px solid var(--border-secondary)" }}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
            {t("addPrompt")}
          </h2>
          <button onClick={onClose} className="text-[rgba(13,13,13,0.40)] hover:text-[#1A1A1A]">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              {t("nameLabel")}
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("namePlaceholder")}
              className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-transparent px-3 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              {t("categoryLabel")}
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-white px-3 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:bg-[#1c1c1f] dark:text-[#EDE8E3]"
            >
              {CATEGORIES.filter((c) => c.key !== "all").map((c) => (
                <option key={c.key} value={c.key}>{t(c.labelKey)}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              {t("promptTextLabel")}
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={t("promptTextPlaceholder")}
              rows={5}
              className="w-full resize-none rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-transparent px-3 py-2 text-[15px] leading-relaxed text-[#1A1A1A] outline-none focus:border-[#D97757] dark:border-[rgba(255,255,255,0.12)] dark:text-[#EDE8E3]"
            />
          </div>

          {mutation.isError && (
            <p className="text-[14px] text-[#e74c3c]">{t("saveError")}</p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-[8px] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.45)]"
            >
              {t("cancel")}
            </button>
            <button
              type="submit"
              disabled={!title.trim() || !content.trim() || mutation.isPending}
              className="rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E] disabled:opacity-40"
            >
              {mutation.isPending ? t("saving") : t("save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Category icon helper ───────────────────────────────────────────────────────
function CategoryIcon({ category }: { category: string }) {
  const cls = "shrink-0 text-[#D97757]";
  const size = 14;
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
