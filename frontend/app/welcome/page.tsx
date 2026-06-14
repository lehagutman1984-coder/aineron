"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Code2, Globe, Pencil, BookOpen, Briefcase, Image,
  ChevronRight, ArrowRight, Check, Star,
} from "lucide-react";

const ONBOARDING_KEY = "onboarding_done";

// ── Interest definitions ───────────────────────────────────────────────────────
const INTERESTS = [
  {
    key: "code",
    label: "Написать код",
    description: "Отладка, рефакторинг, объяснение алгоритмов",
    icon: Code2,
    color: "#0a7cff",
    bg: "rgba(10,124,255,0.08)",
    prompts: [
      "Напиши функцию на Python для валидации email",
      "Объясни разницу между async/await и Promise",
      "Помоги найти баг в этом коде",
    ],
    catalog: "/models/?category=text",
  },
  {
    key: "translate",
    label: "Перевод и текст",
    description: "Переводы, редактирование, рерайт",
    icon: Globe,
    color: "#22a85a",
    bg: "rgba(34,168,90,0.08)",
    prompts: [
      "Переведи этот текст с английского на русский",
      "Сделай этот email более профессиональным",
      "Исправь грамматические ошибки в тексте",
    ],
    catalog: "/models/?category=text",
  },
  {
    key: "creative",
    label: "Творчество",
    description: "Тексты, идеи, контент для соцсетей",
    icon: Pencil,
    color: "#9b59b6",
    bg: "rgba(155,89,182,0.08)",
    prompts: [
      "Придумай 10 идей для поста в Instagram",
      "Напиши короткий рассказ в жанре фантастики",
      "Составь продающее описание для товара",
    ],
    catalog: "/models/?category=text",
  },
  {
    key: "study",
    label: "Учёба",
    description: "Объяснения, конспекты, подготовка",
    icon: BookOpen,
    color: "#e67e22",
    bg: "rgba(230,126,34,0.08)",
    prompts: [
      "Объясни квантовую запутанность простыми словами",
      "Помоги написать план курсовой работы",
      "Составь 10 тестовых вопросов по теме",
    ],
    catalog: "/models/?category=text",
  },
  {
    key: "business",
    label: "Бизнес",
    description: "Анализ, письма, презентации",
    icon: Briefcase,
    color: "#0d9e8c",
    bg: "rgba(13,158,140,0.08)",
    prompts: [
      "Напиши коммерческое предложение для клиента",
      "Проведи SWOT-анализ для стартапа",
      "Составь скрипт для холодного звонка",
    ],
    catalog: "/models/?category=text",
  },
  {
    key: "images",
    label: "Изображения",
    description: "Генерация изображений и арт",
    icon: Image,
    color: "#e74c3c",
    bg: "rgba(231,76,60,0.08)",
    prompts: [
      "Нарисуй портрет в стиле масляной живописи",
      "Создай иллюстрацию для детской книги",
      "Сгенерируй логотип для tech-стартапа",
    ],
    catalog: "/models/?category=image",
  },
] as const;

type InterestKey = (typeof INTERESTS)[number]["key"];

