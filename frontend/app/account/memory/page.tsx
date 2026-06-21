"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Brain,
  Pin,
  Plus,
  Trash2,
  Check,
  X,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Sparkles,
  ArrowLeft,
} from "lucide-react";
import {
  getMemoryFacts,
  getMemorySummaries,
  getMemorySettings,
  createMemoryFact,
  updateMemoryFact,
  deleteMemoryFact,
  clearAutoMemory,
  updateMemorySettings,
  type UserMemory,
  type ChatSummary,
  type MemoryCategory,
} from "@/lib/api/memory";

const CATEGORIES: { value: MemoryCategory; label: string }[] = [
  { value: "profile", label: "Профиль" },
  { value: "skill", label: "Навыки" },
  { value: "preference", label: "Предпочтения" },
  { value: "project", label: "Проекты" },
  { value: "fact", label: "Факты" },
];

const CATEGORY_BADGE: Record<MemoryCategory, string> = {
  profile: "bg-blue-100 text-blue-700",
  skill: "bg-purple-100 text-purple-700",
  preference: "bg-amber-100 text-amber-700",
  project: "bg-green-100 text-green-700",
  fact: "bg-slate-100 text-slate-700",
};

const CATEGORY_LABEL: Record<MemoryCategory, string> = {
  profile: "Профиль",
  skill: "Навыки",
  preference: "Предпочтения",
  project: "Проекты",
  fact: "Факты",
};

type CategoryFilter = "all" | MemoryCategory;
type SourceFilter = "all" | "auto" | "manual";

const isAuto = (source: string) => source === "auto";

