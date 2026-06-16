'use client';

import { MessageSquare, Cpu, Eye, ChevronRight } from 'lucide-react';

interface StudioHeroProps {
  onStart: () => void;
}

const STEPS = [
  {
    icon: MessageSquare,
    title: 'Опишите идею',
    desc: 'Расскажите, что хотите создать, словами на русском',
  },
  {
    icon: Cpu,
    title: 'Агенты пишут код',
    desc: '7 AI-агентов планируют, кодят и проверяют за вас',
  },
  {
    icon: Eye,
    title: 'Смотрите и публикуйте',
    desc: 'Живое превью, правки по запросу, публикация в один клик',
  },
];

export function StudioHero({ onStart }: StudioHeroProps) {
  return (
    <div className="mb-10">
      <h2 className="text-3xl font-semibold tracking-tight mb-3">
        Создайте сайт или приложение,
        <br />
        просто описав идею
      </h2>
      <p className="text-[var(--text-secondary)] text-base mb-8 max-w-xl">
        Studio — команда AI-агентов, которая проектирует, пишет и проверяет код за вас.
        Без знания программирования. Без VPN. Оплата в рублях.
      </p>
      <div className="grid grid-cols-3 gap-4 mb-8">
        {STEPS.map((step, i) => (
          <div
            key={i}
            className="flex flex-col gap-2 p-4 rounded-lg border border-[var(--border)] bg-[var(--card-bg)]"
          >
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--muted)] font-mono">{i + 1}</span>
              <step.icon size={16} className="text-[var(--text-secondary)]" />
            </div>
            <p className="font-medium text-sm">{step.title}</p>
            <p className="text-xs text-[var(--text-secondary)]">{step.desc}</p>
          </div>
        ))}
      </div>
      <button
        onClick={onStart}
        className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
      >
        Создать проект
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
