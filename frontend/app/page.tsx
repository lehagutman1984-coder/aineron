import Link from "next/link";
import {
  ArrowRight, Zap, Globe, Code2, ImageIcon, Check, X,
  Users, MessageSquare, Wallet, ShieldCheck,
} from "lucide-react";
import { serverListNetworks } from "@/lib/api/server";
import type { NetworkListItem } from "@/lib/api/types";
import { formatRub } from "@/lib/money";
import { HeroTypewriter } from "@/components/landing/HeroTypewriter";
import { UseCaseTabs } from "@/components/landing/UseCaseTabs";
import { FaqAccordion } from "@/components/landing/FaqAccordion";

export const revalidate = 3600;

async function getPopularNetworks(): Promise<NetworkListItem[]> {
  return (await serverListNetworks({ is_popular: true }).catch(() => [])) ?? [];
}

export default async function HomePage() {
  const popular = await getPopularNetworks();

  return (
    <>
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-24 text-center sm:px-6">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[rgba(217,119,87,0.25)] bg-[rgba(217,119,87,0.06)] px-3.5 py-1 text-[15px] text-[#D97757]">
          <ShieldCheck size={13} />
          Российский сервис — без VPN и зарубежных карт
        </div>

        <h1 className="mb-4 text-[40px] font-bold leading-tight tracking-tight text-[#1A1A1A] sm:text-[54px]">
          Нейросети без границ
        </h1>

        <p className="mx-auto mb-3 max-w-2xl text-[18px] leading-relaxed text-[rgba(13,13,13,0.55)]">
          <HeroTypewriter />
        </p>
        <p className="mx-auto mb-9 max-w-xl text-[17px] text-[rgba(13,13,13,0.45)]">
          GPT-4o, Claude, Gemini, Midjourney и 200+ моделей. Оплата рублями, один кошелёк.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/register/"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-7 py-3 text-[17px] font-medium text-white hover:bg-[#C4623E] transition-colors"
          >
            Начать бесплатно
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/models/"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-7 py-3 text-[17px] font-medium text-[#1A1A1A] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Смотреть каталог
          </Link>
        </div>
      </section>

      {/* ── Social proof bar ──────────────────────────────────────────────────── */}
      <section className="border-y border-[rgba(13,13,13,0.07)] bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-10 gap-y-4 px-4 py-5">
          {STATS.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="flex items-center gap-2.5">
                <Icon size={16} className="text-[#D97757]" />
                <span className="text-[16px] font-semibold text-[#1A1A1A]">{s.value}</span>
                <span className="text-[15px] text-[rgba(13,13,13,0.50)]">{s.label}</span>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Popular models ────────────────────────────────────────────────────── */}
      {popular.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <div className="mb-8 flex items-end justify-between">
            <div>
              <h2 className="text-[22px] font-bold text-[#1A1A1A]">Популярные модели</h2>
              <p className="mt-1 text-[16px] text-[rgba(13,13,13,0.50)]">
                Самые востребованные нейросети
              </p>
            </div>
            <Link
              href="/models/"
              className="flex items-center gap-1 text-[15px] text-[#D97757] hover:text-[#C4623E] transition-colors"
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

      {/* ── Use cases ─────────────────────────────────────────────────────────── */}
      <section className="border-t border-[rgba(13,13,13,0.07)] bg-[rgba(13,13,13,0.015)]">
        <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6">
          <div className="mb-10 text-center">
            <h2 className="text-[26px] font-bold text-[#1A1A1A]">Для любой задачи</h2>
            <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.52)]">
              Выберите свою роль и посмотрите примеры
            </p>
          </div>
          <UseCaseTabs />
        </div>
      </section>

      {/* ── Comparison table ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <div className="mb-10 text-center">
          <h2 className="text-[26px] font-bold text-[#1A1A1A]">Честное сравнение</h2>
          <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.52)]">
            aineron.ru против главных альтернатив
          </p>
        </div>

        <div className="overflow-x-auto rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white">
          <table className="w-full min-w-[480px] text-[15px]">
            <thead>
              <tr className="border-b border-[rgba(13,13,13,0.08)]">
                <th className="px-5 py-3.5 text-left font-medium text-[rgba(13,13,13,0.50)]">
                  Возможность
                </th>
                <th className="px-4 py-3.5 text-center font-bold text-[#D97757]">aineron.ru</th>
                <th className="px-4 py-3.5 text-center font-medium text-[rgba(13,13,13,0.55)]">ChatGPT</th>
                <th className="px-4 py-3.5 text-center font-medium text-[rgba(13,13,13,0.55)]">RouterAI</th>
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((row, i) => (
                <tr
                  key={row.feature}
                  className={i % 2 === 0 ? "bg-[rgba(13,13,13,0.015)]" : ""}
                >
                  <td className="px-5 py-3 text-[#1A1A1A]">{row.feature}</td>
                  <td className="px-4 py-3 text-center"><Cell val={row.aineron} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={row.chatgpt} /></td>
                  <td className="px-4 py-3 text-center"><Cell val={row.router} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── Features grid ─────────────────────────────────────────────────────── */}
      <section className="border-t border-[rgba(13,13,13,0.07)] bg-[rgba(13,13,13,0.015)]">
        <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
          <h2 className="mb-10 text-center text-[24px] font-bold text-[#1A1A1A]">
            Почему aineron.ru
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      {/* ── Pricing preview ───────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <div className="overflow-hidden rounded-[20px] border border-[rgba(13,13,13,0.10)] bg-white">
          <div className="px-8 py-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[rgba(217,119,87,0.10)]">
              <Wallet size={22} className="text-[#D97757]" />
            </div>
            <h2 className="text-[24px] font-bold text-[#1A1A1A]">Простая оплата в рублях</h2>
            <p className="mt-2 text-[17px] text-[rgba(13,13,13,0.55)]">
              Пополняйте баланс и тратьте на любую модель. Средства не сгорают.
            </p>
          </div>
          <div className="grid grid-cols-1 divide-y border-t border-[rgba(13,13,13,0.08)] sm:grid-cols-3 sm:divide-x sm:divide-y-0" style={{ borderColor: "rgba(13,13,13,0.08)" }}>
            {PRICING.map((p) => (
              <div key={p.title} className="px-7 py-6 text-center">
                <p className="mb-1 text-[15px] font-medium text-[rgba(13,13,13,0.50)]">{p.title}</p>
                <p className="text-[28px] font-bold text-[#1A1A1A]">{p.price}</p>
                <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.45)]">{p.sub}</p>
              </div>
            ))}
          </div>
          <div className="border-t border-[rgba(13,13,13,0.08)] px-8 py-5 text-center">
            <Link
              href="/register/"
              className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-8 py-3 text-[16px] font-medium text-white hover:bg-[#C4623E] transition-colors"
            >
              Начать с 10 ₽ бесплатно
              <ArrowRight size={15} />
            </Link>
            <p className="mt-2 text-[14px] text-[rgba(13,13,13,0.38)]">
              Не нужна карта для старта
            </p>
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <h2 className="mb-8 text-center text-[24px] font-bold text-[#1A1A1A]">
          Частые вопросы
        </h2>
        <FaqAccordion />
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────────── */}
      <section className="border-t border-[rgba(13,13,13,0.07)] bg-[#1A1A1A]">
        <div className="mx-auto max-w-3xl px-4 py-20 text-center sm:px-6">
          <h2 className="mb-3 text-[28px] font-bold text-white">
            Начните прямо сейчас
          </h2>
          <p className="mb-8 text-[16px] text-[rgba(255,255,255,0.55)]">
            10 ₽ бесплатно. Без VPN, без зарубежных карт.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/register/"
              className="inline-flex items-center gap-2 rounded-[10px] bg-white px-7 py-3 text-[17px] font-medium text-[#1A1A1A] hover:bg-[rgba(255,255,255,0.90)] transition-colors"
            >
              Создать аккаунт
              <ArrowRight size={16} />
            </Link>
            <Link
              href="/models/"
              className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(255,255,255,0.45)] bg-[rgba(255,255,255,0.10)] px-7 py-3 text-[17px] font-medium text-white hover:bg-[rgba(255,255,255,0.18)] hover:border-[rgba(255,255,255,0.65)] transition-colors"
            >
              Смотреть модели
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}

