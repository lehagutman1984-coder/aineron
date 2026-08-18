"use client";

import { useState, useMemo, useEffect } from "react";
import { Link } from "@/i18n/navigation";

import { ArrowRight, Code2, ImageIcon, ImagePlus, Palette, X } from "lucide-react";
import type { NetworkListItem, Category } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";
import { useTranslations } from "next-intl";

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
      <div className="mb-6 flex flex-wrap gap-2">
        <CategoryTab
          label={t("all")}
          active={activeCategory === ""}
          onClick={() => setActiveCategory("")}
        />
        {freeNetworks.length > 0 && (
          <CategoryTab
            label={t("free")}
            active={activeCategory === FREE_TAB}
            onClick={() => setActiveCategory(FREE_TAB)}
          />
        )}
        {categories
          // Категория «Бесплатно/Бесплатные» дублирует синтетическую вкладку
          // «Бесплатные» (is_free) и обычно пуста — не показываем её. Матчим
          // по slug (стабилен), а не по name — на fa/tr/id/ar name переведён
          // и с рус./eng. префиксом больше не совпадает.
          .filter((c) => !/^(free|бесплат)/i.test(c.slug.trim()))
          .map((c) => (
            <CategoryTab
              key={c.id}
              label={c.name}
              active={activeCategory === c.slug}
              onClick={() => setActiveCategory(c.slug)}
            />
          ))}
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

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center text-[17px] text-[rgba(13,13,13,0.45)]">
          {t("empty")}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((n) => (
            <NetworkCard key={n.id} network={n} projectId={projectId} />
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
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
        active
          ? "bg-[#D97757] text-white"
          : "border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
      ].join(" ")}
    >
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

function NetworkCard({ network, projectId }: { network: NetworkListItem; projectId?: number }) {
  const t = useTranslations("catalog");
  const href = projectId
    ? `/models/${network.slug}/?project_id=${projectId}`
    : `/models/${network.slug}/`;
  return (
    <Link
      href={href}
      className="group flex flex-col gap-3 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 hover:border-[#D97757] hover:shadow-sm transition-all duration-150"
    >
      <div className="flex items-start gap-3">
        {network.avatar ? (
          <img
            src={network.avatar}
            alt={network.name}
            width={40}
            height={40}
            className="rounded-[10px] object-cover shrink-0"
          />
        ) : (
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
            {network.provider === "fal-ai" || network.output_type ? (
              <ImageIcon size={20} />
            ) : (
              <Code2 size={20} />
            )}
          </div>
        )}
        <div className="min-w-0">
          <p className="truncate text-[16px] font-semibold text-[#1A1A1A] group-hover:text-[#D97757] transition-colors">
            {network.name}
          </p>
          <p className="text-[14px] text-[rgba(13,13,13,0.5)]">
            {network.category.name}
          </p>
        </div>
      </div>
      {network.description && (
        <p className="line-clamp-2 text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {network.description}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-[14px] text-[rgba(13,13,13,0.45)]">
          {network.is_free ? t("priceFree") : network.unlimited ? t("priceUnlimited") : formatMoney(network.cost_kopecks)}
        </span>
        <ArrowRight
          size={14}
          className="text-[rgba(13,13,13,0.3)] group-hover:text-[#D97757] transition-colors"
        />
      </div>
    </Link>
  );
}
