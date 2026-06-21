import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Star, MessageSquare, ImageIcon, Code2, ChevronDown } from "lucide-react";
import { serverGetNetwork, serverListNetworks } from "@/lib/api/server";
import { ChatStartForm } from "./ChatStartForm";

interface Props {
  params: { slug: string };
  searchParams?: { project_id?: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const network = await serverGetNetwork(params.slug);
  if (!network) return { title: "Модель не найдена" };
  const title = network.seo_title || network.name;
  const description = network.seo_description || network.description;
  return {
    title,
    description,
    keywords: network.seo_keywords,
    openGraph: {
      title,
      description,
      type: "website",
      ...(network.avatar && { images: [{ url: network.avatar }] }),
    },
  };
}

export async function generateStaticParams() {
  const networks = await serverListNetworks().catch(() => []);
  return (networks ?? []).map((n) => ({ slug: n.slug }));
}

export const dynamic = "force-dynamic";

export default async function ModelDetailPage({ params, searchParams }: Props) {
  const [network, allNetworks] = await Promise.all([
    serverGetNetwork(params.slug),
    serverListNetworks(),
  ]);
  if (!network) notFound();

  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";
  const pageUrl = `${SITE_URL}/models/${network.slug}/`;

  const softwareAppJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: network.name,
    description: network.seo_description || network.description,
    applicationCategory: "AIApplication",
    url: pageUrl,
    inLanguage: "ru",
    offers: {
      "@type": "Offer",
      priceCurrency: "RUB",
      price: network.unlimited ? "0" : String(network.cost_per_message),
      description: network.unlimited ? "Безлимит по тарифу" : `${network.cost_per_message} звезд за сообщение`,
    },
    ...(network.avatar && { image: network.avatar }),
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Главная", item: SITE_URL },
      { "@type": "ListItem", position: 2, name: "Каталог", item: `${SITE_URL}/models/` },
      { "@type": "ListItem", position: 3, name: network.name, item: pageUrl },
    ],
  };

  const faqJsonLd =
    network.faqs.length > 0
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: network.faqs.map((faq) => ({
            "@type": "Question",
            name: faq.question,
            acceptedAnswer: { "@type": "Answer", text: faq.answer },
          })),
        }
      : null;

  const relatedNetworks = (allNetworks ?? [])
    .filter(
      (n) => n.slug !== network.slug && n.category.slug === network.category.slug
    )
    .slice(0, 4);

  const isMedia = network.handle_photo || network.handle_video;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareAppJsonLd) }}
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

      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
        {/* Breadcrumbs */}
        <nav className="mb-4 flex items-center gap-2 text-[13px] text-[rgba(13,13,13,0.45)]">
          <Link href="/" className="hover:text-[#0d0d0d] transition-colors">Главная</Link>
          <span>/</span>
          <Link href="/models/" className="hover:text-[#0d0d0d] transition-colors">Каталог</Link>
          <span>/</span>
          <span className="text-[rgba(13,13,13,0.65)]">{network.name}</span>
        </nav>

        {/* Back */}
        <Link
          href="/models/"
          className="mb-6 inline-flex items-center gap-1.5 text-[13px] text-[rgba(13,13,13,0.55)] hover:text-[#0d0d0d] transition-colors"
        >
          <ArrowLeft size={14} />
          Каталог
        </Link>

        {/* Header */}
        <div className="mb-8 flex items-start gap-5">
          {network.avatar ? (
            <img
              src={network.avatar}
              alt={network.name}
              width={64}
              height={64}
              className="rounded-[14px] object-cover shrink-0"
            />
          ) : (
            <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[14px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
              {isMedia ? <ImageIcon size={28} /> : <Code2 size={28} />}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <h1 className="text-[26px] font-bold text-[#0d0d0d]">{network.name}</h1>
              <span className="rounded-full bg-[rgba(13,13,13,0.07)] px-2.5 py-0.5 text-[12px] text-[rgba(13,13,13,0.55)]">
                {network.category.name}
              </span>
            </div>
            <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
              {network.description}
            </p>
          </div>
        </div>

        {/* Stats row */}
        <div className="mb-8 flex flex-wrap gap-4">
          <StatChip
            icon={<Star size={14} />}
            label={
              network.unlimited
                ? "Безлимит"
                : `${network.cost_per_message} зв. / сообщение`
            }
          />
          {network.unlimited && network.messages_limit > 0 && (
            <StatChip
              icon={<MessageSquare size={14} />}
              label={`${network.messages_limit} сообщений в день`}
            />
          )}
          {network.handle_photo && (
            <StatChip icon={<ImageIcon size={14} />} label="Изображения" />
          )}
          {network.handle_video && (
            <StatChip icon={<ImageIcon size={14} />} label="Видео" />
          )}
        </div>

        {/* Chat start form */}
        <div className="mb-12 rounded-[14px] border border-[rgba(13,13,13,0.12)] bg-white p-6">
          <h2 className="mb-4 text-[16px] font-semibold text-[#0d0d0d]">
            {isMedia ? "Опишите, что нужно сгенерировать" : "Начать диалог"}
          </h2>
          <ChatStartForm
            networkSlug={network.slug}
            isMedia={isMedia}
            configJson={network.config_json as import("@/lib/api/types").ModelConfigJson | null}
            projectId={searchParams?.project_id ? parseInt(searchParams.project_id, 10) : undefined}
          />
        </div>

        {/* FAQ */}
        {network.faqs.length > 0 && (
          <div className="mb-12">
            <h2 className="mb-5 text-[20px] font-semibold text-[#0d0d0d]">
              Частые вопросы
            </h2>
            <div className="flex flex-col gap-3">
              {network.faqs.map((faq) => (
                <details
                  key={faq.id}
                  className="group rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white"
                >
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[14px] font-medium text-[#0d0d0d]">
                    {faq.question}
                    <ChevronDown
                      size={16}
                      className="shrink-0 text-[rgba(13,13,13,0.4)] transition-transform group-open:rotate-180"
                    />
                  </summary>
                  <div className="px-5 pb-4 text-[14px] leading-relaxed text-[rgba(13,13,13,0.65)]">
                    {faq.answer}
                  </div>
                </details>
              ))}
            </div>
          </div>
        )}

        {/* Related models */}
        {relatedNetworks.length > 0 && (
          <div>
            <h2 className="mb-5 text-[18px] font-semibold text-[#0d0d0d]">
              Похожие модели — {network.category.name}
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {relatedNetworks.map((n) => (
                <Link
                  key={n.id}
                  href={`/models/${n.slug}/`}
                  className="flex flex-col items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white p-4 text-center transition-all hover:border-[rgba(13,13,13,0.25)] hover:shadow-sm"
                >
                  {n.avatar ? (
                    <img src={n.avatar} alt={n.name} width={36} height={36} className="rounded-[8px]" />
                  ) : (
                    <div className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-[rgba(10,124,255,0.08)] text-[#0a7cff]">
                      <Code2 size={16} />
                    </div>
                  )}
                  <span className="text-[12px] font-medium leading-tight text-[#0d0d0d]">
                    {n.name}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function StatChip({
  icon,
  label,
}: {
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[13px] text-[rgba(13,13,13,0.65)]">
      <span className="text-[#0a7cff]">{icon}</span>
      {label}
    </div>
  );
}
