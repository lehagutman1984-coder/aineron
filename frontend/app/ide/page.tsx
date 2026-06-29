import type { Metadata } from "next";
import Link from "next/link";
import { Terminal, ExternalLink, Info, AlertTriangle } from "lucide-react";
import { StandaloneCodeBlock } from "@/components/docs/CodeTabs";

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: "Интеграция с IDE — Cursor, Cline, Continue",
  description:
    "Подключите нейросети GPT-4o, Claude и Gemini к Cursor, Cline и Continue через API aineron.ru. Пошаговые инструкции без VPN.",
};

// ── Code snippets ─────────────────────────────────────────────────────────────

const CURSOR_CHECK_MODELS = `curl https://aineron.ru/api/v1/models \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ"`;

const CLINE_SETTINGS = `API Base URL:  https://aineron.ru/api/v1
API Key:       ak_ВАШ_КЛЮЧ
Model ID:      gpt-4o`;

const CONTINUE_CONFIG = `{
  "models": [
    {
      "title": "GPT-4o (aineron.ru)",
      "provider": "openai",
      "model": "gpt-4o",
      "apiBase": "https://aineron.ru/api/v1",
      "apiKey": "ak_ВАШ_КЛЮЧ"
    },
    {
      "title": "Claude 3.5 Sonnet (aineron.ru)",
      "provider": "openai",
      "model": "claude-3-5-sonnet-20241022",
      "apiBase": "https://aineron.ru/api/v1",
      "apiKey": "ak_ВАШ_КЛЮЧ"
    }
  ],
  "tabAutocompleteModel": {
    "title": "GPT-4o Mini (aineron.ru)",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "apiBase": "https://aineron.ru/api/v1",
    "apiKey": "ak_ВАШ_КЛЮЧ"
  }
}`;

// ── Sub-components ─────────────────────────────────────────────────────────────

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
      <p className="text-[11px] font-medium uppercase tracking-wider text-[rgba(13,13,13,0.35)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-[14px] font-semibold text-[#0d0d0d]">{value}</p>
    </div>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id?: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-sm scroll-mt-8"
    >
      <h2 className="mb-4 text-[20px] font-semibold text-[#0d0d0d]">{title}</h2>
      {children}
    </section>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[#0d0d0d] text-[11px] font-bold text-white">
        {n}
      </span>
      <div className="text-[14px] text-[rgba(13,13,13,0.75)]">{children}</div>
    </div>
  );
}

function H3({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="mb-2 mt-5 text-[15px] font-semibold text-[#0d0d0d] first:mt-0">{children}</h3>
  );
}

function AlertInfo({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 flex gap-3 rounded-[10px] border border-[rgba(37,99,235,0.15)] bg-[rgba(37,99,235,0.05)] p-4 text-[13px] text-[rgba(13,13,13,0.70)]">
      <Info size={16} className="mt-0.5 flex-shrink-0 text-[#2563eb]" />
      <span>{children}</span>
    </div>
  );
}

