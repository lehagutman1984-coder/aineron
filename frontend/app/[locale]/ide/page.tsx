import { redirect } from "@/i18n/navigation";

export const dynamic = "force-dynamic";

// Страница IDE-интеграций объединена с документацией API.
// Сохраняем входящие ссылки: /ide → /api-docs (раздел «Интеграция с IDE»).
export default async function IdeRedirectPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  redirect({ href: "/api-docs/#ide-cursor", locale });
}
