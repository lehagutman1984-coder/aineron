"use client";

import { useState, useEffect, type ReactNode } from "react";
import { Link } from "@/i18n/navigation";

import { ChevronDown, BookOpen } from "lucide-react";

export interface DocItem {
  id: string;
  label: string;
  content: ReactNode;
}
export interface DocGroup {
  title: string;
  items: DocItem[];
}

/**
 * DocLayout — оболочка документации со стойким сайдбаром-вкладками.
 * Клик по пункту переключает содержимое (без перезагрузки), синхронизирует #hash.
 * Адаптив: на мобильных сайдбар превращается в выпадающий селектор.
 * Полная поддержка тёмной темы проекта.
 */
export function DocLayout({
  eyebrow,
  title,
  subtitle,
  breadcrumb,
  groups,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  breadcrumb?: { label: string; href?: string }[];
  groups: DocGroup[];
}) {
  const allItems = groups.flatMap((g) => g.items);
  const [active, setActive] = useState(allItems[0]?.id ?? "");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash && allItems.some((i) => i.id === hash)) setActive(hash);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const select = (id: string) => {
    setActive(id);
    setMobileOpen(false);
    try {
      window.history.replaceState(null, "", `#${id}`);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      /* no-op */
    }
  };

  const current = allItems.find((i) => i.id === active) ?? allItems[0];
  const currentLabel = current?.label ?? "";

  return (
    <div className="min-h-screen bg-[#FAF9F7] dark:bg-[#1C1917]">
      {/* Header band */}
      <div className="border-b border-[rgba(13,13,13,0.08)] dark:border-[rgba(255,255,255,0.07)]">
        <div className="mx-auto max-w-6xl px-4 py-9 sm:px-6">
          {breadcrumb && (
            <nav className="mb-3 flex flex-wrap items-center gap-2 text-[14px]">
              {breadcrumb.map((b, i) => (
                <span key={i} className="flex items-center gap-2">
                  {b.href ? (
                    <Link
                      href={b.href}
                      className="text-[rgba(13,13,13,0.45)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.42)] dark:hover:text-[#EDE8E3]"
                    >
                      {b.label}
                    </Link>
                  ) : (
                    <span className="text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]">
                      {b.label}
                    </span>
                  )}
                  {i < breadcrumb.length - 1 && (
                    <span className="text-[rgba(13,13,13,0.25)] dark:text-[rgba(255,255,255,0.2)]">
                      /
                    </span>
                  )}
                </span>
              ))}
            </nav>
          )}
          {eyebrow && (
            <p className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-[#D97757]">
              {eyebrow}
            </p>
          )}
          <h1 className="text-[30px] font-bold leading-tight text-[#1A1A1A] dark:text-[#EDE8E3] sm:text-[34px]">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-3 max-w-3xl text-[17px] leading-relaxed text-[rgba(13,13,13,0.55)] dark:text-[rgba(236,236,236,0.55)]">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      <div className="mx-auto flex max-w-6xl gap-8 px-4 py-8 sm:px-6">
        {/* Sidebar — desktop */}
        <aside className="hidden w-64 shrink-0 lg:block">
          <nav className="sticky top-[76px] max-h-[calc(100vh-96px)] overflow-y-auto pb-8">
            {groups.map((g) => (
              <div key={g.title} className="mb-5">
                <p className="mb-1.5 px-3 text-[12px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.38)]">
                  {g.title}
                </p>
                <div className="flex flex-col gap-0.5">
                  {g.items.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => select(item.id)}
                      className={[
                        "rounded-[8px] px-3 py-1.5 text-start text-[15px] transition-colors",
                        item.id === active
                          ? "bg-[rgba(217,119,87,0.1)] font-medium text-[#D97757]"
                          : "text-[rgba(13,13,13,0.62)] hover:bg-[rgba(13,13,13,0.045)] hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.6)] dark:hover:bg-[rgba(255,255,255,0.05)] dark:hover:text-[#EDE8E3]",
                      ].join(" ")}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <div className="min-w-0 flex-1">
          {/* Mobile selector */}
          <div className="mb-5 lg:hidden">
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="flex w-full items-center justify-between rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-white px-4 py-3 text-[16px] font-medium text-[#1A1A1A] dark:border-[rgba(255,255,255,0.1)] dark:bg-[#211E1B] dark:text-[#EDE8E3]"
            >
              <span className="flex items-center gap-2">
                <BookOpen size={16} className="text-[#D97757]" />
                {currentLabel}
              </span>
              <ChevronDown
                size={18}
                className={`text-[rgba(13,13,13,0.4)] transition-transform dark:text-[rgba(236,236,236,0.4)] ${
                  mobileOpen ? "rotate-180" : ""
                }`}
              />
            </button>
            {mobileOpen && (
              <div className="mt-2 rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-white p-2 dark:border-[rgba(255,255,255,0.1)] dark:bg-[#211E1B]">
                {groups.map((g) => (
                  <div key={g.title} className="mb-3 last:mb-0">
                    <p className="mb-1 px-2 text-[12px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.38)]">
                      {g.title}
                    </p>
                    {g.items.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => select(item.id)}
                        className={[
                          "block w-full rounded-[8px] px-2 py-1.5 text-start text-[15px] transition-colors",
                          item.id === active
                            ? "bg-[rgba(217,119,87,0.1)] font-medium text-[#D97757]"
                            : "text-[rgba(13,13,13,0.7)] dark:text-[rgba(236,236,236,0.65)]",
                        ].join(" ")}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-6">{current?.content}</div>
        </div>
      </div>
    </div>
  );
}
