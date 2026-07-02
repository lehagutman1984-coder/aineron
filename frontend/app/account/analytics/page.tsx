"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus, Star, Zap, BarChart2 } from "lucide-react";
import { getStarsUsage } from "@/lib/api/client";
import type { StarsUsageDay, StarsUsageModel } from "@/lib/api/types";
import { formatRub } from "@/lib/money";

const PERIODS = [
  { label: "7 дней", value: 7 },
  { label: "30 дней", value: 30 },
  { label: "90 дней", value: 90 },
];

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);

  const { data, isLoading } = useQuery({
    queryKey: ["stars-usage", days],
    queryFn: () => getStarsUsage(days),
    staleTime: 2 * 60 * 1000,
  });

  const delta =
    data && data.prev_period.total_stars > 0
      ? Math.round(
          ((data.totals.total_stars - data.prev_period.total_stars) /
            data.prev_period.total_stars) *
            100
        )
      : null;

  return (
    <div className="py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-[22px] font-bold text-[#1A1A1A] dark:text-[#EDE8E3]">
            Аналитика
          </h1>
          <p className="mt-0.5 text-[15px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.40)]">
            Расходы звёзд по времени и моделям
          </p>
        </div>

        {/* Period selector */}
        <div className="flex rounded-[9px] border border-[rgba(13,13,13,0.12)] bg-white p-0.5 dark:border-[rgba(255,255,255,0.10)] dark:bg-[#1c1c1f]">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setDays(p.value)}
              className={[
                "rounded-[7px] px-3 py-1.5 text-[14px] font-medium transition-all",
                days === p.value
                  ? "bg-[#1A1A1A] text-white dark:bg-[#EDE8E3] dark:text-[#1A1A1A]"
                  : "text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.45)]",
              ].join(" ")}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stat cards */}
      <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard
          label="Потрачено"
          value={data?.totals.total_kopecks ?? 0}
          display={formatRub(data?.totals.total_kopecks ?? 0)}
          delta={delta}
          icon={<Star size={15} className="text-[#D97757]" />}
          loading={isLoading}
        />
        <StatCard
          label="Запросов отправлено"
          value={data?.totals.total_requests ?? 0}
          icon={<Zap size={15} className="text-[#D97757]" />}
          loading={isLoading}
        />
        <StatCard
          label="Среднее в день"
          value={data?.totals.avg_per_day_kopecks ?? 0}
          display={formatRub(data?.totals.avg_per_day_kopecks ?? 0)}
          icon={<BarChart2 size={15} className="text-[#D97757]" />}
          loading={isLoading}
        />
      </div>

      {/* Daily bar chart */}
      <div
        className="mb-6 rounded-[14px] border bg-white p-5 dark:bg-[#1C1917]"
        style={{ borderColor: "rgba(13,13,13,0.10)" }}
      >
        <h2 className="mb-4 text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
          Расход звёзд по дням
        </h2>
        {isLoading ? (
          <div className="h-40 animate-pulse rounded-[8px] bg-[rgba(13,13,13,0.05)]" />
        ) : !data || data.by_day.length === 0 ? (
          <EmptyChart />
        ) : (
          <BarChart days={data.by_day} period={days} />
        )}
      </div>

      {/* Top models */}
      <div
        className="rounded-[14px] border bg-white p-5 dark:bg-[#1C1917]"
        style={{ borderColor: "rgba(13,13,13,0.10)" }}
      >
        <h2 className="mb-4 text-[16px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
          Топ моделей по расходу
        </h2>
        {isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-[8px] bg-[rgba(13,13,13,0.05)]" />
            ))}
          </div>
        ) : !data || data.by_model.length === 0 ? (
          <p className="py-6 text-center text-[15px] text-[rgba(13,13,13,0.40)]">
            Нет данных за выбранный период
          </p>
        ) : (
          <ModelList models={data.by_model} />
        )}
      </div>
    </div>
  );
}

// ── Stat card ──────────────────────────────────────────────────────────────────
function StatCard({
  label, value, delta, suffix = "", display, icon, loading,
}: {
  label: string;
  value: number;
  delta?: number | null;
  suffix?: string;
  /** Готовая отформатированная строка (например, formatRub) — если задана, переопределяет value+suffix */
  display?: string;
  icon: React.ReactNode;
  loading: boolean;
}) {
  return (
    <div
      className="rounded-[14px] border bg-white p-4 dark:bg-[#1C1917]"
      style={{ borderColor: "rgba(13,13,13,0.10)" }}
    >
      <div className="mb-2 flex items-center gap-2">
        {icon}
        <span className="text-[14px] text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.40)]">
          {label}
        </span>
      </div>
      {loading ? (
        <div className="h-7 w-20 animate-pulse rounded-[6px] bg-[rgba(13,13,13,0.06)]" />
      ) : (
        <div className="flex items-end gap-2">
          <span className="text-[24px] font-bold leading-none text-[#1A1A1A] dark:text-[#EDE8E3]">
            {display ?? `${value.toLocaleString("ru-RU")}${suffix}`}
          </span>
          {delta != null && (
            <DeltaBadge delta={delta} />
          )}
        </div>
      )}
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0)
    return (
      <span className="mb-0.5 flex items-center gap-0.5 text-[13px] text-[rgba(13,13,13,0.40)]">
        <Minus size={10} /> 0%
      </span>
    );
  if (delta > 0)
    return (
      <span className="mb-0.5 flex items-center gap-0.5 text-[13px] text-[#22a85a]">
        <TrendingUp size={10} /> +{delta}%
      </span>
    );
  return (
    <span className="mb-0.5 flex items-center gap-0.5 text-[13px] text-[#e74c3c]">
      <TrendingDown size={10} /> {delta}%
    </span>
  );
}