// ── Page ───────────────────────────────────────────────────────────────────────
export default function WelcomePage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [interest, setInterest] = useState<InterestKey | null>(null);
  const [pickedPrompt, setPickedPrompt] = useState<string | null>(null);

  // If already onboarded → skip straight to account
  useEffect(() => {
    if (localStorage.getItem(ONBOARDING_KEY) === "1") {
      router.replace("/account/");
    }
  }, [router]);

  const chosen = INTERESTS.find((i) => i.key === interest);

  const finish = () => {
    localStorage.setItem(ONBOARDING_KEY, "1");
    router.push("/account/");
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#f5f5f7] px-4 py-12">
      {/* Progress */}
      <div className="mb-8 flex items-center gap-2">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={[
                "flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-bold transition-all",
                s < step
                  ? "bg-[#0d0d0d] text-white"
                  : s === step
                  ? "bg-[#0a7cff] text-white"
                  : "bg-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.40)]",
              ].join(" ")}
            >
              {s < step ? <Check size={11} /> : s}
            </div>
            {s < 3 && (
              <div
                className={[
                  "h-[2px] w-8 rounded-full transition-all",
                  s < step ? "bg-[#0d0d0d]" : "bg-[rgba(13,13,13,0.12)]",
                ].join(" ")}
              />
            )}
          </div>
        ))}
      </div>

      {/* Card */}
      <div
        className="w-full max-w-xl rounded-[20px] border bg-white p-8 shadow-sm"
        style={{ borderColor: "rgba(13,13,13,0.10)" }}
      >
        {step === 1 && (
          <Step1
            onSelect={(key) => {
              setInterest(key);
              setStep(2);
            }}
          />
        )}
        {step === 2 && chosen && (
          <Step2
            interest={chosen}
            pickedPrompt={pickedPrompt}
            onPickPrompt={setPickedPrompt}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && chosen && (
          <Step3 interest={chosen} prompt={pickedPrompt} onFinish={finish} />
        )}
      </div>

      {/* Skip */}
      {step < 3 && (
        <button
          onClick={finish}
          className="mt-5 text-[12px] text-[rgba(13,13,13,0.38)] hover:text-[rgba(13,13,13,0.60)] transition-colors"
        >
          Пропустить
        </button>
      )}
    </div>
  );
}

// ── Step 1: Pick interest ──────────────────────────────────────────────────────
function Step1({ onSelect }: { onSelect: (key: InterestKey) => void }) {
  return (
    <>
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-[12px] bg-[rgba(10,124,255,0.08)]">
          <Star size={20} className="text-[#0a7cff]" />
        </div>
        <h1 className="text-[22px] font-bold text-[#0d0d0d]">Добро пожаловать!</h1>
        <p className="mt-1 text-[14px] text-[rgba(13,13,13,0.52)]">
          Для чего вы планируете использовать AI?
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
        {INTERESTS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              className="group flex flex-col items-start rounded-[12px] border border-[rgba(13,13,13,0.10)] p-3.5 text-left transition-all hover:border-[rgba(13,13,13,0.22)] hover:shadow-[0_2px_10px_rgba(0,0,0,0.07)]"
            >
              <div
                className="mb-2.5 flex h-9 w-9 items-center justify-center rounded-[9px]"
                style={{ background: item.bg }}
              >
                <Icon size={17} style={{ color: item.color }} />
              </div>
              <p className="text-[13px] font-semibold text-[#0d0d0d]">{item.label}</p>
              <p className="mt-0.5 text-[11px] leading-snug text-[rgba(13,13,13,0.45)]">
                {item.description}
              </p>
            </button>
          );
        })}
      </div>
    </>
  );
}

// ── Step 2: Sample prompts ─────────────────────────────────────────────────────
function Step2({
  interest,
  pickedPrompt,
  onPickPrompt,
  onBack,
  onNext,
}: {
  interest: (typeof INTERESTS)[number];
  pickedPrompt: string | null;
  onPickPrompt: (p: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const Icon = interest.icon;
  return (
    <>
      <button
        onClick={onBack}
        className="mb-4 flex items-center gap-1 text-[12px] text-[rgba(13,13,13,0.45)] hover:text-[#0d0d0d] transition-colors"
      >
        <ChevronRight size={12} className="rotate-180" />
        Назад
      </button>

      <div className="mb-5 flex items-center gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px]"
          style={{ background: interest.bg }}
        >
          <Icon size={18} style={{ color: interest.color }} />
        </div>
        <div>
          <h2 className="text-[17px] font-bold text-[#0d0d0d]">{interest.label}</h2>
          <p className="text-[13px] text-[rgba(13,13,13,0.50)]">Выберите пример или откройте каталог</p>
        </div>
      </div>

      <div className="mb-5 flex flex-col gap-2">
        {interest.prompts.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onPickPrompt(prompt)}
            className={[
              "flex items-center gap-3 rounded-[10px] border px-4 py-3 text-left text-[13px] transition-all",
              pickedPrompt === prompt
                ? "border-[#0a7cff] bg-[rgba(10,124,255,0.06)] text-[#0d0d0d]"
                : "border-[rgba(13,13,13,0.10)] text-[rgba(13,13,13,0.70)] hover:border-[rgba(13,13,13,0.20)] hover:text-[#0d0d0d]",
            ].join(" ")}
          >
            <div
              className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-all"
              style={{
                borderColor: pickedPrompt === prompt ? "#0a7cff" : "rgba(13,13,13,0.18)",
                background: pickedPrompt === prompt ? "#0a7cff" : "transparent",
              }}
            >
              {pickedPrompt === prompt && <Check size={10} className="text-white" />}
            </div>
            {prompt}
          </button>
        ))}
      </div>

      <div className="flex gap-2">
        <Link
          href={interest.catalog}
          className="flex-1 rounded-[10px] border border-[rgba(13,13,13,0.12)] py-2.5 text-center text-[13px] font-medium text-[rgba(13,13,13,0.60)] transition-colors hover:border-[rgba(13,13,13,0.22)] hover:text-[#0d0d0d]"
          onClick={() => localStorage.setItem(ONBOARDING_KEY, "1")}
        >
          Открыть каталог
        </Link>
        <button
          onClick={onNext}
          className="flex flex-1 items-center justify-center gap-1.5 rounded-[10px] bg-[#0a7cff] py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-[#0066cc]"
        >
          Продолжить
          <ArrowRight size={14} />
        </button>
      </div>
    </>
  );
}

