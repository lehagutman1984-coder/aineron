import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { getTranslations, getLocale } from "next-intl/server";
import { ArrowLeft, CalendarDays, Eye, Tag } from "lucide-react";
import { serverGetBlogPost, serverListBlogPosts } from "@/lib/api/server";
import { routing } from "@/i18n/routing";

interface Props {
  params: { slug: string };
}

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/$/, "");

// Посты блога не параллельные переводы (GLOBAL_EXPANSION_PLAN.md §4.3) — статья существует
// только на своём языке, но detail-эндпоинт ищет по slug без фильтра по lang, так что тот же
// slug технически открывается и под чужим locale-префиксом. Canonical всегда указывает на
// URL под собственным языком статьи, чтобы Google не индексировал дубли под другими локалями.
function canonicalUrl(postLanguage: string, slug: string): string {
  const prefix = postLanguage === routing.defaultLocale ? "" : `/${postLanguage}`;
  return `${SITE_URL}${prefix}/blog/${slug}/`;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const locale = await getLocale();
  const post = await serverGetBlogPost(params.slug, locale);
  if (!post) {
    const t = await getTranslations("blogPost");
    return { title: t("notFoundTitle") };
  }

  const title = post.seo_title || post.title;
  const description = post.seo_description || post.preview_text;

  return {
    title,
    description,
    keywords: post.seo_keywords ?? undefined,
    alternates: { canonical: canonicalUrl(post.language, post.slug) },
    openGraph: {
      title,
      description,
      type: "article",
      publishedTime: post.published_at,
      modifiedTime: post.updated_at,
      ...(post.preview_image_url && { images: [{ url: post.preview_image_url }] }),
    },
  };
}

export async function generateStaticParams() {
  const posts = await serverListBlogPosts().catch(() => []);
  return (posts ?? []).map((p) => ({ slug: p.slug }));
}

export const dynamic = "force-dynamic";

export default async function BlogPostPage({ params }: Props) {
  const t = await getTranslations("blogPost");
  const locale = await getLocale();
  const post = await serverGetBlogPost(params.slug, locale);
  if (!post) notFound();

  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";
  const postUrl = `${SITE_URL}/blog/${post.slug}/`;

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.seo_description || post.preview_text,
    datePublished: post.published_at,
    dateModified: post.updated_at,
    url: postUrl,
    inLanguage: locale,
    publisher: {
      "@type": "Organization",
      name: new URL(SITE_URL).host,
      url: SITE_URL,
    },
    ...(post.author_name && {
      author: { "@type": "Person", name: post.author_name },
    }),
    ...(post.preview_image_url && {
      image: { "@type": "ImageObject", url: post.preview_image_url },
    }),
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: t("breadcrumbHome"), item: SITE_URL },
      { "@type": "ListItem", position: 2, name: t("breadcrumbBlog"), item: `${SITE_URL}/blog/` },
      { "@type": "ListItem", position: 3, name: post.title, item: postUrl },
    ],
  };

  const faqJsonLd = post.faq_items?.length
    ? {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        mainEntity: post.faq_items.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      }
    : null;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />
      {faqJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
        />
      )}

      <article className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        {/* Breadcrumbs */}
        <nav className="mb-6 flex items-center gap-2 text-[15px] text-[rgba(13,13,13,0.45)]">
          <Link href="/" className="hover:text-[#1A1A1A] transition-colors">{t("breadcrumbHome")}</Link>
          <span>/</span>
          <Link href="/blog/" className="hover:text-[#1A1A1A] transition-colors">{t("breadcrumbBlog")}</Link>
          {post.category && (
            <>
              <span>/</span>
              <Link
                href={`/blog/?category=${post.category.slug}`}
                className="hover:text-[#1A1A1A] transition-colors"
              >
                {post.category.name}
              </Link>
            </>
          )}
        </nav>

        {/* Back */}
        <Link
          href="/blog/"
          className="mb-6 inline-flex items-center gap-1.5 text-[15px] text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] transition-colors"
        >
          <ArrowLeft size={14} />
          {t("backToAllPosts")}
        </Link>

        {/* Header */}
        <header className="mb-8">
          {post.category && (
            <span className="mb-3 inline-block text-[14px] font-semibold uppercase tracking-wide text-[#D97757]">
              {post.category.name}
            </span>
          )}
          <h1 className="mb-4 text-[30px] font-bold leading-tight text-[#1A1A1A] sm:text-[34px]">
            {post.title}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-[15px] text-[rgba(13,13,13,0.5)]">
            <span className="flex items-center gap-1.5">
              <CalendarDays size={13} />
              {new Date(post.published_at).toLocaleDateString(locale, {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
            <span className="flex items-center gap-1.5">
              <Eye size={13} />
              {t("viewsCount", { count: post.views_count })}
            </span>
            {post.author_name && (
              <span className="text-[rgba(13,13,13,0.5)]">{post.author_name}</span>
            )}
          </div>
        </header>

        {/* Preview image */}
        {post.preview_image_url && (
          <div className="mb-8 overflow-hidden rounded-[14px]">
            <img
              src={post.preview_image_url}
              alt={post.title}
              className="w-full object-cover"
            />
          </div>
        )}

        {/* Content */}
        <div
          className="prose prose-neutral max-w-none text-[17px] leading-relaxed text-[rgba(13,13,13,0.8)]
            [&_h2]:mt-8 [&_h2]:text-[20px] [&_h2]:font-bold [&_h2]:text-[#1A1A1A]
            [&_h3]:mt-6 [&_h3]:text-[17px] [&_h3]:font-semibold [&_h3]:text-[#1A1A1A]
            [&_p]:mb-4
            [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5
            [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5
            [&_li]:mb-1
            [&_pre]:overflow-x-auto [&_pre]:rounded-[8px] [&_pre]:bg-[#f5f5f5] [&_pre]:p-4 [&_pre]:text-[15px]
            [&_code]:rounded [&_code]:bg-[#f5f5f5] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[15px] [&_code]:font-mono
            [&_a]:text-[#D97757] [&_a]:underline hover:[&_a]:no-underline
            [&_blockquote]:border-l-4 [&_blockquote]:border-[#D97757] [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-[rgba(13,13,13,0.6)]"
          dangerouslySetInnerHTML={{ __html: post.content }}
        />

        {/* FAQ */}
        {post.faq_items?.length > 0 && (
          <div className="mt-10 border-t border-[rgba(13,13,13,0.08)] pt-8">
            <h2 className="mb-4 text-[20px] font-bold text-[#1A1A1A]">{t("faqHeading")}</h2>
            <div className="space-y-5">
              {post.faq_items.map((item, i) => (
                <div key={i}>
                  <p className="mb-1.5 text-[16px] font-semibold text-[#1A1A1A]">{item.question}</p>
                  <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.7)]">{item.answer}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Related networks */}
        {post.network_slugs.length > 0 && (
          <div className="mt-10 border-t border-[rgba(13,13,13,0.08)] pt-8">
            <p className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-[#1A1A1A]">
              <Tag size={14} />
              {t("relatedNetworks")}
            </p>
            <div className="flex flex-wrap gap-2">
              {post.network_slugs.map((slug) => (
                <Link
                  key={slug}
                  href={`/models/${slug}/`}
                  className="rounded-full border border-[rgba(13,13,13,0.15)] px-3 py-1 text-[14px] text-[rgba(13,13,13,0.7)] transition-all hover:border-[#D97757] hover:text-[#D97757]"
                >
                  {slug}
                </Link>
              ))}
            </div>
          </div>
        )}
      </article>
    </>
  );
}
