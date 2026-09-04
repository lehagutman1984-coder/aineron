import type { UiSection } from "@/lib/api/types";

/**
 * Считает доплату за выбранные настройки медиа-генерации — зеркалит
 * validate_and_merge_settings() в src/aitext/fal_utils.py 1:1 (тот же обход
 * полей, та же логика по типам), чтобы фронтенд показывал ровно ту сумму,
 * которая реально спишется. Возвращает доплату в рублях (extra_cost в
 * config_json уже в рублях, см. src/aitext/tasks.py:739).
 */
export function calcExtraCostRub(
  sections: UiSection[] | undefined,
  values: Record<string, unknown>
): number {
  if (!sections) return 0;
  let extra = 0;
  for (const section of sections) {
    for (const field of section.fields) {
      const value = values[field.name];
      if (value === undefined || value === null) continue;

      if (field.type === "checkbox") {
        if (value) extra += field.extra_cost ?? 0;
      } else if (field.type === "select") {
        const opt = (field.options ?? []).find((o) => String(o.value) === String(value));
        if (opt) extra += opt.extra_cost ?? 0;
      } else if (field.type === "slider" || field.type === "number") {
        extra += field.extra_cost ?? 0;
      }
    }
  }
  return extra;
}

/** Итоговая цена генерации в копейках: база + доплата за выбранные настройки. */
export function calcTotalCostKopecks(
  baseCostKopecks: number,
  sections: UiSection[] | undefined,
  values: Record<string, unknown>
): number {
  return baseCostKopecks + Math.round(calcExtraCostRub(sections, values) * 100);
}
