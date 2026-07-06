import type { Metadata } from "next";
import Link from "next/link";
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

export const metadata: Metadata = {
  title: "Sandboxes — песочницы для кода AI-агентов | aineron.ru",
  description:
    "API изолированных microVM для безопасного выполнения кода: агенты, EdTech, запуск сниппетов. Старт за секунды, оплата в рублях от 0,5 ₽/мин. Российская альтернатива E2B.",
  keywords:
    "песочница для кода api, sandbox api, выполнение кода api, e2b аналог россия, code interpreter api, песочница ai агент",
  alternates: { canonical: "https://aineron.ru/sandbox/" },
};

const CODE_EXAMPLE = `# pip install aineron
from aineron import Sandbox

with Sandbox(template="python") as sbx:
    result = sbx.exec(code="print(2 + 2)")
    print(result.stdout)   # 4`;

const FEATURES = [
  {
    icon: ShieldCheck,
    title: "Изоляция уровня VM",
    text: "Каждая песочница — отдельная Firecracker microVM с собственным ядром. Код агента не доберётся ни до ваших данных, ни до соседей.",
  },
  {
    icon: Zap,
    title: "Старт за секунды",
    text: "Тёплый пул виртуальных машин: p95 старта меньше 5 секунд. Состояние сохраняется между запусками кода в одной сессии.",
  },
  {
    icon: Terminal,
    title: "Файлы, exec, логи",
    text: "Полный набор: запись и чтение файлов, выполнение команд и кода (Python, Node, bash), фоновые процессы, стриминг логов.",
  },
  {
    icon: Globe,
    title: "Публичный URL",
    text: "Запустите веб-сервер внутри песочницы — получите HTTPS-адрес, который открывается из браузера. Демо и превью без деплоя.",
  },
  {
    icon: Wallet,
    title: "Рубли и оферта РФ",
    text: "Оплата с российской карты, документы для бухгалтерии, поддержка на русском. Никаких зарубежных подписок и санкционных рисков.",
  },
  {
    icon: BookOpen,
    title: "Один ключ на всё",
    text: "Тот же API-ключ работает с чатами (GPT-5, Claude), генерацией изображений и песочницами. Агент целиком на одной платформе.",
  },
];

const FAQ = [
  {
    q: "Чем это отличается от запуска кода в Docker у себя?",
    a: "Docker-контейнеры делят ядро с хостом — побег из контейнера через уязвимость ядра реален. Наши песочницы — полноценные microVM с отдельным ядром, как у AWS Lambda. Плюс вам не нужно держать и защищать собственные серверы.",
  },
  {
    q: "Сколько это стоит?",
    a: "0,50 ₽/мин за small (1 vCPU / 1 GiB) и 1 ₽/мин за standard (2 vCPU / 2 GiB). Округление до минуты вверх. При создании резервируется стоимость TTL, при остановке неиспользованные минуты возвращаются. Ошибка запуска — полный возврат.",
  },
  {
    q: "Для чего это используют?",
    a: "AI-агенты, которые пишут и выполняют код (code interpreter); проверка решений студентов в EdTech; безопасный запуск пользовательских скриптов в SaaS; быстрые демо веб-приложений с публичным URL.",
  },
  {
    q: "Есть ли SDK?",
    a: "Да, Python SDK: pip install aineron. Для остальных языков — обычный REST API с Bearer-авторизацией, примеры на curl в документации.",
  },
  {
    q: "Какие ограничения?",
    a: "До 3 одновременных песочниц и 240 минут в день на аккаунт, TTL до 60 минут, вывод команды до 256 KB. Сетевой доступ изнутри — по allowlist (pypi, npm и т.д.); нужен свой домен — напишите в поддержку.",
  },
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

export default function SandboxLandingPage() {
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
              Первый sandbox-API в России
            </p>
            <h1 className="text-[36px] font-bold leading-tight sm:text-[44px]">
              Песочницы для кода ваших AI-агентов
            </h1>
            <p className="mt-5 text-[18px] leading-relaxed text-[rgba(13,13,13,0.6)]">
              Изолированные microVM по одному API-вызову: агент пишет код —
              песочница безопасно выполняет. Старт за секунды, оплата в рублях,
              без VPN и зарубежных карт.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/account/keys/"
                className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-6 py-3 text-[16px] font-medium text-white transition-colors hover:bg-[#C4623E]"
              >
                Получить API-ключ
                <ArrowRight size={18} />
              </Link>
              <Link
                href="/api-docs/"
                className="inline-flex items-center rounded-[10px] border border-[rgba(13,13,13,0.15)] px-6 py-3 text-[16px] font-medium text-[#1A1A1A] transition-colors hover:bg-[rgba(13,13,13,0.04)]"
              >
                Документация
              </Link>
            </div>
            <p className="mt-4 text-[14px] text-[rgba(13,13,13,0.45)]">
              Новым пользователям — стартовый баланс: хватит на первые тесты без карты
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
            Всё, что нужно для исполнения недоверенного кода
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
            Прозрачные цены, поминутно
          </h2>
          <div className="overflow-x-auto rounded-[12px] border border-[rgba(13,13,13,0.10)]">
            <table className="w-full text-left text-[15px]">
              <thead>
                <tr className="border-b border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] text-[rgba(13,13,13,0.55)]">
                  <th className="px-5 py-3 font-medium">Размер</th>
                  <th className="px-5 py-3 font-medium">Ресурсы</th>
                  <th className="px-5 py-3 font-medium">Цена</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-[rgba(13,13,13,0.08)]">
                  <td className="px-5 py-4 font-semibold">small</td>
                  <td className="px-5 py-4 text-[rgba(13,13,13,0.65)]">1 vCPU / 1 GiB RAM</td>
                  <td className="px-5 py-4 font-semibold">0,50 ₽/мин</td>
                </tr>
                <tr>
                  <td className="px-5 py-4 font-semibold">standard</td>
                  <td className="px-5 py-4 text-[rgba(13,13,13,0.65)]">2 vCPU / 2 GiB RAM</td>
                  <td className="px-5 py-4 font-semibold">1 ₽/мин</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-center text-[14px] text-[rgba(13,13,13,0.45)]">
            Неиспользованные минуты возвращаются при остановке. Ошибка запуска — полный возврат.
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-[rgba(13,13,13,0.08)] bg-[rgba(13,13,13,0.02)] py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <h2 className="mb-10 text-center text-[28px] font-bold">Вопросы и ответы</h2>
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
              Начать за 5 минут
              <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
