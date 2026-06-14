import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CalendarDays, Eye, Tag } from "lucide-react";
import { serverGetBlogPost, serverListBlogPosts } from "@/lib/api/server";

interface Props {
  params: { slug: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = await serverGetBlogPost(params.slug);
  if (!post) return { title: "Статья не найдена" };

  const title = post.seo_title || post.title;
  const description = post.seo_description || post.preview_text;

  return {
    title,
    description,
    keywords: post.seo_keywords ?? undefined,
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
  const posts = await serverListBlogPosts();
  return (posts ?? []).map((p) => ({ slug: p.slug }));
}

export const revalidate = 60;

export default async function BlogPostPage({ params }: Props) {
  const post = await serverGetBlogPost(params.slug);
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
    inLanguage: "ru",
    publisher: {
      "@type": "Organization",
      name: "aineron.ru",
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
      { "@type": "ListItem", position: 1, name: "Главная", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Блог", item: `${SITE_URL}/blog/` },
      { "@type": "ListItem", position: 3, name: post.title, item: postUrl },
    ],
  };

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

      <article className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
        {/* Breadcrumbs */}
        <nav className="mb-6 flex items-center gap-2 text-[13px] text-[rgba(13,13,13,0.45)]">
          <Link href="/" className="hover:text-[#0d0d0d] transition-colors">Главная</Link>
          <span>/</span>
          <Link href="/blog/" className="hover:text-[#0d0d0d] transition-colors">Блог</Link>
          {post.category && (
            <>
              <span>/</span>
              <Link
                href={`/blog/?category=${post.category.slug}`}
                className="hover:text-[#0d0d0d] transition-colors"
              >
                {post.category.name}
              </Link>
            </>
          )}
        </nav>

        {/* Back */}
        <Link
          href="/blog/"
          className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d] transition-colors"
        >
          <ArrowLeft size={14} />
          Все статьи
        </Link>

        {/* Header */}
        <header className="mb-8">
          {post.category && (
            <span className="mb-3 inline-block text-[12px] font-semibold uppercase tracking-wide text-[#0a7cff]">
              {post.category.name}
            </span>
          )}
          <h1 className="mb-4 text-[30px] font-bold leading-tight text-[#0d0d0d] sm:text-[34px]">
            {post.title}
          </h1>
          <div className="flex flex-wrap items-center gap-4 text-[13px] text-[rgba(13,13,13,0.5)]">
            <span className="flex items-center gap-1.5">
              <CalendarDays size={13} />
              {new Date(post.published_at).toLocaleDateString("ru-RU", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </span>
            <span className="flex items-center gap-1.5">
              <Eye size={13} />
              {post.views_count} просмотров
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
          className="prose prose-neutral max-w-none text-[15px] leading-relaxed text-[rgba(13,13,13,0.8)]
            [&_h2]:mt-8 [&_h2]:text-[20px] [&_h2]:font-bold [&_h2]:text-[#0d0d0d]
            [&_h3]:mt-6 [&_h3]:text-[17px] [&_h3]:font-semibold [&_h3]:text-[#0d0d0d]
            [&_p]:mb-4
            [&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5
            [&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5
            [&_li]:mb-1
            [&_pre]:overflow-x-auto [&_pre]:rounded-[8px] [&_pre]:bg-[#f5f5f5] [&_pre]:p-4 [&_pre]:text-[13px]
            [&_code]:rounded [&_code]:bg-[#f5f5f5] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[13px] [&_code]:font-mono
            [&_a]:text-[#0a7cff] [&_a]:underline hover:[&_a]:no-underline
            [&_blockquote]:border-l-4 [&_blockquote]:border-[#0a7cff] [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-[rgba(13,13,13,0.6)]"
          dangerouslySetInnerHTML={{ __html: post.content }}
        />

        {/* Related networks */}
        {post.network_slugs.length > 0 && (
          <div className="mt-10 border-t border-[rgba(13,13,13,0.08)] pt-8">
            <p className="mb-3 flex items-center gap-2 text-[13px] font-semibold text-[#0d0d0d]">
              <Tag size={14} />
              Связанные нейросети
            </p>
            <div className="flex flex-wrap gap-2">
              {post.network_slugs.map((slug) => (
                <Link
                  key={slug}
                  href={`/models/${slug}/`}
                  className="rounded-full border border-[rgba(13,13,13,0.15)] px-3 py-1 text-[12px] text-[rgba(13,13,13,0.7)] transition-all hover:border-[#0a7cff] hover:text-[#0a7cff]"
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
