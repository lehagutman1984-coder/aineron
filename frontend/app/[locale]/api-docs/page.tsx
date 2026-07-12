/* eslint-disable react/jsx-key -- ячейки таблиц/данные рендерятся внутри keyed .map() в DocKit */
import type { Metadata } from "next";
import { Link } from "@/i18n/navigation";

import { Play, ExternalLink, Download } from "lucide-react";
import { DocLayout, type DocGroup } from "@/components/docs/DocLayout";
import {
  DocSection, Lead, P, H3, IC, Kbd, A, UL, LI, Steps, Step, Callout,
  FeatureGrid, FeatureCard, DataTable, InfoCard, Method, Path,
} from "@/components/docs/DocKit";
import { CodeTabs, StandaloneCodeBlock } from "@/components/docs/CodeTabs";
import type { CodeTabItem } from "@/components/docs/CodeTabs";
import { formatMoney } from "@/lib/money";
import { IS_RU } from "@/lib/site";
import { getTranslations } from "next-intl/server";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("apiDocs");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
  };
}

// Код-сэмплы ниже используют реальный base_url текущего инстанса (aineron.ru / aineron.net),
// а не хардкод — иначе intl-пользователь скопировал бы неверный URL для своего API-ключа.
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://aineron.ru/api/v1";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru";
const BRAND = new URL(SITE_URL).host;

// Пользовательские строки внутри код-сэмплов (промты, комментарии, плейсхолдер
// ключа) — по локали инстанса: en-сборка не должна показывать русские примеры.
const S = IS_RU
  ? {
      key: "ak_ВАШ_КЛЮЧ",
      hello: "Привет! Напиши Hello World на Python",
      hi: "Привет!",
      streamComment: "Стриминг ответа по мере генерации",
      streamShort: "Стриминг",
      joke: "Расскажи анекдот",
      pythagoras: "Объясни теорему Пифагора",
      imgPrompt: "Горный пейзаж на закате, фотореализм, 8K",
      embedInput: "Текст для векторизации",
      ttsInput: "Привет, это синтез речи",
      sbxAutoStopped: "Песочница остановлена автоматически — биллинг завершён",
      sbxStep1: "1. Создать песочницу (TTL 5 минут)",
      sbxStep2: "2. Выполнить код",
      sbxStep3: "3. Остановить (иначе умрёт сама по TTL)",
      sbxWrite: "Записать файлы",
      sbxRead: "Прочитать файл",
      sbxList: "Листинг директории",
      agentDoc: "LLM пишет код → песочница выполняет → результат возвращается.",
      agentTask: "Реши задачу кодом на Python. Верни ТОЛЬКО код:",
      agentErr: "Ошибка выполнения:",
      agentFib: "Найди 100-е число Фибоначчи",
    }
  : {
      key: "ak_YOUR_KEY",
      hello: "Hi! Write Hello World in Python",
      hi: "Hello!",
      streamComment: "Stream the response as it is generated",
      streamShort: "Streaming",
      joke: "Tell me a joke",
      pythagoras: "Explain the Pythagorean theorem",
      imgPrompt: "Mountain landscape at sunset, photorealistic, 8K",
      embedInput: "Text to embed",
      ttsInput: "Hello, this is speech synthesis",
      sbxAutoStopped: "Sandbox stopped automatically — billing finished",
      sbxStep1: "1. Create a sandbox (TTL 5 minutes)",
      sbxStep2: "2. Execute code",
      sbxStep3: "3. Stop it (otherwise it dies by TTL)",
      sbxWrite: "Write files",
      sbxRead: "Read a file",
      sbxList: "List a directory",
      agentDoc: "LLM writes code → sandbox executes it → result comes back.",
      agentTask: "Solve the task with Python code. Return ONLY the code:",
      agentErr: "Execution error:",
      agentFib: "Find the 100th Fibonacci number",
    };

// ── Snippets ──────────────────────────────────────────────────────────────────

