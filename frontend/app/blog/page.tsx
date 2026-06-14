import type { Metadata } from "next";
import Link from "next/link";
import { CalendarDays, Eye } from "lucide-react";
import { serverListBlogPosts, serverListBlogCategories } from "@/lib/api/server";

export const metadata: Metadata = {
  title: "Блог — AI-нейросети, гайды и сравнения",
  description:
    "Статьи о нейросетях без VPN: подключение GPT, Claude, Gemini через API, сравнения моделей, гайды для разработчиков.",
};

export const revalidate = 60;

export default async function BlogListPage({
  searchParams,
}: {
  searchParams: { category?: string };
}) {
  const [posts, categories] = await Promise.all([
    serverListBlogPosts({ category: searchParams.category }),
    serverListBlogCategories(),
  ]);

  const safePosts = posts ?? [];
  const safeCategories = categories ?? [];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: "Блог aineron.ru",
    description: "Статьи о нейросетях и AI API без VPN",
    url: "https://aineron.ru/blog/",
    inLanguage: "ru",
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="mb-8">
          <h1 className="text-[28px] font-bold text-[#0d0d0d]">Блог</h1>
          <p className="mt-2 text-[15px] text-[rgba(13,13,13,0.6)]">
            Гайды, сравнения и новости об AI-нейросетях
          </p>
        </div>

        {/* Category filter */}
        {safeCategories.length > 0 && (
          <div className="mb-8 flex flex-wrap gap-2">
            <Link
              href="/blog/"
              className={[
                "rounded-full px-4 py-1.5 text-[13px] font-medium transition-all",
                !searchParams.category
                  ? "bg-[#0d0d0d] text-white"
                  : "border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.3)]",
              ].join(" ")}
            >
              Все
            </Link>
            {safeCategories.map((cat) => (
              <Link
                key={cat.id}
                href={`/blog/?category=${cat.slug}`}
                className={[
                  "rounded-full px-4 py-1.5 text-[13px] font-medium transition-all",
                  searchParams.category === cat.slug
                    ? "bg-[#0d0d0d] text-white"
                    : "border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.3)]",
                ].join(" ")}
              >
                {cat.name}
              </Link>
            ))}
          </div>
        )}

        {safePosts.length === 0 ? (
          <div className="py-16 text-center text-[14px] text-[rgba(13,13,13,0.45)]">
            Статей пока нет
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {safePosts.map((post) => (
              <Link
                key={post.id}
                href={`/blog/${post.slug}/`}
                className="group flex flex-col rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white overflow-hidden transition-all hover:border-[rgba(13,13,13,0.25)] hover:shadow-sm"
              >
                {post.preview_image_url && (
                  <div className="aspect-[16/9] overflow-hidden">
                    <img
                      src={post.preview_image_url}
                      alt={post.title}
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    />
                  </div>
                )}
                <div className="flex flex-1 flex-col p-5">
                  {post.category && (
                    <span className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#0a7cff]">
                      {post.category.name}
                    </span>
                  )}
                  <h2 className="mb-2 text-[15px] font-semibold leading-snug text-[#0d0d0d] group-hover:text-[#0a7cff] transition-colors">
                    {post.title}
                  </h2>
                  <p className="mb-4 flex-1 text-[13px] leading-relaxed text-[rgba(13,13,13,0.6)]">
                    {post.preview_text}
                  </p>
                  <div className="flex items-center gap-4 text-[11px] text-[rgba(13,13,13,0.4)]">
                    <span className="flex items-center gap-1">
                      <CalendarDays size={11} />
                      {new Date(post.published_at).toLocaleDateString("ru-RU", {
                        day: "numeric",
                        month: "long",
                        year: "numeric",
                      })}
                    </span>
                    <span className="flex items-center gap-1">
                      <Eye size={11} />
                      {post.views_count}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
