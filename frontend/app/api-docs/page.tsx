import type { Metadata } from "next";
import Link from "next/link";
import { Code2, ExternalLink, Play } from "lucide-react";
import { CodeTabs, StandaloneCodeBlock } from "@/components/docs/CodeTabs";
import type { CodeTabItem } from "@/components/docs/CodeTabs";

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: "API для разработчиков",
  description:
    "OpenAI-совместимый API для доступа к GPT-4o, Claude, Gemini и генерации изображений без VPN. Документация, примеры кода и инструкции.",
};

// ── Code snippets ─────────────────────────────────────────────────────────────

const QUICKSTART: CodeTabItem[] = [
  {
    key: "curl",
    label: "curl",
    code: `curl https://aineron.ru/api/v1/chat/completions \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "Привет! Напиши Hello World на Python"}
    ]
  }'`,
  },
  {
    key: "python",
    label: "Python",
    code: [
      `from openai import OpenAI

client = OpenAI(
    base_url="https://aineron.ru/api/v1",
    api_key="ak_ВАШ_КЛЮЧ",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Привет! Напиши Hello World на Python"}
    ]
)

print(response.choices[0].message.content)`,
      `# Стриминг
for chunk in client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Расскажи анекдот"}],
    stream=True,
):
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)`,
    ],
  },
  {
    key: "nodejs",
    label: "Node.js",
    code: [
      `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://aineron.ru/api/v1",
  apiKey: "ak_ВАШ_КЛЮЧ",
});

const response = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [
    { role: "user", content: "Привет! Напиши Hello World на Python" }
  ],
});

console.log(response.choices[0].message.content);`,
      `// Стриминг
const stream = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "Расскажи анекдот" }],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}`,
    ],
  },
  {
    key: "php",
    label: "PHP",
    code: `<?php
$curl = curl_init();
curl_setopt_array($curl, [
    CURLOPT_URL => 'https://aineron.ru/api/v1/chat/completions',
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ak_ВАШ_КЛЮЧ',
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'model'    => 'gpt-4o',
        'messages' => [
            ['role' => 'user', 'content' => 'Привет! Напиши Hello World на Python']
        ],
    ]),
]);

$response = curl_exec($curl);
curl_close($curl);

$data = json_decode($response, true);
echo $data['choices'][0]['message']['content'];`,
  },
];

const ANTHROPIC: CodeTabItem[] = [
  {
    key: "python",
    label: "Python",
    code: `import anthropic

client = anthropic.Anthropic(
    base_url="https://aineron.ru/api/v1",
    api_key="ak_ВАШ_КЛЮЧ",
)

message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Объясни теорему Пифагора"}
    ]
)

print(message.content[0].text)`,
  },
  {
    key: "nodejs",
    label: "Node.js",
    code: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "https://aineron.ru/api/v1",
  apiKey: "ak_ВАШ_КЛЮЧ",
});

const message = await client.messages.create({
  model: "claude-3-5-sonnet-20241022",
  max_tokens: 1024,
  messages: [
    { role: "user", content: "Объясни теорему Пифагора" }
  ],
});

console.log(message.content[0].text);`,
  },
];

const IMAGES: CodeTabItem[] = [
  {
    key: "curl",
    label: "curl",
    code: `curl https://aineron.ru/api/v1/images/generations \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "flux-1-schnell",
    "prompt": "Горный пейзаж на закате, фотореализм, 8K",
    "n": 1,
    "size": "1024x1024"
  }'`,
  },
  {
    key: "python",
    label: "Python",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="https://aineron.ru/api/v1",
    api_key="ak_ВАШ_КЛЮЧ",
)

image = client.images.generate(
    model="flux-1-schnell",
    prompt="Горный пейзаж на закате, фотореализм, 8K",
    n=1,
    size="1024x1024",
)

