import { defineRouting } from "next-intl/routing";

/**
 * i18n-роутинг (GLOBAL_EXPANSION_PLAN.md, фаза G4).
 *
 * Локали и активные локали инстанса — не одно и то же:
 * - SUPPORTED_LOCALES — весь список, который умеет собрать проект (словари есть у всех).
 * - ENABLED_LOCALES — какие из них реально включены на ЭТОМ инстансе (env, build-time).
 *
 * aineron.ru: NEXT_PUBLIC_ENABLED_LOCALES не задан → только "ru". С одной локалью
 * `localePrefix: "as-needed"` никогда не добавляет префикс — все URL остаются как раньше
 * (/, /models/, /chat/... без /ru/). Это то, что делает миграцию безопасной для .ru.
 *
 * aineron.net: NEXT_PUBLIC_ENABLED_LOCALES=en,fa,tr,id,ar, NEXT_PUBLIC_DEFAULT_LOCALE=en →
 * "as-needed" оставляет en без префикса (совместимость с уже проиндексированными /models/...),
 * остальные локали получают /fa/, /tr/ и т.д.
 */
export const SUPPORTED_LOCALES = ["ru", "en", "fa", "tr", "id", "ar"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export const RTL_LOCALES: readonly string[] = ["fa", "ar"];

const LOCALE_LABELS: Record<AppLocale, string> = {
  ru: "Русский",
  en: "English",
  fa: "فارسی",
  tr: "Türkçe",
  id: "Indonesia",
  ar: "العربية",
};

export function localeLabel(locale: string): string {
  return LOCALE_LABELS[locale as AppLocale] ?? locale;
}

function isSupported(value: string): value is AppLocale {
  return (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

function resolveEnabledLocales(): AppLocale[] {
  const raw = process.env.NEXT_PUBLIC_ENABLED_LOCALES;
  if (!raw) return ["ru"];
  const parsed = raw
    .split(",")
    .map((s) => s.trim())
    .filter(isSupported);
  return parsed.length > 0 ? parsed : ["ru"];
}

function resolveDefaultLocale(enabled: AppLocale[]): AppLocale {
  const env = process.env.NEXT_PUBLIC_DEFAULT_LOCALE ?? "ru";
  const candidate = isSupported(env) ? env : "ru";
  return enabled.includes(candidate) ? candidate : enabled[0];
}

export const ENABLED_LOCALES = resolveEnabledLocales();
export const DEFAULT_LOCALE = resolveDefaultLocale(ENABLED_LOCALES);

export const routing = defineRouting({
  locales: ENABLED_LOCALES,
  defaultLocale: DEFAULT_LOCALE,
  localePrefix: "as-needed",
  localeDetection: ENABLED_LOCALES.length > 1,
});
