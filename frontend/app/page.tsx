import Link from "next/link";
import { ArrowRight, Zap, Globe, Code2, ImageIcon } from "lucide-react";
import { serverListNetworks } from "@/lib/api/server";
import type { NetworkListItem } from "@/lib/api/types";

export const revalidate = 3600;

async function getPopularNetworks(): Promise<NetworkListItem[]> {
  const networks = await serverListNetworks({ is_popular: true });
  return networks ?? [];
}

export default async function HomePage() {
  const popular = await getPopularNetworks();

  return (
    <>
      {/* Hero */}
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-24 text-center sm:px-6">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[rgba(10,124,255,0.25)] bg-[rgba(10,124,255,0.06)] px-3 py-1 text-[13px] text-[#0a7cff]">
          <Zap size={13} />
          Без VPN, без регистрации на зарубежных сервисах
        </div>
        <h1 className="mb-5 text-[40px] font-bold leading-tight tracking-tight text-[#0d0d0d] sm:text-[52px]">
          Нейросети для{" "}
          <span
            style={{
              background: "linear-gradient(135deg, #0a7cff, #1dd6c1)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            всех задач
          </span>
        </h1>
        <p className="mx-auto mb-8 max-w-2xl text-[17px] leading-relaxed text-[rgba(13,13,13,0.6)]">
          GPT-4o, Claude, Gemini, Midjourney и десятки других моделей — в одном
          интерфейсе. Оплата звёздами, без подписок на зарубежные сервисы.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/register/"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#0a7cff] px-6 py-3 text-[15px] font-medium text-white hover:bg-[#0066cc] transition-colors"
          >
            Начать бесплатно
            <ArrowRight size={16} />
          </Link>
          <Link
            href="/models/"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-6 py-3 text-[15px] font-medium text-[#0d0d0d] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Смотреть каталог
          </Link>
        </div>
      </section>

      {/* Featured models */}
      {popular.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
          <div className="mb-8 flex items-end justify-between">
            <div>
              <h2 className="text-[22px] font-semibold text-[#0d0d0d]">Популярные модели</h2>
              <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.55)]">Самые часто используемые нейросети</p>
            </div>
            <Link
              href="/models/"
              className="flex items-center gap-1 text-[13px] text-[#0a7cff] hover:text-[#0066cc] transition-colors"
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

      {/* Features */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)]">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
          <h2 className="mb-12 text-center text-[22px] font-semibold text-[#0d0d0d]">
            Почему aineron.ru
          </h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} {...f} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-3xl px-4 py-24 text-center sm:px-6">
        <h2 className="mb-4 text-[28px] font-bold text-[#0d0d0d]">
          Начните прямо сейчас
        </h2>
        <p className="mb-8 text-[16px] text-[rgba(13,13,13,0.6)]">
          10 звёзд бесплатно после регистрации. Без VPN, без зарубежных карт.
        </p>
        <Link
          href="/register/"
          className="inline-flex items-center gap-2 rounded-[10px] bg-[#0a7cff] px-8 py-3.5 text-[15px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          Создать аккаунт
          <ArrowRight size={16} />
        </Link>
      </section>
    </>
  );
}

function NetworkCard({ network }: { network: NetworkListItem }) {
  return (
    <Link
      href={`/models/${network.slug}/`}
      className="group flex flex-col gap-3 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5 hover:border-[#0a7cff] hover:shadow-sm transition-all duration-150"
    >
      <div className="flex items-center gap-3">
        {network.avatar ? (
          <img
            src={network.avatar}
            alt={network.name}
            width={36}
            height={36}
            className="rounded-[8px] object-cover"
          />
        ) : (
          <div className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
            {network.handle_photo || network.handle_video ? (
              <ImageIcon size={18} />
            ) : (
              <Code2 size={18} />
            )}
          </div>
        )}
        <div>
          <p className="text-[14px] font-semibold text-[#0d0d0d] group-hover:text-[#0a7cff] transition-colors">
            {network.name}
          </p>
          <p className="text-[12px] text-[rgba(13,13,13,0.5)]">
            {network.category.name}
          </p>
        </div>
      </div>
      {network.description && (
        <p className="line-clamp-2 text-[13px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          {network.description}
        </p>
      )}
      <div className="mt-auto flex items-center justify-between pt-1">
        <span className="text-[12px] text-[rgba(13,13,13,0.45)]">
          {network.cost_per_message} зв. / сообщение
        </span>
        <ArrowRight size={14} className="text-[rgba(13,13,13,0.3)] group-hover:text-[#0a7cff] transition-colors" />
      </div>
    </Link>
  );
}

function FeatureCard({
  icon: Icon,
  title,
  text,
}: {
  icon: React.ElementType;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-[10px] bg-[rgba(10,124,255,0.10)] text-[#0a7cff]">
        <Icon size={20} />
      </div>
      <p className="mb-1.5 text-[14px] font-semibold text-[#0d0d0d]">{title}</p>
      <p className="text-[13px] leading-relaxed text-[rgba(13,13,13,0.58)]">{text}</p>
    </div>
  );
}

const FEATURES = [
  {
    icon: Globe,
    title: "Без VPN",
    text: "Российский сервис, оплата рублями. Доступно с любого устройства.",
  },
  {
    icon: Zap,
    title: "Мгновенный старт",
    text: "Регистрация за 30 секунд, 10 бесплатных звёзд для начала.",
  },
  {
    icon: Code2,
    title: "OpenAI-совместимый API",
    text: "Подключите к Cursor, VS Code, Continue и другим IDE за 2 минуты.",
  },
  {
    icon: ImageIcon,
    title: "Текст и изображения",
    text: "GPT-4o, Claude, Gemini и генерация изображений в одном кошельке.",
  },
];
