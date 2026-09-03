"use client";

import { useState, useMemo, useEffect } from "react";
import { Link } from "@/i18n/navigation";

import { ArrowRight, Code2, Gift, ImageIcon, ImagePlus, Palette, Video, X } from "lucide-react";
import type { NetworkListItem, Category } from "@/lib/api/types";
import { formatMoney, formatRub } from "@/lib/money";
import { useTranslations } from "next-intl";
import { REFERENCE_PRICING } from "@/lib/data/catalogReferencePricing";
import { IS_RU } from "@/lib/site";

interface Props {
  networks: NetworkListItem[];
  freeNetworks?: NetworkListItem[];
  categories: Category[];
  initialCategory?: string;
  projectId?: number;
}

const FREE_TAB = "__free__";

// Группировка моделей по компании-разработчику — по префиксу slug (та же
// логика, что в download_avatars.py/FALLBACK_COLORS на бэкенде, здесь не
// продублирована как отдельное поле БД, т.к. slug уже приходит в каталоге).
// Список показываемых кнопок вычисляется динамически из реального набора
// моделей (см. availableCompanies) — тут только полный словарь кандидатов.
const COMPANIES: { id: string; label: string; prefixes: string[] }[] = [
  { id: "openai", label: "OpenAI", prefixes: ["gpt", "o1", "o3", "o4", "chatgpt", "dall", "sora", "codex"] },
  { id: "anthropic", label: "Claude", prefixes: ["claude"] },
  { id: "google", label: "Gemini", prefixes: ["gemini", "veo"] },
  { id: "xai", label: "Grok", prefixes: ["grok"] },
  { id: "deepseek", label: "DeepSeek", prefixes: ["deepseek"] },
  { id: "alibaba", label: "Qwen", prefixes: ["qwen", "qwq", "wan"] },
  { id: "bfl", label: "Flux", prefixes: ["flux"] },
  { id: "bytedance", label: "Seedream", prefixes: ["seedream", "doubao"] },
  { id: "minimax", label: "MiniMax", prefixes: ["minimax"] },
  { id: "moonshot", label: "Kimi", prefixes: ["kimi"] },
  { id: "zhipu", label: "GLM", prefixes: ["glm"] },
  { id: "kuaishou", label: "Kling", prefixes: ["kling"] },
];

function matchesCompany(slug: string, companyId: string): boolean {
  const company = COMPANIES.find((c) => c.id === companyId);
  if (!company) return false;
  return company.prefixes.some((p) => slug.startsWith(p));
}

function categoryIcon(n: NetworkListItem) {
  if (n.output_type === "video") return Video;
  if (n.provider === "fal-ai" || n.output_type === "image") return ImageIcon;
  return Code2;
}

