"use client";

import { useEffect, useRef, useState } from "react";
import { Globe } from "lucide-react";
import { useLocale } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { ENABLED_LOCALES, localeLabel, type AppLocale } from "@/i18n/routing";

export function LocaleSwitcher({ variant = "desktop" }: { variant?: "desktop" | "mobile" }) {
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  // Один язык на инстансе (aineron.ru) — переключать нечего.
  if (ENABLED_LOCALES.length <= 1) return null;

  const handleSelect = (next: AppLocale) => {
    setOpen(false);
    if (next !== locale) router.replace(pathname, { locale: next });
  };

  if (variant === "mobile") {
    return (
      <div className="flex flex-wrap gap-1.5 py-2">
        {ENABLED_LOCALES.map((l) => (
          <button
            key={l}
            type="button"
            onClick={() => handleSelect(l)}
            className={[
              "rounded-[8px] px-3 py-1.5 text-[14px] font-medium transition-colors",
              l === locale
                ? "bg-[#1A1A1A] text-white dark:bg-[#EDE8E3] dark:text-[#1A1A1A]"
                : "text-[rgba(13,13,13,0.60)] hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.55)] dark:hover:bg-[rgba(255,255,255,0.07)]",
            ].join(" ")}
          >
            {localeLabel(l)}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Change language"
        aria-expanded={open}
        className="flex h-8 items-center gap-1.5 rounded-[8px] px-2 text-[14px] text-[rgba(13,13,13,0.55)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.50)] dark:hover:bg-[rgba(255,255,255,0.07)] dark:hover:text-[#EDE8E3]"
      >
        <Globe size={15} />
        <span className="uppercase">{locale}</span>
      </button>

      {open && (
        <div className="absolute end-0 z-50 mt-1 min-w-[140px] overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white py-1 shadow-lg dark:border-[rgba(255,255,255,0.10)] dark:bg-[#1C1917]">
          {ENABLED_LOCALES.map((l) => (
            <button
              key={l}
              type="button"
              onClick={() => handleSelect(l)}
              className={[
                "block w-full px-3 py-2 text-start text-[14px] transition-colors",
                l === locale
                  ? "font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]"
                  : "text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.06)] dark:text-[rgba(236,236,236,0.55)] dark:hover:bg-[rgba(255,255,255,0.07)]",
              ].join(" ")}
            >
              {localeLabel(l)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
