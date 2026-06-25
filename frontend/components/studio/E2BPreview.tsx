'use client';

import { useEffect, useRef, useState } from 'react';
import { Coins, ExternalLink, Loader2, RefreshCw, StopCircle, Terminal, XCircle } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { SessionTimer } from './SessionTimer';

type E2BState = 'idle' | 'starting' | 'running' | 'failed' | 'expired';

const STACK_LABELS: Record<string, string> = {
  nextjs: 'next.js',
  python: 'python',
  django: 'django',
};

interface Props {
  projectId: string;
  refreshKey: number;
  stack?: string;
}

export function E2BPreview({ projectId, refreshKey, stack }: Props) {
  const [state, setState] = useState<E2BState>('idle');
  const [publicUrl, setPublicUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number>(0);
  const [startedAt, setStartedAt] = useState<number>(0);
  const [starsPerMin, setStarsPerMin] = useState<number>(1);
  const [elapsedMin, setElapsedMin] = useState<number>(0);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const sessionRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const costTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  const clearPoll = () => {
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    if (costTimerRef.current) { clearInterval(costTimerRef.current); costTimerRef.current = null; }
  };

  const stopSession = async (sid: string) => {
    try { await studioApi.e2bPreviewStop(projectId, sid); } catch { /* best-effort */ }
  };

  const fetchLogs = async () => {
    if (!sessionRef.current) return;
    setLogsLoading(true);
    try {
      const data = await studioApi.e2bPreviewLogs(projectId, sessionRef.current);
      setLogs(data.lines ?? []);
      setTimeout(() => logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    } catch { /* ignore */ } finally { setLogsLoading(false); }
  };

  const toggleLogs = () => {
    const next = !showLogs;
    setShowLogs(next);
    if (next) fetchLogs();
  };

  const handleStop = async () => {
    clearPoll();
    const sid = sessionRef.current;
    sessionRef.current = null;
    setState('idle');
    setPublicUrl(null);
    setExpiresAt(0);
    setLogs([]);
    setShowLogs(false);
    if (sid) await stopSession(sid);
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
    setExpiresAt(0);
    setLogs([]);
    setShowLogs(false);

    try {
      const resp = await studioApi.e2bPreviewStart(projectId);
      sessionRef.current = resp.session_id;
      setPublicUrl(resp.public_url);
      setExpiresAt(resp.expires_at ?? 0);
      setStartedAt(resp.started_at ?? Date.now() / 1000);
      setStarsPerMin(resp.stars_per_min ?? 1);

      // Cost elapsed ticker
      costTimerRef.current = setInterval(() => {
        const t0 = resp.started_at ?? Date.now() / 1000;
        setElapsedMin((Date.now() / 1000 - t0) / 60);
      }, 10000);

      if (resp.state === 'running') {
        setState('running');
        return;
      }

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
            // Auto-expand logs on failure
            if (status.state === 'failed') {
              setShowLogs(true);
              fetchLogs();
            }
          }
        } catch { /* keep polling */ }
      }, 5000);
    } catch (err: unknown) {
      setState('failed');
      setError(err instanceof Error ? err.message : 'Ошибка запуска E2B');
      setShowLogs(true);
    }
  };

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
  // refreshKey intentionally excluded: sandbox must NOT restart on every coding step
  }, [projectId]);

  if (state === 'idle' || state === 'starting') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <Loader2 size={36} className="animate-spin text-blue-500" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">
            {state === 'starting' ? 'Запускаю E2B sandbox…' : 'Инициализация…'}
          </p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">npm install + next dev — 1–5 мин (первый запуск)</p>
        </div>
      </div>
    );
  }

  if (state === 'failed' || state === 'expired') {
    return (
      <div className="flex flex-col h-full">
        <div className="flex flex-col items-center justify-center flex-1 gap-4 p-6 text-center">
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
        {showLogs && logs.length > 0 && (
          <div className="border-t border-[var(--border)] bg-[#0d1117] max-h-48 overflow-y-auto">
            <pre className="text-[11px] font-mono text-green-300 p-3 whitespace-pre-wrap break-all leading-relaxed">
              {logs.join('\n')}
            </pre>
          </div>
        )}
      </div>
    );
  }

  const costStars = Math.ceil(elapsedMin * starsPerMin);

  // RUNNING
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

        {/* Stack badge */}
        {stack && STACK_LABELS[stack] && (
          <span className="text-[10px] font-mono px-1.5 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded">
            {STACK_LABELS[stack]}
          </span>
        )}

        <span className="text-xs text-[var(--text-secondary)] font-mono truncate flex-1">
          e2b {publicUrl ? `· ${new URL(publicUrl).hostname}` : ''}
        </span>

        {/* Cost indicator */}
        {costStars > 0 && (
          <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]" title="Потрачено звёзд за сессию">
            <Coins size={11} />
            {costStars}
          </span>
        )}

        {/* Countdown timer */}
        {expiresAt > 0 && (
          <SessionTimer
            expiresAt={expiresAt}
            onExpired={() => setState('expired')}
          />
        )}

        {/* Stop button */}
        <button
          onClick={handleStop}
          title="Остановить сессию и освободить слот"
          className="hover:text-red-400 transition-colors"
        >
          <StopCircle size={16} />
        </button>

        {/* Logs toggle */}
        <button
          onClick={toggleLogs}
          title={showLogs ? 'Скрыть логи' : 'Показать логи'}
          className={`transition-colors ${showLogs ? 'text-blue-400' : 'hover:text-blue-500'}`}
        >
          <Terminal size={16} />
        </button>
      </div>

      {showLogs && (
        <div className="border-b border-[var(--border)] bg-[#0d1117] overflow-y-auto shrink-0" style={{ maxHeight: '40%' }}>
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)]">
            <span className="text-xs text-[var(--text-secondary)]">Логи sandbox (/tmp/preview.log)</span>
            <button
              onClick={fetchLogs}
              className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
              disabled={logsLoading}
            >
              {logsLoading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
              Обновить
            </button>
          </div>
          <pre className="text-[11px] font-mono text-green-300 p-3 whitespace-pre-wrap break-all leading-relaxed">
            {logs.length === 0
              ? (logsLoading ? 'Загрузка…' : 'Логи недоступны или файл пуст')
              : logs.join('\n')}
          </pre>
          <div ref={logsEndRef} />
        </div>
      )}

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