export function CatalogClient({ networks, freeNetworks = [], categories, initialCategory, projectId }: Props) {
  const t = useTranslations("catalog");
  const [activeCategory, setActiveCategory] = useState(initialCategory ?? "");
  const [activeCompany, setActiveCompany] = useState("");
  const [query, setQuery] = useState("");
  // Ожидающее изображение из «Мои файлы» (кнопки «Редактировать» / «Стиль»):
  // показываем подсказку и сразу фильтруем каталог на модели изображений.
  const [pendingEdit, setPendingEdit] = useState<string | null>(null);
  const [pendingStyle, setPendingStyle] = useState<string | null>(null);

  useEffect(() => {
    try {
      const edit = localStorage.getItem("aineron_edit_image");
      const style = localStorage.getItem("aineron_style_image");
      setPendingEdit(edit);
      setPendingStyle(style);
      if ((edit || style) && !initialCategory) {
        const imagesCat = categories.find((c) => c.slug === "images");
        if (imagesCat) setActiveCategory(imagesCat.slug);
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancelPending = (key: "aineron_edit_image" | "aineron_style_image") => {
    try {
      localStorage.removeItem(key);
    } catch {}
    if (key === "aineron_edit_image") setPendingEdit(null);
    else setPendingStyle(null);
  };

  // Кнопки компаний считаются от полного платного каталога (не от текущего
  // среза по категории/поиску), чтобы ряд не «прыгал» при переключении
  // категорий. Бесплатные модели (Llama/Nemotron/OSS и т.п.) в основном не
  // относятся ни к одному из этих брендов — ряд не показываем на вкладке
  // «Бесплатные». Порог >=2 модели и топ-8 — чтобы ряд оставался компактным
  // и не захламлялся вендорами с одной моделью.
  const availableCompanies = useMemo(() => {
    return COMPANIES.map((c) => {
      const matches = networks.filter((n) => matchesCompany(n.slug, c.id));
      return { ...c, count: matches.length, avatar: matches[0]?.avatar };
    })
      .filter((c) => c.count >= 2)
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [networks]);

  const categoryCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const n of networks) map.set(n.category.slug, (map.get(n.category.slug) ?? 0) + 1);
    return map;
  }, [networks]);

  const filtered = useMemo(() => {
    let list = activeCategory === FREE_TAB ? freeNetworks : networks;
    if (activeCategory && activeCategory !== FREE_TAB) {
      list = list.filter((n) => n.category.slug === activeCategory);
    }
    if (activeCompany && activeCategory !== FREE_TAB) {
      list = list.filter((n) => matchesCompany(n.slug, activeCompany));
    }
    if (query.trim()) {
      const q = query.trim().toLowerCase();
      list = list.filter(
        (n) =>
          n.name.toLowerCase().includes(q) ||
          n.description.toLowerCase().includes(q)
      );
    }
    return list;
  }, [networks, freeNetworks, activeCategory, activeCompany, query]);

  return (
    <>
      {/* Ожидающее редактирование / референс стиля из «Мои файлы» */}
      {pendingEdit && (
        <PendingImageBanner
          imageUrl={pendingEdit}
          icon={<ImagePlus size={13} className="text-[#D97757]" />}
          title={t("editImageTitle")}
          hint={t("editImageHint")}
          onCancel={() => cancelPending("aineron_edit_image")}
        />
      )}
      {pendingStyle && (
        <PendingImageBanner
          imageUrl={pendingStyle}
          icon={<Palette size={13} className="text-[#D97757]" />}
          title={t("styleRefTitle")}
          hint={t("styleRefHint")}
          onCancel={() => cancelPending("aineron_style_image")}
        />
      )}

      {/* Search */}
      <div className="mb-5 relative max-w-sm">
        <input
          type="search"
          placeholder={t("search")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-2.5 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
      </div>

      {/* Category tabs */}
      <div className="mb-4 flex flex-wrap gap-2">
        <CategoryTab
          label={`${t("all")} ${networks.length}`}
          active={activeCategory === ""}
          onClick={() => setActiveCategory("")}
        />
        {categories
          // Категория «Бесплатно/Бесплатные» дублирует синтетическую вкладку
          // «Бесплатные» (is_free) и обычно пуста — не показываем её. Матчим
          // по slug (стабилен), а не по name — на fa/tr/id/ar name переведён
          // и с рус./eng. префиксом больше не совпадает.
          .filter((c) => !/^(free|бесплат)/i.test(c.slug.trim()))
          .map((c) => (
            <CategoryTab
              key={c.id}
              label={`${c.name} ${categoryCounts.get(c.slug) ?? 0}`}
              active={activeCategory === c.slug}
              onClick={() => setActiveCategory(c.slug)}
            />
          ))}
        {freeNetworks.length > 0 && (
          <CategoryTab
            label={`${t("free")} ${freeNetworks.length}`}
            active={activeCategory === FREE_TAB}
            onClick={() => setActiveCategory(FREE_TAB)}
            variant="free"
          />
        )}
      </div>

      {/* Company tabs — фильтр по компании-разработчику, отдельная грань
          от категории по назначению. Повторный клик по активной снимает
          фильтр. Скрыт на вкладке «Бесплатные» — там бренды почти не
          совпадают. */}
      {activeCategory !== FREE_TAB && availableCompanies.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1.5">
          {availableCompanies.map((c) => (
            <CompanyTab
              key={c.id}
              label={c.label}
              avatar={c.avatar}
              active={activeCompany === c.id}
              onClick={() => setActiveCompany(activeCompany === c.id ? "" : c.id)}
            />
          ))}
        </div>
      )}

      {/* List */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center text-[17px] text-[rgba(13,13,13,0.45)]">
          {t("empty")}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((n) => (
            <NetworkRow key={n.id} network={n} projectId={projectId} />
          ))}
        </div>
      )}
    </>
  );
}

