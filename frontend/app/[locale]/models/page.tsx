import type { Metadata } from "next";

import { ArrowRight, Code2, Image, Search } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { serverListNetworks, serverListCategories } from "@/lib/api/server";
import { CatalogClient } from "./CatalogClient";
import { getTranslations } from "next-intl/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("catalog");
  return { title: t("pageTitle"), description: t("pageDescription") };
}

export default async function ModelsPage({
  searchParams,
}: {
  searchParams: { category?: string; project_id?: string };
}) {
  const t = await getTranslations("catalog");
  const [networks, freeNetworks, categories] = await Promise.all([
    serverListNetworks(),
    serverListNetworks({ is_free: true }),
    serverListCategories(),
  ]);

  const projectId = searchParams.project_id ? parseInt(searchParams.project_id, 10) : undefined;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-[28px] font-bold text-[#1A1A1A]">{t("pageTitle")}</h1>
        <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.58)]">
          {t("modelsAvailable", { count: networks?.length ?? 0 })}
        </p>
      </div>

      <CatalogClient
        networks={networks ?? []}
        freeNetworks={freeNetworks ?? []}
        categories={categories ?? []}
        initialCategory={searchParams.category}
        projectId={projectId}
      />
    </div>
  );
}
