/**
 * Единый источник истины для денежных величин на фронтенде.
 * Инвариант: 1 звезда (legacy) = 1 рубль = 100 копеек. См. src/core/money.py и BILLING_MIGRATION_PLAN.md
 */

export const KOPECKS_PER_RUB = 100;

export function kopecksToRub(kopecks: number): number {
  return Math.round(kopecks) / KOPECKS_PER_RUB;
}

export function rubToKopecks(rub: number): number {
  return Math.round(rub * KOPECKS_PER_RUB);
}

/**
 * 125000 -> "1 250 ₽" (целое — без дробной части)
 * 150    -> "1,50 ₽"  (дробное — с копейками, запятая как разделитель)
 */
export function formatRub(kopecks: number): string {
  const rub = kopecksToRub(kopecks);
  if (Number.isInteger(rub)) {
    return `${rub.toLocaleString("ru-RU")} ₽`;
  }
  return `${rub.toFixed(2).replace(".", ",")} ₽`;
}

/**
 * Валюта витрины инстанса (build-time):
 *   rub     — aineron.ru (рубли, как раньше)
 *   credits — международный инстанс (кредиты: 1 кредит = 1 внутренняя единица)
 */
export const CURRENCY = (process.env.NEXT_PUBLIC_CURRENCY ?? "rub") as
  | "rub"
  | "credits";

/** 50000 -> "50,000 credits" */
export function formatCredits(kopecks: number): string {
  return `${Math.round(kopecks).toLocaleString("en-US")} credits`;
}

/**
 * Универсальное форматирование денежной величины по валюте инстанса.
 * В rub-режиме идентична formatRub — на aineron.ru ничего не меняется.
 */
export function formatMoney(kopecks: number): string {
  return CURRENCY === "credits" ? formatCredits(kopecks) : formatRub(kopecks);
}