function PendingImageBanner({
  imageUrl,
  icon,
  title,
  hint,
  onCancel,
}: {
  imageUrl: string;
  icon: React.ReactNode;
  title: string;
  hint: string;
  onCancel: () => void;
}) {
  return (
    <div className="mb-5 flex items-center gap-3 rounded-[12px] border border-[rgba(217,119,87,0.20)] bg-[rgba(217,119,87,0.04)] p-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageUrl}
        alt={title}
        className="h-12 w-12 shrink-0 rounded-[8px] border border-[rgba(13,13,13,0.10)] object-cover"
      />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-[15px] font-medium text-[#1A1A1A]">
          {icon}
          {title}
        </p>
        <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.55)]">{hint}</p>
      </div>
      <button
        onClick={onCancel}
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] border border-[rgba(13,13,13,0.10)] bg-white transition-colors hover:bg-[rgba(13,13,13,0.04)]"
      >
        <X size={13} className="text-[rgba(13,13,13,0.55)]" />
      </button>
    </div>
  );
}

function CategoryTab({
  label,
  active,
  onClick,
  variant,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  variant?: "free";
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "flex items-center gap-1.5 rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
        active
          ? "bg-[#D97757] text-white"
          : variant === "free"
            ? "border border-[rgba(34,153,84,0.35)] bg-[rgba(34,153,84,0.06)] text-[#1F9254] hover:border-[rgba(34,153,84,0.55)]"
            : "border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
      ].join(" ")}
    >
      {variant === "free" && <Gift size={14} />}
      {label}
    </button>
  );
}

function CompanyTab({
  label,
  avatar,
  active,
  onClick,
}: {
  label: string;
  avatar?: string | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={[
        "flex items-center gap-1.5 rounded-full py-1 pl-1 pr-3 text-[13px] font-medium transition-all",
        active
          ? "bg-[#D97757] text-white"
          : "border border-[rgba(13,13,13,0.12)] bg-white text-[rgba(13,13,13,0.6)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
      ].join(" ")}
    >
      {avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={avatar} alt="" width={18} height={18} className="rounded-full object-cover shrink-0" />
      ) : (
        <span className="h-[18px] w-[18px] shrink-0 rounded-full bg-[rgba(13,13,13,0.12)]" />
      )}
      {label}
    </button>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-[6px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] px-2 py-0.5 text-[12px] text-[rgba(13,13,13,0.55)]">
      {label}
    </span>
  );
}

function networkBadges(n: NetworkListItem): { input: string[]; output: string[] } {
  const isVideo = n.output_type === "video";
  const isImage = n.provider === "fal-ai" && !isVideo;
  const input = ["Текст"];
  if (n.handle_photo) input.push("Изображения");
  if (n.handle_video) input.push("Видео");
  if (n.handle_text_files || n.handle_archive) input.push("Файл");
  const output = isVideo ? ["Видео"] : isImage ? ["Изображение"] : ["Текст"];
  return { input, output };
}

function PriceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[13px]">
      <span className="text-[rgba(13,13,13,0.5)]">{label}</span>
      <span className="font-medium text-[#1A1A1A]">{value}</span>
    </div>
  );
}