// ── Cell helper for comparison table ──────────────────────────────────────────
function Cell({ val }: { val: boolean | string }) {
  if (val === true) return <Check size={16} className="mx-auto text-[#22a85a]" />;
  if (val === false) return <X size={15} className="mx-auto text-[rgba(13,13,13,0.25)]" />;
  return <span className="text-[rgba(13,13,13,0.55)]">{val}</span>;
}

// ── Network card ──────────────────────────────────────────────────────────────
function NetworkCard({ network }: { network: NetworkListItem }) {
  return (
    <Link
      href={`/models/${network.slug}/`}
      className="group flex flex-col gap-3 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 hover:border-[#D97757] hover:shadow-sm transition-all duration-150"
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
          <p className="text-[16px] font-semibold text-[#1A1A1A] group-hover:text-[#D97757] transition-colors">
            {network.name}
          </p>
          <p className="text-[14px] text-[rgba(13,13,13,0.5)]">{network.category.name}</p>
        </div>
      </div>
      {network.description && (
        <p className="line-clamp-2 text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {network.description}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-[14px] text-[rgba(13,13,13,0.45)]">
          {formatRub(network.cost_kopecks)} / сообщение
        </span>
        <ArrowRight
          size={14}
          className="text-[rgba(13,13,13,0.3)] group-hover:text-[#D97757] transition-colors"
        />
      </div>
    </Link>
  );
}

// ── Feature card ──────────────────────────────────────────────────────────────
function FeatureCard({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
        <Icon size={20} />
      </div>
      <p className="mb-1.5 text-[16px] font-semibold text-[#1A1A1A]">{title}</p>
      <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.58)]">{text}</p>
    </div>
  );
}

