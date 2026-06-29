"use client";

import { useEffect, useState } from "react";
import { Brain, X } from "lucide-react";

interface Props {
  count: number;
  facts: string[];
  onDismiss: () => void;
}

export function MemoryToast({ count, facts, onDismiss }: Props) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const showTimer = setTimeout(() => setVisible(true), 50);
    const hideTimer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 300);
    }, 4000);
    return () => {
      clearTimeout(showTimer);
      clearTimeout(hideTimer);
    };
  }, [onDismiss]);

  return (
    <div
      className={[
        "fixed bottom-24 right-5 z-50 flex max-w-[280px] items-start gap-2.5 rounded-[12px] border border-[rgba(124,58,237,0.2)] bg-white px-3.5 py-3 shadow-lg transition-all duration-300 dark:bg-[#1a1a1a]",
        visible ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0",
      ].join(" ")}
    >
      <Brain size={15} className="mt-0.5 shrink-0 text-[#7c3aed]" />
      <div className="min-w-0 flex-1">
        <div className="text-[12px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]">
          Запомнено: {count} {count === 1 ? "факт" : count < 5 ? "факта" : "фактов"}
        </div>
        {facts.length > 0 && (
          <div className="mt-1 flex flex-col gap-0.5">
            {facts.slice(0, 3).map((f, i) => (
              <div
                key={i}
                className="truncate text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]"
              >
                — {f}
              </div>
            ))}
          </div>
        )}
      </div>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(onDismiss, 300);
        }}
        className="shrink-0 text-[rgba(13,13,13,0.35)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.3)]"
      >
        <X size={12} />
      </button>
    </div>
  );
}
