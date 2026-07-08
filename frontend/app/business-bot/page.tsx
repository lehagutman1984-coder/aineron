import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Bot,
  MessageSquare,
  ShieldCheck,
  Clock,
  CheckSquare,
  Zap,
  ArrowRight,
} from "lucide-react";
import { CURRENCY } from "@/lib/money";
import { SITE_URL, siteHost } from "@/lib/site";

export const metadata: Metadata = {
  title: `AI-секретарь для Telegram Business — ${siteHost()}`,
  description:
    "Бот aineron отвечает вашим клиентам в Telegram от вашего имени: черновики с подтверждением, автопилот для типовых вопросов, утренняя сводка. 990 ₽/мес, до 300 авто-ответов.",
  keywords:
    "AI секретарь telegram, telegram business бот, автоответчик telegram, нейросеть для бизнеса",
  alternates: { canonical: `${SITE_URL}/business-bot/` },
};

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Черновики с подтверждением",
    text: "Каждое сообщение клиента приходит вам с готовым ответом AI. Одна кнопка — и ответ отправлен от вашего имени. Ничего не уходит без одобрения.",
  },
  {
    icon: Zap,
    title: "Автопилот для типовых вопросов",
    text: "Часы работы, цены, услуги — AI отвечает мгновенно и уведомляет вас. Нестандартные вопросы всегда эскалируются вам.",
  },
  {
    icon: Bot,
    title: "Отвечает как вы",
    text: "AI использует вашу базу знаний (Persistent Memory): факты о бизнесе, прайс, стиль общения. Настраиваемый тон ответов.",
  },
  {
    icon: Clock,
    title: "Утренняя сводка",
    text: "«За ночь 7 сообщений: 3 отвечено автоматически, 2 ждут решения» — каждый день в 9:00.",
  },
  {
    icon: CheckSquare,
    title: "Чек-листы договорённостей",
    text: "AI превращает договорённости из диалога в чек-лист прямо в чате с клиентом.",
  },
  {
    icon: ShieldCheck,
    title: "Приватность",
    text: "Переписка клиентов не хранится: только очередь черновиков с автоудалением через 7 дней.",
  },
];

const STEPS = [
  "Зарегистрируйтесь на aineron.ru и привяжите Telegram в кабинете",
  "Оформите тариф «Бизнес» — 990 ₽/мес",
  "В Telegram: Настройки → Telegram Business → Чат-боты → @aineron_bot",
  "Готово: клиентам отвечает AI, вы контролируете каждый ответ",
];

export default function BusinessBotPage() {
  if (CURRENCY === "credits") {
    notFound();
  }
  return (
    <main className="min-h-screen bg-white text-[#1A1A1A]">
      {/* Hero */}
      <section className="mx-auto max-w-5xl px-4 pb-16 pt-20 text-center sm:px-6">
        <p className="mb-4 text-[14px] font-semibold uppercase tracking-wide text-[#D97757]">
          Первый AI-секретарь для Telegram Business в России
        </p>
        <h1 className="mx-auto max-w-3xl text-[36px] font-bold leading-tight sm:text-[48px]">
          Ваши клиенты получают ответ за минуту. Даже когда вы спите.
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-[18px] leading-relaxed text-[rgba(13,13,13,0.6)]">
          Подключите бота aineron к своему Telegram Business — AI подготовит
          ответы клиентам по вашей базе знаний и отправит их от вашего имени
          после подтверждения.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <a
            href="https://t.me/aineron_bot?start=business"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-6 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            Подключить секретаря
            <ArrowRight size={18} />
          </a>
          <Link
            href="/account/billing/"
            className="inline-flex items-center rounded-[10px] border border-[rgba(13,13,13,0.15)] px-6 py-3 text-[16px] font-medium text-[#1A1A1A] transition-colors hover:bg-[rgba(13,13,13,0.04)]"
          >
            Тариф «Бизнес» — 990 ₽/мес
          </Link>
        </div>
        <p className="mt-4 text-[14px] text-[rgba(13,13,13,0.45)]">
          До 300 авто-ответов в месяц включено, далее 1 ₽ за ответ
        </p>
      </section>

      {/* Features */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] py-16">
        <div className="mx-auto max-w-5xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">
            Как работает AI-секретарь
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

      {/* Steps */}
      <section className="py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">
            Запуск за 5 минут
          </h2>
          <ol className="flex flex-col gap-4">
            {STEPS.map((step, i) => (
              <li
                key={i}
                className="flex items-start gap-4 rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#D97757] text-[15px] font-semibold text-white">
                  {i + 1}
                </span>
                <p className="pt-1 text-[16px] text-[rgba(13,13,13,0.75)]">{step}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Economics */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] py-16">
        <div className="mx-auto max-w-3xl px-4 text-center sm:px-6">
          <h2 className="text-[28px] font-bold">Для кого</h2>
          <p className="mx-auto mt-4 max-w-2xl text-[17px] leading-relaxed text-[rgba(13,13,13,0.6)]">
            Самозанятые, интернет-магазины, эксперты, агентства — все, кто
            тонет в личке. Средний бизнес отвечает клиенту за 2–4 часа;
            AI-секретарь — за минуту. Каждый пропущенный вопрос — потерянный
            клиент.
          </p>
          <a
            href="https://t.me/aineron_bot?start=business"
            className="mt-8 inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-6 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            Попробовать
            <ArrowRight size={18} />
          </a>
        </div>
      </section>
    </main>
  );
}
