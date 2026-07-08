import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations, getLocale } from "next-intl/server";
import { CalendarDays, Eye } from "lucide-react";
import { serverListBlogPosts, serverListBlogCategories } from "@/lib/api/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("blog");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
  };
}

export const dynamic = "force-dynamic";

export default async function BlogListPage({
  searchParams,
}: {
  searchParams: { category?: string };
}) {
  const t = await getTranslations("blog");
  const locale = await getLocale();
  const [posts, categories] = await Promise.all([
    serverListBlogPosts({ category: searchParams.category }),
    serverListBlogCategories(),
  ]);

  const safePosts = posts ?? [];
  const safeCategories = categories ?? [];

  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: t("jsonLdName"),
    description: t("jsonLdDescription"),
    url: `${SITE_URL}/blog/`,
    inLanguage: locale,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6">
        <div className="mb-8">
          <h1 className="text-[28px] font-bold text-[#1A1A1A]">{t("pageTitle")}</h1>
          <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.6)]">
            {t("pageSubtitle")}
          </p>
        </div>

        {/* Category filter */}
        {safeCategories.length > 0 && (
          <div className="mb-8 flex flex-wrap gap-2">
            <Link
              href="/blog/"
              className={[
                "rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
                !searchParams.category
                  ? "bg-[#1A1A1A] text-white"
                  : "border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.3)]",
              ].join(" ")}
            >
              {t("allCategories")}
            </Link>
            {safeCategories.map((cat) => (
              <Link
                key={cat.id}
                href={`/blog/?category=${cat.slug}`}
                className={[
                  "rounded-full px-4 py-1.5 text-[15px] font-medium transition-all",
                  searchParams.category === cat.slug
                    ? "bg-[#1A1A1A] text-white"
                    : "border border-[rgba(13,13,13,0.15)] text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.3)]",
                ].join(" ")}
              >
                {cat.name}
              </Link>
            ))}
          </div>
        )}

        {safePosts.length === 0 ? (
          <div className="py-16 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
            {t("noPostsYet")}
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
                    <span className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-[#D97757]">
                      {post.category.name}
                    </span>
                  )}
                  <h2 className="mb-2 text-[17px] font-semibold leading-snug text-[#1A1A1A] group-hover:text-[#D97757] transition-colors">
                    {post.title}
                  </h2>
                  <p className="mb-4 flex-1 text-[15px] leading-relaxed text-[rgba(13,13,13,0.6)]">
                    {post.preview_text}
                  </p>
                  <div className="flex items-center gap-4 text-[13px] text-[rgba(13,13,13,0.4)]">
                    <span className="flex items-center gap-1">
                      <CalendarDays size={11} />
                      {new Date(post.published_at).toLocaleDateString(locale, {
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