const QUICKSTART: CodeTabItem[] = [
  {
    key: "curl", label: "curl",
    code: `curl ${API_BASE}/chat/completions \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "user", "content": "${S.hello}"}
    ]
  }'`,
  },
  {
    key: "python", label: "Python",
    code: [
      `from openai import OpenAI

client = OpenAI(
    base_url="${API_BASE}",
    api_key="${S.key}",
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "${S.hello}"}
    ]
)

print(response.choices[0].message.content)`,
      `# ${S.streamComment}
for chunk in client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "${S.joke}"}],
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
  baseURL: "${API_BASE}",
  apiKey: "${S.key}",
});

const response = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [
    { role: "user", content: "${S.hello}" }
  ],
});

console.log(response.choices[0].message.content);`,
      `// ${S.streamShort}
const stream = await client.chat.completions.create({
  model: "gpt-4o",
  messages: [{ role: "user", content: "${S.joke}" }],
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
    CURLOPT_URL => '${API_BASE}/chat/completions',
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => [
        'Authorization: Bearer ${S.key}',
        'Content-Type: application/json',
    ],
    CURLOPT_POSTFIELDS => json_encode([
        'model'    => 'gpt-4o',
        'messages' => [
            ['role' => 'user', 'content' => '${S.hi}']
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
    base_url="${API_BASE}",
    api_key="${S.key}",
)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "${S.pythagoras}"}
    ]
)

print(message.content[0].text)`,
  },
  {
    key: "nodejs", label: "Node.js",
    code: `import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic({
  baseURL: "${API_BASE}",
  apiKey: "${S.key}",
});

const message = await client.messages.create({
  model: "claude-sonnet-4-6",
  max_tokens: 1024,
  messages: [{ role: "user", content: "${S.pythagoras}" }],
});

console.log(message.content[0].text);`,
  },
];

const IMAGES: CodeTabItem[] = [
  {
    key: "curl", label: "curl",
    code: `curl ${API_BASE}/images/generations \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "flux-2-pro",
    "prompt": "${S.imgPrompt}",
    "n": 1,
    "size": "1024x1024"
  }'`,
  },
  {
    key: "python", label: "Python",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="${API_BASE}",
    api_key="${S.key}",
)

image = client.images.generate(
    model="flux-2-pro",
    prompt="${S.imgPrompt}",
    n=1,
    size="1024x1024",
)

print(image.data[0].url)`,
  },
];

const EMBEDDINGS = `curl ${API_BASE}/embeddings \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "text-embedding-3-small",
    "input": "${S.embedInput}"
  }'`;

const AUDIO_TTS = `curl ${API_BASE}/audio/speech \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "tts-1", "voice": "alloy", "input": "${S.ttsInput}"}' \\
  --output speech.mp3`;

const AUDIO_ASR = `curl ${API_BASE}/audio/transcriptions \\
  -H "Authorization: Bearer ${S.key}" \\
  -F model="whisper-1" \\
  -F file="@audio.mp3"`;

function errorBody(t: Awaited<ReturnType<typeof getTranslations>>) {
  return `{
  "error": {
    "message": "${t("errorBodyMessage", { need: formatMoney(300), have: formatMoney(150) })}",
    "type": "insufficient_quota",
    "code": "insufficient_quota"
  }
}`;
}

const CLINE_SETTINGS = `API Base URL:  ${API_BASE}
API Key:       ${S.key}
Model ID:      gpt-4o`;

const CONTINUE_CONFIG = `{
  "models": [
    {
      "title": "GPT-4o (${BRAND})",
      "provider": "openai",
      "model": "gpt-4o",
      "apiBase": "${API_BASE}",
      "apiKey": "${S.key}"
    },
    {
      "title": "Claude Sonnet (${BRAND})",
      "provider": "openai",
      "model": "claude-sonnet-4-6",
      "apiBase": "${API_BASE}",
      "apiKey": "${S.key}"
    }
  ],
  "tabAutocompleteModel": {
    "title": "GPT-4o Mini (${BRAND})",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "apiBase": "${API_BASE}",
    "apiKey": "${S.key}"
  }
}`;

const CHECK_MODELS = `curl ${API_BASE}/models \\
  -H "Authorization: Bearer ${S.key}"`;

// ── Sandboxes snippets ────────────────────────────────────────────────────────

const SANDBOX_QUICKSTART: CodeTabItem[] = [
  {
    key: "python", label: "Python SDK",
    code: `# pip install aineron
from aineron import Sandbox

with Sandbox(template="python") as sbx:
    result = sbx.exec(code="print(2 + 2)")
    print(result.stdout)   # 4
# ${S.sbxAutoStopped}`,
  },
  {
    key: "curl", label: "curl",
    code: `# ${S.sbxStep1}
curl -X POST ${API_BASE}/sandboxes/ \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"template": "python", "timeout_seconds": 300}'
# → {"id": "sbx_...", "state": "running", ...}

# ${S.sbxStep2}
curl -X POST ${API_BASE}/sandboxes/sbx_.../exec/ \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"code": "print(2 + 2)", "language": "python"}'
# → {"exit_code": 0, "stdout": "4\\n", ...}

# ${S.sbxStep3}
curl -X DELETE ${API_BASE}/sandboxes/sbx_.../ \\
  -H "Authorization: Bearer ${S.key}"`,
  },
];

const SANDBOX_FILES = `# ${S.sbxWrite}
curl -X POST ${API_BASE}/sandboxes/sbx_.../files/ \\
  -H "Authorization: Bearer ${S.key}" \\
  -H "Content-Type: application/json" \\
  -d '{"files": [{"path": "main.py", "content": "print(42)"}]}'

# ${S.sbxRead}
curl "${API_BASE}/sandboxes/sbx_.../files/?path=/home/user/main.py" \\
  -H "Authorization: Bearer ${S.key}"

# ${S.sbxList}
curl "${API_BASE}/sandboxes/sbx_.../files/?path=/home/user&op=list" \\
  -H "Authorization: Bearer ${S.key}"`;

const SANDBOX_AGENT = `from openai import OpenAI
from aineron import Sandbox

llm = OpenAI(base_url="${API_BASE}", api_key="${S.key}")

def solve_with_code(task: str) -> str:
    """${S.agentDoc}"""
    code = llm.chat.completions.create(
        model="deepseek-v3",
        messages=[{
            "role": "user",
            "content": f"${S.agentTask} {task}",
        }],
    ).choices[0].message.content.strip().strip("\`").removeprefix("python")

    with Sandbox(template="python", timeout=120) as sbx:
        result = sbx.exec(code=code, timeout=60)
        if result.ok:
            return result.stdout
        return f"${S.agentErr} {result.stderr}"

print(solve_with_code("${S.agentFib}"))`;

// ── Groups ────────────────────────────────────────────────────────────────────
// GROUPS — статическая JSX-структура (не может звать хуки/т() на уровне модуля),
// поэтому вся конструкция обёрнута в функцию, вызываемую внутри async-компонента
// страницы с уже полученным `t` (next-intl/server, getTranslations("apiDocs")).

function buildGroups(t: Awaited<ReturnType<typeof getTranslations>>): DocGroup[] {
  return [
  {
    title: t("intro.groupTitle"),
    items: [
      {
        id: "overview",
        label: t("intro.navOverview"),
        content: (
          <>
            <DocSection title={t("intro.overviewSectionTitle")}>
              <Lead>
                {t.rich("intro.overviewLead", {
                  brand: BRAND,
                  b: (chunks) => <b>{chunks}</b>,
                  ic: (chunks) => <IC>{chunks}</IC>,
                })}
              </Lead>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <InfoCard label="Base URL" value={`${BRAND}/api/v1`} />
                <InfoCard label={t("intro.overviewAuthLabel")} value="Bearer ak_..." />
                <InfoCard label={t("intro.overviewFormatLabel")} value="OpenAI + Anthropic" />
                <InfoCard label={t("intro.overviewBillingLabel")} value={t("intro.overviewBillingValue")} />
              </div>
              <P>
                {t.rich("intro.overviewFormatsP", {
                  b1: (chunks) => <b>{chunks}</b>,
                  b2: (chunks) => <b>{chunks}</b>,
                  ic1: (chunks) => <IC>{chunks}</IC>,
                  ic2: (chunks) => <IC>{chunks}</IC>,
                  ic3: (chunks) => <IC>{chunks}</IC>,
                  ic4: (chunks) => <IC>{chunks}</IC>,
                  ic5: (chunks) => <IC>{chunks}</IC>,
                })}
              </P>
            </DocSection>
            <DocSection title={t("intro.overviewGettingStartedTitle")}>
              <UL>
                <LI>{t.rich("intro.gettingStartedItem1", { a: (chunks) => <A href="#quickstart">{chunks}</A> })}</LI>
                <LI>{t.rich("intro.gettingStartedItem2", { a: (chunks) => <A href="#auth">{chunks}</A> })}</LI>
                <LI>{t.rich("intro.gettingStartedItem3", { a: (chunks) => <A href="#billing">{chunks}</A> })}</LI>
                <LI>{t.rich("intro.gettingStartedItem4", { a: (chunks) => <A href="#ide-cursor">{chunks}</A> })}</LI>
              </UL>
              <div className="flex flex-wrap gap-3 pt-1">
                <Link href="/api-docs/playground/" className="inline-flex items-center gap-2 rounded-[10px] bg-[#D97757] px-5 py-2.5 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]">
                  <Play size={14} /> Playground
                </Link>
                <a href="/api/v1/docs/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 rounded-[10px] bg-[#1A1A1A] px-5 py-2.5 text-[15px] font-medium text-white">
                  Swagger UI <ExternalLink size={14} />
                </a>
                <Link href="/account/keys/" className="inline-flex items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-5 py-2.5 text-[15px] font-medium text-[rgba(13,13,13,0.7)] transition-colors hover:bg-[rgba(13,13,13,0.04)] dark:border-[rgba(255,255,255,0.14)] dark:bg-[#211E1B] dark:text-[rgba(236,236,236,0.7)]">
                  {t("intro.createApiKeyButton")}
                </Link>
              </div>
            </DocSection>
          </>
        ),
      },
      {
        id: "quickstart",
        label: t("intro.navQuickstart"),
        content: (
          <DocSection title={t("intro.quickstartTitle")} intro={t("intro.quickstartIntro")}>
            <Steps>
              <Step n={1}>
                {t.rich("intro.quickstartStep1", {
                  b: (chunks) => <b>{chunks}</b>,
                  a: (chunks) => <A href="/account/keys/">{chunks}</A>,
                  ic: (chunks) => <IC>{chunks}</IC>,
                })}
              </Step>
              <Step n={2}>
                {t.rich("intro.quickstartStep2", {
                  b: (chunks) => <b>{chunks}</b>,
                  ic1: () => <IC>{API_BASE}</IC>,
                  ic2: (chunks) => <IC>{chunks}</IC>,
                })}
              </Step>
              <Step n={3}>
                {t.rich("intro.quickstartStep3", { b: (chunks) => <b>{chunks}</b> })}
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
        label: t("intro.navAuth"),
        content: (
          <DocSection title={t("intro.authTitle")} intro={t("intro.authIntro")}>
            <StandaloneCodeBlock code={`Authorization: Bearer ${S.key}`} />
            <UL>
              <LI>{t.rich("intro.authItem1", { a: (chunks) => <A href="/account/keys/">{chunks}</A> })}</LI>
              <LI>{t("intro.authItem2")}</LI>
              <LI>{t("intro.authItem3")}</LI>
            </UL>
            <Callout type="warn" title={t("intro.authWarnTitle")}>
              {t.rich("intro.authWarnBody", { ic: (chunks) => <IC>{chunks}</IC> })}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "billing",
        label: t("intro.navBilling"),
        content: (
          <DocSection title={t("intro.billingTitle")} intro={t("intro.billingIntro")}>
            <UL>
              <LI>{t("intro.billingItem1")}</LI>
              <LI>{t.rich("intro.billingItem2", { a: (chunks) => <A href="/account/analytics/">{chunks}</A> })}</LI>
              <LI>{t.rich("intro.billingItem3", { b: (chunks) => <b>{chunks}</b>, ic: (chunks) => <IC>{chunks}</IC> })}</LI>
              <LI>{t.rich("intro.billingItem4", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
            </UL>
            <Callout type="tip">
              {t.rich("intro.billingTip", { ic: (chunks) => <IC>{chunks}</IC> })}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "errors",
        label: t("intro.navErrors"),
        content: (
          <DocSection title={t("intro.errorsTitle")} intro={t("intro.errorsIntro")}>
            <StandaloneCodeBlock code={errorBody(t)} />
            <div className="pt-2">
              <DataTable
                head={["HTTP", "type", t("intro.errorsTableHeadReason")]}
                rows={[
                  ["401", <IC>authentication_error</IC>, t("intro.errorReason401")],
                  ["402", <IC>insufficient_quota</IC>, t("intro.errorReason402")],
                  ["403", <IC>permission_error</IC>, t("intro.errorReason403")],
                  ["429", <IC>rate_limit_exceeded</IC>, t("intro.errorReason429")],
                  ["400", <IC>invalid_request_error</IC>, t("intro.errorReason400")],
                ]}
              />
            </div>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("endpoints.groupTitle"),
    items: [
      {
        id: "chat",
        label: "Chat Completions",
        content: (
          <DocSection title="Chat Completions" intro={t("endpoints.chatIntro")}>
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/chat/completions</Path>
            </p>
            <CodeTabs tabs={QUICKSTART} />
            <H3>{t("endpoints.chatModelsTitle")}</H3>
            <DataTable
              head={["model", t("endpoints.chatTableHeadPurpose")]}
              rows={[
                [<IC>gpt-4o</IC>, t("endpoints.chatModelGpt4o")],
                [<IC>gpt-5</IC>, t("endpoints.chatModelGpt5")],
                [<IC>gpt-4o-mini</IC>, t("endpoints.chatModelGpt4oMini")],
                [<IC>claude-sonnet-4-6</IC>, t("endpoints.chatModelSonnet")],
                [<IC>claude-opus-4-8</IC>, t("endpoints.chatModelOpus")],
                [<IC>gemini-2.5-pro</IC>, t("endpoints.chatModelGemini")],
                [<IC>deepseek-v3</IC>, t("endpoints.chatModelDeepseek")],
              ]}
            />
            <Callout type="info">
              {t.rich("endpoints.chatCatalogCallout", {
                ic: (chunks) => <IC>{chunks}</IC>,
                a: (chunks) => <A href="/models/">{chunks}</A>,
              })}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "messages",
        label: "Messages (Anthropic)",
        content: (
          <DocSection title={t("endpoints.messagesTitle")} intro={t("endpoints.messagesIntro")}>
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/messages</Path>
            </p>
            <CodeTabs tabs={ANTHROPIC} />
          </DocSection>
        ),
      },
      {
        id: "models",
        label: t("endpoints.modelsNavLabel"),
        content: (
          <DocSection title={t("endpoints.modelsTitle")} intro={t("endpoints.modelsIntro")}>
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>GET</Method> <Path>/api/v1/models</Path>
            </p>
            <StandaloneCodeBlock code={CHECK_MODELS} />
            <P>{t("endpoints.modelsCatalogP")}</P>
            <UL>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/categories/</Path> — {t("endpoints.modelsCatCategories")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/networks/</Path> — {t("endpoints.modelsCatNetworks")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/catalog/networks/{"{slug}"}/</Path> — {t("endpoints.modelsCatDetail")}</LI>
            </UL>
          </DocSection>
        ),
      },
      {
        id: "images",
        label: t("endpoints.imagesNavLabel"),
        content: (
          <DocSection title={t("endpoints.imagesTitle")} intro={t("endpoints.imagesIntro")}>
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/images/generations</Path>
            </p>
            <CodeTabs tabs={IMAGES} />
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/images/enhance-prompt/</Path> — {t("endpoints.imagesEnhancePrompt")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/generations/{"{id}"}/progress/</Path> — {t("endpoints.imagesProgress")}</LI>
              <LI><Method>POST</Method> <Path>/api/v1/generations/{"{id}"}/upscale/</Path> — {t("endpoints.imagesUpscale")}; <IC>/variations/</IC>, <IC>/remove-background/</IC></LI>
            </UL>
            <Callout type="info">
              {t("endpoints.imagesVideoCallout")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "embeddings",
        label: "Embeddings",
        content: (
          <DocSection title="Embeddings" intro={t("endpoints.embeddingsIntro")}>
            <p className="flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/embeddings</Path>
            </p>
            <StandaloneCodeBlock code={EMBEDDINGS} />
          </DocSection>
        ),
      },
      {
        id: "audio",
        label: t("endpoints.audioNavLabel"),
        content: (
          <DocSection title={t("endpoints.audioTitle")}>
            <H3>{t("endpoints.audioTtsTitle")}</H3>
            <p className="mb-2 flex flex-wrap items-center gap-2 text-[15px]">
              <Method>POST</Method> <Path>/api/v1/audio/speech</Path>
            </p>
            <StandaloneCodeBlock code={AUDIO_TTS} />
            <H3>{t("endpoints.audioAsrTitle")}</H3>
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
          <DocSection title="Batch API" intro={t("endpoints.batchIntro")}>
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/batches/</Path> — {t("endpoints.batchCreate")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/batches/{"{id}"}/</Path> — {t("endpoints.batchStatus")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/batches/{"{id}"}/results/</Path> — {t("endpoints.batchResults")}</LI>
              <LI><Method>POST</Method> <Path>/api/v1/batches/{"{id}"}/cancel/</Path> — {t("endpoints.batchCancel")}</LI>
            </UL>
            <P>{t("endpoints.batchP")}</P>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: "Sandboxes",
    items: [
      {
        id: "sandboxes",
        label: t("sandboxes.navOverview"),
        content: (
          <>
            <DocSection title={t("sandboxes.title")}>
              <Lead>
                {t.rich("sandboxes.lead", { b: (chunks) => <b>{chunks}</b> })}
              </Lead>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <InfoCard label={t("sandboxes.infoIsolationLabel")} value="microVM" />
                <InfoCard label={t("sandboxes.infoStartLabel")} value={t("sandboxes.infoStartValue")} />
                <InfoCard label="small" value={t("sandboxes.infoSmallValue")} />
                <InfoCard label="standard" value={t("sandboxes.infoStandardValue")} />
              </div>
              <P>
                {t("sandboxes.typicalScenariosP")}
              </P>
            </DocSection>
            <DocSection title={t("sandboxes.quickstartTitle")} intro={t("sandboxes.quickstartIntro")}>
              <CodeTabs tabs={SANDBOX_QUICKSTART} />
              <Callout type="tip" title={t("sandboxes.billingTipTitle")}>
                {t("sandboxes.billingTipBody")}
              </Callout>
            </DocSection>
          </>
        ),
      },
      {
        id: "sandboxes-ref",
        label: t("sandboxesRef.navLabel"),
        content: (
          <DocSection title={t("sandboxesRef.title")}>
            <DataTable
              head={[t("sandboxesRef.tableHeadMethod"), t("sandboxesRef.tableHeadPath"), t("sandboxesRef.tableHeadPurpose")]}
              rows={[
                [<Method>POST</Method>, <Path>/api/v1/sandboxes/</Path>, t("sandboxesRef.rowCreate")],
                [<Method>GET</Method>, <Path>/api/v1/sandboxes/</Path>, t("sandboxesRef.rowList")],
                [<Method>GET</Method>, <Path>/api/v1/sandboxes/{"{id}"}/</Path>, t("sandboxesRef.rowStatus")],
                [<Method>POST</Method>, <Path>/api/v1/sandboxes/{"{id}"}/exec/</Path>, t("sandboxesRef.rowExec")],
                [<Method>POST</Method>, <Path>/api/v1/sandboxes/{"{id}"}/files/</Path>, t("sandboxesRef.rowFilesWrite")],
                [<Method>GET</Method>, <Path>/api/v1/sandboxes/{"{id}"}/files/</Path>, t("sandboxesRef.rowFilesRead")],
                [<Method>GET</Method>, <Path>/api/v1/sandboxes/{"{id}"}/logs/</Path>, t("sandboxesRef.rowLogs")],
                [<Method>GET</Method>, <Path>/api/v1/sandboxes/{"{id}"}/logs/stream/</Path>, t("sandboxesRef.rowLogsStream")],
                [<Method>POST</Method>, <Path>/api/v1/sandboxes/{"{id}"}/timeout/</Path>, t("sandboxesRef.rowTimeout")],
                [<Method>DELETE</Method>, <Path>/api/v1/sandboxes/{"{id}"}/</Path>, t("sandboxesRef.rowDelete")],
              ]}
            />
            <H3>{t("sandboxesRef.filesTitle")}</H3>
            <StandaloneCodeBlock code={SANDBOX_FILES} />
            <H3>{t("sandboxesRef.paramsTitle")}</H3>
            <DataTable
              head={[t("sandboxesRef.paramHeadParam"), t("sandboxesRef.paramHeadValues"), t("sandboxesRef.paramHeadDefault")]}
              rows={[
                [<IC>template</IC>, "base | python | nodejs | nextjs | django", <IC>base</IC>],
                [<IC>size</IC>, "small (1 vCPU/1 GiB) | standard (2 vCPU/2 GiB)", <IC>standard</IC>],
                [<IC>timeout_seconds</IC>, "60–3600", "300"],
                [<IC>env</IC>, t("sandboxesRef.paramEnvValues"), "—"],
                [<IC>metadata</IC>, t("sandboxesRef.paramMetadataValues"), "—"],
              ]}
            />
            <H3>{t("sandboxesRef.limitsTitle")}</H3>
            <UL>
              <LI>{t("sandboxesRef.limit1")}</LI>
              <LI>{t.rich("sandboxesRef.limit2", { ic: (chunks) => <IC>{chunks}</IC> })}</LI>
              <LI>{t.rich("sandboxesRef.limit3", {
                ic1: () => <IC>/home/user</IC>,
                ic2: () => <IC>/tmp</IC>,
                ic3: () => <IC>/app</IC>,
              })}</LI>
              <LI>{t("sandboxesRef.limit4")}</LI>
            </UL>
            <Callout type="warn" title="Idempotency-Key">
              {t.rich("sandboxesRef.idempotencyBody", { ic: (chunks) => <IC>{chunks}</IC> })}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "sandboxes-agent",
        label: t("sandboxesAgent.navLabel"),
        content: (
          <DocSection
            title={t("sandboxesAgent.title")}
            intro={t("sandboxesAgent.intro")}
          >
            <StandaloneCodeBlock code={SANDBOX_AGENT} />
            <P>
              {t.rich("sandboxesAgent.patternP", {
                ic1: () => <IC>run_python</IC>,
                ic2: () => <IC>tools</IC>,
              })}
            </P>
            <Callout type="tip">
              {t.rich("sandboxesAgent.tipBody", { ic: (chunks) => <IC>{chunks}</IC> })}
            </Callout>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("resources.groupTitle"),
    items: [
      {
        id: "res-chats",
        label: t("resources.resChatsNavLabel"),
        content: (
          <DocSection title={t("resources.resChatsTitle")} intro={t("resources.resChatsIntro")}>
            <DataTable
              head={[t("resources.tableHeadMethod"), t("resources.tableHeadPath"), t("resources.tableHeadPurpose")]}
              rows={[
                [<Method>GET</Method>, <Path>/api/v1/chats/</Path>, t("resources.resChatsRowList")],
                [<Method>POST</Method>, <Path>/api/v1/chats/</Path>, t("resources.resChatsRowCreate")],
                [<Method>POST</Method>, <Path>/api/v1/chats/{"{id}"}/messages/stream/</Path>, t("resources.resChatsRowStream")],
                [<Method>GET</Method>, <Path>/api/v1/chats/search/</Path>, t("resources.resChatsRowSearch")],
                [<Method>GET</Method>, <Path>/api/v1/projects/</Path>, t("resources.resChatsRowProjects")],
                [<Method>POST</Method>, <Path>/api/v1/projects/{"{id}"}/files/</Path>, t("resources.resChatsRowProjectsUpload")],
                [<Method>GET</Method>, <Path>/api/v1/projects/{"{id}"}/kb/stats/</Path>, t("resources.resChatsRowKbStatus")],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-agent",
        label: t("resources.resAgentNavLabel"),
        content: (
          <DocSection title={t("resources.resAgentTitle")}>
            <DataTable
              head={[t("resources.tableHeadMethod"), t("resources.tableHeadPath"), t("resources.tableHeadPurpose")]}
              rows={[
                [<Method>GET</Method>, <Path>/api/v1/memory/</Path>, t("resources.resAgentRowMemoryList")],
                [<Method>POST</Method>, <Path>/api/v1/memory/quick-save/</Path>, t("resources.resAgentRowMemorySave")],
                [<Method>GET</Method>, <Path>/api/v1/orgs/{"{id}"}/memory/</Path>, t("resources.resAgentRowMemoryOrg")],
                [<Method>GET</Method>, <Path>/api/v1/tasks/</Path>, t("resources.resAgentRowTasksList")],
                [<Method>POST</Method>, <Path>/api/v1/tasks/{"{id}"}/run/</Path>, t("resources.resAgentRowTasksRun")],
                [<Method>POST</Method>, <Path>/api/v1/agent/</Path>, t("resources.resAgentRowAgentRun")],
                [<Method>GET</Method>, <Path>/api/v1/agent/{"{id}"}/</Path>, t("resources.resAgentRowAgentStatus")],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-research",
        label: t("resources.resResearchNavLabel"),
        content: (
          <DocSection title={t("resources.resResearchTitle")} intro={t("resources.resResearchIntro")}>
            <DataTable
              head={[t("resources.tableHeadMethod"), t("resources.tableHeadPath"), t("resources.tableHeadPurpose")]}
              rows={[
                [<Method>POST</Method>, <Path>/api/v1/chats/{"{id}"}/research/</Path>, t("resources.resResearchRowStart")],
                [<Method>GET</Method>, <Path>/api/v1/research/{"{id}"}/</Path>, t("resources.resResearchRowStatus")],
                [<Method>POST</Method>, <Path>/api/v1/research/{"{id}"}/save/</Path>, t("resources.resResearchRowSave")],
              ]}
            />
          </DocSection>
        ),
      },
      {
        id: "res-webhooks",
        label: t("resources.resWebhooksNavLabel"),
        content: (
          <DocSection title={t("resources.resWebhooksTitle")}>
            <H3>{t("resources.resWebhooksOutgoingTitle")}</H3>
            <P>{t("resources.resWebhooksOutgoingIntro")}</P>
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/webhooks/</Path> — {t("resources.resWebhooksRowCreate")}</LI>
              <LI><Method>POST</Method> <Path>/api/v1/webhooks/{"{id}"}/test/</Path> — {t("resources.resWebhooksRowTest")}</LI>
            </UL>
            <H3>{t("resources.resWebhooksUsageTitle")}</H3>
            <UL>
              <LI><Method>GET</Method> <Path>/api/v1/usage/</Path> — {t("resources.resWebhooksRowUsage")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/audit/</Path> — {t("resources.resWebhooksRowAudit")}</LI>
              <LI><Method>GET</Method> <Path>/api/v1/status/</Path> — {t("resources.resWebhooksRowStatus")}</LI>
            </UL>
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("ide.groupTitle"),
    items: [
      {
        id: "ide-cursor",
        label: "Cursor",
        content: (
          <DocSection title="Cursor" intro={t("ide.cursorIntro")}>
            <Steps>
              <Step n={1}>
                {t.rich("ide.cursorStep1", {
                  kbd1: () => <Kbd>Ctrl+Shift+J</Kbd>,
                  kbd2: () => <Kbd>Cmd+Shift+J</Kbd>,
                  b1: () => <b>Models</b>,
                  b2: () => <b>Add Model</b>,
                })}
              </Step>
              <Step n={2}>
                {t.rich("ide.cursorStep2", {
                  b1: () => <b>OpenAI API Key</b>,
                  b2: () => <b>Override OpenAI Base URL</b>,
                  urlIc: () => <IC>{API_BASE}</IC>,
                  b3: () => <b>API Key</b>,
                  keyIc: () => <IC>ak_...</IC>,
                })}
              </Step>
              <Step n={3}>
                {t.rich("ide.cursorStep3", {
                  b: () => <b>Model Name</b>,
                  ic1: () => <IC>gpt-4o</IC>,
                  ic2: () => <IC>claude-sonnet-4-6</IC>,
                })}
                <div className="mt-3"><StandaloneCodeBlock code={CHECK_MODELS} /></div>
              </Step>
              <Step n={4}>
                {t.rich("ide.cursorStep4", {
                  b: () => <b>Save</b>,
                  kbd: () => <Kbd>Ctrl+L</Kbd>,
                })}
              </Step>
            </Steps>
            <Callout type="info">
              {t("ide.cursorCalloutInfo")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "ide-cline",
        label: "Cline",
        content: (
          <DocSection title="Cline" intro={t("ide.clineIntro")}>
            <Steps>
              <Step n={1}>
                {t.rich("ide.clineStep1", { b: () => <b>Cline</b> })}
              </Step>
              <Step n={2}>
                {t.rich("ide.clineStep2", {
                  b1: () => <b>API Provider</b>,
                  b2: () => <b>OpenAI Compatible</b>,
                })}
                <div className="mt-3"><StandaloneCodeBlock code={CLINE_SETTINGS} /></div>
              </Step>
              <Step n={3}>
                {t.rich("ide.clineStep3", {
                  ic1: () => <IC>claude-sonnet-4-6</IC>,
                  ic2: () => <IC>gpt-4o</IC>,
                  ic3: () => <IC>claude-opus-4-8</IC>,
                })}
              </Step>
              <Step n={4}>{t("ide.clineStep4")}</Step>
            </Steps>
            <Callout type="warn">
              {t("ide.clineCalloutWarn")}
            </Callout>
          </DocSection>
        ),
      },
      {
        id: "ide-continue",
        label: "Continue",
        content: (
          <DocSection title="Continue" intro={t("ide.continueIntro")}>
            <Steps>
              <Step n={1}>
                {t.rich("ide.continueStep1", {
                  b1: () => <b>Continue</b>,
                  ic: () => <IC>~/.continue/config.json</IC>,
                  b2: () => <b>Continue: Open Config</b>,
                })}
              </Step>
              <Step n={2}>
                {t.rich("ide.continueStep2", { ic: () => <IC>models</IC> })}
                <div className="mt-3"><StandaloneCodeBlock code={CONTINUE_CONFIG} /></div>
              </Step>
              <Step n={3}>{t("ide.continueStep3")}</Step>
            </Steps>
            <H3>{t("ide.continueShortcutsTitle")}</H3>
            <DataTable
              head={[t("ide.continueTableHeadCombo"), t("ide.continueTableHeadAction")]}
              rows={[
                [<Kbd>Ctrl+L</Kbd>, t("ide.continueRowCtrlL")],
                [<Kbd>Ctrl+I</Kbd>, t("ide.continueRowCtrlI")],
                [<Kbd>Tab</Kbd>, t("ide.continueRowTab")],
                [<Kbd>Ctrl+Shift+R</Kbd>, t("ide.continueRowCtrlShiftR")],
              ]}
            />
          </DocSection>
        ),
      },
    ],
  },
  {
    title: t("more.groupTitle"),
    items: [
      {
        id: "telegram",
        label: t("more.telegramNavLabel"),
        content: (
          <DocSection title={t("more.telegramTitle")} intro={t("more.telegramIntro")}>
            <UL>
              <LI><Method>POST</Method> <Path>/api/v1/telegram/link-token/</Path> — {t("more.telegramLinkTokenRow")}</LI>
              <LI><Method>POST</Method> <Path>/api/v1/telegram/webapp-auth/</Path> — {t("more.telegramWebappAuthRow")}</LI>
            </UL>
            <P>
              {t.rich("more.telegramGuideP", { a: (chunks) => <A href="/docs/#tg-start">{chunks}</A> })}
            </P>
          </DocSection>
        ),
      },
      {
        id: "tools",
        label: t("more.toolsNavLabel"),
        content: (
          <DocSection title={t("more.toolsTitle")}>
            <FeatureGrid>
              <FeatureCard icon={<Play size={16} />} title="Playground">
                {t.rich("more.toolsPlaygroundBody", { a: (chunks) => <A href="/api-docs/playground/">{chunks}</A> })}
              </FeatureCard>
              <FeatureCard icon={<ExternalLink size={16} />} title="Swagger UI">
                {t.rich("more.toolsSwaggerBody", { a: (chunks) => <A href="/api/v1/docs/">{chunks}</A> })}
              </FeatureCard>
              <FeatureCard icon={<Download size={16} />} title={t("more.toolsPostmanTitle")}>
                {t.rich("more.toolsPostmanBody", { a: (chunks) => <A href="/static/docs/postman_collection.json">{chunks}</A> })}
              </FeatureCard>
              <FeatureCard icon={<ExternalLink size={16} />} title={t("more.toolsOpenapiTitle")}>
                {t.rich("more.toolsOpenapiBody", {
                  a: () => <A href="/api/v1/schema/">/api/v1/schema/</A>,
                })}
              </FeatureCard>
            </FeatureGrid>
          </DocSection>
        ),
      },
      {
        id: "dev-faq",
        label: t("more.devFaqNavLabel"),
        content: (
          <DocSection title={t("more.devFaqTitle")}>
            <H3>{t("more.devFaqQ1")}</H3>
            <P>
              {t.rich("more.devFaqA1", {
                ic1: () => <IC>claude-sonnet-4-6</IC>,
                ic2: () => <IC>gpt-4o</IC>,
                ic3: () => <IC>gpt-4o-mini</IC>,
              })}
            </P>
            <H3>{t("more.devFaqQ2")}</H3>
            <P>{t("more.devFaqA2")}</P>
            <H3>{t("more.devFaqQ3")}</H3>
            <P>
              {t.rich("more.devFaqA3", {
                ic1: () => <IC>stream: true</IC>,
                ic2: () => <IC>/chat/completions</IC>,
              })}
            </P>
            <H3>{t("more.devFaqQ4")}</H3>
            <P>
              {t.rich("more.devFaqA4", {
                method: () => <Method>GET</Method>,
                path: () => <Path>/api/v1/usage/</Path>,
                a: (chunks) => <A href="/account/analytics/">{chunks}</A>,
              })}
            </P>
            <H3>{t("more.devFaqQ5")}</H3>
            <P>
              {t.rich("more.devFaqA5", { ic: () => <IC>base_url</IC> })}
            </P>
            <Callout type="info" title={t("more.devFaqHelpTitle")}>
              {t.rich("more.devFaqHelpBody", { a: (chunks) => <A href="/docs/">{chunks}</A> })}
            </Callout>
          </DocSection>
        ),
      },
    ],
  },
  ];
}

export default async function ApiDocsPage() {
  const t = await getTranslations("apiDocs");
  return (
    <DocLayout
      eyebrow={t("eyebrow")}
      title={t("title")}
      subtitle={t("subtitle")}
      breadcrumb={[{ label: t("breadcrumbHome"), href: "/" }, { label: t("breadcrumbApiDocs") }]}
      groups={buildGroups(t)}
    />
  );
}
