'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { GitBranch, CheckCircle, Clock } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { text } from './styles';

export function StepTimeline({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { data: steps = [] } = useQuery({
    queryKey: ['studio-timeline', projectId],
    queryFn: () => studioApi.timeline(projectId),
    refetchInterval: 5000,
  });

  const branch = async (versionId: number) => {
    const res = await studioApi.branchFrom(projectId, versionId);
    router.push(`/studio/${res.id}/`);
  };

  if (steps.length === 0) {
    return (
      <div className="p-4 text-xs text-[var(--text-secondary)] opacity-60">
        Таймлайн появится после запуска кодинга
      </div>
    );
  }

  return (
    <div className="flex gap-3 overflow-x-auto p-3">
      {steps.map((s) => {
        const done = s.version_id !== null;
        return (
          <div
            key={s.step_index}
            className={`shrink-0 w-60 border rounded-lg p-3 space-y-2 ${
              done ? 'border-green-500/40 bg-green-500/5' : 'border-[var(--border)]'
            }`}
          >
            <div className="flex items-center gap-1.5">
              {done ? (
                <CheckCircle size={12} className="text-green-500 shrink-0" />
              ) : (
                <Clock size={12} className="text-[var(--text-secondary)] shrink-0" />
              )}
              <span className="text-xs font-medium truncate">{s.name}</span>
            </div>
            {s.changed_files.length > 0 && (
              <div className="space-y-0.5">
                <div className={text.mutedLabel}>
                  Файлов: {s.changed_files.length}
                </div>
                {s.changed_files.slice(0, 4).map((f) => (
                  <div key={f} className="text-[13px] font-mono truncate text-[var(--text-secondary)] opacity-70">
                    {f}
                  </div>
                ))}
              </div>
            )}
            {done && s.version_id !== null && (
              <button
                onClick={() => branch(s.version_id!)}
                className="flex items-center gap-1 text-[13px] text-blue-500 hover:underline mt-1"
              >
                <GitBranch size={11} />
                Ветка от этого шага
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
