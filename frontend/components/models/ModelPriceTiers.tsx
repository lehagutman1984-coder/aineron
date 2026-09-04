import type { ModelConfigJson, UiField } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";
import { calcTotalCostKopecks } from "@/lib/utils/mediaCost";

/**
 * Таблица «цена по настройкам» на странице модели — строится напрямую из
 * реального config_json (не из статичных данных), так что всегда совпадает
 * с тем, что реально спишется в чате. Показывает только те select-поля, где
 * хотя бы одна опция имеет ненулевую доплату (resolution/mode/quality/duration
 * и т.п.) — декоративные поля вроде aspect_ratio/size (extra_cost везде 0)
 * в таблицу не попадают, иначе она разрастётся без пользы.
 */
export function ModelPriceTiers({
  configJson,
  costKopecks,
  title,
}: {
  configJson: ModelConfigJson | null | undefined;
  costKopecks: number;
  title: string;
}) {
  const sections = configJson?.ui_settings?.sections;
  if (!sections?.length) return null;

  const fields = sections.flatMap((s) => s.fields);
  const isPriced = (f: UiField) =>
    f.type === "select" && (f.options ?? []).some((o) => (o.extra_cost ?? 0) !== 0);

  const axes = fields.filter(isPriced).slice(0, 2);
  const checkboxNotes = fields.filter((f) => f.type === "checkbox" && (f.extra_cost ?? 0) !== 0);

  if (axes.length === 0 && checkboxNotes.length === 0) return null;

  const defaults = (configJson?.api_defaults ?? {}) as Record<string, unknown>;

  let rows: { labels: string[]; total: number }[] = [];
  if (axes.length === 2) {
    const [a, b] = axes;
    for (const optA of a.options ?? []) {
      for (const optB of b.options ?? []) {
        const values = { ...defaults, [a.name]: optA.value, [b.name]: optB.value };
        rows.push({
          labels: [optA.label, optB.label],
          total: calcTotalCostKopecks(costKopecks, sections, values),
        });
      }
    }
  } else if (axes.length === 1) {
    const [a] = axes;
    for (const optA of a.options ?? []) {
      const values = { ...defaults, [a.name]: optA.value };
      rows.push({
        labels: [optA.label],
        total: calcTotalCostKopecks(costKopecks, sections, values),
      });
    }
  }

  const columnLabels = axes.map((a) => a.label);

  return (
    <div className="mb-12">
      <h2 className="mb-5 text-[20px] font-semibold text-[#1A1A1A]">{title}</h2>
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white">
          <table className="w-full border-collapse text-[14px]">
            <thead>
              <tr className="border-b border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)]">
                {columnLabels.map((l) => (
                  <th key={l} className="px-4 py-2.5 text-left font-medium text-[rgba(13,13,13,0.5)]">
                    {l}
                  </th>
                ))}
                <th className="px-4 py-2.5 text-right font-medium text-[rgba(13,13,13,0.5)]">Цена</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b border-[rgba(13,13,13,0.06)] last:border-0">
                  {row.labels.map((l, j) => (
                    <td key={j} className="px-4 py-2 text-[#1A1A1A]">
                      {l}
                    </td>
                  ))}
                  <td className="px-4 py-2 text-right font-medium tabular-nums text-[#D97757]">
                    {formatMoney(row.total)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {checkboxNotes.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 text-[13px] text-[rgba(13,13,13,0.5)]">
          {checkboxNotes.map((f) => (
            <li key={f.name}>
              + {formatMoney((f.extra_cost ?? 0) * 100)} — {f.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
