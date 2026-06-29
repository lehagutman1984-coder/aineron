import type { Metadata } from "next";
import Link from "next/link";
import { FileText, MessageSquare, Folder, Code2, BookOpen, Briefcase, Zap, Globe, Palette, Clock } from "lucide-react";
import type { PublicSpace } from "@/lib/api/types";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1").replace(/\/$/, "");

async function fetchSpace(slug: string): Promise<PublicSpace | null> {
  try {
    const res = await fetch(`${BASE}/public/spaces/${slug}/`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: { params: { slug: string } }): Promise<Metadata> {
  const space = await fetchSpace(params.slug);
  if (!space) return { title: "Space не найден — Aineron" };
  return {
    title: `${space.name} — Project Space на Aineron`,
    description: space.system_prompt
      ? space.system_prompt.slice(0, 160)
      : `Project Space «${space.name}» на платформе Aineron.ru`,
    openGraph: {
      title: `${space.name} — Project Space`,
      description: space.system_prompt?.slice(0, 160) ?? `Project Space на Aineron.ru`,
      siteName: "Aineron.ru",
      type: "website",
    },
  };
}

const ICON_MAP: Record<string, React.ElementType> = {
  Folder, Code2, BookOpen, Briefcase, Zap, Globe, Palette, MessageSquare,
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "numeric", month: "long", year: "numeric",
  });
}

const FILE_TYPE_LABEL: Record<string, string> = {
  pdf: "PDF", doc: "Документ", text: "Текст", code: "Код", other: "Файл",
};

export default async function PublicSpacePage({ params }: { params: { slug: string } }) {
  const space = await fetchSpace(params.slug);

  if (!space) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f7f7f8]">
        <div className="text-center">
          <p className="text-[17px] font-medium text-[#1A1A1A]">Space не найден</p>
          <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.45)]">Ссылка недействительна или доступ ограничен</p>
          <Link href="/" className="mt-4 inline-block text-[15px] text-[#D97757] hover:underline">
            На главную
          </Link>
        </div>
      </div>
    );
  }

  const SpaceIcon = ICON_MAP[space.icon] ?? Folder;

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      {/* Header */}
      <header className="border-b border-[rgba(13,13,13,0.08)] bg-white">
        <div className="mx-auto flex max-w-[760px] items-center justify-between px-4 py-3">
          <Link href="/" className="text-[15px] font-semibold text-[#1A1A1A] tracking-tight">
            Aineron.ru
          </Link>
          <span className="text-[13px] text-[rgba(13,13,13,0.40)]">Project Space</span>
        </div>
      </header>

      <main className="mx-auto max-w-[760px] px-4 py-10">
        {/* Space title card */}
        <div className="mb-6 flex items-center gap-4">
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[14px]"
            style={{ background: `${space.color}18` }}
          >
            <SpaceIcon size={26} style={{ color: space.color }} />
          </div>
          <div>
            <h1 className="text-[22px] font-bold text-[#1A1A1A] leading-tight">{space.name}</h1>
            <p className="mt-0.5 flex items-center gap-1.5 text-[14px] text-[rgba(13,13,13,0.40)]">
              <Clock size={11} />
              Создан {formatDate(space.created_at)}
            </p>
          </div>
        </div>

        {/* Instructions */}
        {space.system_prompt && (
          <section className="mb-6 rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
            <div className="mb-3 flex items-center gap-2">
              <FileText size={14} className="text-[rgba(13,13,13,0.40)]" />
              <h2 className="text-[15px] font-semibold text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
                Инструкции
              </h2>
            </div>
            <p className="whitespace-pre-wrap text-[16px] leading-relaxed text-[rgba(13,13,13,0.80)]">
              {space.system_prompt}
            </p>
          </section>
        )}

        {/* Knowledge base files */}
        {space.public_show_files && space.files.length > 0 && (
          <section className="mb-6 rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen size={14} className="text-[rgba(13,13,13,0.40)]" />
              <h2 className="text-[15px] font-semibold text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
                База знаний
              </h2>
              <span className="ml-auto rounded-full bg-[rgba(13,13,13,0.07)] px-2 py-0.5 text-[13px] font-medium text-[rgba(13,13,13,0.50)]">
                {space.files.length} {space.files.length === 1 ? "файл" : space.files.length < 5 ? "файла" : "файлов"}
              </span>
            </div>
            <div className="divide-y divide-[rgba(13,13,13,0.07)]">
              {space.files.map((f) => (
                <div key={f.id} className="flex items-center justify-between py-2.5">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileText size={14} className="shrink-0 text-[rgba(13,13,13,0.35)]" />
                    <span className="truncate text-[15px] text-[#1A1A1A]">{f.filename}</span>
                    <span className="shrink-0 rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 text-[12px] text-[rgba(13,13,13,0.45)]">
                      {FILE_TYPE_LABEL[f.file_type] ?? "Файл"}
                    </span>
                  </div>
                  <span className="ml-3 shrink-0 text-[14px] text-[rgba(13,13,13,0.40)]">
                    {formatSize(f.file_size)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Chats */}
        {space.public_show_chats && space.chats.length > 0 && (
          <section className="mb-6 rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
            <div className="mb-3 flex items-center gap-2">
              <MessageSquare size={14} className="text-[rgba(13,13,13,0.40)]" />
              <h2 className="text-[15px] font-semibold text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
                Чаты
              </h2>
            </div>
            <div className="divide-y divide-[rgba(13,13,13,0.07)]">
              {space.chats.map((c) => (
                <div key={c.id} className="flex items-center justify-between py-2.5">
                  <span className="truncate text-[15px] text-[#1A1A1A]">{c.title || "Без названия"}</span>
                  <span className="ml-3 shrink-0 text-[14px] text-[rgba(13,13,13,0.40)]">
                    {new Date(c.updated_at).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}
                  </span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* CTA */}
        <div className="rounded-[14px] border border-[rgba(217,119,87,0.15)] bg-[rgba(217,119,87,0.04)] p-5">
          <p className="text-[15px] font-medium text-[#1A1A1A]">
            Создайте свой Project Space на Aineron.ru
          </p>
          <p className="mt-1 text-[14px] leading-relaxed text-[rgba(13,13,13,0.55)]">
            Организуйте чаты, загружайте документы в базу знаний и подключайте git-репозитории.
          </p>
          <Link
            href="/"
            className="mt-3 inline-flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] transition-colors"
          >
            Попробовать бесплатно
          </Link>
        </div>
      </main>
    </div>
  );
}
