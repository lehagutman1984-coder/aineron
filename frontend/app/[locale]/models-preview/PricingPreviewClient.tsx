"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Code2, Gift, ImageIcon, Info, Search, Video, type LucideIcon } from "lucide-react";
import { PREVIEW_MODELS, type PreviewCategory, type PreviewModel } from "@/lib/data/pricingPreviewModels";
import { formatRub } from "@/lib/money";

type TabKey = PreviewCategory | "all" | "free";

const CATEGORY_LABELS: Record<TabKey, string> = {
  all: "Все",
  text: "Текст",
  image: "Изображения",
  video: "Видео",
  free: "Бесплатные",
};

const CATEGORY_ICON: Record<PreviewCategory, LucideIcon> = {
  text: Code2,
  image: ImageIcon,
  video: Video,
};

const ACTION_LABEL: Record<PreviewCategory, string> = {
  text: "Открыть чат",
  image: "Сгенерировать",
  video: "Создать видео",
};

// Платные модели каждой category — бесплатные (isFree) скрыты из общего
// каталога и живут только во вкладке "free", как в проде (см. комментарий
// над FREE_MODELS в pricingPreviewModels.ts).
const PAID_MODELS = PREVIEW_MODELS.filter((m) => !m.isFree);
const FREE_TAB_MODELS = PREVIEW_MODELS.filter((m) => m.isFree);

export function PricingPreviewClient() {
  const [activeTab, setActiveTab] = useState<TabKey>("all");
  const [activeProvider, setActiveProvider] = useState("");
  const [query, setQuery] = useState("");

  const counts = useMemo(
    () => ({
      all: PAID_MODELS.length,
      text: PAID_MODELS.filter((m) => m.category === "text").length,
      image: PAID_MODELS.filter((m) => m.category === "image").length,
      video: PAID_MODELS.filter((m) => m.category === "video").length,
      free: FREE_TAB_MODELS.length,
    }),
    []
  );

  const providers = useMemo(() => {
    const base =
      activeTab === "free" ? FREE_TAB_MODELS : activeTab === "all" ? PAID_MODELS : PAID_MODELS.filter((m) => m.category === activeTab);
    const map = new Map<string, number>();
    base.forEach((m) => map.set(m.provider, (map.get(m.provider) ?? 0) + 1));
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }));
  }, [activeTab]);

  const filtered = useMemo(() => {
    let list = activeTab === "free" ? FREE_TAB_MODELS : activeTab === "all" ? PAID_MODELS : PAID_MODELS.filter((m) => m.category === activeTab);
    if (activeProvider) list = list.filter((m) => m.provider === activeProvider);
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter((m) => m.name.toLowerCase().includes(q) || m.description.toLowerCase().includes(q));
    }
    return list;
  }, [activeTab, activeProvider, query]);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
      <div className="mb-6">
        <h1 className="text-[28px] font-bold text-[#1A1A1A]">Каталог моделей и цены</h1>
        <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.58)]">
          {PAID_MODELS.length} платных моделей — сравнение стоимости в рублях за 1М токенов, генерацию и секунду
          видео, плюс {FREE_TAB_MODELS.length} бесплатных без каких-либо затрат.
        </p>
      </div>

      <div className="mb-6 flex items-start gap-2.5 rounded-[12px] border border-[rgba(217,119,87,0.20)] bg-[rgba(217,119,87,0.04)] p-3.5">
        <Info size={16} className="mt-0.5 shrink-0 text-[#D97757]" />
        <p className="text-[14px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          Предпросмотр новой витрины цен — не подключён к биллингу и не заменяет текущий каталог. Цены рассчитаны
          по формуле «опт провайдера × наценка» (см. <code className="text-[13px]">PRICING_SIMPLIFICATION_PLAN.md</code>).
        </p>
      </div>

      {/* Search */}
      <div className="mb-5 relative max-w-sm">
        <Search
          size={16}
          className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]"
        />
        <input
          type="search"
          placeholder="Найти модель..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white pl-10 pr-4 py-2.5 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
      </div>

      {/* Category tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        {(["all", "text", "image", "video", "free"] as const).map((tab) => {
          const active = activeTab === tab;
          const count = counts[tab];
          return (
            <button
              key={tab}
              type="button"
              onClick={() => {
                setActiveTab(tab);
                setActiveProvider("");
              }}
              className={[
                "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
                active
                  ? "bg-[#D97757] text-white"
                  : tab === "free"
                    ? "border border-[rgba(34,153,84,0.35)] bg-[rgba(34,153,84,0.06)] text-[#1F9254] hover:border-[rgba(34,153,84,0.55)]"
                    : "border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
              ].join(" ")}
            >
              {tab === "free" && <Gift size={14} />}
              {CATEGORY_LABELS[tab]} {count}
            </button>
          );
        })}
      </div>

      {/* Provider chips */}
      {providers.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1.5">
          {providers.map((p) => {
            const active = activeProvider === p.name;
            return (
              <button
                key={p.name}
                type="button"
                onClick={() => setActiveProvider(active ? "" : p.name)}
                className={[
                  "rounded-full px-3 py-1 text-[13px] font-medium transition-all",
                  active
                    ? "bg-[#D97757] text-white"
                    : "border border-[rgba(13,13,13,0.12)] bg-white text-[rgba(13,13,13,0.6)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
                ].join(" ")}
              >
                {p.name} · {p.count}
              </button>
            );
          })}
        </div>
      )}

      {/* List */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center text-[17px] text-[rgba(13,13,13,0.45)]">Ничего не найдено</div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((m) => (
            <ModelRow key={m.id} model={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-[6px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] px-2 py-0.5 text-[12px] text-[rgba(13,13,13,0.55)]">
      {label}
    </span>
  );
}

