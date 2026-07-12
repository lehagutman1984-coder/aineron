'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { History, RotateCcw, GitBranch, Loader2 } from 'lucide-react';
import { studioApi, StudioVersion } from '@/lib/api/studio';
import { card, btn } from './styles';

interface GitHistoryProps {
  projectId: string;
}

export function GitHistory({ projectId }: GitHistoryProps) {
  const queryClient = useQueryClient();
  const [confirmId, setConfirmId] = useState<number | null>(null);

  const { data: versions = [], isLoading } = useQuery({
    queryKey: ['studio-commits', projectId],
    queryFn: () => studioApi.commits(projectId),
    refetchInterval: 10000,
  });

  const rollbackMutation = useMutation({
    mutationFn: (versionId: number) => studioApi.rollback(projectId, versionId),
    onSuccess: () => {
      setConfirmId(null);
      queryClient.invalidateQueries({ queryKey: ['studio-files', projectId] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-[var(--text-secondary)]">
        <Loader2 size={14} className="animate-spin" />
        Загрузка истории...
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="p-4 text-sm text-[var(--text-secondary)]">
        <GitBranch size={14} className="inline me-1" />
        Коммиты появятся после завершения шагов
      </div>
    );
  }

  return (
    <div className="p-3 space-y-2">
      <div className="flex items-center gap-2 mb-3 text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
        <History size={12} />
        История версий
      </div>
      {versions.map((v) => (
        <div
          key={v.id}
          className={card.historyItem}
        >
          <div className="min-w-0">
            <div className="font-medium truncate">{v.step_name}</div>
            <div className="text-[var(--text-secondary)] mt-0.5 flex items-center gap-2">
              {v.git_sha ? (
                <span className="font-mono">{v.git_sha.slice(0, 7)}</span>
              ) : (
                <span className="opacity-40">нет sha</span>
              )}
              <span>{v.stars_spent_at_version} ₽</span>
            </div>
          </div>
          {confirmId === v.id ? (
            <div className="flex items-center gap-1 ms-2 shrink-0">
              <button
                onClick={() => rollbackMutation.mutate(v.id)}
                disabled={rollbackMutation.isPending}
                className={btn.redSm}
              >
                {rollbackMutation.isPending ? <Loader2 size={10} className="animate-spin" /> : 'Да'}
              </button>
              <button
                onClick={() => setConfirmId(null)}
                className="px-2 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
              >
                Нет
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmId(v.id)}
              title="Откатиться к этой версии"
              className="ms-2 shrink-0 p-1 text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
            >
              <RotateCcw size={14} />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
