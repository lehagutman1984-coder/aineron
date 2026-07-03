import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

// Страница IDE-интеграций объединена с документацией API.
// Сохраняем входящие ссылки: /ide → /api-docs (раздел «Интеграция с IDE»).
export default function IdeRedirectPage() {
  redirect("/api-docs/#ide-cursor");
}
