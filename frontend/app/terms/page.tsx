import { FileText } from "lucide-react";
import Link from "next/link";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1").replace(/\/$/, "");

async function getLegalDoc(type: "privacy" | "terms") {
  try {
    const res = await fetch(`${API_BASE}/v1/legal/${type}/`, { next: { revalidate: 3600 } });
    if (!res.ok) return null;
    return res.json() as Promise<{ title: string; content: string; last_updated: string }>;
  } catch {
    return null;
  }
}

export async function generateMetadata() {
  const doc = await getLegalDoc("terms");
  return {
    title: doc?.title ?? "Пользовательское соглашение",
  };
}

export default async function TermsPage() {
  const doc = await getLegalDoc("terms");

  const date = doc?.last_updated
    ? new Date(doc.last_updated).toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div className="min-h-screen bg-[#f5f5f7] px-4 py-12">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center gap-3">
          <FileText size={20} className="text-[rgba(13,13,13,0.45)]" />
          <Link
            href="/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
          >
            Главная
          </Link>
          <span className="text-[13px] text-[rgba(13,13,13,0.25)]">/</span>
          <span className="text-[13px] text-[rgba(13,13,13,0.65)]">Пользовательское соглашение</span>
        </div>

        <div className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-8 shadow-sm">
          <h1 className="mb-2 text-[26px] font-bold text-[#0d0d0d]">
            {doc?.title ?? "Пользовательское соглашение"}
          </h1>
          {date && (
            <p className="mb-8 text-[13px] text-[rgba(13,13,13,0.45)]">
              Обновлено: {date}
            </p>
          )}

          {doc ? (
            <div
              className="prose prose-sm max-w-none text-[rgba(13,13,13,0.75)] [&_h2]:text-[18px] [&_h2]:font-semibold [&_h2]:text-[#0d0d0d] [&_h2]:mt-6 [&_h2]:mb-3 [&_p]:mb-3 [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5"
              dangerouslySetInnerHTML={{ __html: doc.content }}
            />
          ) : (
            <p className="text-[14px] text-[rgba(13,13,13,0.55)]">
              Документ находится в разработке. Свяжитесь с нами по адресу{" "}
              <a href="mailto:support@aineron.ru" className="text-[#f0a38a] hover:underline">
                support@aineron.ru
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
