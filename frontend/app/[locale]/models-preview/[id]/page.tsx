import { redirect } from "@/i18n/navigation";

export const dynamic = "force-dynamic";

/**
 * См. комментарий в ../page.tsx — витрина-превью отработала, детали перенесены
 * на /models/[slug]. Точного 1:1 маппинга id->slug для редиректа нет (часть
 * id — витринные и отличаются от реальных слагов, см. SLUG_ALIASES в
 * lib/data/catalogReferencePricing.ts), поэтому ведём на общий каталог.
 */
export default async function ModelDetailPreviewPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect({ href: "/models", locale });
}
