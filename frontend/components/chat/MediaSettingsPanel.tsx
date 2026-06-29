"use client";

import { useState } from "react";
import { Dices, Lock, Unlock, ChevronDown, ChevronRight } from "lucide-react";
import type { UiField, UiSection } from "@/lib/api/types";

// Aspect ratio visual presets for the "size" select field.
const RATIO_PRESETS = [
  { label: "1:1", w: 1, h: 1 },
  { label: "4:3", w: 4, h: 3 },
  { label: "3:4", w: 3, h: 4 },
  { label: "16:9", w: 16, h: 9 },
  { label: "9:16", w: 9, h: 16 },
];

function parseSize(val: string): { w: number; h: number } | null {
  const m = String(val).match(/^(\d+)[x×:](\d+)$/i);
  return m ? { w: Number(m[1]), h: Number(m[2]) } : null;
}

function closestOption(options: { value: string }[], targetW: number, targetH: number): string | null {
  let best: string | null = null;
  let bestDiff = Infinity;
  for (const opt of options) {
    const s = parseSize(opt.value);
    if (!s) continue;
    const optRatio = s.w / s.h;
    const targetRatio = targetW / targetH;
    const diff = Math.abs(optRatio - targetRatio);
    if (diff < bestDiff) { bestDiff = diff; best = opt.value; }
  }
  return best;
}

function AspectRatioPresets({
  options,
  currentValue,
  onSet,
}: {
  options: { value: string }[];
  currentValue: unknown;
  onSet: (v: unknown) => void;
}) {
  const currentSize = parseSize(String(currentValue ?? ""));
  const currentRatio = currentSize ? currentSize.w / currentSize.h : null;

  return (
    <div className="flex flex-wrap gap-1 mb-1.5">
      {RATIO_PRESETS.map(({ label, w, h }) => {
        const targetRatio = w / h;
        const isActive = currentRatio !== null && Math.abs(currentRatio - targetRatio) < 0.05;
        return (
          <button
            key={label}
            type="button"
            onClick={() => {
              const best = closestOption(options, w, h);
              if (best) onSet(best);
            }}
            title={label}
            className={`flex flex-col items-center justify-center gap-0.5 rounded-[6px] border px-1.5 py-1 transition-colors ${
              isActive
                ? "border-[#0a7cff] bg-[rgba(10,124,255,0.08)] text-[#0a7cff]"
                : "border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.5)]"
            }`}
          >
            <span
              className="block border border-current"
              style={{
                width: `${Math.round(20 * Math.min(1, w / h))}px`,
                height: `${Math.round(20 * Math.min(1, h / w))}px`,
              }}
            />
            <span className="text-[9px] font-medium leading-none">{label}</span>
          </button>
        );
      })}
    </div>
  );
}

function randomSeed(max?: number): number {
  const cap = max && max > 0 ? Math.min(max, 9_999_999_999) : 9_999_999_999;
  return Math.floor(Math.random() * (cap + 1));
}

// Seed: число + "Случайный" (кубик) + замок (закрепить). Замок выключен →
// seed не отправляется (провайдер рандомит каждую генерацию).
function SeedField({
  field,
  value,
  onSet,
}: {
  field: UiField;
  value: unknown;
  onSet: (v: unknown) => void;
}) {
  const locked = value !== undefined && value !== null && value !== "";

  return (
    <div className="flex flex-col gap-1" style={{ minWidth: "200px" }}>
      <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
        {field.label}
      </label>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          title={locked ? "Seed закреплён" : "Seed случайный"}
          aria-pressed={locked}
          onClick={() => onSet(locked ? null : randomSeed(field.max))}
          className={[
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] border transition-colors",
            locked
              ? "border-[#0a7cff] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]"
              : "border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.5)] dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.5)]",
          ].join(" ")}
        >
          {locked ? <Lock size={13} /> : <Unlock size={13} />}
        </button>
        <input
          type="number"
          min={field.min ?? 0}
          max={field.max ?? undefined}
          disabled={!locked}
          value={locked ? String(value) : ""}
          placeholder="случайный"
          onChange={(e) => {
            const raw = e.target.value;
            onSet(raw === "" ? null : Math.floor(Number(raw)));
          }}
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-2 py-1 text-[12px] text-[#0d0d0d] focus:outline-none disabled:bg-[rgba(13,13,13,0.04)] disabled:text-[rgba(13,13,13,0.35)] dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#ececec]"
        />
        <button
          type="button"
          title="Случайный seed"
          onClick={() => onSet(randomSeed(field.max))}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.5)] hover:text-[#0a7cff] transition-colors dark:border-[rgba(255,255,255,0.12)] dark:text-[rgba(236,236,236,0.5)]"
        >
          <Dices size={13} />
        </button>
      </div>
    </div>
  );
}

