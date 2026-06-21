"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowRight, Code2, ImageIcon } from "lucide-react";
import type { NetworkListItem, Category } from "@/lib/api/types";

interface Props {
  networks: NetworkListItem[];
  categories: Category[];
  initialCategory?: string;
  projectId?: number;
}

export function CatalogClient({ networks, categories, initialCategory, projectId }: Props) {
  const [activeCategory, setActiveCategory] = useState(initialCategory ?? "");
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    let list = networks;
    if (activeCategory) {
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
  }, [networks, activeCategory, query]);

  return (
    <>
      {/* Search */}
      <div className="mb-5 relative max-w-sm">
        <input
          type="search"
          placeholder="Поиск по моделям..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-2.5 text-[14px] text-[#0d0d0d] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
        />
      </div>

      {/* Category tabs */}
      <div className="mb-6 flex flex-wrap gap-2">
        <CategoryTab
          label="Все"
          active={activeCategory === ""}
          onClick={() => setActiveCategory("")}
        />
        {categories.map((c) => (
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
        <div className="py-16 text-center text-[15px] text-[rgba(13,13,13,0.45)]">
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
        "rounded-full px-4 py-1.5 text-[13px] font-medium transition-all",
        active
          ? "bg-[#0a7cff] text-white"
          : "border border-[rgba(13,13,13,0.15)] bg-white text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#0d0d0d]",
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
      className="group flex flex-col gap-3 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 hover:border-[#0a7cff] hover:shadow-sm transition-all duration-150"
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
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
            {network.handle_photo || network.handle_video ? (
              <ImageIcon size={20} />
            ) : (
              <Code2 size={20} />
            )}
          </div>
        )}
        <div className="min-w-0">
          <p className="truncate text-[14px] font-semibold text-[#0d0d0d] group-hover:text-[#0a7cff] transition-colors">
            {network.name}
          </p>
          <p className="text-[12px] text-[rgba(13,13,13,0.5)]">
            {network.category.name}
          </p>
        </div>
      </div>
      {network.description && (
        <p className="line-clamp-2 text-[13px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {network.description}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-[12px] text-[rgba(13,13,13,0.45)]">
          {network.unlimited ? "Безлимит" : `${network.cost_per_message} зв.`}
        </span>
        <ArrowRight
          size={14}
          className="text-[rgba(13,13,13,0.3)] group-hover:text-[#0a7cff] transition-colors"
        />
      </div>
    </Link>
  );
}
