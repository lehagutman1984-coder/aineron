'use client';

import { useState } from 'react';
import { AlertTriangle, Play, SkipForward, ArrowRight } from 'lucide-react';
import { AgentLog } from './AgentLog';
import { studioApi } from '@/lib/api/studio';

interface ContextChatProps {
  projectId: string;
  pauseReason: string;
  resumeHint: string;
  onResume: () => void;
}

export function ContextChat({ projectId, pauseReason, resumeHint, onResume }: ContextChatProps) {
  const [hint, setHint] = useState(resumeHint ?? '');
  const [loading, setLoading] = useState(false);

  const resume = async (action: 'continue' | 'with_hint' | 'skip_step') => {
    setLoading(true);
    try {
      await studioApi.resume(projectId, { action, hint: action === 'with_hint' ? hint : undefined });
      onResume();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-start gap-3 p-4 border-b border-[var(--border)] bg-red-950/30 shrink-0">
        <AlertTriangle size={18} className="text-red-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-sm font-medium text-red-400">Пайплайн остановлен</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{pauseReason}</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <AgentLog projectId={projectId} />
      </div>

      <div className="p-4 border-t border-[var(--border)] space-y-3 shrink-0">
        <textarea
          value={hint}
          onChange={(e) => setHint(e.target.value)}
          placeholder="Подсказка для кодера (необязательно)..."
          rows={3}
          className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div className="flex gap-2">
          <button
            onClick={() => resume('with_hint')}
            disabled={loading || !hint.trim()}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <ArrowRight size={14} />
            С подсказкой
          </button>
          <button
            onClick={() => resume('continue')}
            disabled={loading}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <Play size={14} />
            Продолжить
          </button>
          <button
            onClick={() => resume('skip_step')}
            disabled={loading}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-2 rounded-lg text-xs font-medium transition-colors"
          >
            <SkipForward size={14} />
            Пропустить шаг
          </button>
        </div>
      </div>
    </div>
  );
}
