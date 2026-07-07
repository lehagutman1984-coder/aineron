"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { ArrowRight, Code2, ImageIcon, ImagePlus, Palette, X } from "lucide-react";
import type { NetworkListItem, Category } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";

interface Props {
  networks: NetworkListItem[];
  freeNetworks?: NetworkListItem[];
  categories: Category[];
  initialCategory?: string;
  projectId?: number;
}

const FREE_TAB = "__free__";

export function CatalogClient({ networks, freeNetworks = [], categories, initialCategory, projectId }: Props) {
  const [activeCategory, setActiveCategory] = useState(initialCategory ?? "");
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

  const filtered = useMemo(() => {
    let list = activeCategory === FREE_TAB ? freeNetworks : networks;
    if (activeCategory && activeCategory !== FREE_TAB) {
      list = list.filter((n) => n.category.slug === activeCategory);
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
  }, [networks, freeNetworks, activeCategory, query]);

  return (
    <>
      {/* Ожидающее редактирование / референс стиля из «Мои файлы» */}
      {pendingEdit && (
        <PendingImageBanner
          imageUrl={pendingEdit}
          icon={<ImagePlus size={13} className="text-[#D97757]" />}
          title="Редактирование изображения"
          hint="Выберите модель изображений — она применит ваши изменения к этому файлу"
          onCancel={() => cancelPending("aineron_edit_image")}
        />
      )}
      {pendingStyle && (
        <PendingImageBanner
          imageUrl={pendingStyle}
          icon={<Palette size={13} className="text-[#D97757]" />}
          title="Референс стиля"
          hint="Выберите модель изображений — новые генерации переймут стиль этого файла"
          onCancel={() => cancelPending("aineron_style_image")}
        />
      )}

      {/* Search */}
      <div className="mb-5 relative max-w-sm">
        <input
          type="search"
          placeholder="Поиск по моделям..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-2.5 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
      </div>

      {/* Category tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        <CategoryTab
          label="Все"
          active={activeCategory === ""}
          onClick={() => setActiveCategory("")}
        />
        {freeNetworks.length > 0 && (
          <CategoryTab
            label="Бесплатные"
            active={activeCategory === FREE_TAB}
            onClick={() => setActiveCategory(FREE_TAB)}
          />
        )}
        {categories
          // Категория «Бесплатно/Бесплатные» дублирует синтетическую вкладку
          // «Бесплатные» (is_free) и обычно пуста — не показываем её.
          .filter((c) => !/^бесплат/i.test(c.name.trim()))
          .map((c) => (
            <CategoryTab
              key={c.id}
              label={c.name}
              active={activeCategory === c.slug}
              onClick={() => setActiveCategory(c.slug)}
            />
          ))}
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <div className="py-16 text-center text-[17px] text-[rgba(13,13,13,0.45)]">
          Ничего не найдено
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
        title="Отменить"
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

function NetworkCard({ network, projectId }: { network: NetworkListItem; projectId?: number }) {
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
          {network.is_free ? "Бесплатно" : network.unlimited ? "Безлимит" : formatMoney(network.cost_kopecks)}
        </span>
        <ArrowRight
          size={14}
          className="text-[rgba(13,13,13,0.3)] group-hover:text-[#D97757] transition-colors"
        />
      </div>
    </Link>
  );
}
