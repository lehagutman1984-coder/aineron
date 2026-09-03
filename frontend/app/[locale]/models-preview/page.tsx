import { redirect } from "@/i18n/navigation";

export const dynamic = "force-dynamic";

/**
 * Витрина-превью выполнила свою роль 2026-09-02/03: её ₽/1М-цены и развёрнутые
 * детали (bestFor/supportedParameters/reasoningLevels) перенесены на реальный
 * /models и /models/[slug] (см. lib/data/catalogReferencePricing.ts), а список
 * моделей и биллинг в проде синхронизированы с тем, что здесь проверялось.
 * Роут оставлен редиректом — не 404 для старых ссылок/закладок.
 */
export default async function ModelsPreviewPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect({ href: "/models", locale });
}
