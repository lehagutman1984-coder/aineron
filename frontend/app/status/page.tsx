"use client";

import { useEffect, useState } from "react";
import { CheckCircle, XCircle, AlertCircle, RefreshCw } from "lucide-react";

interface ServiceCheck {
  status: "operational" | "degraded" | "unknown";
  latency_ms?: number;
  error?: string;
  active_models?: number;
}

interface StatusData {
  status: "operational" | "degraded";
  checks: {
    database?: ServiceCheck;
    cache?: ServiceCheck;
    upstream?: ServiceCheck;
  };
  timestamp: number;
}

const SERVICES: { key: keyof StatusData["checks"]; label: string }[] = [
  { key: "database", label: "База данных" },
  { key: "cache", label: "Кэш / очередь (Redis)" },
  { key: "upstream", label: "AI-сервис" },
];

function StatusIcon({ status }: { status: string }) {
  if (status === "operational")
    return <CheckCircle size={18} className="text-green-500 shrink-0" />;
  if (status === "degraded")
    return <XCircle size={18} className="text-red-500 shrink-0" />;
  return <AlertCircle size={18} className="text-yellow-500 shrink-0" />;
}

export default function StatusPage() {
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/status/");
      if (res.ok) {
        const json = (await res.json()) as StatusData;
        setData(json);
        setLastRefreshed(new Date());
      }
    } catch {
      // network error — leave previous data
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 60_000);
    return () => clearInterval(interval);
  }, []);

  const overall = data?.status ?? "unknown";

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
      {/* Overall badge */}
      <div className="mb-10 text-center">
        <div
          className={[
            "mb-4 inline-flex items-center gap-2 rounded-full px-5 py-2 text-[15px] font-semibold",
            overall === "operational"
              ? "bg-green-50 text-green-700"
              : "bg-red-50 text-red-700",
          ].join(" ")}
        >
          <StatusIcon status={overall} />
          {overall === "operational" ? "Все системы работают" : "Есть проблемы"}
        </div>
        <h1 className="text-[28px] font-bold text-[#0d0d0d]">
          Статус aineron.ru
        </h1>
        <p className="mt-2 text-[14px] text-[rgba(13,13,13,0.5)]">
          Обновляется каждую минуту
          {lastRefreshed && ` · Последнее: ${lastRefreshed.toLocaleTimeString("ru-RU")}`}
        </p>
      </div>

      {/* Services list */}
      <div className="mb-6 overflow-hidden rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white">
        {SERVICES.map((svc, idx) => {
          const check = data?.checks[svc.key];
          return (
            <div
              key={svc.key}
              className={[
                "flex items-center justify-between px-5 py-4",
                idx < SERVICES.length - 1
                  ? "border-b border-[rgba(13,13,13,0.06)]"
                  : "",
              ].join(" ")}
            >
              <div className="flex items-center gap-3">
                <StatusIcon status={check?.status ?? "unknown"} />
                <span className="text-[14px] font-medium text-[#0d0d0d]">
                  {svc.label}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[13px] text-[rgba(13,13,13,0.5)]">
                {check?.latency_ms !== undefined && (
                  <span>{check.latency_ms} мс</span>
                )}
                {check?.active_models !== undefined && (
                  <span>{check.active_models} моделей</span>
                )}
                {check?.error && (
                  <span className="text-red-500">{check.error}</span>
                )}
                <span className="capitalize">
                  {check?.status === "operational"
                    ? "Работает"
                    : check?.status === "degraded"
                    ? "Сбой"
                    : "Неизвестно"}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={fetchStatus}
        disabled={loading}
        className="flex items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-4 py-2 text-[13px] font-medium text-[rgba(13,13,13,0.7)] transition-all hover:border-[rgba(13,13,13,0.3)] disabled:opacity-50"
      >
        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
        Обновить
      </button>
    </div>
  );
}
