"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { Search, CheckCircle, AlertCircle, Loader2, BookOpen } from "lucide-react";
import type { DeepResearchStep, DeepResearchStatus } from "@/lib/api/types";

const STEP_ICONS: Record<string, React.ReactNode> = {
  plan:       <Loader2 size={13} className="animate-spin text-[#D97757]" />,
  plan_done:  <CheckCircle size={13} className="text-[#16a34a]" />,
  search:     <Search size={13} className="text-[#D97757]" />,
  dedup:      <CheckCircle size={13} className="text-[#16a34a]" />,
  synthesize: <Loader2 size={13} className="animate-spin text-[#D97757]" />,
  done:       <CheckCircle size={13} className="text-[#16a34a]" />,
  error:      <AlertCircle size={13} className="text-red-500" />,
};

interface Props {
  steps: DeepResearchStep[];
  status: DeepResearchStatus;
  error?: string;
}

export function DeepResearchPanel({ steps, status, error }: Props) {
  const t = useTranslations("chat.deepResearchPanel");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps.length]);

  const isRunning = status === "pending" || status === "running";

  return (
    <div className="my-3 rounded-[12px] border border-[rgba(217,119,87,0.2)] bg-[rgba(217,119,87,0.03)]">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-[rgba(217,119,87,0.12)] px-3 py-2.5">
        <BookOpen size={13} className="text-[#D97757]" />
        <span className="text-[14px] font-semibold uppercase tracking-wide text-[#D97757]">
          {t("title")}
        </span>
        {isRunning && (
          <Loader2 size={11} className="ms-auto animate-spin text-[#D97757]" />
        )}
        {status === "done" && (
          <CheckCircle size={11} className="ms-auto text-[#16a34a]" />
        )}
        {status === "error" && (
          <AlertCircle size={11} className="ms-auto text-red-500" />
        )}
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-0 px-3 py-2">
        {steps.map((step, i) => (
          <div
            key={i}
            className="flex items-start gap-2 py-1 text-[14px] leading-snug text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]"
          >
            <span className="mt-0.5 shrink-0">
              {STEP_ICONS[step.kind] ?? <CheckCircle size={13} className="text-[rgba(13,13,13,0.35)]" />}
            </span>
            <span>{step.text}</span>
          </div>
        ))}
        {isRunning && steps.length === 0 && (
          <div className="flex items-center gap-2 py-2 text-[14px] text-[rgba(13,13,13,0.45)] dark:text-[rgba(236,236,236,0.4)]">
            <Loader2 size={12} className="animate-spin" />
            {t("starting")}
          </div>
        )}
        {status === "error" && error && (
          <div className="mt-1 rounded-[6px] bg-red-50 px-2 py-1.5 text-[13px] text-red-600 dark:bg-red-950/30 dark:text-red-400">
            {error}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
