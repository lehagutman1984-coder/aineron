
import { Link } from "@/i18n/navigation";
import {
  ArrowRight, Code2, ImageIcon, Check, X,
  Wallet, ShieldCheck, Layers, Sparkles,
} from "lucide-react";
import { getTranslations } from "next-intl/server";
import { serverListNetworks } from "@/lib/api/server";
import type { NetworkListItem } from "@/lib/api/types";
import { formatMoney } from "@/lib/money";
import { HeroTypewriter } from "@/components/landing/HeroTypewriter";
import { FaqAccordion } from "@/components/landing/FaqAccordion";
import { HomeCta } from "@/components/landing/HomeCta";

export const revalidate = 3600;

async function getPopularNetworks(): Promise<NetworkListItem[]> {
  return (await serverListNetworks({ is_popular: true }).catch(() => [])) ?? [];
}

async function getFreeNetworks(): Promise<NetworkListItem[]> {
  return (await serverListNetworks({ is_free: true }).catch(() => [])) ?? [];
}

const FEATURE_ICONS = [Layers, ShieldCheck, Code2, ImageIcon];

// Матрица сравнения (галочки/крестики) — тексты строк в словаре home.comparisonRows
const COMPARISON_MARKS: { aineron: boolean; chatgpt: boolean; gemini: boolean }[] = [
  { aineron: true, chatgpt: false, gemini: false },
  { aineron: true, chatgpt: false, gemini: false },
  { aineron: true, chatgpt: false, gemini: false },
  { aineron: true, chatgpt: false, gemini: false },
  { aineron: true, chatgpt: true, gemini: true },
  { aineron: true, chatgpt: true, gemini: true },
  { aineron: true, chatgpt: true, gemini: false },
  { aineron: true, chatgpt: false, gemini: false },
];

export default async function HomePage() {
  const t = await getTranslations("home");
  const [popular, freeNetworks] = await Promise.all([
    getPopularNetworks(),
    getFreeNetworks(),
  ]);
  const freeCount = freeNetworks.length;

  const features = t.raw("features") as { title: string; text: string }[];
  const comparisonRows = t.raw("comparisonRows") as string[];
  const pricing = t.raw("pricing") as { title: string; price: string; sub: string }[];

  return (
    <>
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-24 text-center sm:px-6">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[rgba(217,119,87,0.25)] bg-[rgba(217,119,87,0.06)] px-3.5 py-1 text-[15px] text-[#D97757]">
          <ShieldCheck size={13} />
          {t("badge")}
        </div>

        <h1 className="mb-4 text-[40px] font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-[54px]">
          {t("title")}
        </h1>

        <p className="mx-auto mb-3 max-w-2xl text-[18px] leading-relaxed text-[var(--text-secondary)]">
          <HeroTypewriter />
        </p>
        <p className="mx-auto mb-9 max-w-xl text-[17px] text-[var(--text-tertiary)]">
          {t("subtitle")}
        </p>

        <HomeCta placement="hero" />
      </section>

      {/* ── Popular models ────────────────────────────────────────────────────── */}
      {popular.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-16 pt-4 sm:px-6">
          <div className="mb-8 flex items-end justify-between">
            <div>
              <h2 className="text-[22px] font-bold text-[var(--text-primary)]">{t("popularTitle")}</h2>
              <p className="mt-1 text-[16px] text-[var(--text-tertiary)]">
                {t("popularSubtitle")}
              </p>
            </div>
            <Link
              href="/models/"
              className="flex items-center gap-1 text-[15px] text-[#D97757] transition-colors hover:text-[#C4623E]"
            >
              {t("allModels")}
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {popular.slice(0, 6).map((n) => (
              <NetworkCard key={n.id} network={n} perMessage={t("perMessage", { price: formatMoney(n.cost_kopecks) })} />
            ))}
          </div>
        </section>
      )}

      {/* ── Free text models ──────────────────────────────────────────────────── */}
      {freeCount > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
          <div className="flex flex-col items-start gap-5 rounded-[20px] border border-[rgba(217,119,87,0.30)] bg-[rgba(217,119,87,0.06)] px-7 py-7 sm:flex-row sm:items-center sm:justify-between sm:px-9">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] bg-[rgba(217,119,87,0.12)] text-[#D97757]">
                <Sparkles size={22} />
              </div>
              <div>
                <h2 className="text-[20px] font-bold text-[var(--text-primary)] sm:text-[22px]">
                  {t("freeTitle", { count: freeCount })}
                </h2>
                <p className="mt-1.5 max-w-xl text-[16px] leading-relaxed text-[var(--text-secondary)]">
                  {t("freeText")}
                </p>
              </div>
            </div>
            <Link
              href="/models/?category=__free__"
              className="inline-flex shrink-0 items-center gap-2 rounded-[12px] bg-[#D97757] px-5 py-3 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
            >
              {t("freeCta")}
              <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      )}

      {/* ── Features grid ─────────────────────────────────────────────────────── */}
      <section className="border-t border-[var(--border-tertiary)] bg-[var(--background-tertiary)]">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <h2 className="mb-10 text-center text-[24px] font-bold text-[var(--text-primary)]">
            {t("whyTitle")}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f, i) => (
              <FeatureCard key={f.title} icon={FEATURE_ICONS[i] ?? Layers} title={f.title} text={f.text} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparison table ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <div className="mb-10 text-center">
          <h2 className="text-[26px] font-bold text-[var(--text-primary)]">{t("comparisonTitle")}</h2>
          <p className="mt-2 text-[17px] text-[var(--text-secondary)]">
            {t("comparisonSubtitle")}
          </p>
        </div>

        <div className="overflow-x-auto rounded-[16px] border border-[var(--border-primary)] bg-[var(--card-bg)]">
          <table className="w-full min-w-[480px] text-[15px]">
            <thead>
              <tr className="border-b border-[var(--border-secondary)]">
                <th className="px-5 py-3.5 text-start font-medium text-[var(--text-tertiary)]">
                  {t("comparisonFeatureCol")}
                </th>
                <th className="px-4 py-3.5 text-center font-bold text-[#D97757]">aineron</th>
                <th className="px-4 py-3.5 text-center font-medium text-[var(--text-secondary)]">ChatGPT</th>
                <th className="px-4 py-3.5 text-center font-medium text-[var(--text-secondary)]">Gemini</th>
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((feature, i) => (
                <tr
                  key={feature}
                  className={i % 2 === 0 ? "bg-[var(--background-tertiary)]" : ""}
                >
                  <td className="px-5 py-3 text-[var(--text-primary)]">{feature}</td>
                  <td className="px-4 py-3 text-center"><Cell val={COMPARISON_MARKS[i]?.aineron ?? true} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={COMPARISON_MARKS[i]?.chatgpt ?? false} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={COMPARISON_MARKS[i]?.gemini ?? false} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Pricing preview ───────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <div className="overflow-hidden rounded-[20px] border border-[var(--border-primary)] bg-[var(--card-bg)]">
          <div className="px-8 py-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[rgba(217,119,87,0.10)]">
              <Wallet size={22} className="text-[#D97757]" />
            </div>
            <h2 className="text-[24px] font-bold text-[var(--text-primary)]">{t("pricingTitle")}</h2>
            <p className="mt-2 text-[17px] text-[var(--text-secondary)]">
              {t("pricingSubtitle")}
            </p>
          </div>
          <div className="grid grid-cols-1 divide-y divide-[var(--border-tertiary)] border-t border-[var(--border-secondary)] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {pricing.map((p) => (
              <div key={p.title} className="px-7 py-6 text-center">
                <p className="mb-1 text-[15px] font-medium text-[var(--text-tertiary)]">{p.title}</p>
                <p className="text-[28px] font-bold text-[var(--text-primary)]">{p.price}</p>
                <p className="mt-1 text-[14px] text-[var(--text-tertiary)]">{p.sub}</p>
              </div>
            ))}
          </div>
          <div className="border-t border-[var(--border-secondary)] px-8 py-5 text-center">
            <HomeCta placement="pricing" />
            <p className="mt-2 text-[14px] text-[var(--text-tertiary)]">
              {t("pricingNote")}
            </p>
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <h2 className="mb-8 text-center text-[24px] font-bold text-[var(--text-primary)]">
          {t("faqTitle")}
        </h2>
        <FaqAccordion />
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────────── */}
      <section className="border-t border-[var(--border-tertiary)] bg-[#1A1A1A]">
        <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
          <h2 className="mb-3 text-[28px] font-bold text-white">
            {t("finalTitle")}
          </h2>
          <p className="mb-8 text-[16px] text-[rgba(255,255,255,0.55)]">
            {t("finalText")}
          </p>
          <HomeCta placement="final" />
        </div>
      </section>
    </>
  );
}

