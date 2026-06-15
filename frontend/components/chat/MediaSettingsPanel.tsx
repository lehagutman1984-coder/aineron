"use client";

import type { UiSection } from "@/lib/api/types";

export function MediaSettingsPanel({
  sections,
  values,
  onChange,
}: {
  sections: UiSection[];
  values: Record<string, unknown>;
  onChange: (v: Record<string, unknown>) => void;
}) {
  const set = (name: string, value: unknown) => onChange({ ...values, [name]: value });

  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.02)] p-3 dark:border-[rgba(255,255,255,0.10)] dark:bg-[rgba(255,255,255,0.04)]">
      {sections.map((section) => (
        <div key={section.title} className="mb-3 last:mb-0">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.38)] dark:text-[rgba(236,236,236,0.35)]">
            {section.title}
          </p>
          <div className="flex flex-wrap gap-3">
            {section.fields.map((field) => {
              const val = values[field.name];

              if (field.type === "select") {
                return (
                  <div key={field.name} className="flex flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      {field.label}
                    </label>
                    <select
                      value={String(val ?? "")}
                      onChange={(e) => set(field.name, e.target.value)}
                      className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-2 py-1 text-[12px] font-medium text-[#0d0d0d] focus:outline-none dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#ececec]"
                      style={{ minWidth: "120px" }}
                    >
                      {(field.options ?? []).map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                          {opt.extra_cost ? ` (+${opt.extra_cost})` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                );
              }

              if (field.type === "checkbox") {
                const checked = Boolean(val);
                return (
                  <div key={field.name} className="flex items-center gap-2">
                    <button
                      type="button"
                      role="switch"
                      aria-checked={checked}
                      onClick={() => set(field.name, !checked)}
                      className={[
                        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none",
                        checked ? "bg-[#0a7cff]" : "bg-[rgba(13,13,13,0.15)] dark:bg-[rgba(255,255,255,0.15)]",
                      ].join(" ")}
                    >
                      <span
                        className={[
                          "inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform",
                          checked ? "translate-x-4" : "translate-x-0.5",
                        ].join(" ")}
                      />
                    </button>
                    <label
                      className="cursor-pointer text-[12px] text-[rgba(13,13,13,0.65)] dark:text-[rgba(236,236,236,0.6)]"
                      onClick={() => set(field.name, !checked)}
                    >
                      {field.label}
                    </label>
                  </div>
                );
              }

              if (field.type === "slider") {
                return (
                  <div key={field.name} className="flex flex-col gap-1" style={{ minWidth: "160px" }}>
                    <label className="flex items-center justify-between text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      <span>{field.label}</span>
                      <span className="font-medium text-[#0d0d0d] dark:text-[#ececec]">
                        {String(val ?? field.min ?? 0)}
                      </span>
                    </label>
                    <input
                      type="range"
                      min={field.min ?? 0}
                      max={field.max ?? 100}
                      step={field.step ?? 1}
                      value={Number(val ?? field.min ?? 0)}
                      onChange={(e) => set(field.name, Number(e.target.value))}
                      className="w-full accent-[#0a7cff]"
                    />
                  </div>
                );
              }

              if (field.type === "text" || field.type === "textarea") {
                return (
                  <div key={field.name} className="flex w-full flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      {field.label}
                    </label>
                    <input
                      type="text"
                      value={String(val ?? "")}
                      maxLength={field.max_length}
                      onChange={(e) => set(field.name, e.target.value)}
                      placeholder={field.label}
                      className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-2 py-1 text-[12px] text-[#0d0d0d] focus:outline-none dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#ececec]"
                      style={{ width: "100%" }}
                    />
                  </div>
                );
              }

              return null;
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
