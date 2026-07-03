/* eslint-disable react/jsx-key -- ячейки таблиц/данные рендерятся внутри keyed .map() в DocKit */
import type { Metadata } from "next";
import Link from "next/link";
import { Play, ExternalLink, Download } from "lucide-react";
import { DocLayout, type DocGroup } from "@/components/docs/DocLayout";
import {
  DocSection, Lead, P, H3, IC, Kbd, A, UL, LI, Steps, Step, Callout,
  FeatureGrid, FeatureCard, DataTable, InfoCard, Method, Path,
} from "@/components/docs/DocKit";
import { CodeTabs, StandaloneCodeBlock } from "@/components/docs/CodeTabs";
import type { CodeTabItem } from "@/components/docs/CodeTabs";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "API и интеграции для разработчиков",
  description:
    "OpenAI- и Anthropic-совместимый API: GPT-5, Claude, Gemini, генерация изображений и видео, embeddings, аудио, batch. Интеграция с Cursor, Cline, Continue. Без VPN, из России.",
};

// ── Snippets ──────────────────────────────────────────────────────────────────

const QUICKSTART: CodeTabItem[] = [
  {
    key: "curl", label: "curl",
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
    key: "python", label: "Python",
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
      `# Стриминг ответа по мере генерации
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
    key: "nodejs", label: "Node.js",
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
    key: "php", label: "PHP",
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
            ['role' => 'user', 'content' => 'Привет!']
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
    key: "python", label: "Python",
    code: `import anthropic

client = anthropic.Anthropic(
    base_url="https://aineron.ru/api/v1",
    api_key="ak_ВАШ_КЛЮЧ",
)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "Объясни теорему Пифагора"}
    ]
)

print(message.content[0].text)`,
  },
  {
    key: "nodejs", label: "Node.js",
    code: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "https://aineron.ru/api/v1",
  apiKey: "ak_ВАШ_КЛЮЧ",
});

const message = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 1024,
  messages: [{ role: "user", content: "Объясни теорему Пифагора" }],
});

console.log(message.content[0].text);`,
  },
];

const IMAGES: CodeTabItem[] = [
  {
    key: "curl", label: "curl",
    code: `curl https://aineron.ru/api/v1/images/generations \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "flux-2-pro",
    "prompt": "Горный пейзаж на закате, фотореализм, 8K",
    "n": 1,
    "size": "1024x1024"
  }'`,
  },
  {
    key: "python", label: "Python",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="https://aineron.ru/api/v1",
    api_key="ak_ВАШ_КЛЮЧ",
)

image = client.images.generate(
    model="flux-2-pro",
    prompt="Горный пейзаж на закате, фотореализм, 8K",
    n=1,
    size="1024x1024",
)

print(image.data[0].url)`,
  },
];

const EMBEDDINGS = `curl https://aineron.ru/api/v1/embeddings \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "text-embedding-3-small",
    "input": "Текст для векторизации"
  }'`;

const AUDIO_TTS = `curl https://aineron.ru/api/v1/audio/speech \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "tts-1", "voice": "alloy", "input": "Привет, это синтез речи"}' \\
  --output speech.mp3`;

const AUDIO_ASR = `curl https://aineron.ru/api/v1/audio/transcriptions \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ" \\
  -F model="whisper-1" \\
  -F file="@audio.mp3"`;

const ERROR_BODY = `{
  "error": {
    "message": "Недостаточно средств. Нужно 3 ₽, у вас 1,50 ₽.",
    "type": "insufficient_quota",
    "code": "insufficient_quota"
  }
}`;

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
      "title": "Claude Sonnet (aineron.ru)",
      "provider": "openai",
      "model": "claude-sonnet-4-6",
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

const CHECK_MODELS = `curl https://aineron.ru/api/v1/models \\
  -H "Authorization: Bearer ak_ВАШ_КЛЮЧ"`;

// ── Groups ────────────────────────────────────────────────────────────────────

