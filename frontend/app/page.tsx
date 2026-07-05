import Link from "next/link";
import {
  ArrowRight, Code2, ImageIcon, Check, X,
  Wallet, ShieldCheck, Layers, Sparkles,
} from "lucide-react";
import { serverListNetworks } from "@/lib/api/server";
import type { NetworkListItem } from "@/lib/api/types";
import { formatRub } from "@/lib/money";
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

export default async function HomePage() {
  const [popular, freeNetworks] = await Promise.all([
    getPopularNetworks(),
    getFreeNetworks(),
  ]);
  const freeCount = freeNetworks.length;

  return (
    <>
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-24 text-center sm:px-6">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[rgba(217,119,87,0.25)] bg-[rgba(217,119,87,0.06)] px-3.5 py-1 text-[15px] text-[#D97757]">
          <ShieldCheck size={13} />
          Российский сервис — без VPN и зарубежных карт
        </div>

        <h1 className="mb-4 text-[40px] font-bold leading-tight tracking-tight text-[var(--text-primary)] sm:text-[54px]">
          Все нейросети в одном окне
        </h1>

        <p className="mx-auto mb-3 max-w-2xl text-[18px] leading-relaxed text-[var(--text-secondary)]">
          <HeroTypewriter />
        </p>
        <p className="mx-auto mb-9 max-w-xl text-[17px] text-[var(--text-tertiary)]">
          GPT-4o, Claude, Gemini, Midjourney и 200+ моделей. Один аккаунт, оплата рублями.
        </p>

        <HomeCta placement="hero" />
      </section>

      {/* ── Popular models ────────────────────────────────────────────────────── */}
      {popular.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-16 pt-4 sm:px-6">
          <div className="mb-8 flex items-end justify-between">
            <div>
              <h2 className="text-[22px] font-bold text-[var(--text-primary)]">Популярные модели</h2>
              <p className="mt-1 text-[16px] text-[var(--text-tertiary)]">
                Самые востребованные нейросети
              </p>
            </div>
            <Link
              href="/models/"
              className="flex items-center gap-1 text-[15px] text-[#D97757] transition-colors hover:text-[#C4623E]"
            >
              Все модели
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {popular.slice(0, 6).map((n) => (
              <NetworkCard key={n.id} network={n} />
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
                  {freeCount} бесплатных текстовых моделей
                </h2>
                <p className="mt-1.5 max-w-xl text-[16px] leading-relaxed text-[var(--text-secondary)]">
                  GPT-OSS, Qwen3, Gemma, DeepSeek R1 и другие нейросети для чата — 0 ₽,
                  без пополнения баланса. Доступны сразу после регистрации.
                </p>
              </div>
            </div>
            <Link
              href="/models/?category=__free__"
              className="inline-flex shrink-0 items-center gap-2 rounded-[12px] bg-[#D97757] px-5 py-3 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
            >
              Открыть бесплатные модели
              <ArrowRight size={16} />
            </Link>
          </div>
        </section>
      )}

      {/* ── Features grid ─────────────────────────────────────────────────────── */}
      <section className="border-t border-[var(--border-tertiary)] bg-[var(--background-tertiary)]">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <h2 className="mb-10 text-center text-[24px] font-bold text-[var(--text-primary)]">
            Почему aineron.ru
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparison table ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <div className="mb-10 text-center">
          <h2 className="text-[26px] font-bold text-[var(--text-primary)]">Честное сравнение</h2>
          <p className="mt-2 text-[17px] text-[var(--text-secondary)]">
            aineron.ru против мировых лидеров
          </p>
        </div>

        <div className="overflow-x-auto rounded-[16px] border border-[var(--border-primary)] bg-[var(--card-bg)]">
          <table className="w-full min-w-[480px] text-[15px]">
            <thead>
              <tr className="border-b border-[var(--border-secondary)]">
                <th className="px-5 py-3.5 text-left font-medium text-[var(--text-tertiary)]">
                  Возможность
                </th>
                <th className="px-4 py-3.5 text-center font-bold text-[#D97757]">aineron.ru</th>
                <th className="px-4 py-3.5 text-center font-medium text-[var(--text-secondary)]">ChatGPT</th>
                <th className="px-4 py-3.5 text-center font-medium text-[var(--text-secondary)]">Gemini</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row, i) => (
                <tr
                  key={row.feature}
                  className={i % 2 === 0 ? "bg-[var(--background-tertiary)]" : ""}
                >
                  <td className="px-5 py-3 text-[var(--text-primary)]">{row.feature}</td>
                  <td className="px-4 py-3 text-center"><Cell val={row.aineron} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={row.chatgpt} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={row.gemini} /></td>
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
            <h2 className="text-[24px] font-bold text-[var(--text-primary)]">Простая оплата в рублях</h2>
            <p className="mt-2 text-[17px] text-[var(--text-secondary)]">
              Пополняйте баланс и тратьте на любую модель. Средства не сгорают.
            </p>
          </div>
          <div className="grid grid-cols-1 divide-y divide-[var(--border-tertiary)] border-t border-[var(--border-secondary)] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
            {PRICING.map((p) => (
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
              Не нужна карта для старта
            </p>
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <h2 className="mb-8 text-center text-[24px] font-bold text-[var(--text-primary)]">
          Частые вопросы
        </h2>
        <FaqAccordion />
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────────── */}
      <section className="border-t border-[var(--border-tertiary)] bg-[#1A1A1A]">
        <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
          <h2 className="mb-3 text-[28px] font-bold text-white">
            Начните прямо сейчас
          </h2>
          <p className="mb-8 text-[16px] text-[rgba(255,255,255,0.55)]">
            10 ₽ бесплатно. Без VPN, без зарубежных карт.
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
function NetworkCard({ network }: { network: NetworkListItem }) {
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
          {formatRub(network.cost_kopecks)} / сообщение
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

// ── Data ──────────────────────────────────────────────────────────────────────
const FEATURES = [
  { icon: Layers, title: "Все модели сразу", text: "GPT-4o, Claude, Gemini, Midjourney и 200+ моделей — один аккаунт и общий баланс." },
  { icon: ShieldCheck, title: "Без VPN", text: "Серверы в России, оплата рублями. Работает с любого устройства в РФ." },
  { icon: Code2, title: "API для разработчиков", text: "OpenAI-совместимый API. Подключите Cursor, VS Code или свой продукт." },
  { icon: ImageIcon, title: "Текст, фото и видео", text: "Чат, генерация изображений и видео — в одном интерфейсе." },
];

const COMPARISON: {
  feature: string;
  aineron: boolean | string;
  chatgpt: boolean | string;
  gemini: boolean | string;
}[] = [
  { feature: "Работает в России без VPN", aineron: true, chatgpt: false, gemini: false },
  { feature: "Оплата рублями и картой РФ", aineron: true, chatgpt: false, gemini: false },
  { feature: "GPT, Claude, Gemini в одном окне", aineron: true, chatgpt: false, gemini: false },
  { feature: "Сравнение моделей бок о бок", aineron: true, chatgpt: false, gemini: false },
  { feature: "Генерация изображений и видео", aineron: true, chatgpt: true, gemini: true },
  { feature: "Загрузка файлов и веб-поиск", aineron: true, chatgpt: true, gemini: true },
  { feature: "OpenAI-совместимый API", aineron: true, chatgpt: true, gemini: false },
  { feature: "Telegram-бот с нейросетями", aineron: true, chatgpt: false, gemini: false },
];

const PRICING = [
  { title: "Старт", price: "10 ₽", sub: "бесплатно после регистрации" },
  { title: "Пополнение", price: "рублями", sub: "картой РФ или Telegram Stars" },
  { title: "Подписки", price: "со скидкой", sub: "пакеты для активных пользователей" },
];