// ── Cell helper for comparison table ──────────────────────────────────────────
function Cell({ val }: { val: boolean | string }) {
  if (val === true) return <Check size={16} className="mx-auto text-[#22a85a]" />;
  if (val === false) return <X size={15} className="mx-auto text-[var(--text-tertiary)]" />;
  return <span className="text-[var(--text-secondary)]">{val}</span>;
}

// ── Network card ──────────────────────────────────────────────────────────────
function NetworkCard({ network, perMessage }: { network: NetworkListItem; perMessage: string }) {
  return (
    <Link
      href={`/models/${network.slug}/`}
      className="group flex flex-col gap-3 rounded-[12px] border border-[var(--border-primary)] bg-[var(--card-bg)] p-5 transition-all duration-150 hover:border-[#D97757] hover:shadow-sm"
    >
      <div className="flex items-center gap-3">
        {network.avatar ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={network.avatar}
            alt={network.name}
            width={36}
            height={36}
            className="rounded-[8px] object-cover"
          />
        ) : (
          <div className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
            {network.handle_photo || network.handle_video ? (
              <ImageIcon size={18} />
            ) : (
              <Code2 size={18} />
            )}
          </div>
        )}
        <div>
          <p className="text-[16px] font-semibold text-[var(--text-primary)] transition-colors group-hover:text-[#D97757]">
            {network.name}
          </p>
          <p className="text-[14px] text-[var(--text-tertiary)]">{network.category.name}</p>
        </div>
      </div>
      {network.description && (
        <p className="line-clamp-2 text-[15px] leading-relaxed text-[var(--text-secondary)]">
          {network.description}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-[14px] text-[var(--text-tertiary)]">
          {perMessage}
        </span>
        <ArrowRight
          size={14}
          className="text-[var(--text-tertiary)] transition-colors group-hover:text-[#D97757]"
        />
      </div>
    </Link>
  );
}

// ── Feature card ──────────────────────────────────────────────────────────────
function FeatureCard({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div className="rounded-[12px] border border-[var(--border-primary)] bg-[var(--card-bg)] p-5">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
        <Icon size={20} />
      </div>
      <p className="mb-1.5 text-[16px] font-semibold text-[var(--text-primary)]">{title}</p>
      <p className="text-[15px] leading-relaxed text-[var(--text-secondary)]">{text}</p>
    </div>
  );
}
