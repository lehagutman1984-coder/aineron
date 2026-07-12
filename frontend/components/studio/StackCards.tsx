'use client';

import { FileCode, Atom, Layers, Boxes } from 'lucide-react';

interface StackCardsProps {
  selected: string;
  onSelect: (stack: string) => void;
}

const STACKS = [
  {
    value: 'html',
    icon: FileCode,
    label: 'HTML',
    subtitle: 'Лендинги, промо, визитки',
    pros: ['Мгновенное превью', 'Не нужен Node.js', 'Max совместимость'],
    previewNote: 'Превью открывается сразу из файлов',
  },
  {
    value: 'react',
    icon: Atom,
    label: 'React',
    subtitle: 'SPA, дашборды, формы',
    pros: ['Богатые UI-компоненты', 'Hooks', 'Огромная экосистема'],
    previewNote: 'Первый запуск ~2-3 мин (установка зависимостей)',
  },
  {
    value: 'vue',
    icon: Layers,
    label: 'Vue',
    subtitle: 'Средние SPA',
    pros: ['Проще синтаксис', 'Плавный старт'],
    previewNote: 'Первый запуск ~2-3 мин (установка зависимостей)',
  },
  {
    value: 'nextjs',
    icon: Boxes,
    label: 'Next.js',
    subtitle: 'Полноценные приложения',
    pros: ['SEO из коробки', 'API routes', 'Деплой на Vercel'],
    previewNote: 'Первый запуск ~3-5 мин',
  },
];

export function StackCards({ selected, onSelect }: StackCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {STACKS.map((s) => (
        <button
          key={s.value}
          type="button"
          onClick={() => onSelect(s.value)}
          className={`text-start p-3 rounded-lg border transition-colors ${
            selected === s.value
              ? 'border-blue-500 bg-blue-600/10'
              : 'border-[var(--border)] hover:border-[var(--text-secondary)]'
          }`}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <s.icon
              size={14}
              className={selected === s.value ? 'text-blue-400' : 'text-[var(--text-secondary)]'}
            />
            <span className="font-medium text-sm">{s.label}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mb-1.5">{s.subtitle}</p>
          <ul className="space-y-0.5 mb-1.5">
            {s.pros.map((p) => (
              <li key={p} className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
                <span className="text-[var(--success)]">+</span> {p}
              </li>
            ))}
          </ul>
          <p className="text-xs text-[var(--muted)]">{s.previewNote}</p>
        </button>
      ))}
    </div>
  );
}