print(image.data[0].url)`,
  },
];

const ERROR_BODY = `{
  "error": {
    "message": "Недостаточно средств. Нужно 3 ₽, у вас 1,50 ₽.",
    "type": "insufficient_quota",
    "code": "insufficient_quota"
  }
}`;

// ── Sub-components (server-renderable) ────────────────────────────────────────

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
      <p className="text-[13px] font-medium uppercase tracking-wider text-[rgba(13,13,13,0.35)]">
        {label}
      </p>
      <p className="mt-1 font-mono text-[16px] font-semibold text-[#1A1A1A]">{value}</p>
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
      className="rounded-[16px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-sm"
    >
      <h2 className="mb-4 text-[18px] font-semibold text-[#1A1A1A]">{title}</h2>
      {children}
    </section>
  );
}

function MethodBadge({ method }: { method: "GET" | "POST" | "DELETE" }) {
  const cls = {
    GET: "bg-[rgba(22,163,74,0.10)] text-[#16a34a]",
    POST: "bg-[rgba(217,119,87,0.10)] text-[#D97757]",
    DELETE: "bg-[rgba(220,38,38,0.10)] text-[#dc2626]",
  }[method];
  return (
    <span
      className={`inline-flex items-center rounded-[5px] px-2 py-0.5 font-mono text-[13px] font-semibold ${cls}`}
    >
      {method}
    </span>
  );
}

const ENDPOINTS: { method: "GET" | "POST" | "DELETE"; path: string; desc: string }[] = [
  { method: "POST", path: "/api/v1/chat/completions", desc: "Chat completions (OpenAI-совместимый, stream)" },
  { method: "POST", path: "/api/v1/messages", desc: "Messages API (Anthropic-совместимый)" },
  { method: "GET", path: "/api/v1/models", desc: "Список доступных моделей" },
  { method: "POST", path: "/api/v1/images/generations", desc: "Генерация изображений и видео" },
  { method: "GET", path: "/api/v1/keys/", desc: "Список API-ключей" },
  { method: "POST", path: "/api/v1/keys/", desc: "Создать API-ключ" },
  { method: "DELETE", path: "/api/v1/keys/{id}/", desc: "Удалить API-ключ" },
  { method: "GET", path: "/api/v1/schema/", desc: "OpenAPI схема (YAML/JSON)" },
  { method: "GET", path: "/api/v1/docs/", desc: "Swagger UI" },
];

const ERRORS: { code: number; type: string; desc: string }[] = [
  { code: 401, type: "authentication_error", desc: "Неверный или отсутствующий API-ключ" },
  { code: 402, type: "insufficient_quota", desc: "Недостаточно средств на балансе" },
  { code: 403, type: "permission_error", desc: "Нет доступа к ресурсу" },
  { code: 429, type: "rate_limit_exceeded", desc: "Превышен лимит запросов (120/мин)" },
  { code: 400, type: "invalid_request_error", desc: "Неверные параметры запроса" },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ApiDocsPage() {
  return (
    <div className="min-h-screen bg-[#FAF9F7] px-4 py-12">
      <div className="mx-auto max-w-4xl space-y-6">
        {/* Breadcrumb */}
        <nav className="flex items-center gap-2">
          <Code2 size={15} className="text-[rgba(13,13,13,0.35)]" />
          <Link
            href="/"
            className="text-[15px] text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A] transition-colors"
          >
            Главная
          </Link>
          <span className="text-[15px] text-[rgba(13,13,13,0.25)]">/</span>
          <span className="text-[15px] text-[rgba(13,13,13,0.65)]">API для разработчиков</span>
        </nav>

        {/* Hero */}
        <div>
          <h1 className="text-[30px] font-bold leading-tight text-[#1A1A1A]">
            API для разработчиков
          </h1>
          <p className="mt-2 max-w-2xl text-[17px] text-[rgba(13,13,13,0.55)]">
            OpenAI-совместимый API для доступа к GPT-4o, Claude, Gemini, Mistral и генерации
            изображений — без VPN, без санкций, из России. Работает с openai SDK простой сменой{" "}
            <code className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 font-mono text-[15px]">
              base_url
            </code>
            .
          </p>
        </div>

        {/* Info cards */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <InfoCard label="Base URL" value="aineron.ru/api/v1" />
          <InfoCard label="Аутентификация" value="Bearer ak_..." />
          <InfoCard label="Формат ошибок" value="OpenAI-совместимый" />
          <InfoCard label="Биллинг" value="Рубли / 1 000 токенов" />
        </div>

        {/* Quick start */}
        <Section title="Быстрый старт">
          <ol className="mb-5 space-y-3 text-[16px]">
            {[
              <>
                <strong className="text-[#1A1A1A]">Создайте API-ключ</strong> в личном кабинете
                — раздел{" "}
                <Link href="/account/keys/" className="text-[#D97757] hover:underline">
                  API-ключи
                </Link>
                . Ключ показывается один раз, сохраните его сразу.
              </>,
              <>
                <strong className="text-[#1A1A1A]">Укажите наш base_url</strong> вместо{" "}
                <code className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 font-mono text-[14px]">
                  api.openai.com
                </code>{" "}
                в вашем SDK или HTTP-клиенте.
              </>,
              <>
                <strong className="text-[#1A1A1A]">Пополните баланс</strong> и начните
                запросы — списание по токенам автоматически.
              </>,
            ].map((step, i) => (
              <li key={i} className="flex gap-3 text-[rgba(13,13,13,0.75)]">
                <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-[#1A1A1A] text-[13px] font-bold text-white">
                  {i + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
          <CodeTabs tabs={QUICKSTART} />
        </Section>

        {/* Anthropic SDK */}
        <Section title="Anthropic SDK (Claude-модели)">
          <p className="mb-4 text-[16px] text-[rgba(13,13,13,0.65)]">
            Если вы используете официальный Anthropic SDK, достаточно указать наш{" "}
            <code className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 font-mono text-[14px]">
              base_url
            </code>{" "}
            — API полностью совместим с{" "}
            <code className="rounded-[4px] bg-[rgba(13,13,13,0.07)] px-1.5 py-0.5 font-mono text-[14px]">
              POST /api/v1/messages
            </code>
            .
          </p>
          <CodeTabs tabs={ANTHROPIC} />
        </Section>

        {/* Images */}
        <Section title="Генерация изображений и видео">
          <p className="mb-4 text-[16px] text-[rgba(13,13,13,0.65)]">
            Доступ к Flux, SDXL, Wan, Kling и другим медиа-моделям через стандартный OpenAI Images
            API.
          </p>
          <CodeTabs tabs={IMAGES} />
        </Section>

        {/* Endpoints */}
        <Section title="Список эндпоинтов">
          <div className="overflow-x-auto">
            <table className="w-full text-[15px]">
              <thead>
                <tr className="border-b border-[rgba(13,13,13,0.08)]">
                  <th className="pb-2.5 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Метод
                  </th>
                  <th className="pb-2.5 pl-4 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Путь
                  </th>
                  <th className="pb-2.5 pl-4 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Описание
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(13,13,13,0.06)]">
                {ENDPOINTS.map((e, i) => (
                  <tr key={i}>
                    <td className="py-2.5">
                      <MethodBadge method={e.method} />
                    </td>
                    <td className="py-2.5 pl-4 font-mono text-[14px] text-[rgba(13,13,13,0.70)]">
                      {e.path}
                    </td>
                    <td className="py-2.5 pl-4 text-[rgba(13,13,13,0.65)]">{e.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* Error codes */}
        <Section title="Коды ошибок">
          <p className="mb-4 text-[16px] text-[rgba(13,13,13,0.65)]">
            Все ошибки возвращаются в OpenAI-совместимом формате:
          </p>
          <div className="mb-5">
            <StandaloneCodeBlock code={ERROR_BODY} />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[15px]">
              <thead>
                <tr className="border-b border-[rgba(13,13,13,0.08)]">
                  <th className="pb-2.5 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    HTTP
                  </th>
                  <th className="pb-2.5 pl-4 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    type
                  </th>
                  <th className="pb-2.5 pl-4 text-left font-medium text-[rgba(13,13,13,0.40)]">
                    Причина
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[rgba(13,13,13,0.06)]">
                {ERRORS.map((e) => (
                  <tr key={e.code}>
                    <td className="py-2.5 font-semibold text-[#1A1A1A]">{e.code}</td>
                    <td className="py-2.5 pl-4 font-mono text-[14px] text-[rgba(13,13,13,0.70)]">
                      {e.type}
                    </td>
                    <td className="py-2.5 pl-4 text-[rgba(13,13,13,0.65)]">{e.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        {/* Action links */}
        <div className="flex flex-wrap gap-3 pb-4">
          <Link
            href="/api-docs/playground/"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-5 py-2.5 text-[16px] font-medium text-white hover:bg-[#C4623E] transition-colors"
          >
            <Play size={14} />
            Playground
          </Link>
          <a
            href="/api/v1/docs/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-[10px] bg-[#1A1A1A] px-5 py-2.5 text-[16px] font-medium text-white hover:bg-[#1a1a1a] transition-colors"
          >
            Swagger UI
            <ExternalLink size={14} />
          </a>
          <a
            href="/static/docs/postman_collection.json"
            download="aineron_api.postman_collection.json"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[16px] font-medium text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Postman-коллекция
          </a>
          <Link
            href="/ide/"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[16px] font-medium text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Интеграция с IDE
          </Link>
          <Link
            href="/account/keys/"
            className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[16px] font-medium text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
          >
            Создать API-ключ
          </Link>
        </div>
      </div>
    </div>
  );
}
