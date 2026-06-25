'use client';

import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Loader2, RefreshCw, XCircle } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

type E2BState = 'idle' | 'starting' | 'running' | 'failed' | 'expired';

interface Props {
  projectId: string;
  refreshKey: number;
}

export function E2BPreview({ projectId, refreshKey }: Props) {
  const [state, setState] = useState<E2BState>('idle');
  const [publicUrl, setPublicUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const stopSession = async (sid: string) => {
    try {
      await studioApi.e2bPreviewStop(projectId, sid);
    } catch { /* best-effort */ }
  };

  const startPreview = async () => {
    clearPoll();
    if (sessionRef.current) {
      stopSession(sessionRef.current);
      sessionRef.current = null;
    }

    setState('starting');
    setError(null);
    setPublicUrl(null);

    try {
      const resp = await studioApi.e2bPreviewStart(projectId);
      sessionRef.current = resp.session_id;
      setPublicUrl(resp.public_url);

      if (resp.state === 'running') {
        setState('running');
        return;
      }

      // Poll for RUNNING state
      pollTimerRef.current = setInterval(async () => {
        if (!sessionRef.current) return;
        try {
          const status = await studioApi.e2bPreviewStatus(projectId, sessionRef.current);
          if (status.state === 'running') {
            setState('running');
            clearPoll();
          } else if (status.state === 'failed' || status.state === 'expired' || status.state === 'stopped') {
            setState(status.state as E2BState);
            clearPoll();
          }
        } catch { /* keep polling */ }
      }, 5000);
    } catch (err: unknown) {
      setState('failed');
      setError(err instanceof Error ? err.message : 'Ошибка запуска E2B');
    }
  };

  // Auto-start when mounted or refreshKey changes
  useEffect(() => {
    startPreview();
    return () => {
      clearPoll();
      if (sessionRef.current) {
        stopSession(sessionRef.current);
        sessionRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, refreshKey]);

  if (state === 'idle' || state === 'starting') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <Loader2 size={36} className="animate-spin text-blue-500" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">
            {state === 'starting' ? 'Запускаю E2B sandbox…' : 'Инициализация…'}
          </p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">npm install + next dev — 30–60 с</p>
        </div>
      </div>
    );
  }

  if (state === 'failed' || state === 'expired') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <XCircle size={36} className="text-red-400" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">
            {state === 'expired' ? 'Сессия истекла' : 'Не удалось запустить превью'}
          </p>
          {error && <p className="text-xs text-red-400 mt-1 max-w-xs">{error}</p>}
        </div>
        <button
          onClick={startPreview}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
        >
          <RefreshCw size={14} />
          Попробовать снова
        </button>
      </div>
    );
  }

  // RUNNING — show iframe
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] shrink-0">
        <button
          onClick={startPreview}
          title="Перезапустить E2B sandbox"
          className="hover:text-blue-500 transition-colors"
        >
          <RefreshCw size={16} />
        </button>
        {publicUrl && (
          <a
            href={publicUrl}
            target="_blank"
            rel="noreferrer"
            title="Открыть в новой вкладке"
            className="hover:text-blue-500 transition-colors"
          >
            <ExternalLink size={16} />
          </a>
        )}
        <span className="text-xs text-[var(--text-secondary)] font-mono truncate">
          e2b {publicUrl ? `· ${new URL(publicUrl).hostname}` : ''}
        </span>
      </div>
      {publicUrl && (
        <div className="flex-1 overflow-hidden">
          <iframe
            src={publicUrl}
            className="w-full h-full border-0 bg-white"
            title="E2B preview"
            allow="cross-origin-isolated"
          />
        </div>
      )}
    </div>
  );
}