function AlertWarning({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 flex gap-3 rounded-[10px] border border-[rgba(202,138,4,0.20)] bg-[rgba(202,138,4,0.06)] p-4 text-[13px] text-[rgba(13,13,13,0.70)]">
      <AlertTriangle size={16} className="mt-0.5 flex-shrink-0 text-[#ca8a04]" />
      <span>{children}</span>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded-[5px] border border-[rgba(13,13,13,0.15)] bg-[rgba(13,13,13,0.05)] px-1.5 py-0.5 font-mono text-[12px] text-[#0d0d0d]">
      {children}
    </kbd>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return (
    <code className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 font-mono text-[12px] text-[#0d0d0d]">
      {children}
    </code>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function IdePage() {
  return (
    <div className="min-h-screen bg-[#f5f5f7] px-4 py-12">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2">
          <Terminal size={15} className="text-[rgba(13,13,13,0.35)]" />
          <Link
            href="/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
          >
            Главная
          </Link>
          <span className="text-[13px] text-[rgba(13,13,13,0.25)]">/</span>
          <Link
            href="/api-docs/"
            className="text-[13px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
          >
            API
          </Link>
          <span className="text-[13px] text-[rgba(13,13,13,0.25)]">/</span>
          <span className="text-[13px] text-[rgba(13,13,13,0.65)]">Интеграция с IDE</span>
        </nav>

        {/* Hero */}
        <div>
          <h1 className="text-[30px] font-bold leading-tight text-[#0d0d0d]">
            Интеграция с IDE
          </h1>
          <p className="mt-2 max-w-2xl text-[15px] text-[rgba(13,13,13,0.55)]">
            Подключите GPT-4o, Claude, Gemini и другие модели прямо в ваш редактор через
            OpenAI-совместимый API aineron.ru — без VPN, без зарубежных карт.
          </p>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-2 gap-3">
          <InfoCard label="Base URL" value="aineron.ru/api/v1" />
          <InfoCard label="API Key" value="ak_... (из кабинета)" />
        </div>

        {/* IDE cards */}
        <section className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-[18px] font-semibold text-[#0d0d0d]">
            Поддерживаемые инструменты
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              {
                name: "Cursor",
                desc: "AI-редактор на базе VS Code со встроенными чатом и автодополнением.",
                href: "#cursor",
              },
              {
                name: "Cline",
                desc: "Агент-расширение для VS Code — автономно редактирует файлы и выполняет команды.",
                href: "#cline",
              },
              {
                name: "Continue",
                desc: "Open-source AI-ассистент для VS Code и JetBrains с поддержкой любых OpenAI-совместимых провайдеров.",
                href: "#continue",
              },
            ].map((ide) => (
              <a
                key={ide.name}
                href={ide.href}
                className="group rounded-[12px] border border-[rgba(13,13,13,0.10)] p-4 hover:border-[rgba(13,13,13,0.20)] hover:bg-[rgba(13,13,13,0.02)] transition-all"
              >
                <p className="mb-1.5 font-semibold text-[#0d0d0d] group-hover:text-[#f0a38a] transition-colors">
                  {ide.name}
                </p>
                <p className="text-[13px] text-[rgba(13,13,13,0.55)]">{ide.desc}</p>
              </a>
            ))}
          </div>
        </section>

        {/* Cursor */}
        <Section id="cursor" title="Cursor">
          <p className="mb-5 text-[14px] text-[rgba(13,13,13,0.65)]">
            Cursor поддерживает кастомные OpenAI-провайдеры начиная с версии 0.40. Настройка
            занимает меньше минуты.
          </p>
          <div className="space-y-4">
            <Step n={1}>
              Нажмите <Kbd>Ctrl+Shift+J</Kbd> (или <Kbd>Cmd+Shift+J</Kbd> на Mac) → вкладка{" "}
              <strong className="text-[#0d0d0d]">Models</strong> → кнопка{" "}
              <strong className="text-[#0d0d0d]">Add Model</strong>.
            </Step>
            <Step n={2}>
              Прокрутите до раздела <strong className="text-[#0d0d0d]">OpenAI API Key</strong>,
              нажмите <strong className="text-[#0d0d0d]">Override OpenAI Base URL</strong> и
              введите <Code>https://aineron.ru/api/v1</Code>. В поле{" "}
              <strong className="text-[#0d0d0d]">API Key</strong> введите ваш ключ{" "}
              <Code>ak_...</Code>.
            </Step>
            <Step n={3}>
              <div>
                В поле <strong className="text-[#0d0d0d]">Model Name</strong> введите
                идентификатор нужной модели, например <Code>gpt-4o</Code> или{" "}
                <Code>claude-3-5-sonnet-20241022</Code>. Посмотреть все доступные модели:
              </div>
              <div className="mt-3">
                <StandaloneCodeBlock code={CURSOR_CHECK_MODELS} />
              </div>
            </Step>
            <Step n={4}>
              Нажмите <strong className="text-[#0d0d0d]">Save</strong>. В правом нижнем углу
              редактора выберите добавленную модель и откройте чат (<Kbd>Ctrl+L</Kbd>). Отправьте
              тестовое сообщение — готово.
            </Step>
          </div>
          <AlertInfo>
            Cursor кэширует ответы для автодополнения. При нехватке звёзд автодополнение временно
            отключится — пополните баланс в личном кабинете.
          </AlertInfo>
        </Section>

        {/* Cline */}
        <Section id="cline" title="Cline">
          <p className="mb-5 text-[14px] text-[rgba(13,13,13,0.65)]">
            Cline — расширение VS Code, которое может самостоятельно создавать и редактировать
            файлы, запускать команды и серфить веб. Поддерживает любой OpenAI-совместимый
            провайдер.
          </p>
          <div className="space-y-4">
            <Step n={1}>
              Найдите <strong className="text-[#0d0d0d]">Cline</strong> в маркетплейсе VS Code и
              установите. После этого появится иконка в левой панели.
            </Step>
            <Step n={2}>
              <div>
                Откройте настройки Cline → раздел{" "}
                <strong className="text-[#0d0d0d]">API Provider</strong> → выберите{" "}
                <strong className="text-[#0d0d0d]">OpenAI Compatible</strong>. Заполните поля:
              </div>
              <div className="mt-3">
                <StandaloneCodeBlock code={CLINE_SETTINGS} />
              </div>
            </Step>
            <Step n={3}>
              <div>
                В поле <strong className="text-[#0d0d0d]">Model ID</strong> введите любой
                идентификатор из нашего каталога. Рекомендованные для агентских задач:
              </div>
              <ul className="mt-2 space-y-1.5 text-[rgba(13,13,13,0.65)]">
                <li>
                  <Code>gpt-4o</Code> — универсальный выбор, хорошо следует инструкциям
                </li>
                <li>
                  <Code>claude-3-5-sonnet-20241022</Code> — лучший для работы с кодом и длинными
                  файлами
                </li>
                <li>
                  <Code>claude-opus-4-5</Code> — максимальные возможности для сложных задач
                </li>
              </ul>
            </Step>
            <Step n={4}>
              Откройте любой проект, нажмите на иконку Cline в боковой панели и опишите задачу на
              русском или английском. Cline попросит разрешение перед каждым изменением файла.
            </Step>
          </div>
          <AlertWarning>
            Агентские сессии Cline могут расходовать больше токенов, чем обычный чат, так как
            модель читает контекст файлов. Следите за балансом через личный кабинет.
          </AlertWarning>
        </Section>

        {/* Continue */}
        <Section id="continue" title="Continue">
          <p className="mb-5 text-[14px] text-[rgba(13,13,13,0.65)]">
            Continue — открытый AI-ассистент для VS Code и JetBrains с гибкой конфигурацией
            провайдеров через JSON-файл.
          </p>
          <div className="space-y-4">
            <Step n={1}>
              Установите <strong className="text-[#0d0d0d]">Continue</strong> из маркетплейса VS
              Code или JetBrains. После установки откройте файл конфигурации:{" "}
              <Code>~/.continue/config.json</Code> (или через команду{" "}
              <strong className="text-[#0d0d0d]">Continue: Open Config</strong>).
            </Step>
            <Step n={2}>
              <div>
                Отредактируйте <Code>config.json</Code>, добавив блок <Code>models</Code>:
              </div>
              <div className="mt-3">
                <StandaloneCodeBlock code={CONTINUE_CONFIG} />
              </div>
            </Step>
            <Step n={3}>
              Сохраните файл — Continue автоматически применит новую конфигурацию. В выпадающем
              меню в правом нижнем углу чата выберите нужную модель.
            </Step>
          </div>

          <H3>Горячие клавиши Continue</H3>
          <div className="overflow-x-auto">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[rgba(13,13,13,0.08)]">
                  <th className="pb-2.5 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Сочетание
                  </th>
                  <th className="pb-2.5 pl-4 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Действие
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(13,13,13,0.06)]">
                {[
                  ["Ctrl+L", "Открыть чат / добавить выделение в контекст"],
                  ["Ctrl+I", "Редактировать выделенный код"],
                  ["Tab", "Принять автодополнение"],
                  ["Ctrl+Shift+R", "Выбрать другую модель"],
                ].map(([key, action]) => (
                  <tr key={key}>
                    <td className="py-2.5">
                      <Kbd>{key}</Kbd>
                    </td>
                    <td className="py-2.5 pl-4 text-[rgba(13,13,13,0.65)]">{action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <AlertInfo>
            Continue поддерживает несколько моделей одновременно — вы можете переключаться между
            GPT-4o и Claude, не меняя конфигурацию.
          </AlertInfo>
        </Section>

        {/* FAQ */}
        <section className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-sm">
          <h2 className="mb-5 text-[18px] font-semibold text-[#0d0d0d]">
            Советы и типичные вопросы
          </h2>
          <div className="space-y-5">
            {[
              {
                q: "Какую модель выбрать для кода?",
                a: (
                  <>
                    Для большинства задач: <Code>claude-3-5-sonnet-20241022</Code> или{" "}
                    <Code>gpt-4o</Code>. Для быстрого автодополнения подойдёт{" "}
                    <Code>gpt-4o-mini</Code> — он дешевле и значительно быстрее.
                  </>
                ),
              },
              {
                q: "Как проверить остаток звёзд?",
                a: "Баланс отображается в заголовке личного кабинета на сайте.",
              },
              {
                q: "Что делать при ошибке 429?",
                a: "Превышен лимит 120 запросов в минуту на ключ. IDE обычно автоматически повторяет запрос через несколько секунд. Если проблема постоянная — создайте несколько ключей для разных инструментов.",
              },
              {
                q: "Работает ли автодополнение?",
                a: (
                  <>
                    Да, Cursor и Continue используют эндпоинт <Code>/chat/completions</Code> для
                    автодополнения. Рекомендуем назначить для него быструю модель (
                    <Code>gpt-4o-mini</Code>), чтобы снизить задержку и расход звёзд.
                  </>
                ),
              },
            ].map((item, i) => (
              <div key={i}>
                <p className="mb-1.5 font-semibold text-[15px] text-[#0d0d0d]">{item.q}</p>
                <p className="text-[14px] text-[rgba(13,13,13,0.65)]">{item.a}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Action links */}
        <div className="flex flex-wrap gap-3 pb-4">
          <Link
            href="/api-docs/"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#0d0d0d] px-5 py-2.5 text-[14px] font-medium text-white hover:bg-[#1a1a1a] transition-colors"
          >
            Документация API
          </Link>
          <a
            href="/api/v1/docs/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[14px] font-medium text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Swagger UI
            <ExternalLink size={14} />
          </a>
          <Link
            href="/account/keys/"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[14px] font-medium text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Создать API-ключ
          </Link>
        </div>
      </div>
    </div>
  );
}