// ── Data ──────────────────────────────────────────────────────────────────────
const STATS = [
  { icon: Globe, value: "200+", label: "нейросетей" },
  { icon: Users, value: "10 000+", label: "пользователей" },
  { icon: MessageSquare, value: "1 млн+", label: "сообщений обработано" },
  { icon: Zap, value: "< 1 сек", label: "среднее время ответа" },
];

const FEATURES = [
  { icon: Globe, title: "Без VPN", text: "Российский сервис, оплата рублями. Доступно с любого устройства в РФ." },
  { icon: Zap, title: "Мгновенный старт", text: "Регистрация за 30 секунд, 10 ₽ на балансе сразу." },
  { icon: Code2, title: "OpenAI API", text: "Подключите к Cursor, VS Code, Continue и любому OpenAI-совместимому приложению." },
  { icon: ImageIcon, title: "Текст и медиа", text: "LLM, изображения и видео — один кошелёк, одна точка входа." },
];

const COMPARISON: {
  feature: string;
  aineron: boolean | string;
  chatgpt: boolean | string;
  router: boolean | string;
}[] = [
  { feature: "Без VPN (серверы в РФ)", aineron: true, chatgpt: false, router: false },
  { feature: "Оплата рублями", aineron: true, chatgpt: false, router: true },
  { feature: "200+ моделей", aineron: true, chatgpt: false, router: true },
  { feature: "Генерация изображений в UI", aineron: true, chatgpt: true, router: false },
  { feature: "Сравнение моделей side-by-side", aineron: true, chatgpt: false, router: false },
  { feature: "Промпт-библиотека", aineron: true, chatgpt: false, router: false },
  { feature: "OpenAI-совместимый API", aineron: true, chatgpt: true, router: true },
  { feature: "Команды и организации", aineron: true, chatgpt: true, router: true },
  { feature: "Загрузка файлов в чате", aineron: true, chatgpt: true, router: false },
  { feature: "Веб-поиск", aineron: true, chatgpt: true, router: false },
];

const PRICING = [
  { title: "10 ₽", price: "бесплатно", sub: "после регистрации" },
  { title: "Пополнение", price: "от 1 ₽", sub: "любая сумма, без минимума" },
  { title: "Подписки", price: "со скидкой", sub: "пакеты для активных пользователей" },
];
