'use client';

import { useEffect, useRef, useState } from 'react';
import { Coins, ExternalLink, Loader2, Monitor, RefreshCw, Smartphone, StopCircle, Tablet, Terminal, XCircle, Zap } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { APIError } from '@/lib/api/client';
import { SessionTimer } from './SessionTimer';

type E2BState = 'idle' | 'starting' | 'running' | 'failed' | 'expired' | 'capped';

// Human-readable copy per claim_source (L6 progressive UI)
const CLAIM_COPY: Record<string, { label: string; sub: string }> = {
  prewarm: {
    label: 'Подключаю готовый sandbox…',
    sub: 'Зависимости установлены заранее — будет быстро',
  },
  paused: {
    label: 'Восстанавливаю сессию…',
    sub: 'Состояние сохранено — npm install не нужен',
  },
  pool: {
    label: 'Запускаю из пула…',
    sub: 'Sandbox уже прогрет — заливаю код',
  },
  cold: {
    label: 'Запускаю sandbox…',
    sub: 'Первый запуск — устанавливаю зависимости',
  },
};

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
  const [viewWidth, setViewWidth] = useState<'100%' | '768px' | '375px'>('100%');
  const [logs, setLogs] = useState<string[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  // Sprint 12: claim source + ETA for progressive UI
  const [claimSource, setClaimSource] = useState<string>('cold');
  const [etaSeconds, setEtaSeconds] = useState<number>(12);
  const [elapsedStart, setElapsedStart] = useState<number>(0);
  const [elapsedSeconds, setElapsedSeconds] = useState<number>(0);

  const sessionRef = useRef<string | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const costTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const etaTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  const logsPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const genRef = useRef<number>(0);
  const expiresAtRef = useRef<number>(0);
  const stateRef = useRef<E2BState>('idle');

  // keep refs in sync so visibilitychange closure always reads fresh values
  useEffect(() => { stateRef.current = state; }, [state]);
  useEffect(() => { expiresAtRef.current = expiresAt; }, [expiresAt]);

  const clearStatusPoll = () => {
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    if (etaTimerRef.current) { clearInterval(etaTimerRef.current); etaTimerRef.current = null; }
  };

  const clearPoll = () => {
    clearStatusPoll();
    if (costTimerRef.current) { clearInterval(costTimerRef.current); costTimerRef.current = null; }
    if (logsPollRef.current) { clearInterval(logsPollRef.current); logsPollRef.current = null; }
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
    genRef.current++;
    clearPoll();
    const sid = sessionRef.current;
    sessionRef.current = null;
    setState('idle');
    setPublicUrl(null);
    setExpiresAt(0);
    setLogs([]);
    setShowLogs(false);
    setElapsedSeconds(0);
    if (sid) await stopSession(sid);
  };

  const startPreview = async () => {
    clearPoll();
    if (sessionRef.current) {
      stopSession(sessionRef.current);
      sessionRef.current = null;
    }
    const myGen = ++genRef.current;

    setState('starting');
    setError(null);
    setPublicUrl(null);
    setExpiresAt(0);
    setLogs([]);
    setShowLogs(false);
    setElapsedSeconds(0);

    try {
      const resp = await studioApi.e2bPreviewStart(projectId);
      if (genRef.current !== myGen) {
        // Stopped or restarted while fetch was in-flight — kill the orphan session
        if (resp?.session_id) stopSession(resp.session_id);
        return;
      }
      sessionRef.current = resp.session_id;
      setPublicUrl(resp.public_url);
      setExpiresAt(resp.expires_at ?? 0);
      setStartedAt(resp.started_at ?? Date.now() / 1000);
      setStarsPerMin(resp.stars_per_min ?? 1);

      // L6: claim_source-aware UX
      const src = resp.claim_source ?? 'cold';
      const eta = resp.eta_seconds ?? 12;
      setClaimSource(src);
      setEtaSeconds(eta);
      const t0 = Date.now() / 1000;
      setElapsedStart(t0);
      setElapsedSeconds(0);

      // ETA elapsed ticker (shows "3s / ~5s" during starting state)
      etaTimerRef.current = setInterval(() => {
        setElapsedSeconds(Math.floor(Date.now() / 1000 - t0));
      }, 1000);

      // Cost elapsed ticker
      costTimerRef.current = setInterval(() => {
        const t0cost = resp.started_at ?? Date.now() / 1000;
        setElapsedMin((Date.now() / 1000 - t0cost) / 60);
      }, 10000);

      if (resp.state === 'running') {
        clearStatusPoll();
        setState('running');
        return;
      }

      pollTimerRef.current = setInterval(async () => {
        if (!sessionRef.current) return;
        try {
          const status = await studioApi.e2bPreviewStatus(projectId, sessionRef.current);
          if (status.state === 'running') {
            setState('running');
            clearStatusPoll();
          } else if (status.state === 'failed' || status.state === 'expired' || status.state === 'stopped') {
            setState(status.state as E2BState);
            clearPoll();
            if (status.state === 'failed') {
              setShowLogs(true);
              fetchLogs();
            }
          }
        } catch { /* keep polling */ }
      }, 3000);
    } catch (err: unknown) {
      const isCapped = err instanceof APIError && err.status === 429;
      setState(isCapped ? 'capped' : 'failed');
      setError(err instanceof Error ? err.message : 'Ошибка запуска E2B');
      if (!isCapped) setShowLogs(true);
      clearPoll();
    }
  };

  useEffect(() => {
    startPreview();
    return () => {
      genRef.current++;
      clearPoll();
      if (sessionRef.current) {
        stopSession(sessionRef.current);
        sessionRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  // refreshKey intentionally excluded: sandbox must NOT restart on every coding step
  }, [projectId]);

  // Auto-restart when user returns to tab after sandbox expired in background
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState !== 'visible') return;
      const isRunningOrExpired = stateRef.current === 'running' || stateRef.current === 'expired';
      const isExpired = expiresAtRef.current > 0 && Date.now() / 1000 > expiresAtRef.current + 5;
      if (isRunningOrExpired && isExpired) {
        startPreview();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  useEffect(() => {
    if (showLogs && state === 'running') {
      fetchLogs();
      logsPollRef.current = setInterval(fetchLogs, 3000);
    } else {
      if (logsPollRef.current) { clearInterval(logsPollRef.current); logsPollRef.current = null; }
    }
    return () => {
      if (logsPollRef.current) { clearInterval(logsPollRef.current); logsPollRef.current = null; }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showLogs, state]);

  // ── Loading / starting state (L6 progressive) ───────────────────────────────
  if (state === 'idle' || state === 'starting') {
    const copy = CLAIM_COPY[claimSource] ?? CLAIM_COPY.cold;
    const isHot = claimSource === 'prewarm' || claimSource === 'paused';
    const pct = Math.min(100, Math.round((elapsedSeconds / Math.max(etaSeconds, 1)) * 100));

    return (
      <div className="flex flex-col items-center justify-center h-full gap-5 p-6 text-center">
        <div className="relative">
          <Loader2 size={36} className="animate-spin text-blue-500" />
          {isHot && (
            <span className="absolute -top-1 -right-1">
              <Zap size={14} className="text-yellow-400" />
            </span>
          )}
        </div>

        <div className="w-full max-w-xs">
          <p className="text-sm font-medium text-[var(--text)] mb-1">{copy.label}</p>
          <p className="text-xs text-[var(--text-secondary)] mb-3">{copy.sub}</p>

          {/* Progress bar */}
          <div className="w-full h-1 bg-[var(--border)] rounded-full overflow-hidden mb-1">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-1000"
              style={{ width: `${pct}%` }}
            />
          </div>

          <p className="text-[10px] text-[var(--text-secondary)] font-mono">
            {elapsedSeconds}s{etaSeconds > 0 ? ` / ~${etaSeconds}s` : ''}
          </p>
        </div>
      </div>
    );
  }

  // ── Daily cap exceeded ────────────────────────────────────────────────────
  if (state === 'capped') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <Coins size={36} className="text-amber-400" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">Дневной лимит превью исчерпан</p>
          {error && <p className="text-xs text-amber-400 mt-2 max-w-xs leading-relaxed">{error}</p>}
          <p className="text-xs text-[var(--text-secondary)] mt-2">Лимит сбросится в полночь по московскому времени</p>
        </div>
      </div>
    );
  }

  // ── Error / expired state ─────────────────────────────────────────────────
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

  // ── RUNNING ───────────────────────────────────────────────────────────────
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

        {/* Sprint 12: claim source badge — shows prewarm/resume path to user */}
        {claimSource !== 'cold' && (
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 rounded flex items-center gap-1"
            title={`Запущено через: ${claimSource}`}
          >
            <Zap size={9} />
            {claimSource}
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

        {/* Viewport switcher */}
        <div className="flex items-center ml-1 border border-[var(--border)] rounded overflow-hidden">
          <button
            onClick={() => setViewWidth('375px')}
            title="375px"
            className={`p-1 transition-colors ${viewWidth === '375px' ? 'bg-blue-500/20 text-blue-400' : 'text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
          >
            <Smartphone size={13} />
          </button>
          <button
            onClick={() => setViewWidth('768px')}
            title="768px"
            className={`p-1 transition-colors ${viewWidth === '768px' ? 'bg-blue-500/20 text-blue-400' : 'text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
          >
            <Tablet size={13} />
          </button>
          <button
            onClick={() => setViewWidth('100%')}
            title="100%"
            className={`p-1 transition-colors ${viewWidth === '100%' ? 'bg-blue-500/20 text-blue-400' : 'text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
          >
            <Monitor size={13} />
          </button>
        </div>
      </div>

      {showLogs && (
        <div className="border-b border-[var(--border)] bg-[#0d1117] overflow-y-auto shrink-0" style={{ maxHeight: '40%' }}>
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)]">
            <span className="text-xs text-[var(--text-secondary)]">Логи sandbox (/tmp/preview.log)</span>
            <span className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
              {logsLoading
                ? <Loader2 size={10} className="animate-spin" />
                : <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />}
              {state === 'running' ? 'авто' : 'стоп'}
            </span>
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
        <div className="flex-1 overflow-auto flex justify-center bg-[var(--hover)]">
          <iframe
            src={publicUrl}
            style={{ width: viewWidth }}
            className="h-full border-0 bg-white"
            title="E2B preview"
            allow="cross-origin-isolated"
          />
        </div>
      )}
    </div>
  );
}
