import { getRequestConfig } from "next-intl/server";

/**
 * i18n-конфигурация (GLOBAL_EXPANSION_PLAN.md, фаза G2).
 *
 * Режим «без роутинга»: локаль инстанса фиксируется переменной окружения
 * NEXT_PUBLIC_DEFAULT_LOCALE (aineron.ru → "ru", международный инстанс → "en").
 * URL-структура не меняется. Переход на [locale]-роутинг с префиксами —
 * отдельный шаг G2 для международного инстанса.
 *
 * Словари: frontend/messages/{locale}.json (ICU Message Format).
 * Перевод: npm run translate-locales (LLM-пайплайн), проверка: npm run check-locales.
 */

export const SUPPORTED_LOCALES = ["ru", "en", "fa", "tr", "id", "ar"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export const RTL_LOCALES: readonly string[] = ["fa", "ar"];

export function resolveDefaultLocale(): AppLocale {
  const env = process.env.NEXT_PUBLIC_DEFAULT_LOCALE ?? "ru";
  return (SUPPORTED_LOCALES as readonly string[]).includes(env)
    ? (env as AppLocale)
    : "ru";
}

export default getRequestConfig(async () => {
  const locale = resolveDefaultLocale();
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
