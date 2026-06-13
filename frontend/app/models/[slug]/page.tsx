import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Star, MessageSquare, ImageIcon, Code2, ChevronDown } from "lucide-react";
import { serverGetNetwork, serverListNetworks } from "@/lib/api/server";
import { ChatStartForm } from "./ChatStartForm";

interface Props {
  params: { slug: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const network = await serverGetNetwork(params.slug);
  if (!network) return { title: "Модель не найдена" };
  return {
    title: network.seo_title || network.name,
    description: network.seo_description || network.description,
    keywords: network.seo_keywords,
    openGraph: {
      title: network.seo_title || network.name,
      description: network.seo_description || network.description,
      type: "website",
    },
  };
}

export async function generateStaticParams() {
  const networks = await serverListNetworks();
  return (networks ?? []).map((n) => ({ slug: n.slug }));
}

export const revalidate = 3600;

export default async function ModelDetailPage({ params }: Props) {
  const network = await serverGetNetwork(params.slug);
  if (!network) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: network.name,
    description: network.description,
    applicationCategory: "AIApplication",
    offers: {
      "@type": "Offer",
      priceCurrency: "RUB",
      price: "0",
    },
  };

  const isMedia = network.handle_photo || network.handle_video;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
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
          <ChatStartForm networkSlug={network.slug} isMedia={isMedia} />
        </div>

        {/* FAQ */}
        {network.faqs.length > 0 && (
          <div>
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