function ModelRow({ model }: { model: PreviewModel }) {
  const Icon = CATEGORY_ICON[model.category];

  return (
    <div className="flex flex-col gap-4 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 transition-all hover:border-[rgba(217,119,87,0.4)] sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-1 items-start gap-3.5">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
          <Icon size={20} />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <p className="text-[16px] font-semibold text-[#1A1A1A]">{model.name}</p>
            <span className="text-[13px] text-[rgba(13,13,13,0.45)]">{model.provider}</span>
          </div>
          <p className="mt-0.5 text-[14px] leading-relaxed text-[rgba(13,13,13,0.6)]">{model.description}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {model.inputBadges.map((b) => (
              <Badge key={`in-${b}`} label={b} />
            ))}
            <ArrowRight size={12} className="mt-1 text-[rgba(13,13,13,0.25)]" />
            {model.outputBadges.map((b) => (
              <Badge key={`out-${b}`} label={b} />
            ))}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-2.5 sm:w-[240px] sm:border-l sm:border-[rgba(13,13,13,0.08)] sm:pl-5">
        <PriceBlock model={model} />
        <div className="flex gap-2">
          <button
            type="button"
            className="flex-1 rounded-[8px] bg-[#D97757] px-3 py-2 text-[14px] font-medium text-white transition-colors hover:bg-[#C4664A]"
          >
            {ACTION_LABEL[model.category]}
          </button>
          <Link
            href={`/models-preview/${model.id}`}
            className="flex items-center rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[rgba(13,13,13,0.3)] hover:text-[#1A1A1A]"
          >
            Детали
          </Link>
        </div>
      </div>
    </div>
  );
}

function PriceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[13px]">
      <span className="text-[rgba(13,13,13,0.5)]">{label}</span>
      <span className="font-medium text-[#1A1A1A]">{value}</span>
    </div>
  );
}

function PriceBlock({ model }: { model: PreviewModel }) {
  if (model.isFree) {
    return (
      <div className="flex flex-col gap-1">
        <PriceRow label="Цена" value="Бесплатно" />
        {model.dailyLimit && <PriceRow label="Лимит" value={`${model.dailyLimit} сообщ./день`} />}
      </div>
    );
  }
  if (model.category === "text") {
    return (
      <div className="flex flex-col gap-1">
        {model.contextLabel && <PriceRow label="Контекст" value={model.contextLabel} />}
        <PriceRow label="Входящие токены за 1М" value={formatRub((model.priceInRub ?? 0) * 100)} />
        <PriceRow label="Исходящие токены за 1М" value={formatRub((model.priceOutRub ?? 0) * 100)} />
      </div>
    );
  }
  if (model.category === "image") {
    return (
      <div className="flex flex-col gap-1">
        {model.contextLabel && <PriceRow label="Параметры" value={model.contextLabel} />}
        <PriceRow label="За генерацию" value={formatRub((model.priceGenRub ?? 0) * 100)} />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      {model.contextLabel && <PriceRow label="Параметры" value={model.contextLabel} />}
      <PriceRow
        label={model.priceUnit === "call" ? "За видео" : "Секунда видео"}
        value={formatRub((model.priceVideoRub ?? 0) * 100)}
      />
    </div>
  );
}
