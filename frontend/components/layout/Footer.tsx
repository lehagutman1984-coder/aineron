import Link from "next/link";

const COLUMNS = [
  {
    title: "Продукт",
    links: [
      { label: "Каталог моделей", href: "/models/" },
      { label: "Сравнение моделей", href: "/compare/" },
      { label: "Проекты", href: "/projects/" },
      { label: "Промты", href: "/prompts/" },
      { label: "Статус сервиса", href: "/status/" },
    ],
  },
  {
    title: "Разработчикам",
    links: [
      { label: "API документация", href: "/api-docs/" },
      { label: "IDE интеграция", href: "/ide/" },
      { label: "Личный кабинет", href: "/account/" },
    ],
  },
  {
    title: "Компания",
    links: [
      { label: "Блог", href: "/blog/" },
      { label: "Политика конфиденциальности", href: "/privacy-policy/" },
      { label: "Условия использования", href: "/terms/" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-[rgba(13,13,13,0.10)] bg-white dark:border-[rgba(255,255,255,0.08)] dark:bg-[#111113]">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {/* Brand */}
          <div className="col-span-2 sm:col-span-1">
            <Link
              href="/"
              className="text-[15px] font-semibold text-[#0d0d0d] dark:text-[#ececec]"
            >
              aineron.ru
            </Link>
            <p className="mt-2 text-[13px] leading-relaxed text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.40)]">
              AI-нейросети без VPN. GPT-4o, Claude, Gemini и другие — в одном месте.
            </p>
          </div>

          {/* Columns */}
          {COLUMNS.map((col) => (
            <div key={col.title}>
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.35)]">
                {col.title}
              </p>
              <ul className="flex flex-col gap-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-[13px] text-[rgba(13,13,13,0.65)] transition-colors hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.50)] dark:hover:text-[#ececec]"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-[rgba(13,13,13,0.08)] pt-6 dark:border-[rgba(255,255,255,0.07)] sm:flex-row">
          <p className="text-[12px] text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.30)]">
            &copy; {new Date().getFullYear()} aineron.ru
          </p>
          <div className="flex items-center gap-4">
            <Link
              href="/privacy-policy/"
              className="text-[12px] text-[rgba(13,13,13,0.40)] transition-colors hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.30)] dark:hover:text-[#ececec]"
            >
              Конфиденциальность
            </Link>
            <Link
              href="/terms/"
              className="text-[12px] text-[rgba(13,13,13,0.40)] transition-colors hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.30)] dark:hover:text-[#ececec]"
            >
              Условия
            </Link>
            <Link
              href="/status/"
              className="text-[12px] text-[rgba(13,13,13,0.40)] transition-colors hover:text-[#0d0d0d] dark:text-[rgba(236,236,236,0.30)] dark:hover:text-[#ececec]"
            >
              Статус
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
