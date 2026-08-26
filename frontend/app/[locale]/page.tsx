import { Link } from "@/i18n/navigation";
import Image from "next/image";
import { Check, X, ArrowDown } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { serverListNetworks } from "@/lib/api/server";
import { formatMoney } from "@/lib/money";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { LandingDemo } from "@/components/landing/LandingDemo";
import { LandingFaq } from "@/components/landing/LandingFaq";
import { LandingVideo } from "@/components/landing/LandingVideo";
import "./landing.css";

export const revalidate = 3600;

// Реальные kopecks-цены живых моделей из каталога (сверено 2026-08-26,
// одинаковы на aineron.ru и aineron.net) — formatMoney сам покажет рубли
// на .ru и credits на .net, никаких хардкод-сумм в переводах.
const PRICES = {
  sora: 2500,
  veo: 1500,
  kling: 1000,
  flux: 1200,
  gptImage: 1400,
  nanoBanana: 600,
  signupBonus: 1000,
  demoGptCoffee: 400,
  demoClaudeCoffee: 1200,
  demoGptLease: 800,
  demoClaudeLease: 1500,
};

const COVER_IMAGE = "/landing-media/gptimg-1.png";

export default async function HomePage({
  params,
}: {
  params: { locale: string };
}) {
  const t = await getTranslations("landing");
  const [all, free] = await Promise.all([
    serverListNetworks({ lang: params.locale }).catch(() => []),
    serverListNetworks({ is_free: true, lang: params.locale }).catch(() => []),
  ]);
  const modelCount = all?.length ?? 0;
  const freeCount = free?.length ?? 0;

  const signupAmount = formatMoney(PRICES.signupBonus);
  const marquee = t.raw("marquee") as string[];
  const marqueeLine = [...marquee, ...marquee];

  const demoAnswers = {
    "gpt|coffee": {
      label: `${t("demo.answerLabel", { model: "GPT-5" })}`,
      costKopecks: PRICES.demoGptCoffee,
      lines: t.raw("demo.answers.gptCoffee.lines") as string[],
      note: t("demo.answers.gptCoffee.note"),
    },
    "claude|coffee": {
      label: t("demo.answerLabel", { model: "Claude Sonnet 5" }),
      costKopecks: PRICES.demoClaudeCoffee,
      lines: t.raw("demo.answers.claudeCoffee.lines") as string[],
      note: t("demo.answers.claudeCoffee.note"),
    },
    "flux|coffee": {
      label: t("demo.answerLabel", { model: "Flux 2 Pro" }),
      note: t("demo.answers.fluxCoffee.note"),
    },
    "gpt|lease": {
      label: t("demo.answerLabel", { model: "GPT-5" }),
      costKopecks: PRICES.demoGptLease,
      lines: t.raw("demo.answers.gptLease.lines") as string[],
      note: t("demo.answers.gptLease.note"),
    },
    "claude|lease": {
      label: t("demo.answerLabel", { model: "Claude Sonnet 5" }),
      costKopecks: PRICES.demoClaudeLease,
      lines: t.raw("demo.answers.claudeLease.lines") as string[],
      note: t("demo.answers.claudeLease.note"),
    },
    "flux|lease": {
      label: t("demo.answerLabel", { model: "Flux 2 Pro" }),
      note: t("demo.answers.fluxLease.note"),
    },
    "flux|cover": {
      label: t("demo.answerLabel", { model: "Flux 2 Pro" }),
      costKopecks: PRICES.flux,
      note: t("demo.answers.fluxCover.note"),
    },
    "gpt|cover": {
      label: t("demo.answerLabel", { model: "GPT-5" }),
      note: t("demo.answers.gptCover.note"),
    },
    "claude|cover": {
      label: t("demo.answerLabel", { model: "Claude Sonnet 5" }),
      note: t("demo.answers.claudeCover.note"),
    },
  };

  const compareRows = t.raw("compare.rows") as string[];
  const COMPARE_MARKS: [boolean, boolean, boolean][] = [
    [true, false, false],
    [true, false, false],
    [true, false, false],
    [true, false, false],
    [true, true, true],
    [true, true, true],
    [true, true, false],
    [true, false, false],
  ];

  const otherRows = t.raw("save.otherRows") as { label: string; value: string }[];
  const usRowsRaw = t.raw("save.usRows") as { label: string; value: string }[];
  const usRows = usRowsRaw
    .filter((r) => freeCount > 0 || !r.label.includes("{count}"))
    .map((r) => ({
      ...r,
      label: r.label.replace("{count}", String(freeCount)),
    }));

  const faqItems = (t.raw("faq") as { q: string; a: string }[])
    .filter((f) => freeCount > 0 || !f.a.includes("{freeCount}"))
    .map((f) => ({
      q: f.q,
      a: f.a.replace("{count}", String(modelCount)).replace("{freeCount}", String(freeCount)),
    }));

  const year = new Date().getFullYear();

  return (
    <div className="landing-page">
      <LandingHeader
        labels={{
          models: t("nav.models"),
          features: t("nav.features"),
          compare: t("nav.compare"),
          save: t("nav.save"),
          faq: t("nav.faq"),
        }}
        loginLabel={t("nav.login")}
        ctaLabel={t("nav.cta")}
        menuLabel={t("nav.menu")}
      />

      {/* ПЕРВЫЙ ЭКРАН */}
      <section className="hero">
        <div className="hero-glow" />
        <div className="hero-mesh" />
        <div className="wrap hero-inner">
          <div>
            <div className="tagline">
              <i />
              {t("hero.tagline", { count: modelCount })}
            </div>
            <h1>
              {t("hero.title")}
              <span className="dim">{t("hero.titleDim")}</span>
            </h1>
            <p className="hero-sub">{t("hero.subtitle")}</p>
            <div className="hero-cta">
              <a href="#final" className="btn btn-primary">
                {t("hero.ctaPrimary")} →
              </a>
              <a href="#models" className="btn btn-ghost">
                {t("hero.ctaGhost")}
              </a>
            </div>
            <p className="hero-note">{t("hero.note", { amount: signupAmount })}</p>
          </div>
          <div className="metrics">
            <div className="metric">
              <span className="k">{t("metrics.models")}</span>
              <span className="v">{modelCount}</span>
            </div>
            {freeCount > 0 && (
              <div className="metric">
                <span className="k">{t("metrics.free")}</span>
                <span className="v">{freeCount}</span>
              </div>
            )}
            <div className="metric">
              <span className="k">{t("metrics.latency")}</span>
              <span className="v sm">{t("metrics.latencyValue")}</span>
            </div>
            <div className="metric hl">
              <span className="k">{t("metrics.start")}</span>
              <span className="v">{signupAmount}</span>
            </div>
          </div>
        </div>

        <LandingDemo
          prompts={{
            coffee: { text: t("demo.prompts.coffee"), kind: "text" },
            lease: { text: t("demo.prompts.lease"), kind: "text" },
            cover: { text: t("demo.prompts.cover"), kind: "image" },
          }}
          chipLabels={{
            coffee: t("demo.chips.coffee"),
            lease: t("demo.chips.lease"),
            cover: t("demo.chips.cover"),
          }}
          sendLabel={t("demo.send")}
          answers={demoAnswers}
          coverImageUrl={COVER_IMAGE}
        />
        <div className="wrap">
          <div className="demo-foot" style={{ marginTop: -1 }}>
            <span>
              <b>{modelCount}</b> {t("demo.foot.models")}
            </span>
            <span>
              <b>{t("metrics.latencyValue")}</b> {t("demo.foot.latency")}
            </span>
            <span>
              <b>{t("demo.foot.noSub")}</b> {t("demo.foot.noSubLabel")}
            </span>
            <span>
              <b>{t("demo.foot.currency")}</b> {t("demo.foot.currencyLabel")}
            </span>
          </div>
        </div>
      </section>

      {/* БЕГУЩАЯ СТРОКА */}
      <div className="marquee">
        <div className="marquee-track">
          {marqueeLine.map((m, i) => (
            <span key={i} className={`mq${i % 4 === 1 ? " on" : ""}`}>
              <i />
              {m}
            </span>
          ))}
        </div>
      </div>

      {/* МОДЕЛИ */}
      <section className="sec" id="models">
        <div className="wrap">
          <div className="eyebrow">
            <b>I</b> — {t("models.eyebrow")}
          </div>
          <h2 className="sec-title">{t("models.title")}</h2>
          <p className="sec-sub">{t("models.subtitle")}</p>

          <div style={{ marginTop: 52 }}>
            {/* SORA 2 */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.sora.badge")}</div>
                <h3>{t("models.sora.name")}</h3>
                <div className="kind">{t("models.sora.kind")}</div>
                <p className="desc">{t("models.sora.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.sora.factDuration")} value={t("models.sora.factDurationVal")} />
                  <Fact label={t("models.sora.factRes")} value={t("models.sora.factResVal")} />
                  <Fact label={t("models.sora.factSound")} value={t("models.sora.factSoundVal")} />
                  <Fact
                    label={t("models.sora.factPrice")}
                    value={`${formatMoney(PRICES.sora)} ${t("models.sora.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.sora.try")} →
                </a>
              </div>
              <div>
                <LandingVideo src="/landing-media/sora-2.mp4" tag={t("models.requestLabel")} />
                <MediaCaption label={t("models.requestLabel")} text={t("models.sora.query")} />
              </div>
            </article>

            {/* VEO 3.1 FAST */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.veo.badge")}</div>
                <h3>{t("models.veo.name")}</h3>
                <div className="kind">{t("models.veo.kind")}</div>
                <p className="desc">{t("models.veo.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.veo.factDuration")} value={t("models.veo.factDurationVal")} />
                  <Fact label={t("models.veo.factRes")} value={t("models.veo.factResVal")} />
                  <Fact label={t("models.veo.factSound")} value={t("models.veo.factSoundVal")} />
                  <Fact
                    label={t("models.veo.factPrice")}
                    value={`${formatMoney(PRICES.veo)} ${t("models.veo.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.veo.try")} →
                </a>
              </div>
              <div>
                <LandingVideo src="/landing-media/veo-3-1-fast.mp4" tag={t("models.requestLabel")} />
                <MediaCaption label={t("models.requestLabel")} text={t("models.veo.query")} />
              </div>
            </article>

            {/* KLING V2.6 */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.kling.badge")}</div>
                <h3>{t("models.kling.name")}</h3>
                <div className="kind">{t("models.kling.kind")}</div>
                <p className="desc">{t("models.kling.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.kling.factDuration")} value={t("models.kling.factDurationVal")} />
                  <Fact label={t("models.kling.factRes")} value={t("models.kling.factResVal")} />
                  <Fact label={t("models.kling.factSound")} value={t("models.kling.factSoundVal")} />
                  <Fact
                    label={t("models.kling.factPrice")}
                    value={`${formatMoney(PRICES.kling)} ${t("models.kling.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.kling.try")} →
                </a>
              </div>
              <div>
                <LandingVideo src="/landing-media/kling-v2-6.mp4" tag={t("models.requestLabel")} />
                <MediaCaption label={t("models.requestLabel")} text={t("models.kling.query")} />
              </div>
            </article>

            {/* FLUX 2 PRO */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.flux.badge")}</div>
                <h3>{t("models.flux.name")}</h3>
                <div className="kind">{t("models.flux.kind")}</div>
                <p className="desc">{t("models.flux.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.flux.factSize")} value={t("models.flux.factSizeVal")} />
                  <Fact label={t("models.flux.factStyle")} value={t("models.flux.factStyleVal")} />
                  <Fact label={t("models.flux.factSpeed")} value={t("models.flux.factSpeedVal")} />
                  <Fact
                    label={t("models.flux.factPrice")}
                    value={`${formatMoney(PRICES.flux)} ${t("models.flux.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.flux.try")} →
                </a>
              </div>
              <div className="grid-3">
                <Shot src="/landing-media/flux-1.png" caption={t("models.requestLabel") + " 1"} text={t("models.flux.query1")} />
                <Shot src="/landing-media/flux-2.png" caption={t("models.requestLabel") + " 2"} text={t("models.flux.query2")} />
                <Shot src="/landing-media/flux-3.png" caption={t("models.requestLabel") + " 3"} text={t("models.flux.query3")} />
              </div>
            </article>

            {/* GPT IMAGE 1 */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.gptimage.badge")}</div>
                <h3>{t("models.gptimage.name")}</h3>
                <div className="kind">{t("models.gptimage.kind")}</div>
                <p className="desc">{t("models.gptimage.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.gptimage.factSize")} value={t("models.gptimage.factSizeVal")} />
                  <Fact label={t("models.gptimage.factText")} value={t("models.gptimage.factTextVal")} />
                  <Fact label={t("models.gptimage.factSpeed")} value={t("models.gptimage.factSpeedVal")} />
                  <Fact
                    label={t("models.gptimage.factPrice")}
                    value={`${formatMoney(PRICES.gptImage)} ${t("models.gptimage.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.gptimage.try")} →
                </a>
              </div>
              <div className="grid-3">
                <Shot src="/landing-media/gptimg-1.png" caption={t("models.requestLabel") + " 1"} text={t("models.gptimage.query1")} />
                <Shot src="/landing-media/gptimg-2.png" caption={t("models.requestLabel") + " 2"} text={t("models.gptimage.query2")} />
                <Shot src="/landing-media/gptimg-3.png" caption={t("models.requestLabel") + " 3"} text={t("models.gptimage.query3")} />
              </div>
            </article>

            {/* NANO BANANA */}
            <article className="model">
              <div>
                <div className="model-badge">{t("models.nanobanana.badge")}</div>
                <h3>{t("models.nanobanana.name")}</h3>
                <div className="kind">{t("models.nanobanana.kind")}</div>
                <p className="desc">{t("models.nanobanana.desc")}</p>
                <div className="model-facts">
                  <Fact label={t("models.nanobanana.factEdit")} value={t("models.nanobanana.factEditVal")} />
                  <Fact label={t("models.nanobanana.factFace")} value={t("models.nanobanana.factFaceVal")} />
                  <Fact label={t("models.nanobanana.factSpeed")} value={t("models.nanobanana.factSpeedVal")} />
                  <Fact
                    label={t("models.nanobanana.factPrice")}
                    value={`${formatMoney(PRICES.nanoBanana)} ${t("models.nanobanana.factPriceUnit")}`}
                    coral
                  />
                </div>
                <a href="#final" className="btn btn-ghost btn-sm">
                  {t("models.nanobanana.try")} →
                </a>
              </div>
              <div className="grid-2">
                <Pair
                  before="/landing-media/nb-1-before.png"
                  after="/landing-media/nb-1-after.png"
                  caption={t("models.requestLabel") + " 1"}
                  text={t("models.nanobanana.query1")}
                />
                <Pair
                  before="/landing-media/nb-2-before.png"
                  after="/landing-media/nb-2-after.png"
                  caption={t("models.requestLabel") + " 2"}
                  text={t("models.nanobanana.query2")}
                />
              </div>
            </article>
          </div>
        </div>
      </section>

      {/* ВОЗМОЖНОСТИ */}
      <section className="sec" id="features">
        <div className="wrap">
          <div className="eyebrow">
            <b>II</b> — {t("features.eyebrow")}
          </div>
          <h2 className="sec-title">{t("features.title")}</h2>
          <p className="sec-sub">{t("features.subtitle")}</p>
          <div className="feat-grid">
            {(t.raw("features.items") as { title: string; text: string }[]).map((f, i) => (
              <div className="feat" key={i}>
                <span className="feat-n mono">{String(i + 1).padStart(2, "0")}</span>
                <h4>{f.title}</h4>
                <p>{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* СРАВНЕНИЕ */}
      <section
        className="sec"
        id="compare"
        style={{ background: "var(--bg-2)", borderTop: "1px solid var(--line)", borderBottom: "1px solid var(--line)" }}
      >
        <div className="wrap">
          <div className="eyebrow">
            <b>III</b> — {t("compare.eyebrow")}
          </div>
          <h2 className="sec-title">{t("compare.title")}</h2>
          <p className="sec-sub">{t("compare.subtitle")}</p>
          <div className="table">
            <div className="trow thead">
              <div>{t("compare.colFeature")}</div>
              <div className="cell us">{t("compare.colUs")}</div>
              <div className="cell">{t("compare.colChatgpt")}</div>
              <div className="cell">{t("compare.colGemini")}</div>
            </div>
            {compareRows.map((row, i) => (
              <div className="trow" key={i}>
                <div>{row}</div>
                <Mark v={COMPARE_MARKS[i]?.[0]} />
                <Mark v={COMPARE_MARKS[i]?.[1]} />
                <Mark v={COMPARE_MARKS[i]?.[2]} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ЭКОНОМИЯ */}
      <section className="sec" id="save">
        <div className="wrap">
          <div className="eyebrow">
            <b>IV</b> — {t("save.eyebrow")}
          </div>
          <h2 className="sec-title">{t("save.title")}</h2>
          <p className="sec-sub">{t("save.subtitle")}</p>
          <div className="save">
            <div className="save-card">
              <h4>{t("save.otherTitle")}</h4>
              {otherRows.map((r, i) => (
                <div className="srow" key={i}>
                  <span>{r.label}</span>
                  <b>{r.value}</b>
                </div>
              ))}
              <div className="stotal">
                <span>{t("save.otherTotalLabel")}</span>
                <b>{t("save.otherTotalValue")}</b>
              </div>
            </div>
            <div className="save-card win">
              <h4>{t("save.usTitle")}</h4>
              {usRows.map((r, i) => (
                <div className="srow" key={i}>
                  <span>{r.label}</span>
                  <b>{r.value}</b>
                </div>
              ))}
              <div className="stotal">
                <span>{t("save.usTotalLabel")}</span>
                <b className="c">{t("save.usTotalValue", { amount: formatMoney(PRICES.signupBonus) })}</b>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="sec" id="faq" style={{ background: "var(--bg-2)", borderTop: "1px solid var(--line)" }}>
        <div className="wrap">
          <div className="eyebrow">
            <b>V</b> — {t("nav.faq")}
          </div>
          <h2 className="sec-title">{t("faqTitle")}</h2>
          <LandingFaq items={faqItems} />
        </div>
      </section>

      {/* ФИНАЛ */}
      <section className="final" id="final">
        <div className="final-glow" />
        <div className="wrap final-inner">
          <h2>{t("final.title")}</h2>
          <p>{t("final.subtitle", { amount: signupAmount })}</p>
          <div className="final-btns">
            <Link href="/register" className="btn btn-primary">
              {t("final.ctaPrimary")} →
            </Link>
            <a href="#compare" className="btn btn-ghost">
              {t("final.ctaGhost")}
            </a>
          </div>
          <small>{t("final.disclaimer")}</small>
        </div>
      </section>

      <footer>
        <div className="wrap">
          <div className="f-grid">
            <div>
              <Link href="/" className="logo">
                <i />
                Aineron
              </Link>
              <p className="f-about">{t("footer.about", { count: modelCount })}</p>
            </div>
            <div className="f-col">
              <h5>{t("footer.serviceTitle")}</h5>
              <Link href="/models">{t("footer.catalog")}</Link>
              <Link href="/compare">{t("footer.compare")}</Link>
              <Link href="/personas">{t("footer.personas")}</Link>
              <Link href="/prompts">{t("footer.prompts")}</Link>
              <Link href="/account/billing">{t("footer.pricing")}</Link>
              <Link href="/gallery">{t("footer.gallery")}</Link>
            </div>
            <div className="f-col">
              <h5>{t("footer.devTitle")}</h5>
              <Link href="/api-docs">{t("footer.api")}</Link>
              <Link href="/docs">{t("footer.docs")}</Link>
              <Link href="/api-docs/playground">{t("footer.playground")}</Link>
            </div>
            <div className="f-col">
              <h5>{t("footer.connectTitle")}</h5>
              <Link href="/blog">{t("footer.blog")}</Link>
              <a href="mailto:support@aineron.ru">{t("footer.support")}</a>
              <a href="https://t.me/aineron_bot" target="_blank" rel="noopener">
                {t("footer.telegram")}
              </a>
              <Link href="/terms">{t("footer.terms")}</Link>
              <Link href="/privacy-policy">{t("footer.privacy")}</Link>
            </div>
          </div>
          <div className="f-bottom">
            <p>{t("footer.legal", { year })}</p>
            <span className="f-tag">{t("footer.tag")}</span>
          </div>
        </div>
      </footer>

      <div className="dock">
        <div className="dock-note">
          <b>{signupAmount}</b>
          {t("dock.note")}
        </div>
        <a href="#final" className="btn btn-primary">
          {t("dock.cta")} →
        </a>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function Fact({ label, value, coral }: { label: string; value: string; coral?: boolean }) {
  return (
    <div className="fact">
      <span>{label}</span>
      <b className={coral ? "c" : undefined}>{value}</b>
    </div>
  );
}

function MediaCaption({ label, text }: { label: string; text: string }) {
  return (
    <div className="media-caption">
      <div className="pr">
        <b>{label}</b>
        <span className="mono">{text}</span>
      </div>
    </div>
  );
}

function Shot({ src, caption, text }: { src: string; caption: string; text: string }) {
  return (
    <div>
      <div className="shot">
        <Image src={src} alt={text} width={600} height={800} sizes="(max-width: 640px) 33vw, 200px" />
      </div>
      <MediaCaption label={caption} text={text} />
    </div>
  );
}

function Pair({ before, after, caption, text }: { before: string; after: string; caption: string; text: string }) {
  return (
    <div>
      <div className="pair">
        <div className="shot wide">
          <Image src={before} alt="" width={600} height={300} sizes="(max-width: 640px) 100vw, 300px" />
        </div>
        <div className="arrow">
          <ArrowDown size={16} />
        </div>
        <div className="shot wide">
          <Image src={after} alt={text} width={600} height={300} sizes="(max-width: 640px) 100vw, 300px" />
        </div>
      </div>
      <MediaCaption label={caption} text={text} />
    </div>
  );
}

function Mark({ v }: { v?: boolean }) {
  return (
    <div className={`cell ${v ? "yes" : "no"}`}>
      {v ? <Check size={15} style={{ display: "inline" }} /> : <X size={14} style={{ display: "inline" }} />}
    </div>
  );
}
