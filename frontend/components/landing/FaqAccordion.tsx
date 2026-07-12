"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";

export function FaqAccordion() {
  const t = useTranslations("home");
  const FAQS = t.raw("faq") as { q: string; a: string }[];
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div className="flex flex-col divide-y" style={{ borderTop: "1px solid var(--border-tertiary)", borderBottom: "1px solid var(--border-tertiary)" }}>
      {FAQS.map((faq, i) => (
        <div key={i}>
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between gap-4 py-4 text-start"
          >
            <span className="text-[16px] font-medium text-[#1A1A1A]">{faq.q}</span>
            <ChevronDown
              size={16}
              className="shrink-0 text-[rgba(13,13,13,0.40)] transition-transform duration-200"
              style={{ transform: open === i ? "rotate(180deg)" : "none" }}
            />
          </button>
          {open === i && (
            <p className="pb-4 text-[16px] leading-relaxed text-[rgba(13,13,13,0.60)]">
              {faq.a}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
