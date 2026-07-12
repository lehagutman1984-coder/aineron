import type { MetadataRoute } from "next";
import { routing } from "@/i18n/routing";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/$/, "");

const ALLOW = ["/", "/models/", "/blog/", "/api-docs/", "/ide/"];
const DISALLOW = [
  "/api/",
  "/admin/",
  "/users/api/",
  "/aitext/",
  "/accounts/",
  "/account/",
  "/chat/",
  "/dashboard/",
];

// Не-дефолтные локали живут под /{locale}/... ("as-needed") — те же правила
// нужно продублировать с префиксом, иначе disallow-пути там не действуют.
function withLocalePrefixes(paths: string[]): string[] {
  const prefixed = routing.locales
    .filter((l) => l !== routing.defaultLocale)
    .flatMap((locale) => paths.map((p) => `/${locale}${p}`));
  return [...paths, ...prefixed];
}

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: withLocalePrefixes(ALLOW),
        disallow: withLocalePrefixes(DISALLOW),
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
