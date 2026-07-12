import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

/**
 * i18n-конфигурация (GLOBAL_EXPANSION_PLAN.md, фаза G4 — [locale]-роутинг).
 * Локаль резолвится из URL-сегмента через middleware (см. middleware.ts,
 * i18n/routing.ts) — requestLocale отражает уже провалидированный next-intl'ом
 * сегмент (или routing.defaultLocale, если сегмент не совпал).
 *
 * Словари: frontend/messages/{locale}.json (ICU Message Format).
 * Перевод: npm run translate-locales (LLM-пайплайн), проверка: npm run check-locales.
 */
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale =
    requested && (routing.locales as readonly string[]).includes(requested)
      ? requested
      : routing.defaultLocale;

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
