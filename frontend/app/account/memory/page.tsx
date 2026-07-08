"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useTranslations, useLocale } from "next-intl";
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

type Translate = ReturnType<typeof useTranslations>;

function getCategories(t: Translate): { value: MemoryCategory; label: string }[] {
  return [
    { value: "profile", label: t("categoryProfile") },
    { value: "skill", label: t("categorySkill") },
    { value: "preference", label: t("categoryPreference") },
    { value: "project", label: t("categoryProject") },
    { value: "fact", label: t("categoryFact") },
  ];
}

const CATEGORY_BADGE: Record<MemoryCategory, string> = {
  profile: "bg-blue-100 text-blue-700",
  skill: "bg-purple-100 text-purple-700",
  preference: "bg-amber-100 text-amber-700",
  project: "bg-green-100 text-green-700",
  fact: "bg-slate-100 text-slate-700",
};

function getCategoryLabel(t: Translate, category: MemoryCategory): string {
  const map: Record<MemoryCategory, string> = {
    profile: t("categoryProfile"),
    skill: t("categorySkill"),
    preference: t("categoryPreference"),
    project: t("categoryProject"),
    fact: t("categoryFact"),
  };
  return map[category];
}

type CategoryFilter = "all" | MemoryCategory;
type SourceFilter = "all" | "auto" | "manual";

const isAuto = (source: string) => source === "auto";

