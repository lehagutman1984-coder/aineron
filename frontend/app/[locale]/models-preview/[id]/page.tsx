import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Code2, ImageIcon, Video, type LucideIcon } from "lucide-react";
import { PREVIEW_MODELS, type PreviewCategory, type PreviewModel } from "@/lib/data/pricingPreviewModels";
import { DETAILS, PARAMETER_INFO } from "@/lib/data/pricingPreviewDetails";
import { formatRub } from "@/lib/money";

const CATEGORY_ICON: Record<PreviewCategory, LucideIcon> = {
  text: Code2,
  image: ImageIcon,
  video: Video,
};

const CATEGORY_LABELS: Record<PreviewCategory, string> = {
  text: "Текст",
  image: "Изображения",
  video: "Видео",
};

// force-dynamic (тот же паттерн, что и у реальной /models/[slug]/) —
// generateStaticParams() статически рендерил все 59 карточек, но на сборке
// в проде next.js молча (без ошибки в логе) не сгенерировал ОДНУ конкретную
// страницу (seedance-2-5) — воспроизвелось 3/3 при чистых пересборках,
// хотя локально собиралось верно. Известный класс бага next-intl app-router:
// страница, отсутствующая в статическом выводе, при попытке фолбэка на
// динамику падает с "Page changed from static to dynamic... reason: headers"
// (next-intl's requestLocale() зовёт headers(), что запрещено для страницы,
// объявленной как static). force-dynamic убирает саму возможность такого
// рассинхрона — рендерим всегда на лету, как /models/[slug]/.
export const dynamic = "force-dynamic";

export function generateMetadata({ params }: { params: { id: string } }): Metadata {
  const model = PREVIEW_MODELS.find((m) => m.id === params.id);
  if (!model) return { title: "Модель не найдена" };
  return {
    title: `${model.name} — цена и параметры (превью)`,
    description: model.description,
    robots: { index: false, follow: false },
  };
}