// ── Bar chart (pure CSS) ───────────────────────────────────────────────────────
function BarChart({ days, period }: { days: StarsUsageDay[]; period: number }) {
  // Fill sparse data: create a map of date→row, then build full range
  const map = new Map(days.map((d) => [d.date, d]));

  // Compute start date from the earliest entry or period
  const now = new Date();
  const entries: StarsUsageDay[] = [];
  for (let i = period - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    entries.push(map.get(key) ?? { date: key, stars: 0, kopecks: 0, requests: 0 });
  }

  // Show at most 30 bars (group if period=90)
  const grouped = period > 30
    ? groupByWeek(entries)
    : entries;

  const maxGrouped = Math.max(...grouped.map((g) => g.kopecks), 1);

  return (
    <div className="flex h-40 items-end gap-[2px]">
      {grouped.map((entry) => {
        const pct = Math.max((entry.kopecks / maxGrouped) * 100, entry.kopecks > 0 ? 2 : 0);
        const label = formatDateLabel(entry.date, period);
        return (
          <div
            key={entry.date}
            className="group relative flex flex-1 flex-col items-center justify-end"
            title={`${label}: ${formatRub(entry.kopecks)}, ${entry.requests} запр.`}
          >
            <div
              className="w-full rounded-t-[3px] transition-all duration-200"
              style={{
                height: `${pct}%`,
                background: entry.kopecks > 0
                  ? "rgba(217,119,87,0.75)"
                  : "rgba(13,13,13,0.07)",
                minHeight: "2px",
              }}
            />
            {/* Tooltip */}
            {entry.kopecks > 0 && (
              <div className="pointer-events-none absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 z-10 hidden rounded-[7px] bg-[#1A1A1A] px-2 py-1 text-[12px] text-white whitespace-nowrap group-hover:block">
                {label}<br />{formatRub(entry.kopecks)}, {entry.requests} запр.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function groupByWeek(days: StarsUsageDay[]): StarsUsageDay[] {
  const weeks: Record<string, StarsUsageDay> = {};
  for (const d of days) {
    const date = new Date(d.date);
    const weekStart = new Date(date);
    weekStart.setDate(date.getDate() - date.getDay());
    const key = weekStart.toISOString().slice(0, 10);
    if (!weeks[key]) weeks[key] = { date: key, stars: 0, kopecks: 0, requests: 0 };
    weeks[key].stars += d.stars;
    weeks[key].kopecks += d.kopecks;
    weeks[key].requests += d.requests;
  }
  return Object.values(weeks).sort((a, b) => a.date.localeCompare(b.date));
}

function formatDateLabel(date: string, period: number) {
  const d = new Date(date + "T00:00:00");
  if (period <= 7) return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  if (period <= 30) return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  return `нед. ${d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}`;
}

// ── Top models list ────────────────────────────────────────────────────────────
function ModelList({ models }: { models: StarsUsageModel[] }) {
  const maxKopecks = Math.max(...models.map((m) => m.kopecks), 1);

  return (
    <div className="flex flex-col gap-2">
      {models.map((m, i) => {
        const pct = (m.kopecks / maxKopecks) * 100;
        return (
          <div key={m.name} className="flex items-center gap-3">
            <span className="w-4 shrink-0 text-right text-[13px] font-medium text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.28)]">
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="truncate text-[15px] text-[#1A1A1A] dark:text-[#EDE8E3]">
                  {m.name}
                </span>
                <span className="shrink-0 text-[14px] font-medium text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.45)]">
                  {formatRub(m.kopecks)}
                </span>
              </div>
              <div className="h-[5px] w-full overflow-hidden rounded-full bg-[rgba(13,13,13,0.07)] dark:bg-[rgba(255,255,255,0.07)]">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${pct}%`, background: "#D97757" }}
                />
              </div>
            </div>
            <span className="w-12 shrink-0 text-right text-[13px] text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.30)]">
              {m.requests} запр.
            </span>
          </div>
        );
      })}
    </div>
  );
}

function EmptyChart() {
  return (
    <div className="flex h-40 items-center justify-center">
      <p className="text-[15px] text-[rgba(13,13,13,0.40)]">
        Нет данных за выбранный период
      </p>
    </div>
  );
}