const GROUPS: DocGroup[] = [
  {
    title: "Введение",
    items: [
      {
        id: "overview",
        label: "Обзор API",
        content: (
          <>
            <DocSection title="OpenAI-совместимый API">
              <Lead>
                aineron предоставляет доступ к GPT-5, Claude, Gemini, Grok, DeepSeek,
                генерации изображений и видео через <b>стандартный OpenAI-совместимый API</b> —
                без VPN и зарубежных карт, напрямую из России. Если ваш код уже работает
                с OpenAI SDK, достаточно сменить <IC>base_url</IC> и ключ.
              </Lead>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <InfoCard label="Base URL" value="aineron.ru/api/v1" />
                <InfoCard label="Аутентификация" value="Bearer ak_..." />
                <InfoCard label="Формат" value="OpenAI + Anthropic" />
                <InfoCard label="Биллинг" value="Рубли / токены" />
              </div>
              <P>
                Поддерживаются два формата: <b>OpenAI</b> (<IC>/chat/completions</IC>,{" "}
                <IC>/images/generations</IC>, <IC>/embeddings</IC>, <IC>/audio/*</IC>) и{" "}
                <b>Anthropic</b> (<IC>/messages</IC>). Стриминг, батч-обработка, вебхуки —
                на месте.
              </P>
            </DocSection>
            <DocSection title="С чего начать">
              <UL>
                <LI><A href="#quickstart">Быстрый старт</A> — создать ключ и сделать первый запрос.</LI>
                <LI><A href="#auth">Аутентификация</A> — как передавать ключ.</LI>
                <LI><A href="#billing">Биллинг и лимиты</A> — сколько стоит и какие ограничения.</LI>
                <LI><A href="#ide-cursor">Интеграция с IDE</A> — Cursor, Cline, Continue.</LI>
              </UL>
              <div className="flex flex-wrap gap-3 pt-1">
                <Link href="/api-docs/playground/" className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-5 py-2.5 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]">
                  <Play size={14} /> Playground
                </Link>
                <a href="/api/v1/docs/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-[10px] bg-[#1A1A1A] px-5 py-2.5 text-[15px] font-medium text-white dark:bg-[#EDE8E3] dark:text-[#1A1A1A]">
                  Swagger UI <ExternalLink size={14} />
                </a>
                <Link href="/account/keys/" className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[15px] font-medium text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.14)] dark:bg-[#211E1B] dark:text-[rgba(236,236,236,0.7)]">
                  Создать API-ключ
                </Link>
              </div>
            </DocSection>
          </>
        ),
      },
      {
        id: "quickstart",
        label: "Быстрый старт",
        content: (
          <DocSection title="Быстрый старт" intro="Три шага до первого ответа от нейросети.">
            <Steps>
              <Step n={1}>
                <b>Создайте API-ключ</b> в кабинете — раздел{" "}
                <A href="/account/keys/">API-ключи</A>. Ключ вида <IC>ak_...</IC>{" "}
                показывается один раз, сохраните сразу.
              </Step>
              <Step n={2}>
                <b>Укажите наш base_url</b> <IC>https://aineron.ru/api/v1</IC> вместо{" "}
                <IC>api.openai.com</IC> в вашем SDK или HTTP-клиенте.
              </Step>
              <Step n={3}>
                <b>Пополните баланс</b> и делайте запросы — списание по токенам автоматически.
              </Step>
            </Steps>
            <div className="pt-2">
              <CodeTabs tabs={QUICKSTART} />
            </div>
          </DocSection>
        ),
      },
      {
        id: "auth",
        label: "Аутентификация",
        content: (
          <DocSection title="Аутентификация" intro="Все запросы к API требуют ключ в заголовке Authorization.">
            <StandaloneCodeBlock code={`Authorization: Bearer ak_ВАШ_КЛЮЧ`} />
            <UL>
              <LI>Ключи создаются и удаляются в <A href="/account/keys/">кабинете</A>; можно завести несколько (например, отдельный для каждого инструмента).</LI>
              <LI>Ключ привязан к вашему аккаунту и общему балансу.</LI>
              <LI>Для Mini App и внутренних интеграций поддерживаются JWT-токены (выдаются при авторизации через Telegram).</LI>
            </UL>
            <Callout type="warn" title="Не публикуйте ключ">
              Не храните <IC>ak_...</IC> в публичных репозиториях и клиентском коде браузера.
              Если ключ скомпрометирован — удалите его в кабинете и создайте новый.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "billing",
        label: "Биллинг и лимиты",
        content: (
          <DocSection title="Биллинг и лимиты" intro="Оплата в рублях, списание по токенам. Прозрачно и предсказуемо.">
            <UL>
              <LI>Стоимость зависит от модели и объёма (входные + выходные токены).</LI>
              <LI>Баланс и траты видны в <A href="/account/analytics/">аналитике кабинета</A>.</LI>
              <LI>Rate limit: до <b>120 запросов в минуту</b> на ключ (ошибка <IC>429</IC> при превышении — сделайте паузу/повтор).</LI>
              <LI>При нехватке средств API вернёт <IC>402 insufficient_quota</IC>.</LI>
            </UL>
            <Callout type="tip">
              Для автодополнения в IDE используйте быструю дешёвую модель (<IC>gpt-4o-mini</IC>),
              а для сложных задач — мощную. Так вы экономите и снижаете задержку.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "errors",
        label: "Коды ошибок",
        content: (
          <DocSection title="Коды ошибок" intro="Ошибки возвращаются в OpenAI-совместимом формате.">
            <StandaloneCodeBlock code={ERROR_BODY} />
            <div className="pt-2">
              <DataTable
                head={["HTTP", "type", "Причина"]}
                rows={[
                  ["401", <IC>authentication_error</IC>, "Неверный или отсутствующий ключ"],
                  ["402", <IC>insufficient_quota</IC>, "Недостаточно средств на балансе"],
                  ["403", <IC>permission_error</IC>, "Нет доступа к ресурсу"],
                  ["429", <IC>rate_limit_exceeded</IC>, "Превышен лимит (120/мин)"],
                  ["400", <IC>invalid_request_error</IC>, "Неверные параметры запроса"],
                ]}
              />
            </div>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: "Эндпоинты",
    items: [
      {
        id: "chat",
        label: "Chat Completions",
        content: (
          <DocSection title="Chat Completions" intro="Основной эндпоинт для текстовых моделей. Полностью совместим с OpenAI, включая стриминг.">
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/chat/completions</Path>
            </p>
            <CodeTabs tabs={QUICKSTART} />
            <H3>Популярные модели</H3>
            <DataTable
              head={["model", "Назначение"]}
              rows={[
                [<IC>gpt-4o</IC>, "Универсальная, хорошо следует инструкциям"],
                [<IC>gpt-5</IC>, "Максимум качества и рассуждений"],
                [<IC>gpt-4o-mini</IC>, "Быстрая и дешёвая, для автодополнения"],
                [<IC>claude-sonnet-4-6</IC>, "Лучшая для кода и длинных файлов"],
                [<IC>claude-opus-4-8</IC>, "Топ для сложных задач"],
                [<IC>gemini-2.5-pro</IC>, "Большой контекст, мультимодальность"],
                [<IC>deepseek-v3</IC>, "Очень дёшево, хорошее качество"],
              ]}
            />
            <Callout type="info">
              Полный актуальный список — запросом <IC>GET /api/v1/models</IC> или в{" "}
              <A href="/models/">каталоге</A>.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "messages",
        label: "Messages (Anthropic)",
        content: (
          <DocSection title="Messages API (Anthropic-совместимый)" intro="Если вы используете официальный Anthropic SDK — просто укажите наш base_url.">
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/messages</Path>
            </p>
            <CodeTabs tabs={ANTHROPIC} />
          </DocSection>
        ),
      },
      {
        id: "models",
        label: "Модели и каталог",
        content: (
          <DocSection title="Список моделей" intro="Получить актуальный список доступных моделей.">
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>GET</Method> <Path>/api/v1/models</Path>
            </p>
            <StandaloneCodeBlock code={CHECK_MODELS} />
            <P>Также доступен публичный каталог с категориями и ценами:</P>
            <UL>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/categories/</Path> — категории</LI>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/networks/</Path> — модели с ценами</LI>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/networks/{"{slug}"}/</Path> — детали модели</LI>
            </UL>
          </DocSection>
        ),
      },
      {
        id: "images",
        label: "Изображения и видео",
        content: (
          <DocSection title="Генерация изображений и видео" intro="Через стандартный OpenAI Images API. Видео генерируется асинхронно.">
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/images/generations</Path>
            </p>
            <CodeTabs tabs={IMAGES} />
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/images/enhance-prompt/</Path> — усилить промпт</LI>
              <LI><Method>GET</Method> <Path>/api/v1/generations/{"{id}"}/progress/</Path> — прогресс генерации (SSE)</LI>
              <LI><Method>POST</Method> <Path>/api/v1/generations/{"{id}"}/upscale/</Path> — апскейл; <IC>/variations/</IC>, <IC>/remove-background/</IC></LI>
            </UL>
            <Callout type="info">
              Видео-модели (Sora 2, Veo 3.1, Kling) работают через тот же интерфейс, но результат
              готовится 5–15 минут — опрашивайте статус генерации.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "embeddings",
        label: "Embeddings",
        content: (
          <DocSection title="Embeddings" intro="Векторные представления текста для поиска и RAG.">
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/embeddings</Path>
            </p>
            <StandaloneCodeBlock code={EMBEDDINGS} />
          </DocSection>
        ),
      },
      {
        id: "audio",
        label: "Аудио (TTS / ASR)",
        content: (
          <DocSection title="Аудио: синтез и распознавание речи">
            <H3>Синтез речи (TTS)</H3>
            <p className="mb-2 flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/audio/speech</Path>
            </p>
            <StandaloneCodeBlock code={AUDIO_TTS} />
            <H3>Распознавание речи (ASR / Whisper)</H3>
            <p className="mb-2 flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/audio/transcriptions</Path>
            </p>
            <StandaloneCodeBlock code={AUDIO_ASR} />
          </DocSection>
        ),
      },
      {
        id: "batch",
        label: "Batch API",
        content: (
          <DocSection title="Batch API" intro="Пакетная асинхронная обработка большого числа запросов.">
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/batches/</Path> — создать пакет</LI>
              <LI><Method>GET</Method> <Path>/api/v1/batches/{"{id}"}/</Path> — статус</LI>
              <LI><Method>GET</Method> <Path>/api/v1/batches/{"{id}"}/results/</Path> — результаты</LI>
              <LI><Method>POST</Method> <Path>/api/v1/batches/{"{id}"}/cancel/</Path> — отменить</LI>
            </UL>
            <P>Подходит для массовой классификации, разметки, генерации — без ручного контроля rate limit.</P>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: "Ресурсы платформы",
    items: [
      {
        id: "res-chats",
        label: "Чаты и проекты",
        content: (
          <DocSection title="Чаты, проекты, файлы (API)" intro="Веб-функции доступны и программно — можно строить свои интерфейсы поверх платформы.">
            <DataTable
              head={["Метод", "Путь", "Назначение"]}
              rows={[
                [<Method>GET</Method>, <Path>/api/v1/chats/</Path>, "Список чатов"],
                [<Method>POST</Method>, <Path>/api/v1/chats/</Path>, "Создать чат + сообщение"],
                [<Method>POST</Method>, <Path>/api/v1/chats/{"{id}"}/messages/stream/</Path>, "Стриминг ответа (SSE)"],
                [<Method>GET</Method>, <Path>/api/v1/chats/search/</Path>, "Поиск по истории (слова + смысл)"],
                [<Method>GET</Method>, <Path>/api/v1/projects/</Path>, "Проекты и база знаний"],
                [<Method>POST</Method>, <Path>/api/v1/projects/{"{id}"}/files/</Path>, "Загрузить файл в базу знаний"],
                [<Method>GET</Method>, <Path>/api/v1/projects/{"{id}"}/kb/stats/</Path>, "Статус индексации базы знаний"],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-agent",
        label: "Память, задачи, агент",
        content: (
          <DocSection title="Память, AI-задачи и Agent Mode (API)">
            <DataTable
              head={["Метод", "Путь", "Назначение"]}
              rows={[
                [<Method>GET</Method>, <Path>/api/v1/memory/</Path>, "Факты памяти (фильтр по скоупу)"],
                [<Method>POST</Method>, <Path>/api/v1/memory/quick-save/</Path>, "Сохранить факт"],
                [<Method>GET</Method>, <Path>/api/v1/orgs/{"{id}"}/memory/</Path>, "Общая память организации"],
                [<Method>GET</Method>, <Path>/api/v1/tasks/</Path>, "AI-задачи по расписанию"],
                [<Method>POST</Method>, <Path>/api/v1/tasks/{"{id}"}/run/</Path>, "Запустить задачу сейчас"],
                [<Method>POST</Method>, <Path>/api/v1/agent/</Path>, "Запустить Agent Mode"],
                [<Method>GET</Method>, <Path>/api/v1/agent/{"{id}"}/</Path>, "Статус и результат агента"],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-research",
        label: "Deep Research API",
        content: (
          <DocSection title="Deep Research (API)" intro="Запуск исследования и опрос статуса из вашего кода.">
            <DataTable
              head={["Метод", "Путь", "Назначение"]}
              rows={[
                [<Method>POST</Method>, <Path>/api/v1/chats/{"{id}"}/research/</Path>, "Запустить исследование"],
                [<Method>GET</Method>, <Path>/api/v1/research/{"{id}"}/</Path>, "Статус, шаги, отчёт"],
                [<Method>POST</Method>, <Path>/api/v1/research/{"{id}"}/save/</Path>, "Сохранить отчёт в базу знаний"],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-webhooks",
        label: "Webhooks, usage, audit",
        content: (
          <DocSection title="Вебхуки и наблюдаемость">
            <H3>Исходящие вебхуки</H3>
            <P>Получайте события платформы на свой URL (с HMAC-подписью).</P>
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/webhooks/</Path> — создать вебхук</LI>
              <LI><Method>POST</Method> <Path>/api/v1/webhooks/{"{id}"}/test/</Path> — тестовое событие</LI>
            </UL>
            <H3>Использование и аудит</H3>
            <UL>
              <LI><Method>GET</Method> <Path>/api/v1/usage/</Path> — статистика трат</LI>
              <LI><Method>GET</Method> <Path>/api/v1/audit/</Path> — журнал действий</LI>
              <LI><Method>GET</Method> <Path>/api/v1/status/</Path> — статус сервиса</LI>
            </UL>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: "Интеграция с IDE",
    items: [
      {
        id: "ide-cursor",
        label: "Cursor",
        content: (
          <DocSection title="Cursor" intro="AI-редактор на базе VS Code. Поддерживает кастомные OpenAI-провайдеры с версии 0.40.">
            <Steps>
              <Step n={1}>
                <Kbd>Ctrl+Shift+J</Kbd> (или <Kbd>Cmd+Shift+J</Kbd>) → вкладка <b>Models</b> → <b>Add Model</b>.
              </Step>
              <Step n={2}>
                В разделе <b>OpenAI API Key</b> включите <b>Override OpenAI Base URL</b> и введите{" "}
                <IC>https://aineron.ru/api/v1</IC>. В поле <b>API Key</b> — ваш <IC>ak_...</IC>.
              </Step>
              <Step n={3}>
                В <b>Model Name</b> укажите модель, например <IC>gpt-4o</IC> или{" "}
                <IC>claude-sonnet-4-6</IC>. Список — запросом:
                <div className="mt-3"><StandaloneCodeBlock code={CHECK_MODELS} /></div>
              </Step>
              <Step n={4}>
                <b>Save</b> → выберите модель в правом нижнем углу → чат <Kbd>Ctrl+L</Kbd>. Готово.
              </Step>
            </Steps>
            <Callout type="info">
              При нехватке средств автодополнение временно отключится — пополните баланс в кабинете.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "ide-cline",
        label: "Cline",
        content: (
          <DocSection title="Cline" intro="Агент-расширение VS Code: сам создаёт и редактирует файлы, выполняет команды.">
            <Steps>
              <Step n={1}>Установите <b>Cline</b> из маркетплейса VS Code.</Step>
              <Step n={2}>
                Настройки Cline → <b>API Provider</b> → <b>OpenAI Compatible</b>. Заполните:
                <div className="mt-3"><StandaloneCodeBlock code={CLINE_SETTINGS} /></div>
              </Step>
              <Step n={3}>
                Рекомендованные модели для агентских задач: <IC>claude-sonnet-4-6</IC> (лучшая для кода),{" "}
                <IC>gpt-4o</IC>, <IC>claude-opus-4-8</IC>.
              </Step>
              <Step n={4}>Опишите задачу на русском или английском. Cline спросит разрешение перед каждым изменением файла.</Step>
            </Steps>
            <Callout type="warn">
              Агентские сессии читают контекст файлов и расходуют больше токенов, чем обычный чат.
              Следите за балансом.
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "ide-continue",
        label: "Continue",
        content: (
          <DocSection title="Continue" intro="Открытый AI-ассистент для VS Code и JetBrains. Конфигурируется JSON-файлом.">
            <Steps>
              <Step n={1}>
                Установите <b>Continue</b>, откройте <IC>~/.continue/config.json</IC> (команда{" "}
                <b>Continue: Open Config</b>).
              </Step>
              <Step n={2}>
                Добавьте блок <IC>models</IC>:
                <div className="mt-3"><StandaloneCodeBlock code={CONTINUE_CONFIG} /></div>
              </Step>
              <Step n={3}>Сохраните — Continue применит конфигурацию. Выберите модель в выпадающем меню чата.</Step>
            </Steps>
            <H3>Горячие клавиши</H3>
            <DataTable
              head={["Сочетание", "Действие"]}
              rows={[
                [<Kbd>Ctrl+L</Kbd>, "Открыть чат / добавить выделение в контекст"],
                [<Kbd>Ctrl+I</Kbd>, "Редактировать выделенный код"],
                [<Kbd>Tab</Kbd>, "Принять автодополнение"],
                [<Kbd>Ctrl+Shift+R</Kbd>, "Выбрать другую модель"],
              ]}
            />
          </DocSection>
        ),
      },
    ],
  },
  {
    title: "Ещё",
    items: [
      {
        id: "telegram",
        label: "Telegram-интеграция",
        content: (
          <DocSection title="Telegram (для интеграций)" intro="Эндпоинты для привязки аккаунта и авторизации Mini App.">
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/telegram/link-token/</Path> — одноразовый токен привязки аккаунта</LI>
              <LI><Method>POST</Method> <Path>/api/v1/telegram/webapp-auth/</Path> — обмен initData на JWT (для Mini App)</LI>
            </UL>
            <P>Как пользователю подключить бота — см. <A href="/docs/#tg-start">руководство пользователя</A>.</P>
          </DocSection>
        ),
      },
      {
        id: "tools",
        label: "Инструменты",
        content: (
          <DocSection title="Инструменты разработчика">
            <FeatureGrid>
              <FeatureCard icon={<Play size={16} />} title="Playground">
                Интерактивная песочница — пробуйте запросы в браузере. <A href="/api-docs/playground/">Открыть →</A>
              </FeatureCard>
              <FeatureCard icon={<ExternalLink size={16} />} title="Swagger UI">
                Полная интерактивная схема всех эндпоинтов. <A href="/api/v1/docs/">Открыть →</A>
              </FeatureCard>
              <FeatureCard icon={<Download size={16} />} title="Postman-коллекция">
                Готовые запросы для Postman. <A href="/static/docs/postman_collection.json">Скачать →</A>
              </FeatureCard>
              <FeatureCard icon={<ExternalLink size={16} />} title="OpenAPI-схема">
                Машиночитаемая спецификация. <A href="/api/v1/schema/">/api/v1/schema/</A>
              </FeatureCard>
            </FeatureGrid>
          </DocSection>
        ),
      },
      {
        id: "dev-faq",
        label: "FAQ разработчика",
        content: (
          <DocSection title="Частые вопросы разработчиков">
            <H3>Какую модель выбрать для кода?</H3>
            <P><IC>claude-sonnet-4-6</IC> или <IC>gpt-4o</IC>. Для быстрого автодополнения — <IC>gpt-4o-mini</IC>.</P>
            <H3>Что делать при ошибке 429?</H3>
            <P>Лимит 120 запросов/мин на ключ. IDE обычно повторяют запрос сами. Если упираетесь
              постоянно — заведите несколько ключей под разные инструменты.</P>
            <H3>Работает ли стриминг?</H3>
            <P>Да, передайте <IC>stream: true</IC> — как в OpenAI SDK. Поддерживается везде,
              где есть <IC>/chat/completions</IC>.</P>
            <H3>Как проверить баланс из кода?</H3>
            <P>Запрос <Method>GET</Method> <Path>/api/v1/usage/</Path> или смотрите в{" "}
              <A href="/account/analytics/">аналитике</A>.</P>
            <H3>Совместимо ли с LangChain / LlamaIndex?</H3>
            <P>Да — это OpenAI-совместимый провайдер. Укажите <IC>base_url</IC> и ключ в настройках
              OpenAI-клиента внутри фреймворка.</P>
            <Callout type="info" title="Нужна помощь?">
              Контакты поддержки — в подвале сайта. Для пользовательских функций смотрите{" "}
              <A href="/docs/">руководство пользователя</A>.
            </Callout>
          </DocSection>
        ),
      },
    ],
  },
];

export default function ApiDocsPage() {
  return (
    <DocLayout
      eyebrow="Для разработчиков"
      title="API и интеграции"
      subtitle="OpenAI- и Anthropic-совместимый API к GPT-5, Claude, Gemini и генерации медиа — без VPN. Плюс интеграции с Cursor, Cline, Continue. Выбирайте раздел слева."
      breadcrumb={[{ label: "Главная", href: "/" }, { label: "API для разработчиков" }]}
      groups={GROUPS}
    />
  );
}
