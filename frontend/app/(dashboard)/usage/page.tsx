"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BarChart2, Zap, Wallet, Activity } from "lucide-react";
import { getUsageStats, listOrgs } from "@/lib/api/client";
import type { UsageStats, Organization } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";

const PERIOD_OPTIONS = [
  { label: "7 дней", value: 7 },
  { label: "30 дней", value: 30 },
  { label: "90 дней", value: 90 },
];

export default function UsagePage() {
  const [days, setDays] = useState(30);
  const [orgId, setOrgId] = useState<number | undefined>(undefined);

  const { data: orgs = [] } = useQuery<Organization[]>({
    queryKey: ["orgs"],
    queryFn: listOrgs,
    staleTime: 60_000,
  });

  const { data: stats, isLoading } = useQuery<UsageStats>({
    queryKey: ["usage", days, orgId],
    queryFn: () => getUsageStats({ days, org_id: orgId }),
    staleTime: 60_000,
  });

  const maxTokens =
    stats?.by_day.reduce((m, d) => Math.max(m, d.total_tokens), 1) ?? 1;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-8 flex items-center gap-3">
        <Link
          href="/account/"
          className="flex items-center gap-1 text-[15px] text-[rgba(13,13,13,0.5)] hover:text-[#1A1A1A] transition-colors"
        >
          <ArrowLeft size={14} />
          Кабинет
        </Link>
        <span className="text-[rgba(13,13,13,0.25)]">/</span>
        <h1 className="text-[20px] font-bold text-[#1A1A1A]">Статистика использования</h1>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={[
                "rounded-[6px] px-3 py-1.5 text-[15px] font-medium transition-all",
                days === opt.value
                  ? "bg-[#D97757] text-white"
                  : "text-[rgba(13,13,13,0.6)] hover:text-[#1A1A1A]",
              ].join(" ")}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {orgs.length > 0 && (
          <select
            value={orgId ?? ""}
            onChange={(e) => setOrgId(e.target.value ? Number(e.target.value) : undefined)}
            className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[15px] text-[rgba(13,13,13,0.7)] outline-none focus:border-[#D97757]"
          >
            <option value="">Мои запросы</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {isLoading ? (
        <div className="py-16 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
          Загрузка...
        </div>
      ) : !stats ? (
        <div className="py-16 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
          Нет данных
        </div>
      ) : (
        <>
          {/* Totals */}
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <TotalCard
              icon={<Zap size={18} />}
              label="Запросов"
              value={stats.totals.total_requests.toLocaleString("ru-RU")}
            />
            <TotalCard
              icon={<Activity size={18} />}
              label="Токенов"
              value={stats.totals.total_tokens.toLocaleString("ru-RU")}
            />
            <TotalCard
              icon={<Wallet size={18} />}
              label="Потрачено"
              value={formatMoney(stats.totals.total_kopecks)}
            />
          </div>

          {/* Daily chart (CSS bar chart) */}
          {stats.by_day.length > 0 && (
            <div className="mb-6 rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
              <p className="mb-4 text-[15px] font-semibold text-[#1A1A1A]">
                Токены по дням
              </p>
              <div className="flex items-end gap-1" style={{ height: "100px" }}>
                {stats.by_day.map((day) => {
                  const pct = maxTokens > 0 ? (day.total_tokens / maxTokens) * 100 : 0;
                  return (
                    <div
                      key={day.date}
                      className="group relative flex-1"
                      style={{ height: "100px" }}
                    >
                      <div
                        className="absolute bottom-0 left-0 right-0 rounded-t-[2px] bg-[#D97757] transition-all group-hover:bg-[#C4623E]"
                        style={{ height: `${Math.max(pct, 2)}%` }}
                      />
                      <div className="absolute bottom-full left-1/2 mb-1 hidden -translate-x-1/2 rounded-[4px] bg-[#1A1A1A] px-2 py-1 text-[12px] text-white group-hover:block whitespace-nowrap">
                        {day.date}: {day.total_tokens.toLocaleString("ru-RU")} tok
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-2 flex justify-between text-[12px] text-[rgba(13,13,13,0.35)]">
                <span>{stats.by_day[0]?.date}</span>
                <span>{stats.by_day[stats.by_day.length - 1]?.date}</span>
              </div>
            </div>
          )}

          {/* By model */}
          {stats.by_model.length > 0 && (
            <div className="rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
              <p className="mb-4 text-[15px] font-semibold text-[#1A1A1A]">
                По моделям (топ 20)
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-[15px]">
                  <thead>
                    <tr className="border-b border-[rgba(13,13,13,0.08)] text-left text-[13px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                      <th className="pb-2 pr-4">Модель</th>
                      <th className="pb-2 pr-4 text-right">Запросов</th>
                      <th className="pb-2 pr-4 text-right">Токенов</th>
                      <th className="pb-2 text-right">Потрачено</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.by_model.map((row) => (
                      <tr
                        key={row.model_slug}
                        className="border-b border-[rgba(13,13,13,0.05)] last:border-0"
                      >
                        <td className="py-2 pr-4 font-medium text-[#1A1A1A]">
                          <Link
                            href={`/models/${row.model_slug}/`}
                            className="hover:text-[#D97757] transition-colors"
                          >
                            {row.model_name}
                          </Link>
                        </td>
                        <td className="py-2 pr-4 text-right text-[rgba(13,13,13,0.65)]">
                          {row.requests.toLocaleString("ru-RU")}
                        </td>
                        <td className="py-2 pr-4 text-right text-[rgba(13,13,13,0.65)]">
                          {row.total_tokens.toLocaleString("ru-RU")}
                        </td>
                        <td className="py-2 text-right text-[rgba(13,13,13,0.65)]">
                          {formatMoney(row.cost_kopecks)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function TotalCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
        {icon}
      </div>
      <p className="mb-0.5 text-[24px] font-bold text-[#1A1A1A]">{value}</p>
      <p className="text-[14px] text-[rgba(13,13,13,0.5)]">{label}</p>
    </div>
  );
}
