export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";

export function siteHost(): string {
  return new URL(SITE_URL).host;
}

export function brandName(): string {
  const host = siteHost();
  return host.charAt(0).toUpperCase() + host.slice(1);
}

export function supportEmail(): string {
  return `support@${siteHost()}`;
}

/**
 * Локаль инстанса на этапе сборки (G2, режим i18n без роутинга).
 * Для строк на уровне модуля, где next-intl-хуки недоступны
 * (код-сэмплы, dynamic()-лоадеры). В компонентах — useTranslations.
 */
export const BUILD_LOCALE = process.env.NEXT_PUBLIC_DEFAULT_LOCALE ?? "ru";
export const IS_RU = BUILD_LOCALE === "ru";