export default function MemoryPage() {
  const queryClient = useQueryClient();

  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [showForm, setShowForm] = useState(false);
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState<MemoryCategory>("fact");
  const [confirmClear, setConfirmClear] = useState(false);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const settingsQuery = useQuery({
    queryKey: ["memory-settings"],
    queryFn: getMemorySettings,
    staleTime: 30_000,
  });

  const factsQuery = useQuery({
    queryKey: ["memory-facts"],
    queryFn: getMemoryFacts,
    staleTime: 30_000,
    enabled: settingsQuery.data?.memory_enabled ?? false,
  });

  const summariesQuery = useQuery({
    queryKey: ["memory-summaries"],
    queryFn: getMemorySummaries,
    staleTime: 30_000,
    enabled: settingsQuery.data?.memory_enabled ?? false,
  });

  const settingsMutation = useMutation({
    mutationFn: (enabled: boolean) =>
      updateMemorySettings({ memory_enabled: enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-settings"] });
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
      queryClient.invalidateQueries({ queryKey: ["memory-summaries"] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createMemoryFact({ content: newContent.trim(), category: newCategory }),
    onSuccess: () => {
      setNewContent("");
      setNewCategory("fact");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
      queryClient.invalidateQueries({ queryKey: ["memory-settings"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      data,
    }: {
      id: number;
      data: Partial<Pick<UserMemory, "is_active" | "is_pinned">>;
    }) => updateMemoryFact(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteMemoryFact(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
      queryClient.invalidateQueries({ queryKey: ["memory-settings"] });
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearAutoMemory,
    onSuccess: () => {
      setConfirmClear(false);
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
      queryClient.invalidateQueries({ queryKey: ["memory-settings"] });
    },
  });

  const facts = useMemo(() => factsQuery.data ?? [], [factsQuery.data]);

  const stats = useMemo(() => {
    const total = facts.length;
    const active = facts.filter((f) => f.is_active).length;
    const auto = facts.filter((f) => isAuto(f.source)).length;
    const manual = total - auto;
    return { total, active, auto, manual };
  }, [facts]);

  const filtered = useMemo(() => {
    return facts.filter((f) => {
      if (categoryFilter !== "all" && f.category !== categoryFilter) return false;
      if (sourceFilter === "auto" && !isAuto(f.source)) return false;
      if (sourceFilter === "manual" && isAuto(f.source)) return false;
      return true;
    });
  }, [facts, categoryFilter, sourceFilter]);

  const pinnedFacts = filtered.filter((f) => f.is_pinned);
  const regularFacts = filtered.filter((f) => !f.is_pinned);

  const memoryEnabled = settingsQuery.data?.memory_enabled ?? false;

  // ---- Loading / unauth fallback ----
  if (settingsQuery.isLoading) {
    return (
      <div className="flex h-[calc(100vh-56px)] items-center justify-center text-[14px] text-[rgba(13,13,13,0.45)]">
        Загрузка...
      </div>
    );
  }

  if (settingsQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-8 text-center">
          <p className="text-[14px] text-[rgba(13,13,13,0.55)]">
            Не удалось загрузить память. Войдите в аккаунт и попробуйте снова.
          </p>
          <Link
            href="/account/"
            className="mt-4 inline-flex items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[14px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            <ArrowLeft size={16} />В кабинет
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      {/* Header */}
      <div className="mb-2">
        <Link
          href="/account/"
          className="inline-flex items-center gap-1.5 text-[13px] text-[rgba(13,13,13,0.5)] hover:text-[#0d0d0d] transition-colors"
        >
          <ArrowLeft size={16} />
          Личный кабинет
        </Link>
      </div>

      <div className="mb-8 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[rgba(13,13,13,0.05)] text-[#0d0d0d]">
            <Brain size={24} />
          </div>
          <div>
            <h1 className="text-[24px] font-bold text-[#0d0d0d]">
              Долговременная память
            </h1>
            <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.55)]">
              Факты о вас и краткие итоги сессий, которые модель учитывает в новых
              чатах.
            </p>
          </div>
        </div>

        {/* Global toggle */}
        <button
          type="button"
          role="switch"
          aria-checked={memoryEnabled}
          disabled={settingsMutation.isPending}
          onClick={() => settingsMutation.mutate(!memoryEnabled)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
            memoryEnabled ? "bg-[#0d0d0d]" : "bg-[rgba(13,13,13,0.18)]"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              memoryEnabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </div>

      {!memoryEnabled ? (
        /* ---- Disabled empty state ---- */
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-10 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[12px] bg-[rgba(13,13,13,0.05)] text-[rgba(13,13,13,0.55)]">
            <Brain size={24} />
          </div>
          <h2 className="mb-2 text-[18px] font-semibold text-[#0d0d0d]">
            Память отключена
          </h2>
          <p className="mx-auto mb-6 max-w-md text-[14px] text-[rgba(13,13,13,0.55)]">
            Включите долговременную память, чтобы модель запоминала важные факты о
            вас и краткие итоги диалогов между сессиями.
          </p>
          <button
            type="button"
            disabled={settingsMutation.isPending}
            onClick={() => settingsMutation.mutate(true)}
            className="inline-flex items-center gap-2 rounded-[8px] bg-[#0d0d0d] px-4 py-2 text-[14px] text-white hover:bg-[#333] transition-colors disabled:opacity-50"
          >
            <Sparkles size={16} />
            Включить память
          </button>
        </div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="mb-6 grid grid-cols-3 gap-3">
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#0d0d0d]">{stats.total}</p>
              <p className="text-[12px] text-[rgba(13,13,13,0.55)]">всего фактов</p>
            </div>
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#0d0d0d]">{stats.auto}</p>
              <p className="text-[12px] text-[rgba(13,13,13,0.55)]">авто</p>
            </div>
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#0d0d0d]">{stats.manual}</p>
              <p className="text-[12px] text-[rgba(13,13,13,0.55)]">вручную</p>
            </div>
          </div>

          {/* ============ Section 1: Facts ============ */}
          <section className="mb-10">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold text-[#0d0d0d]">Факты</h2>
              <button
                type="button"
                onClick={() => setShowForm((v) => !v)}
                className="inline-flex items-center gap-2 rounded-[8px] bg-[#0d0d0d] px-4 py-2 text-[14px] text-white hover:bg-[#333] transition-colors"
              >
                {showForm ? <X size={16} /> : <Plus size={16} />}
                {showForm ? "Отмена" : "Добавить факт"}
              </button>
            </div>

            {/* Add form */}
            {showForm && (
              <div className="mb-5 rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="Например: Я backend-разработчик, пишу на Python и предпочитаю краткие ответы."
                  rows={3}
                  className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[14px] text-[#0d0d0d] outline-none placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#0d0d0d]"
                />
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <select
                    value={newCategory}
                    onChange={(e) =>
                      setNewCategory(e.target.value as MemoryCategory)
                    }
                    className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[14px] text-[#0d0d0d] outline-none focus:border-[#0d0d0d]"
                  >
                    {CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!newContent.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                    className="inline-flex items-center gap-2 rounded-[8px] bg-[#0d0d0d] px-4 py-2 text-[14px] text-white hover:bg-[#333] transition-colors disabled:opacity-50"
                  >
                    <Check size={16} />
                    Сохранить
                  </button>
                  {createMutation.isError && (
                    <span className="text-[13px] text-red-600">
                      Не удалось сохранить факт.
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Filters */}
            <div className="mb-4 space-y-3">
              <div className="flex flex-wrap gap-2">
                <FilterTab
                  active={categoryFilter === "all"}
                  onClick={() => setCategoryFilter("all")}
                >
                  Все
                </FilterTab>
                {CATEGORIES.map((c) => (
                  <FilterTab
                    key={c.value}
                    active={categoryFilter === c.value}
                    onClick={() => setCategoryFilter(c.value)}
                  >
                    {c.label}
                  </FilterTab>
                ))}
              </div>
              <div className="flex flex-wrap gap-2">
                <FilterTab
                  active={sourceFilter === "all"}
                  onClick={() => setSourceFilter("all")}
                >
                  Все источники
                </FilterTab>
                <FilterTab
                  active={sourceFilter === "auto"}
                  onClick={() => setSourceFilter("auto")}
                >
                  Авто
                </FilterTab>
                <FilterTab
                  active={sourceFilter === "manual"}
                  onClick={() => setSourceFilter("manual")}
                >
                  Вручную
                </FilterTab>
              </div>
            </div>

            {/* Facts list */}
            {factsQuery.isLoading ? (
              <p className="py-8 text-center text-[14px] text-[rgba(13,13,13,0.45)]">
                Загрузка фактов...
              </p>
            ) : filtered.length === 0 ? (
              <div className="rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] bg-white px-4 py-10 text-center">
                <p className="text-[14px] text-[rgba(13,13,13,0.55)]">
                  {facts.length === 0
                    ? "Пока нет фактов. Они появятся автоматически по мере общения или добавьте вручную."
                    : "Нет фактов по выбранным фильтрам."}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {pinnedFacts.length > 0 && (
                  <div>
                    <div className="mb-2 flex items-center gap-1.5 text-[12px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                      <Pin size={12} />
                      Закреплённые
                    </div>
                    <div className="space-y-2">
                      {pinnedFacts.map((fact) => (
                        <FactCard
                          key={fact.id}
                          fact={fact}
                          onToggleActive={() =>
                            updateMutation.mutate({
                              id: fact.id,
                              data: { is_active: !fact.is_active },
                            })
                          }
                          onTogglePin={() =>
                            updateMutation.mutate({
                              id: fact.id,
                              data: { is_pinned: !fact.is_pinned },
                            })
                          }
                          onDelete={() => deleteMutation.mutate(fact.id)}
                          busy={updateMutation.isPending || deleteMutation.isPending}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {regularFacts.length > 0 && (
                  <div className="space-y-2">
                    {pinnedFacts.length > 0 && (
                      <div className="mb-2 text-[12px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                        Остальные
                      </div>
                    )}
                    {regularFacts.map((fact) => (
                      <FactCard
                        key={fact.id}
                        fact={fact}
                        onToggleActive={() =>
                          updateMutation.mutate({
                            id: fact.id,
                            data: { is_active: !fact.is_active },
                          })
                        }
                        onTogglePin={() =>
                          updateMutation.mutate({
                            id: fact.id,
                            data: { is_pinned: !fact.is_pinned },
                          })
                        }
                        onDelete={() => deleteMutation.mutate(fact.id)}
                        busy={updateMutation.isPending || deleteMutation.isPending}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* ============ Section 2: Session history ============ */}
          <section className="mb-10">
            <h2 className="mb-4 text-[18px] font-semibold text-[#0d0d0d]">
              История сессий
            </h2>
            {summariesQuery.isLoading ? (
              <p className="py-8 text-center text-[14px] text-[rgba(13,13,13,0.45)]">
                Загрузка истории...
              </p>
            ) : (summariesQuery.data ?? []).filter((s) => s.best_summary || s.rolling_summary).length === 0 ? (
              <div className="rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] bg-white px-4 py-10 text-center">
                <p className="text-[14px] text-[rgba(13,13,13,0.55)]">
                  Итоги сессий появятся после первого длинного диалога.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {(summariesQuery.data ?? []).filter((s) => s.best_summary || s.rolling_summary).slice(0, 20).map((s) => (
                  <SummaryCard
                    key={s.id}
                    summary={s}
                    expanded={!!expanded[s.id]}
                    onToggle={() =>
                      setExpanded((prev) => ({ ...prev, [s.id]: !prev[s.id] }))
                    }
                  />
                ))}
              </div>
            )}
          </section>

          {/* ============ Section 3: Management ============ */}
          <section className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-6">
            <div className="mb-4 flex items-center gap-2 text-[13px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.55)]">
              Управление
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-[14px] font-medium text-[#0d0d0d]">
                  Активные факты:{" "}
                  <span className="inline-flex items-center rounded-full bg-[rgba(13,13,13,0.06)] px-2 py-0.5 text-[13px]">
                    {stats.active}
                  </span>
                </p>
                <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.55)]">
                  Удаление авто-фактов уберёт только записи, добавленные
                  автоматически. Факты, добавленные вручную, сохранятся.
                </p>
              </div>
              {confirmClear ? (
                <div className="flex items-center gap-2">
                  <span className="text-[13px] text-[rgba(13,13,13,0.7)]">
                    Удалить все авто-факты?
                  </span>
                  <button
                    type="button"
                    disabled={clearMutation.isPending}
                    onClick={() => clearMutation.mutate()}
                    className="inline-flex items-center gap-1.5 rounded-[8px] bg-red-500 px-4 py-2 text-[14px] text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                  >
                    <Check size={16} />
                    Да, удалить
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmClear(false)}
                    className="inline-flex items-center rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[14px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
                  >
                    Отмена
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={stats.auto === 0}
                  onClick={() => setConfirmClear(true)}
                  className="inline-flex items-center gap-2 rounded-[8px] bg-red-500 px-4 py-2 text-[14px] text-white hover:bg-red-600 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 size={16} />
                  Удалить все авто-факты
                </button>
              )}
            </div>
            {clearMutation.isSuccess && (
              <p className="mt-3 text-[13px] text-[rgba(13,13,13,0.55)]">
                Удалено авто-фактов: {clearMutation.data?.deleted ?? 0}.
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

// ============ Sub-components ============

function FilterTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-[8px] px-3 py-1.5 text-[13px] transition-colors ${
        active
          ? "bg-[#0d0d0d] text-white"
          : "border border-[rgba(13,13,13,0.12)] bg-white text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)]"
      }`}
    >
      {children}
    </button>
  );
}

function FactCard({
  fact,
  onToggleActive,
  onTogglePin,
  onDelete,
  busy,
}: {
  fact: UserMemory;
  onToggleActive: () => void;
  onTogglePin: () => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const auto = isAuto(fact.source);
  return (
    <div
      className={`rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4 transition-opacity ${
        fact.is_active ? "" : "opacity-55"
      }`}
    >
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={onTogglePin}
          disabled={busy}
          aria-label={fact.is_pinned ? "Открепить" : "Закрепить"}
          className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] transition-colors disabled:opacity-50 ${
            fact.is_pinned
              ? "bg-amber-100 text-amber-600"
              : "text-[rgba(13,13,13,0.35)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d]"
          }`}
        >
          <Pin size={16} fill={fact.is_pinned ? "currentColor" : "none"} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-medium ${
                CATEGORY_BADGE[fact.category]
              }`}
            >
              {fact.category_display || CATEGORY_LABEL[fact.category]}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-medium ${
                auto
                  ? "bg-[rgba(13,13,13,0.06)] text-[rgba(13,13,13,0.55)]"
                  : "bg-blue-100 text-blue-700"
              }`}
            >
              {auto ? "Авто" : "Вручную"}
            </span>
          </div>
          <p className="text-[14px] leading-relaxed text-[#0d0d0d]">
            {fact.content}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {/* Active toggle */}
          <button
            type="button"
            role="switch"
            aria-checked={fact.is_active}
            aria-label="Активность факта"
            disabled={busy}
            onClick={onToggleActive}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
              fact.is_active ? "bg-[#0d0d0d]" : "bg-[rgba(13,13,13,0.18)]"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                fact.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
              }`}
            />
          </button>
          {/* Delete */}
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            aria-label="Удалить факт"
            className="flex h-7 w-7 items-center justify-center rounded-[8px] text-[rgba(13,13,13,0.4)] hover:bg-red-50 hover:text-red-600 transition-colors disabled:opacity-50"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

const SUMMARY_PREVIEW_LIMIT = 220;

function SummaryCard({
  summary,
  expanded,
  onToggle,
}: {
  summary: ChatSummary;
  expanded: boolean;
  onToggle: () => void;
}) {
  const displayText = summary.best_summary || summary.summary_text || summary.rolling_summary || '';
  const isLong = displayText.length > SUMMARY_PREVIEW_LIMIT;
  const text =
    expanded || !isLong
      ? displayText
      : `${displayText.slice(0, SUMMARY_PREVIEW_LIMIT).trimEnd()}…`;

  return (
    <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-[rgba(13,13,13,0.05)] text-[rgba(13,13,13,0.55)]">
            <MessageSquare size={16} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[14px] font-medium text-[#0d0d0d]">
              {summary.chat_title}
            </p>
            <p className="text-[12px] text-[rgba(13,13,13,0.5)]">
              {summary.network_name} · {summary.message_count} сообщ. ·{" "}
              {new Date(summary.created_at).toLocaleDateString("ru-RU")}
            </p>
          </div>
        </div>
      </div>
      <p className="text-[14px] leading-relaxed text-[rgba(13,13,13,0.75)]">
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={onToggle}
          className="mt-2 inline-flex items-center gap-1 text-[13px] text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d] transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp size={16} />
              Свернуть
            </>
          ) : (
            <>
              <ChevronDown size={16} />
              Показать полностью
            </>
          )}
        </button>
      )}
    </div>
  );
}
