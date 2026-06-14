"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookMarked, Code2, Globe, BarChart2, Mail, BookOpen, Pencil, FileText,
  Search, Plus, Trash2, Copy, Check, X,
} from "lucide-react";
import Link from "next/link";
import { listPrompts, createPrompt, deletePrompt } from "@/lib/api/client";
import { useAuthStore } from "@/lib/stores/auth";
import type { PromptTemplate } from "@/lib/api/types";

const CATEGORIES = [
  { key: "all", label: "Все", Icon: BookMarked },
  { key: "code", label: "Код", Icon: Code2 },
  { key: "translate", label: "Перевод", Icon: Globe },
  { key: "analyze", label: "Анализ", Icon: BarChart2 },
  { key: "email", label: "Письма", Icon: Mail },
  { key: "study", label: "Учёба", Icon: BookOpen },
  { key: "creative", label: "Творчество", Icon: Pencil },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];

export default function PromptsPage() {
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
        <h1 className="text-[24px] font-bold text-[#0d0d0d] dark:text-[#ececec]">
          Библиотека промтов
        </h1>
        <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.48)] dark:text-[rgba(236,236,236,0.42)]">
          {prompts.length} готовых шаблонов для быстрого старта
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
            placeholder="Поиск промтов..."
            className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-white pl-8 pr-3 text-[13px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] dark:border-[rgba(255,255,255,0.10)] dark:bg-[#1c1c1f] dark:text-[#ececec]"
          />
        </div>

        {user && (
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 rounded-[9px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc]"
          >
            <Plus size={14} />
            Добавить промт
          </button>
        )}
      </div>

      {/* Category tabs */}
      <div className="mb-6 flex gap-1.5 overflow-x-auto pb-1">
        {CATEGORIES.map(({ key, label, Icon }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={[
              "flex shrink-0 items-center gap-1.5 rounded-[8px] px-3.5 py-1.5 text-[13px] font-medium transition-all",
              activeCategory === key
                ? "bg-[#0d0d0d] text-white dark:bg-[#ececec] dark:text-[#0d0d0d]"
                : "text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.55)] dark:hover:bg-[rgba(255,255,255,0.07)]",
            ].join(" ")}
          >
            <Icon size={13} />
            {label}
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
          <p className="text-[14px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.38)]">
            {search ? "Ничего не найдено" : "В этой категории пока нет промтов"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <PromptCard
              key={p.id}
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
  prompt, copied, onCopy, onDelete,
}: {
  prompt: PromptTemplate;
  copied: boolean;
  onCopy: () => void;
  onDelete?: () => void;
}) {
  return (
    <div
      className="group flex flex-col rounded-[12px] border p-4 transition-all hover:shadow-[0_2px_12px_rgba(0,0,0,0.08)]"
      style={{ borderColor: "rgba(13,13,13,0.10)" }}
    >
      {/* Top row */}
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <CategoryIcon category={prompt.category} />
          <p className="text-[13px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
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
      <p className="mb-4 line-clamp-3 flex-1 text-[12px] leading-relaxed text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.40)]">
        {prompt.content}
      </p>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onCopy}
          className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.10)] px-2.5 py-1.5 text-[12px] font-medium text-[rgba(13,13,13,0.60)] transition-colors hover:border-[rgba(13,13,13,0.20)] hover:text-[#0d0d0d] dark:border-[rgba(255,255,255,0.10)] dark:text-[rgba(236,236,236,0.50)]"
        >
          {copied ? <Check size={12} className="text-[#0a7cff]" /> : <Copy size={12} />}
          {copied ? "Скопировано" : "Копировать"}
        </button>
        <Link
          href={`/models/`}
          className="flex items-center gap-1.5 rounded-[7px] bg-[rgba(10,124,255,0.08)] px-2.5 py-1.5 text-[12px] font-medium text-[#0a7cff] transition-colors hover:bg-[rgba(10,124,255,0.14)]"
        >
          Использовать
        </Link>
      </div>
    </div>
  );
}

// ── Add prompt modal ───────────────────────────────────────────────────────────
function AddPromptModal({ onClose }: { onClose: () => void }) {
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
        className="relative w-full max-w-lg rounded-[16px] bg-white p-6 shadow-2xl dark:bg-[#18181b]"
        style={{ border: "1px solid rgba(13,13,13,0.10)" }}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#0d0d0d] dark:text-[#ececec]">
            Добавить промт
          </h2>
          <button onClick={onClose} className="text-[rgba(13,13,13,0.40)] hover:text-[#0d0d0d]">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              Название
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например: Анализ резюме"
              className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-transparent px-3 text-[13px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] dark:border-[rgba(255,255,255,0.12)] dark:text-[#ececec]"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              Категория
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="h-9 w-full rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-white px-3 text-[13px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] dark:border-[rgba(255,255,255,0.12)] dark:bg-[#1c1c1f] dark:text-[#ececec]"
            >
              {CATEGORIES.filter((c) => c.key !== "all").map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.60)] dark:text-[rgba(236,236,236,0.50)]">
              Текст промта
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Введите шаблон промта..."
              rows={5}
              className="w-full resize-none rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-transparent px-3 py-2 text-[13px] leading-relaxed text-[#0d0d0d] outline-none focus:border-[#0a7cff] dark:border-[rgba(255,255,255,0.12)] dark:text-[#ececec]"
            />
          </div>

          {mutation.isError && (
            <p className="text-[12px] text-[#e74c3c]">Ошибка сохранения. Попробуйте ещё раз.</p>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-[8px] px-4 py-2 text-[13px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.05)] dark:text-[rgba(236,236,236,0.45)]"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!title.trim() || !content.trim() || mutation.isPending}
              className="rounded-[8px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc] disabled:opacity-40"
            >
              {mutation.isPending ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Category icon helper ───────────────────────────────────────────────────────
function CategoryIcon({ category }: { category: string }) {
  const cls = "shrink-0 text-[#0a7cff]";
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