// ── Step 3: What's next ────────────────────────────────────────────────────────
function Step3({
  interest,
  prompt,
  onFinish,
}: {
  interest: (typeof INTERESTS)[number];
  prompt: string | null;
  onFinish: () => void;
}) {
  return (
    <>
      <div className="mb-6 text-center">
        <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[rgba(34,168,90,0.10)]">
          <Check size={22} className="text-[#22a85a]" />
        </div>
        <h2 className="text-[20px] font-bold text-[#0d0d0d]">Всё готово!</h2>
        <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.50)]">
          На вашем балансе уже есть звёзды для первых запросов
        </p>
      </div>

      {/* Chosen prompt card */}
      {prompt && (
        <Link
          href={`${interest.catalog}`}
          onClick={() => localStorage.setItem(ONBOARDING_KEY, "1")}
          className="mb-4 flex items-start gap-3 rounded-[12px] border border-[#0a7cff] bg-[rgba(10,124,255,0.05)] p-4 text-[13px] transition-all hover:bg-[rgba(10,124,255,0.08)]"
        >
          <div className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0a7cff]" />
          <div>
            <p className="mb-0.5 text-[11px] font-medium uppercase tracking-wide text-[#0a7cff]">
              Ваш первый запрос
            </p>
            <p className="text-[#0d0d0d]">{prompt}</p>
          </div>
          <ArrowRight size={14} className="ml-auto mt-0.5 shrink-0 text-[#0a7cff]" />
        </Link>
      )}

      {/* Quick links */}
      <div className="mb-6 flex flex-col gap-2">
        {[
          {
            href: "/models/",
            label: "Каталог нейросетей",
            sub: "200+ моделей на любую задачу",
          },
          {
            href: "/compare/",
            label: "Сравнение моделей",
            sub: "Отправьте запрос в несколько моделей сразу",
          },
          {
            href: "/account/billing/",
            label: "Пополнить баланс",
            sub: "Купите больше звёзд или оформите подписку",
          },
        ].map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => localStorage.setItem(ONBOARDING_KEY, "1")}
            className="flex items-center gap-3 rounded-[10px] border border-[rgba(13,13,13,0.10)] px-4 py-3 transition-all hover:border-[rgba(13,13,13,0.20)] hover:shadow-[0_1px_8px_rgba(0,0,0,0.06)]"
          >
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-medium text-[#0d0d0d]">{item.label}</p>
              <p className="text-[11px] text-[rgba(13,13,13,0.45)]">{item.sub}</p>
            </div>
            <ChevronRight size={14} className="shrink-0 text-[rgba(13,13,13,0.30)]" />
          </Link>
        ))}
      </div>

      <button
        onClick={onFinish}
        className="w-full rounded-[10px] bg-[#0d0d0d] py-2.5 text-[14px] font-medium text-white transition-colors hover:bg-[rgba(13,13,13,0.85)]"
      >
        Перейти в личный кабинет
      </button>
    </>
  );
}
