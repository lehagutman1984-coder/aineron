"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Layers } from "lucide-react";
import type { MessageVariant } from "@/lib/api/types";

interface Props {
  variants: MessageVariant[];
}

export function ResponseVariants({ variants }: Props) {
  const t = useTranslations("chat.responseVariants");
  const [activeIndex, setActiveIndex] = useState(0);

  if (!variants || variants.length < 1) return null;

  const active = variants[activeIndex];

  return (
    <div className="mt-3 rounded-[12px] border border-[rgba(217,119,87,0.18)] bg-[rgba(217,119,87,0.03)]">
      {/* Tab bar */}
      <div className="flex items-center gap-0.5 border-b border-[rgba(217,119,87,0.12)] px-3 py-2">
        <Layers size={13} className="mr-1.5 shrink-0 text-[#D97757]" />
        <span className="mr-3 text-[13px] font-semibold uppercase tracking-wide text-[#D97757]">
          {t("title")}
        </span>
        {variants.map((v, i) => (
          <button
            key={v.label}
            onClick={() => setActiveIndex(i)}
            className={[
              "rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors",
              i === activeIndex
                ? "bg-[#D97757] text-white"
                : "text-[#8B7E77] hover:bg-[rgba(217,119,87,0.08)] hover:text-[#D97757]",
            ].join(" ")}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Active variant content */}
      <div
        className="px-4 py-3 text-[16px] leading-relaxed"
        dangerouslySetInnerHTML={{ __html: active.content }}
      />
    </div>
  );
}
