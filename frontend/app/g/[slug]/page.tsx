import type { Metadata } from "next";
import Link from "next/link";
import { Clock, Cpu, LogIn, Sparkles } from "lucide-react";
import type { PublicGeneration } from "@/lib/api/types";
import { TryPromptButton } from "./TryPromptButton";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1").replace(/\/$/, "");

async function fetchGeneration(slug: string): Promise<PublicGeneration | null> {
  try {
    const res = await fetch(`${BASE}/generations/${slug}/public/`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const gen = await fetchGeneration(params.slug);
  if (!gen) return { title: "Генерация не найдена — Aineron" };
  const title = gen.prompt ? gen.prompt.slice(0, 80) : "AI-генерация на Aineron";
  const description = gen.prompt
    ? gen.prompt.slice(0, 160)
    : `Сгенерировано на Aineron.ru${gen.model_name ? ` моделью ${gen.model_name}` : ""}`;
  const images = gen.media_type === "image" && gen.image_url ? [{ url: gen.image_url }] : undefined;
  return {
    title: `${title} — Aineron`,
    description,
    openGraph: {
      title,
      description,
      siteName: "Aineron.ru",
      type: "website",
      images,
    },
    twitter: {
      card: gen.media_type === "image" && gen.image_url ? "summary_large_image" : "summary",
      title,
      description,
      images: gen.media_type === "image" && gen.image_url ? [gen.image_url] : undefined,
    },
  };
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default async function PublicGenerationPage({ params }: { params: { slug: string } }) {
  const gen = await fetchGeneration(params.slug);

  if (!gen) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f7f7f8]">
        <div className="text-center">
          <p className="text-[17px] font-medium text-[#1A1A1A]">Генерация не найдена</p>
          <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.45)]">
            Ссылка недействительна или публикация снята
          </p>
          <Link href="/gallery/" className="mt-4 inline-block text-[15px] text-[#D97757] hover:underline">
            В галерею
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#f7f7f8]">
      {/* Header */}
      <header className="border-b border-[rgba(13,13,13,0.08)] bg-white">
        <div className="mx-auto flex max-w-[860px] items-center justify-between px-4 py-3">
          <Link href="/" className="text-[15px] font-semibold tracking-tight text-[#1A1A1A]">
            Aineron.ru
          </Link>
          <Link href="/gallery/" className="text-[14px] text-[rgba(13,13,13,0.50)] hover:text-[#1A1A1A]">
            Публичная галерея
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[860px] px-4 py-8">
        {/* Media */}
        <div className="overflow-hidden rounded-[16px] border border-[rgba(13,13,13,0.09)] bg-black">
          {gen.media_type === "video" ? (
            <video
              src={gen.image_url}
              controls
              className="mx-auto max-h-[70vh] w-full object-contain"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={gen.image_url}
              alt={gen.prompt || "AI-генерация"}
              className="mx-auto max-h-[70vh] w-full object-contain"
            />
          )}
        </div>

        {/* Meta */}
        <div className="mt-5 rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
          {gen.prompt && (
            <>
              <h2 className="mb-1.5 text-[14px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
                Промт
              </h2>
              <p className="whitespace-pre-wrap text-[17px] leading-relaxed text-[rgba(13,13,13,0.85)]">
                {gen.prompt}
              </p>
            </>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3 text-[14px] text-[rgba(13,13,13,0.45)]">
            {gen.model_name && (
              <span className="inline-flex items-center gap-1.5 rounded-[6px] bg-[rgba(217,119,87,0.08)] px-2 py-1 font-medium text-[#D97757]">
                <Cpu size={12} />
                {gen.model_name}
              </span>
            )}
            <span className="inline-flex items-center gap-1.5">
              <Clock size={12} />
              {formatDate(gen.created_at)}
            </span>
            {gen.width && gen.height ? (
              <span>{gen.width}×{gen.height}</span>
            ) : null}
            <span className="ml-auto">Автор: {gen.username}</span>
          </div>

          {gen.prompt && (
            <div className="mt-4">
              <TryPromptButton prompt={gen.prompt} />
            </div>
          )}
        </div>

        {/* CTA */}
        <div className="mt-5 flex items-center gap-4 rounded-[14px] border border-[rgba(217,119,87,0.15)] bg-[rgba(217,119,87,0.04)] p-5">
          <div className="hidden h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-[rgba(217,119,87,0.10)] sm:flex">
            <Sparkles size={22} className="text-[#D97757]" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-medium text-[#1A1A1A]">
              Создайте похожее на Aineron.ru
            </p>
            <p className="mt-0.5 text-[14px] leading-relaxed text-[rgba(13,13,13,0.55)]">
              Десятки моделей для генерации изображений и видео в одном кабинете.
            </p>
          </div>
          <Link
            href="/login/"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            <LogIn size={14} />
            Войти, чтобы создать
          </Link>
        </div>
      </main>
    </div>
  );
}
