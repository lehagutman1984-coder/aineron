import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Code2, Image, Search } from "lucide-react";
import { serverListNetworks, serverListCategories } from "@/lib/api/server";
import { CatalogClient } from "./CatalogClient";

export const revalidate = 3600;

export const metadata: Metadata = {
  title: "Каталог нейросетей",
  description:
    "GPT-4o, Claude, Gemini, генерация изображений и десятки других AI-моделей без VPN. Выберите нейросеть и начните чат.",
};

export default async function ModelsPage({
  searchParams,
}: {
  searchParams: { category?: string };
}) {
  const [networks, categories] = await Promise.all([
    serverListNetworks(),
    serverListCategories(),
  ]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-[28px] font-bold text-[#0d0d0d]">Каталог нейросетей</h1>
        <p className="mt-2 text-[15px] text-[rgba(13,13,13,0.58)]">
          {networks?.length ?? 0} моделей доступно
        </p>
      </div>

      <CatalogClient
        networks={networks ?? []}
        categories={categories ?? []}
        initialCategory={searchParams.category}
      />
    </div>
  );
}
