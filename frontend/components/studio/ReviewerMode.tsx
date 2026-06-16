'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface ReviewerModeProps {
  projectId: string;
  stepIndex: number;
  plannedText: string;
}

const SEVERITY_STYLE = {
  high: 'border-red-500/40 bg-red-500/5 text-red-400',
  medium: 'border-amber-500/40 bg-amber-500/5 text-amber-400',
  low: 'border-[var(--border)] text-[var(--text-secondary)]',
};

export function ReviewerMode({ projectId, stepIndex, plannedText }: ReviewerModeProps) {
  const [enabled, setEnabled] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['studio-deviation', projectId, stepIndex],
    queryFn: () => studioApi.deviation(projectId, stepIndex),
    enabled,
    staleTime: 60_000,
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <h3 className="font-medium text-xs">Режим ревьюера</h3>
        {!enabled && (
          <button
            onClick={() => setEnabled(true)}
            className="text-xs text-blue-500 hover:underline"
          >
            Проверить отклонения
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {/* Left: planned */}
        <div>
          <div className="text-[11px] text-[var(--text-secondary)] font-medium mb-1">Плановый шаг</div>
          <pre className="whitespace-pre-wrap font-mono text-[11px] bg-[var(--hover)] rounded p-2 max-h-48 overflow-auto">
            {plannedText || '—'}
          </pre>
        </div>

        {/* Right: deviations */}
        <div>
          <div className="text-[11px] text-[var(--text-secondary)] font-medium mb-1">Отклонения</div>
          {!enabled && (
            <div className="flex items-center justify-center h-20 text-[11px] text-[var(--text-secondary)] opacity-60">
              Нажмите «Проверить отклонения»
            </div>
          )}
          {enabled && isLoading && (
            <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-secondary)] p-2">
              <Loader2 size={12} className="animate-spin" /> Анализирую…
            </div>
          )}
          {enabled && error && (
            <div className="text-[11px] text-red-400 p-2">Ошибка анализа</div>
          )}
          {data && (
            <div className="space-y-1.5 max-h-48 overflow-auto">
              {data.matched.length > 0 && (
                <div className="flex items-center gap-1 text-[11px] text-green-500 py-1">
                  <CheckCircle size={11} /> {data.matched.length} пунктов выполнено
                </div>
              )}
              {data.deviations.length === 0 && (
                <div className="text-[11px] text-green-500">Отклонений не найдено</div>
              )}
              {data.deviations.map((d, i) => (
                <div
                  key={i}
                  className={`border rounded p-2 text-[11px] space-y-0.5 ${SEVERITY_STYLE[d.severity]}`}
                >
                  <div className="flex items-center gap-1 font-medium">
                    <AlertTriangle size={10} />
                    {d.severity === 'high' ? 'Критично' : d.severity === 'medium' ? 'Важно' : 'Незначительно'}
                  </div>
                  <div className="opacity-80">Ожидалось: {d.planned}</div>
                  <div className="opacity-80">Реализовано: {d.actual}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
