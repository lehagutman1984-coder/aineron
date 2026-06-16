'use client';

import { useState } from 'react';
import { AlertCircle, RefreshCw, SkipForward } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface PipelineRecoveryProps {
  projectId: string;
  reason: string;
  recoveryType: 'loop' | 'same_diff' | 'failed' | 'no_funds' | 'manual';
  onResume: () => void;
}

export function PipelineRecovery({
  projectId,
  reason,
  recoveryType,
  onResume,
}: PipelineRecoveryProps) {
  const [hint, setHint] = useState('');
  const [loading, setLoading] = useState<string | null>(null);

  const handleResume = async (action: 'continue' | 'skip_step' | 'with_hint') => {
    setLoading(action);
    try {
      if (action === 'skip_step') {
        await studioApi.skipStep(projectId);
      } else {
        await studioApi.resumePipeline(projectId, {
          action,
          hint: action === 'with_hint' ? hint : undefined,
        });
      }
      onResume();
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-lg border border-[var(--danger)] bg-[var(--card-bg)] p-4 space-y-3">
      <div className="flex items-start gap-2">
        <AlertCircle size={16} className="text-[var(--danger)] mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-medium">Генерация приостановлена</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{reason}</p>
        </div>
      </div>

      {recoveryType === 'same_diff' && (
        <textarea
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          placeholder="Опишите, что именно должно измениться..."
          rows={3}
          className="w-full text-sm rounded border border-[var(--border)] bg-[var(--bg)] p-2 resize-none"
        />
      )}

      <div className="flex gap-2">
        <button
          onClick={() =>
            handleResume(
              recoveryType === 'same_diff' && hint ? 'with_hint' : 'continue',
            )
          }
          disabled={!!loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading === 'continue' ? 'animate-spin' : ''} />
          Попробовать снова
        </button>
        <button
          onClick={() => handleResume('skip_step')}
          disabled={!!loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm border border-[var(--border)] hover:bg-[var(--hover)] disabled:opacity-50"
        >
          <SkipForward size={14} />
          Пропустить шаг
        </button>
      </div>
    </div>
  );
}