function PriceBlock({ network }: { network: NetworkListItem }) {
  const ref = IS_RU && !network.is_free ? REFERENCE_PRICING[network.slug] : undefined;
  const t = useTranslations("catalog");

  if (network.is_free) {
    return (
      <div className="flex flex-col gap-1">
        <PriceRow label="Цена" value={t("priceFree")} />
        {network.messages_limit > 0 && <PriceRow label="Лимит" value={`${network.messages_limit} сообщ./день`} />}
      </div>
    );
  }
  if (network.unlimited) {
    return (
      <div className="flex flex-col gap-1">
        {ref?.contextLabel && <PriceRow label="Контекст" value={ref.contextLabel} />}
        <PriceRow label="Цена" value={t("priceUnlimited")} />
      </div>
    );
  }
  if (ref?.category === "text") {
    return (
      <div className="flex flex-col gap-1">
        {ref.contextLabel && <PriceRow label="Контекст" value={ref.contextLabel} />}
        <PriceRow label="Входящие токены за 1М" value={formatRub((ref.priceInRub ?? 0) * 100)} />
        <PriceRow label="Исходящие токены за 1М" value={formatRub((ref.priceOutRub ?? 0) * 100)} />
        <PriceRow label="Спишется за сообщение" value={formatMoney(network.cost_kopecks)} />
      </div>
    );
  }
  if (ref?.category === "image") {
    return (
      <div className="flex flex-col gap-1">
        <PriceRow label="За генерацию (опт × курс)" value={formatRub((ref.priceGenRub ?? 0) * 100)} />
        <PriceRow label="Спишется за генерацию" value={formatMoney(network.cost_kopecks)} />
      </div>
    );
  }
  if (ref?.category === "video") {
    return (
      <div className="flex flex-col gap-1">
        <PriceRow
          label={ref.priceUnit === "call" ? "За видео (опт × курс)" : "Секунда видео (опт × курс)"}
          value={formatRub((ref.priceVideoRub ?? 0) * 100)}
        />
        <PriceRow label="Спишется за ролик" value={formatMoney(network.cost_kopecks)} />
      </div>
    );
  }
  // Модель вне куратированного списка (не должно случаться для активных
  // платных моделей, но не падаем, если появится новая без ref-записи).
  return (
    <div className="flex flex-col gap-1">
      <PriceRow label="Цена" value={formatMoney(network.cost_kopecks)} />
    </div>
  );
}

function NetworkRow({ network, projectId }: { network: NetworkListItem; projectId?: number }) {
  const t = useTranslations("catalog");
  const href = projectId
    ? `/models/${network.slug}/?project_id=${projectId}`
    : `/models/${network.slug}/`;
  const Icon = categoryIcon(network);
  const { input, output } = networkBadges(network);
  const action =
    network.output_type === "video" ? t("actionVideo") : network.provider === "fal-ai" ? t("actionImage") : t("actionChat");

  return (
    <div className="flex flex-col gap-4 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 transition-all hover:border-[rgba(217,119,87,0.4)] sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-1 items-start gap-3.5">
        {network.avatar ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={network.avatar}
            alt={network.name}
            width={44}
            height={44}
            className="h-11 w-11 shrink-0 rounded-[10px] object-cover"
          />
        ) : (
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
            <Icon size={20} />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <p className="text-[16px] font-semibold text-[#1A1A1A]">{network.name}</p>
            <span className="text-[13px] text-[rgba(13,13,13,0.45)]">{network.category.name}</span>
          </div>
          {network.description && (
            <p className="mt-0.5 line-clamp-2 text-[14px] leading-relaxed text-[rgba(13,13,13,0.6)]">
              {network.description}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {input.map((b) => (
              <Badge key={`in-${b}`} label={b} />
            ))}
            <ArrowRight size={12} className="mt-1 text-[rgba(13,13,13,0.25)]" />
            {output.map((b) => (
              <Badge key={`out-${b}`} label={b} />
            ))}
          </div>
        </div>
      </div>

      <div className="flex shrink-0 flex-col gap-2.5 sm:w-[240px] sm:border-l sm:border-[rgba(13,13,13,0.08)] sm:pl-5">
        <PriceBlock network={network} />
        <div className="flex gap-2">
          <Link
            href={href}
            className="flex-1 rounded-[8px] bg-[#D97757] px-3 py-2 text-center text-[14px] font-medium text-white transition-colors hover:bg-[#C4664A]"
          >
            {action}
          </Link>
          <Link
            href={href}
            className="flex items-center rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-3 py-2 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[rgba(13,13,13,0.3)] hover:text-[#1A1A1A]"
          >
            {t("details")}
          </Link>
        </div>
      </div>
    </div>
  );
}