export default function ModelDetailPreviewPage({ params }: { params: { id: string } }) {
  const model = PREVIEW_MODELS.find((m) => m.id === params.id);
  if (!model) notFound();

  const detail = DETAILS[model.id];
  const Icon = CATEGORY_ICON[model.category];

  const related = PREVIEW_MODELS.filter(
    (m) => m.category === model.category && Boolean(m.isFree) === Boolean(model.isFree) && m.id !== model.id
  ).slice(0, 4);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
      {/* Back */}
      <Link
        href="/models-preview"
        className="mb-6 inline-flex items-center gap-1.5 text-[15px] text-[rgba(13,13,13,0.55)] hover:text-[#1A1A1A] transition-colors"
      >
        <ArrowLeft size={14} />
        Каталог моделей и цены
      </Link>

      {/* Header */}
      <div className="mb-8 flex items-start gap-5">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-[14px] bg-[rgba(217,119,87,0.10)] text-[#D97757]">
          <Icon size={28} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h1 className="text-[26px] font-bold text-[#1A1A1A]">{model.name}</h1>
            <span className="rounded-full bg-[rgba(13,13,13,0.07)] px-2.5 py-0.5 text-[14px] text-[rgba(13,13,13,0.55)]">
              {model.provider}
            </span>
            <span className="rounded-full bg-[rgba(13,13,13,0.07)] px-2.5 py-0.5 text-[14px] text-[rgba(13,13,13,0.55)]">
              {CATEGORY_LABELS[model.category]}
            </span>
          </div>
          <p className="text-[17px] leading-relaxed text-[rgba(13,13,13,0.65)]">
            {detail?.longDescription ?? model.description}
          </p>
          {detail?.note && (
            <p className="mt-2 text-[14px] leading-relaxed text-[rgba(13,13,13,0.5)]">{detail.note}</p>
          )}
        </div>
      </div>

      {/* Stat chips */}
      <div className="mb-8 flex flex-wrap gap-4">
        {(detail?.contextTokens ?? model.contextLabel) && (
          <StatChip
            label={`${model.category === "text" ? "Контекст" : "Параметры"}: ${detail?.contextTokens ?? model.contextLabel}`}
          />
        )}
        {detail?.maxOutputTokens && <StatChip label={`Макс. ответ: ${detail.maxOutputTokens}`} />}
        <StatChip label={`Вход: ${model.inputBadges.join(", ")}`} />
        <StatChip label={`Выход: ${model.outputBadges.join(", ")}`} />
      </div>

      {/* Pricing */}
      <Section title="Цена">
        <PricingCard model={model} />
      </Section>

      {/* Best for */}
      {detail?.bestFor && detail.bestFor.length > 0 && (
        <Section title="Хорошо подходит для">
          <ul className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {detail.bestFor.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white px-3.5 py-3 text-[15px] leading-snug text-[rgba(13,13,13,0.75)]"
              >
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#D97757]" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* Reasoning levels */}
      {detail?.reasoningLevels && detail.reasoningLevels.length > 0 && (
        <Section title="Уровни рассуждений">
          <div className="flex flex-wrap gap-2">
            {detail.reasoningLevels.map((level) => (
              <span
                key={level}
                className="rounded-[8px] border border-[rgba(13,13,13,0.12)] bg-white px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.7)]"
              >
                {level}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* Supported parameters */}
      {detail?.supportedParameters && detail.supportedParameters.length > 0 && (
        <Section title="Поддерживаемые параметры API">
          <div className="overflow-hidden rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white">
            {detail.supportedParameters.map((param, i) => {
              const name = typeof param === "string" ? param : param.name;
              const desc = typeof param === "string" ? (PARAMETER_INFO[param] ?? "") : param.description;
              return (
                <div
                  key={name}
                  className={[
                    "flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-baseline sm:gap-4",
                    i > 0 ? "border-t border-[rgba(13,13,13,0.08)]" : "",
                  ].join(" ")}
                >
                  <code className="w-[160px] shrink-0 text-[14px] font-medium text-[#D97757]">{name}</code>
                  <span className="text-[14px] leading-relaxed text-[rgba(13,13,13,0.6)]">{desc}</span>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Code example */}
      <Section title="Пример запроса">
        <CodeExample apiModelName={detail?.apiModelName ?? model.id} category={model.category} />
      </Section>

      {/* Related */}
      {related.length > 0 && (
        <Section title="Похожие модели">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {related.map((m) => (
              <Link
                key={m.id}
                href={`/models-preview/${m.id}`}
                className="flex flex-col items-center gap-2 rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white p-4 text-center transition-all hover:border-[rgba(13,13,13,0.25)] hover:shadow-sm"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-[rgba(217,119,87,0.08)] text-[#D97757]">
                  <Icon size={16} />
                </div>
                <span className="text-[14px] font-medium leading-tight text-[#1A1A1A]">{m.name}</span>
              </Link>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-10">
      <h2 className="mb-4 text-[18px] font-semibold text-[#1A1A1A]">{title}</h2>
      {children}
    </div>
  );
}

function StatChip({ label }: { label: string }) {
  return (
    <div className="rounded-full border border-[rgba(13,13,13,0.12)] px-3 py-1.5 text-[15px] text-[rgba(13,13,13,0.65)]">
      {label}
    </div>
  );
}

function PricingCard({ model }: { model: PreviewModel }) {
  if (model.isFree) {
    return (
      <div className="rounded-[12px] border border-[rgba(34,153,84,0.25)] bg-[rgba(34,153,84,0.04)] p-5">
        <div className="grid grid-cols-2 gap-4">
          <PriceStat label="Цена" value="Бесплатно" />
          {model.dailyLimit && <PriceStat label="Лимит" value={`${model.dailyLimit} сообщений в день`} />}
        </div>
      </div>
    );
  }
  if (model.category === "text") {
    const inRub = model.priceInRub ?? 0;
    const outRub = model.priceOutRub ?? 0;
    const exampleKopecks = Math.round((100_000 * inRub + 20_000 * outRub) * (100 / 1_000_000));
    return (
      <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <PriceStat label="Вход, за 1М токенов" value={formatRub(inRub * 100)} />
          <PriceStat label="Выход, за 1М токенов" value={formatRub(outRub * 100)} />
          <PriceStat label="Пример: 100К вход + 20К выход" value={formatRub(exampleKopecks)} />
        </div>
      </div>
    );
  }
  if (model.category === "image") {
    return (
      <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
        <PriceStat label="За одну генерацию" value={formatRub((model.priceGenRub ?? 0) * 100)} />
      </div>
    );
  }
  if (model.priceUnit === "call") {
    return (
      <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
        <PriceStat label="За видео (тарификация за клип, не за секунду)" value={formatRub((model.priceVideoRub ?? 0) * 100)} />
      </div>
    );
  }
  return (
    <div className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-5">
      <div className="grid grid-cols-2 gap-4">
        <PriceStat label="За секунду видео" value={formatRub((model.priceVideoRub ?? 0) * 100)} />
        <PriceStat label="Пример: ролик 8 сек" value={formatRub(Math.round((model.priceVideoRub ?? 0) * 8 * 100))} />
      </div>
    </div>
  );
}

function PriceStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[13px] text-[rgba(13,13,13,0.5)]">{label}</p>
      <p className="mt-0.5 text-[20px] font-semibold text-[#1A1A1A]">{value}</p>
    </div>
  );
}

function CodeExample({ apiModelName, category }: { apiModelName: string; category: PreviewCategory }) {
  const code =
    category === "text"
      ? `curl https://aineron.ru/api/v1/chat/completions \\
  -H "Authorization: Bearer $AINERON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${apiModelName}",
    "messages": [{"role": "user", "content": "Привет!"}]
  }'`
      : category === "image"
        ? `curl https://aineron.ru/api/v1/images/generations \\
  -H "Authorization: Bearer $AINERON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${apiModelName}",
    "prompt": "..."
  }'`
        : `curl https://aineron.ru/api/v1/videos/generations \\
  -H "Authorization: Bearer $AINERON_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${apiModelName}",
    "prompt": "..."
  }'`;

  return (
    <pre className="overflow-x-auto rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.03)] p-4 text-[13px] leading-relaxed text-[rgba(13,13,13,0.8)]">
      <code>{code}</code>
    </pre>
  );
}