export default function MemoryPage() {
  const t = useTranslations("accountMemory");
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
  const categories = getCategories(t);

  // ---- Loading / unauth fallback ----
  if (settingsQuery.isLoading) {
    return (
      <div className="flex h-[calc(100vh-56px)] items-center justify-center text-[16px] text-[rgba(13,13,13,0.45)]">
        {t("loading")}
      </div>
    );
  }

  if (settingsQuery.isError) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-8 text-center">
          <p className="text-[16px] text-[rgba(13,13,13,0.55)]">
            {t("loadError")}
          </p>
          <Link
            href="/account/"
            className="mt-4 inline-flex items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[16px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            <ArrowLeft size={16} />{t("backToAccount")}
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
          className="inline-flex items-center gap-1.5 text-[15px] text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-colors"
        >
          <ArrowLeft size={16} />
          {t("backToAccountLink")}
        </Link>
      </div>

      <div className="mb-8 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[rgba(13,13,13,0.05)] text-[#1A1A1A]">
            <Brain size={24} />
          </div>
          <div>
            <h1 className="text-[24px] font-bold text-[#1A1A1A]">
              {t("pageTitle")}
            </h1>
            <p className="mt-1 text-[16px] text-[rgba(13,13,13,0.55)]">
              {t("pageSubtitle")}
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
            memoryEnabled ? "bg-[#1A1A1A]" : "bg-[rgba(13,13,13,0.18)]"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-[#fff] transition-transform ${
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
          <h2 className="mb-2 text-[18px] font-semibold text-[#1A1A1A]">
            {t("disabledTitle")}
          </h2>
          <p className="mx-auto mb-6 max-w-md text-[16px] text-[rgba(13,13,13,0.55)]">
            {t("disabledDescription")}
          </p>
          <button
            type="button"
            disabled={settingsMutation.isPending}
            onClick={() => settingsMutation.mutate(true)}
            className="inline-flex items-center gap-2 rounded-[8px] bg-[#1A1A1A] px-4 py-2 text-[16px] text-white hover:bg-[#333] transition-colors disabled:opacity-50"
          >
            <Sparkles size={16} />
            {t("enableMemory")}
          </button>
        </div>
      ) : (
        <>
          {/* Stats bar */}
          <div className="mb-6 grid grid-cols-3 gap-3">
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#1A1A1A]">{stats.total}</p>
              <p className="text-[14px] text-[rgba(13,13,13,0.55)]">{t("statsTotal")}</p>
            </div>
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#1A1A1A]">{stats.auto}</p>
              <p className="text-[14px] text-[rgba(13,13,13,0.55)]">{t("statsAuto")}</p>
            </div>
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
              <p className="text-[22px] font-bold text-[#1A1A1A]">{stats.manual}</p>
              <p className="text-[14px] text-[rgba(13,13,13,0.55)]">{t("statsManual")}</p>
            </div>
          </div>

          {/* ============ Section 1: Facts ============ */}
          <section className="mb-10">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold text-[#1A1A1A]">{t("factsTitle")}</h2>
              <button
                type="button"
                onClick={() => setShowForm((v) => !v)}
                className="inline-flex items-center gap-2 rounded-[8px] bg-[#1A1A1A] px-4 py-2 text-[16px] text-white hover:bg-[#333] transition-colors"
              >
                {showForm ? <X size={16} /> : <Plus size={16} />}
                {showForm ? t("cancel") : t("addFact")}
              </button>
            </div>

            {/* Add form */}
            {showForm && (
              <div className="mb-5 rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder={t("factPlaceholder")}
                  rows={3}
                  className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[16px] text-[#1A1A1A] outline-none placeholder:text-[rgba(13,13,13,0.35)] focus:border-[#1A1A1A]"
                />
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <select
                    value={newCategory}
                    onChange={(e) =>
                      setNewCategory(e.target.value as MemoryCategory)
                    }
                    className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[16px] text-[#1A1A1A] outline-none focus:border-[#1A1A1A]"
                  >
                    {categories.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!newContent.trim() || createMutation.isPending}
                    onClick={() => createMutation.mutate()}
                    className="inline-flex items-center gap-2 rounded-[8px] bg-[#1A1A1A] px-4 py-2 text-[16px] text-white hover:bg-[#333] transition-colors disabled:opacity-50"
                  >
                    <Check size={16} />
                    {t("save")}
                  </button>
                  {createMutation.isError && (
                    <span className="text-[15px] text-red-600">
                      {t("saveFactError")}
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
                  {t("filterAll")}
                </FilterTab>
                {categories.map((c) => (
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
                  {t("filterAllSources")}
                </FilterTab>
                <FilterTab
                  active={sourceFilter === "auto"}
                  onClick={() => setSourceFilter("auto")}
                >
                  {t("autoLabel")}
                </FilterTab>
                <FilterTab
                  active={sourceFilter === "manual"}
                  onClick={() => setSourceFilter("manual")}
                >
                  {t("manualLabel")}
                </FilterTab>
              </div>
            </div>

            {/* Facts list */}
            {factsQuery.isLoading ? (
              <p className="py-8 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
                {t("loadingFacts")}
              </p>
            ) : factsQuery.isError ? (
              <div className="rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] bg-white px-4 py-10 text-center">
                <p className="text-[16px] text-[rgba(13,13,13,0.55)]">
                  {t("factsLoadError")}
                </p>
              </div>
            ) : filtered.length === 0 ? (
              <div className="rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] bg-white px-4 py-10 text-center">
                <p className="text-[16px] text-[rgba(13,13,13,0.55)]">
                  {facts.length === 0
                    ? t("noFactsYet")
                    : t("noFactsFiltered")}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {pinnedFacts.length > 0 && (
                  <div>
                    <div className="mb-2 flex items-center gap-1.5 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                      <Pin size={12} />
                      {t("pinnedSectionTitle")}
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
                      <div className="mb-2 text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                        {t("otherSectionTitle")}
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
            <h2 className="mb-4 text-[18px] font-semibold text-[#1A1A1A]">
              {t("historyTitle")}
            </h2>
            {summariesQuery.isLoading ? (
              <p className="py-8 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
                {t("loadingHistory")}
              </p>
            ) : (summariesQuery.data ?? []).filter((s) => s.best_summary || s.rolling_summary).length === 0 ? (
              <div className="rounded-[14px] border border-dashed border-[rgba(13,13,13,0.15)] bg-white px-4 py-10 text-center">
                <p className="text-[16px] text-[rgba(13,13,13,0.55)]">
                  {t("noHistoryYet")}
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
            <div className="mb-4 flex items-center gap-2 text-[15px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.55)]">
              {t("managementTitle")}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-[16px] font-medium text-[#1A1A1A]">
                  {t("activeFactsLabel")}{" "}
                  <span className="inline-flex items-center rounded-full bg-[rgba(13,13,13,0.06)] px-2 py-0.5 text-[15px]">
                    {stats.active}
                  </span>
                </p>
                <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.55)]">
                  {t("autoDeleteDescription")}
                </p>
              </div>
              {confirmClear ? (
                <div className="flex items-center gap-2">
                  <span className="text-[15px] text-[rgba(13,13,13,0.7)]">
                    {t("confirmClearAutoTitle")}
                  </span>
                  <button
                    type="button"
                    disabled={clearMutation.isPending}
                    onClick={() => clearMutation.mutate()}
                    className="inline-flex items-center gap-1.5 rounded-[8px] bg-red-500 px-4 py-2 text-[16px] text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                  >
                    <Check size={16} />
                    {t("confirmYesDelete")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmClear(false)}
                    className="inline-flex items-center rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[16px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
                  >
                    {t("cancel")}
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  disabled={stats.auto === 0}
                  onClick={() => setConfirmClear(true)}
                  className="inline-flex items-center gap-2 rounded-[8px] bg-red-500 px-4 py-2 text-[16px] text-white hover:bg-red-600 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 size={16} />
                  {t("deleteAllAutoFacts")}
                </button>
              )}
            </div>
            {clearMutation.isSuccess && (
              <p className="mt-3 text-[15px] text-[rgba(13,13,13,0.55)]">
                {t("deletedAutoFactsCount", { count: clearMutation.data?.deleted ?? 0 })}
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
      className={`rounded-[8px] px-3 py-1.5 text-[15px] transition-colors ${
        active
          ? "bg-[#1A1A1A] text-white"
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
  const t = useTranslations("accountMemory");
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
          aria-label={fact.is_pinned ? t("unpinFact") : t("pinFact")}
          className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] transition-colors disabled:opacity-50 ${
            fact.is_pinned
              ? "bg-amber-100 text-amber-600"
              : "text-[rgba(13,13,13,0.35)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A]"
          }`}
        >
          <Pin size={16} fill={fact.is_pinned ? "currentColor" : "none"} />
        </button>

        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[14px] font-medium ${
                CATEGORY_BADGE[fact.category]
              }`}
            >
              {fact.category_display || getCategoryLabel(t, fact.category)}
            </span>
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[14px] font-medium ${
                auto
                  ? "bg-[rgba(13,13,13,0.06)] text-[rgba(13,13,13,0.55)]"
                  : "bg-blue-100 text-blue-700"
              }`}
            >
              {auto ? t("autoLabel") : t("manualLabel")}
            </span>
          </div>
          <p className="text-[16px] leading-relaxed text-[#1A1A1A]">
            {fact.content}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {/* Active toggle */}
          <button
            type="button"
            role="switch"
            aria-checked={fact.is_active}
            aria-label={t("factActiveToggleLabel")}
            disabled={busy}
            onClick={onToggleActive}
            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors disabled:opacity-50 ${
              fact.is_active ? "bg-[#1A1A1A]" : "bg-[rgba(13,13,13,0.18)]"
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-[#fff] transition-transform ${
                fact.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
              }`}
            />
          </button>
          {/* Delete */}
          <button
            type="button"
            onClick={onDelete}
            disabled={busy}
            aria-label={t("deleteFactAriaLabel")}
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
  const t = useTranslations("accountMemory");
  const locale = useLocale();
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
            <p className="truncate text-[16px] font-medium text-[#1A1A1A]">
              {summary.chat_title}
            </p>
            <p className="text-[14px] text-[rgba(13,13,13,0.5)]">
              {summary.network_name} · {t("messageCountLabel", { count: summary.message_count })} ·{" "}
              {new Date(summary.created_at).toLocaleDateString(locale)}
            </p>
          </div>
        </div>
      </div>
      <p className="text-[16px] leading-relaxed text-[rgba(13,13,13,0.75)]">
        {text}
      </p>
      {isLong && (
        <button
          type="button"
          onClick={onToggle}
          className="mt-2 inline-flex items-center gap-1 text-[15px] text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp size={16} />
              {t("collapseSummary")}
            </>
          ) : (
            <>
              <ChevronDown size={16} />
              {t("expandSummary")}
            </>
          )}
        </button>
      )}
    </div>
  );
}
