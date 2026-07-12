"use client";

import { useState } from "react";
import { Code2, Megaphone, BookOpen, Palette } from "lucide-react";

const CASES = [
  {
    key: "dev",
    label: "Разработчик",
    icon: Code2,
    heading: "Код, дебаг и архитектура",
    items: [
      "Написать функцию на Python / Go / TypeScript",
      "Найти и исправить баг за секунды",
      "Провести код-ревью и предложить улучшения",
      "Сгенерировать тесты к готовому коду",
      "Подключить API через OpenAI-совместимый эндпоинт",
    ],
    prompt: "Напиши unit-тест для этой функции на Jest:",
  },
  {
    key: "marketer",
    label: "Маркетолог",
    icon: Megaphone,
    heading: "Контент и реклама",
    items: [
      "Тексты для постов ВКонтакте и Telegram",
      "Рекламные объявления под любую ЦА",
      "Email-рассылки с высоким открытием",
      "Анализ конкурентов и SWOT",
      "Изображения для рекламы через Midjourney",
    ],
    prompt: "Придумай 5 заголовков для рекламы фитнес-приложения:",
  },
  {
    key: "student",
    label: "Студент",
    icon: BookOpen,
    heading: "Учёба и исследования",
    items: [
      "Объяснить сложную тему простыми словами",
      "Написать конспект лекции",
      "Помочь с курсовой и дипломной работой",
      "Перевести научную статью",
      "Составить план подготовки к экзамену",
    ],
    prompt: "Объясни квантовую запутанность на примере из жизни:",
  },
  {
    key: "designer",
    label: "Дизайнер",
    icon: Palette,
    heading: "Визуал и идеи",
    items: [
      "Промты для Midjourney и Stable Diffusion",
      "Идеи для логотипов и брендбука",
      "Описание стиля и мудборда",
      "Референсы и инспирация для проекта",
      "Текст для интерфейсов и UX-копирайтинг",
    ],
    prompt: "Напиши промт для Midjourney: минималистичный логотип IT-стартапа:",
  },
] as const;

export function UseCaseTabs() {
  const [active, setActive] = useState<(typeof CASES)[number]["key"]>("dev");
  const current = CASES.find((c) => c.key === active)!;
  const Icon = current.icon;

  return (
    <div>
      {/* Tab buttons */}
      <div className="mb-6 flex gap-1.5 flex-wrap justify-center">
        {CASES.map((c) => {
          const CIcon = c.icon;
          return (
            <button
              key={c.key}
              onClick={() => setActive(c.key)}
              className={[
                "flex items-center gap-1.5 rounded-[9px] px-4 py-2 text-[15px] font-medium transition-all",
                active === c.key
                  ? "bg-[#1A1A1A] text-white"
                  : "border border-[rgba(13,13,13,0.12)] text-[rgba(13,13,13,0.60)] hover:border-[rgba(13,13,13,0.25)] hover:text-[#1A1A1A]",
              ].join(" ")}
            >
              <CIcon size={13} />
              {c.label}
            </button>
          );
        })}
      </div>

      {/* Content card */}
      <div
        className="overflow-hidden rounded-[16px] border bg-white"
        style={{ borderColor: "var(--border-secondary)" }}
      >
        <div className="grid grid-cols-1 md:grid-cols-2">
          {/* Left — feature list */}
          <div className="p-7">
            <div className="mb-4 flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-[9px] bg-[rgba(217,119,87,0.10)]">
                <Icon size={17} className="text-[#D97757]" />
              </div>
              <p className="text-[16px] font-semibold text-[#1A1A1A]">{current.heading}</p>
            </div>
            <ul className="flex flex-col gap-2.5">
              {current.items.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-[16px] text-[rgba(13,13,13,0.70)]">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#D97757]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Right — fake chat demo */}
          <div
            className="flex flex-col justify-between border-s p-7"
            style={{ borderColor: "var(--border-tertiary)", background: "var(--background-tertiary)" }}
          >
            <p className="mb-3 text-[13px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.38)]">
              Пример запроса
            </p>
            <div className="mb-4 rounded-[12px] bg-[rgba(217,119,87,0.07)] px-4 py-3 text-[15px] text-[#1A1A1A]">
              {current.prompt}
            </div>
            <div className="rounded-[12px] border border-[rgba(13,13,13,0.08)] bg-white px-4 py-3">
              <div className="mb-2 flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-[#D97757]" />
                <span className="text-[13px] font-medium text-[rgba(13,13,13,0.50)]">AI отвечает</span>
              </div>
              <div className="space-y-1.5">
                <div className="h-2.5 w-full rounded-full bg-[rgba(13,13,13,0.08)]" />
                <div className="h-2.5 w-4/5 rounded-full bg-[rgba(13,13,13,0.06)]" />
                <div className="h-2.5 w-3/5 rounded-full bg-[rgba(13,13,13,0.05)]" />
              </div>
            </div>
            <a
              href="/register/"
              className="mt-5 flex items-center justify-center gap-1.5 rounded-[9px] bg-[#D97757] px-4 py-2.5 text-[15px] font-medium text-white transition-colors hover:bg-[#C4623E]"
            >
              Попробовать
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
