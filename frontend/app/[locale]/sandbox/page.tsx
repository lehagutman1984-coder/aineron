import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";

import {
  Box,
  ShieldCheck,
  Zap,
  Terminal,
  Globe,
  Wallet,
  ArrowRight,
  BookOpen,
} from "lucide-react";
import { getTranslations } from "next-intl/server";
import { formatMoney } from "@/lib/money";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";

function brandName(): string {
  const host = new URL(SITE_URL).host;
  return host.charAt(0).toUpperCase() + host.slice(1);
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("sandbox");
  const brand = brandName();
  return {
    title: t("metaTitle", { brand }),
    description: t("metaDescription", { price: formatMoney(50) }),
    keywords: t("metaKeywords"),
    alternates: { canonical: `${SITE_URL}/sandbox/` },
  };
}

const CODE_EXAMPLE = `# pip install aineron
from aineron import Sandbox

with Sandbox(template="python") as sbx:
    result = sbx.exec(code="print(2 + 2)")
    print(result.stdout)   # 4`;

export default async function SandboxLandingPage() {
  const t = await getTranslations("sandbox");

  const FEATURES = [
    { icon: ShieldCheck, title: t("feature1Title"), text: t("feature1Text") },
    { icon: Zap, title: t("feature2Title"), text: t("feature2Text") },
    { icon: Terminal, title: t("feature3Title"), text: t("feature3Text") },
    { icon: Globe, title: t("feature4Title"), text: t("feature4Text") },
    { icon: Wallet, title: t("feature5Title"), text: t("feature5Text") },
    { icon: BookOpen, title: t("feature6Title"), text: t("feature6Text") },
  ];

  const smallPrice = formatMoney(50);
  const standardPrice = formatMoney(100);

  const FAQ = [
    { q: t("faq1Q"), a: t("faq1A") },
    { q: t("faq2Q"), a: t("faq2A", { smallPrice, standardPrice }) },
    { q: t("faq3Q"), a: t("faq3A") },
    { q: t("faq4Q"), a: t("faq4A") },
    { q: t("faq5Q"), a: t("faq5A") },
  ];

  const JSON_LD = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };

  return (
    <main className="min-h-screen bg-white text-[#1A1A1A]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />

      {/* Hero */}
      <section className="mx-auto max-w-5xl px-4 pb-16 pt-20 sm:px-6">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <p className="mb-4 text-[14px] font-semibold uppercase tracking-wide text-[#D97757]">
              {t("heroEyebrow")}
            </p>
            <h1 className="text-[36px] font-bold leading-tight sm:text-[44px]">
              {t("heroTitle")}
            </h1>
            <p className="mt-5 text-[18px] leading-relaxed text-[rgba(13,13,13,0.6)]">
              {t("heroSubtitle")}
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/account/keys/"
                className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-6 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
              >
                {t("getApiKeyButton")}
                <ArrowRight size={18} />
              </Link>
              <Link
                href="/api-docs/"
                className="inline-flex items-center rounded-[10px] border border-[rgba(13,13,13,0.15)] px-6 py-3 text-[16px] font-medium text-[#1A1A1A] transition-colors hover:bg-[rgba(13,13,13,0.04)]"
              >
                {t("docsButton")}
              </Link>
            </div>
            <p className="mt-4 text-[14px] text-[rgba(13,13,13,0.45)]">
              {t("freeTrialNote")}
            </p>
          </div>
          <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-[#1A1A1A] p-5">
            <div className="mb-3 flex items-center gap-2 text-[13px] text-[rgba(255,255,255,0.45)]">
              <Box size={14} />
              quickstart.py
            </div>
            <pre className="overflow-x-auto text-[14px] leading-relaxed text-[#ECECEC]">
              <code>{CODE_EXAMPLE}</code>
            </pre>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] py-16">
        <div className="mx-auto max-w-5xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">
            {t("featuresTitle")}
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-6"
              >
                <f.icon size={24} className="mb-4 text-[#D97757]" />
                <h3 className="mb-2 text-[17px] font-semibold">{f.title}</h3>
                <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.6)]">
                  {f.text}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">
            {t("pricingTitle")}
          </h2>
          <div className="overflow-x-auto rounded-[12px] border border-[rgba(13,13,13,0.10)]">
            <table className="w-full text-start text-[15px]">
              <thead>
                <tr className="border-b border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] text-[rgba(13,13,13,0.55)]">
                  <th className="px-5 py-3 font-medium">{t("pricingSizeCol")}</th>
                  <th className="px-5 py-3 font-medium">{t("pricingResourcesCol")}</th>
                  <th className="px-5 py-3 font-medium">{t("pricingPriceCol")}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[rgba(13,13,13,0.08)]">
                  <td className="px-5 py-4 font-semibold">small</td>
                  <td className="px-5 py-4 text-[rgba(13,13,13,0.65)]">{t("pricingSmallResources")}</td>
                  <td className="px-5 py-4 font-semibold">{t("pricingPerMinute", { price: smallPrice })}</td>
                </tr>
                <tr>
                  <td className="px-5 py-4 font-semibold">standard</td>
                  <td className="px-5 py-4 text-[rgba(13,13,13,0.65)]">{t("pricingStandardResources")}</td>
                  <td className="px-5 py-4 font-semibold">{t("pricingPerMinute", { price: standardPrice })}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-[14px] text-[rgba(13,13,13,0.45)]">
            {t("pricingNote")}
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">{t("faqTitle")}</h2>
          <div className="flex flex-col gap-4">
            {FAQ.map((item) => (
              <div
                key={item.q}
                className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-6"
              >
                <h3 className="mb-2 text-[16px] font-semibold">{item.q}</h3>
                <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.6)]">
                  {item.a}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-10 text-center">
            <Link
              href="/api-docs/"
              className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-6 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
            >
              {t("ctaButton")}
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