// Обычное число (не seed).
function NumberField({
  field,
  value,
  onSet,
}: {
  field: UiField;
  value: unknown;
  onSet: (v: unknown) => void;
}) {
  return (
    <div className="flex flex-col gap-1" style={{ minWidth: "140px" }}>
      <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
        {field.label}
      </label>
      <input
        type="number"
        min={field.min ?? undefined}
        max={field.max ?? undefined}
        step={field.step ?? 1}
        value={value === undefined || value === null ? "" : String(value)}
        onChange={(e) => {
          const raw = e.target.value;
          onSet(raw === "" ? null : Number(raw));
        }}
        className="rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-2 py-1 text-[12px] text-[#0d0d0d] focus:outline-none dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#ececec]"
      />
    </div>
  );
}

// Свёртываемая textarea (например, негативный промт).
function CollapsibleTextarea({
  field,
  value,
  onSet,
}: {
  field: UiField;
  value: unknown;
  onSet: (v: unknown) => void;
}) {
  const text = typeof value === "string" ? value : "";
  const [open, setOpen] = useState(Boolean(text));

  return (
    <div className="flex w-full flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1 text-[11px] text-[rgba(13,13,13,0.5)] hover:text-[#0d0d0d] transition-colors dark:text-[rgba(236,236,236,0.45)] dark:hover:text-[#ececec]"
      >
        {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        <span>{field.label}</span>
        {!open && text ? (
          <span className="ml-1 truncate text-[rgba(13,13,13,0.35)] dark:text-[rgba(236,236,236,0.3)]">
            — {text.slice(0, 40)}
          </span>
        ) : null}
      </button>
      {open && (
        <textarea
          value={text}
          maxLength={field.max_length}
          rows={3}
          onChange={(e) => onSet(e.target.value)}
          placeholder={field.label}
          className="w-full resize-y rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-2 py-1.5 text-[12px] text-[#0d0d0d] focus:outline-none dark:border-[rgba(255,255,255,0.12)] dark:bg-[rgba(255,255,255,0.08)] dark:text-[#ececec]"
        />
      )}
    </div>
  );
}

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
                const isSizeField =
                  field.name === "size" &&
                  (field.options ?? []).some((o) => parseSize(o.value) !== null);
                return (
                  <div key={field.name} className="flex flex-col gap-1">
                    <label className="text-[11px] text-[rgba(13,13,13,0.5)] dark:text-[rgba(236,236,236,0.45)]">
                      {field.label}
                    </label>
                    {isSizeField && (
                      <AspectRatioPresets
                        options={field.options ?? []}
                        currentValue={val}
                        onSet={(v) => set(field.name, v)}
                      />
                    )}
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

              if (field.type === "number") {
                return field.name === "seed" ? (
                  <SeedField
                    key={field.name}
                    field={field}
                    value={val}
                    onSet={(v) => set(field.name, v)}
                  />
                ) : (
                  <NumberField
                    key={field.name}
                    field={field}
                    value={val}
                    onSet={(v) => set(field.name, v)}
                  />
                );
              }

              if (field.type === "textarea") {
                return (
                  <CollapsibleTextarea
                    key={field.name}
                    field={field}
                    value={val}
                    onSet={(v) => set(field.name, v)}
                  />
                );
              }

              if (field.type === "text") {
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
