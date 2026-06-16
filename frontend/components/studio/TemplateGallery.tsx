'use client';

import { useQuery } from '@tanstack/react-query';
import { LayoutTemplate, Sparkles, Loader2 } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import type { StudioStack } from '@/lib/api/studio';
import { card, badge } from './styles';

interface TemplateGalleryProps {
  onSelect: (name: string, description: string, stack: StudioStack) => void;
}

const STACK_LABEL: Record<string, string> = {
  nextjs: 'Next.js',
  react: 'React',
  vue: 'Vue',
  html: 'HTML',
};

export function TemplateGallery({ onSelect }: TemplateGalleryProps) {
  const { data: templates, isLoading, error } = useQuery({
    queryKey: ['studio-templates'],
    queryFn: () => studioApi.templates(),
    staleTime: 60 * 1000,
    retry: 1,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-[var(--text-secondary)]">
        <Loader2 size={14} className="animate-spin" />
        Загрузка шаблонов...
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-2 text-xs text-red-400">
        Ошибка загрузки шаблонов: {(error as Error).message}
      </div>
    );
  }

  if (!templates || templates.length === 0) return null;

  return (
    <div>
      <div className="flex items-center gap-2 mb-3 text-sm font-medium text-[var(--text-secondary)]">
        <LayoutTemplate size={14} />
        Начать с шаблона
      </div>
      <div className="grid grid-cols-2 gap-2">
        {templates.map((tpl) => (
          <button
            key={tpl.slug}
            type="button"
            onClick={() => onSelect(tpl.name, tpl.seed_prompt, tpl.stack as StudioStack)}
            className={card.template}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Sparkles size={12} className="text-blue-400 group-hover:text-blue-500 transition-colors" />
              <span className="text-xs font-medium">{tpl.name}</span>
            </div>
            <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{tpl.description}</p>
            <span className={badge.stack}>
              {STACK_LABEL[tpl.stack] ?? tpl.stack}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
