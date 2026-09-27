import type { Metadata } from "next";
import { routing } from "@/i18n/routing";

/**
 * SEO-хелперы: canonical и hreflang.
 *
 * Реальные URL сайта БЕЗ завершающего слеша: `/models` отдаёт 200, а `/models/` - 308 на
 * `/models` (Next.js по умолчанию). Раньше sitemap.xml и часть canonical перечисляли адреса
 * со слешем, то есть каждый URL карты сайта сам был редиректом. Все адреса строятся здесь.
 *
 * "as-needed": дефолтная локаль инстанса - без префикса, остальные - /{locale}.
 * aineron.ru: одна локаль - только canonical; aineron.net: canonical + hreflang для всех
 * включённых локалей и x-default.
 */
export const SEO_SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/+$/, "");

/** "/models/" -> "/models"; "/" и "" -> "" (корень). */
function normalizePath(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return p.replace(/\/+$/, "");
}

/** Абсолютный канонический URL страницы `path` для локали `locale`. */
export function localizedUrl(locale: string, path: string): string {
  const prefix = locale === routing.defaultLocale ? "" : `/${locale}`;
  const tail = `${prefix}${normalizePath(path)}`;
  return `${SEO_SITE_URL}${tail || "/"}`;
}

/** alternates для generateMetadata: canonical на себя + hreflang на все локали инстанса. */
export function pageAlternates(locale: string, path: string): NonNullable<Metadata["alternates"]> {
  const canonical = localizedUrl(locale, path);
  if (routing.locales.length < 2) return { canonical };
  const languages: Record<string, string> = {};
  for (const l of routing.locales) {
    languages[l] = localizedUrl(l, path);
  }
  languages["x-default"] = localizedUrl(routing.defaultLocale, path);
  return { canonical, languages };
}
