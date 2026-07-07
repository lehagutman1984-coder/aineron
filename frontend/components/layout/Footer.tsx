import Link from "next/link";
import { useTranslations } from "next-intl";

const COLUMNS = [
  {
    key: "product",
    links: [
      { label: "catalog", href: "/models/" },
      { label: "compare", href: "/compare/" },
      { label: "gallery", href: "/gallery/" },
      { label: "projects", href: "/projects/" },
      { label: "prompts", href: "/prompts/" },
      { label: "personas", href: "/personas/" },
      { label: "arena", href: "/arena/" },
    ],
  },
  {
    key: "developers",
    links: [
      { label: "docs", href: "/docs/" },
      { label: "api", href: "/api-docs/" },
      { label: "sandboxes", href: "/sandbox/" },
      { label: "playground", href: "/api-docs/playground/" },
      { label: "ide", href: "/ide/" },
      { label: "account", href: "/account/" },
    ],
  },
  {
    key: "company",
    links: [
      { label: "blog", href: "/blog/" },
      { label: "privacy", href: "/privacy-policy/" },
      { label: "terms", href: "/terms/" },
    ],
  },
] as const;

export function Footer() {
  const t = useTranslations("footer");
  return (
    <footer className="border-t border-[rgba(13,13,13,0.10)] bg-white dark:border-[rgba(255,255,255,0.08)] dark:bg-[#1C1917]">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
          {/* Brand */}
          <div className="col-span-2 sm:col-span-1">
            <Link
              href="/"
              className="text-[17px] font-semibold text-[#1A1A1A] dark:text-[#EDE8E3]"
            >
              aineron.ru
            </Link>
            <p className="mt-2 text-[15px] leading-relaxed text-[rgba(13,13,13,0.50)] dark:text-[rgba(236,236,236,0.40)]">
              {t("description")}
            </p>
          </div>

          {/* Columns */}
          {COLUMNS.map((col) => (
            <div key={col.key}>
              <p className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.35)]">
                {t(`${col.key}.title`)}
              </p>
              <ul className="flex flex-col gap-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-[15px] text-[rgba(13,13,13,0.65)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.50)] dark:hover:text-[#EDE8E3]"
                    >
                      {t(`${col.key}.${link.label}`)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-[rgba(13,13,13,0.08)] pt-6 dark:border-[rgba(255,255,255,0.07)] sm:flex-row">
          <div className="flex flex-col gap-1 text-center sm:text-left">
            <p className="text-[14px] text-[rgba(13,13,13,0.40)] dark:text-[rgba(236,236,236,0.30)]">
              &copy; {new Date().getFullYear()} aineron.ru
            </p>
            <p className="text-[13px] text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.25)]">
              {t("legal")} ·{" "}
              <a
                href="mailto:support@aineron.ru"
                className="transition-colors hover:text-[#1A1A1A] dark:hover:text-[#EDE8E3]"
              >
                support@aineron.ru
              </a>
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/privacy-policy/"
              className="text-[14px] text-[rgba(13,13,13,0.40)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.30)] dark:hover:text-[#EDE8E3]"
            >
              {t("privacyShort")}
            </Link>
            <Link
              href="/terms/"
              className="text-[14px] text-[rgba(13,13,13,0.40)] transition-colors hover:text-[#1A1A1A] dark:text-[rgba(236,236,236,0.30)] dark:hover:text-[#EDE8E3]"
            >
              {t("termsShort")}
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
