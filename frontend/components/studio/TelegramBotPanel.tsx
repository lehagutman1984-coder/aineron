'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, Bot, ExternalLink, Loader2, RefreshCw, StopCircle, Terminal } from 'lucide-react';
import { BotEmulator } from './BotEmulator';
import { SessionTimer } from './SessionTimer';
import { studioApi } from '@/lib/api/studio';

type Tab = 'emulator' | 'live';
type BotState = 'idle' | 'starting' | 'running' | 'failed';

const BOT_TTL = 900; // 15 min in seconds

interface Props {
  projectId: string;
  refreshKey: number;
}

export function TelegramBotPanel({ projectId, refreshKey }: Props) {
  const [tab, setTab] = useState<Tab>('emulator');
  const [token, setToken] = useState('');
  const [botState, setBotState] = useState<BotState>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [botUsername, setBotUsername] = useState<string | null>(null);
  const [logsLoading, setLogsLoading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);
  const sessionRef = useRef<string | null>(null);
  const genRef = useRef(0);

  const clearPoll = () => {
    if (pollRef.current !== null) { clearInterval(pollRef.current); pollRef.current = null; }
  };

  const clearLogsPoll = () => {
    if (logsPollRef.current !== null) { clearInterval(logsPollRef.current); logsPollRef.current = null; }
  };

  useEffect(() => {
    return () => {
      clearPoll();
      clearLogsPoll();
      const sid = sessionRef.current;
      if (sid) {
        try { studioApi.e2bPreviewStop(projectId, sid).catch(() => {}); } catch {}
        sessionRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-poll logs while bot is running and logs panel is open
  useEffect(() => {
    if (botState === 'running' && showLogs && sessionId) {
      fetchLogs(sessionId);
      logsPollRef.current = setInterval(() => fetchLogs(sessionId), 3000);
    } else {
      clearLogsPoll();
    }
    return clearLogsPoll;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botState, showLogs, sessionId]);

  useEffect(() => {
    clearPoll();
    genRef.current++;
    sessionRef.current = null;
    setBotState('idle');
    setSessionId(null);
    setExpiresAt(0);
    setWarning(null);
    setError(null);
    setLogs([]);
    setShowLogs(false);
    setBotUsername(null);
  }, [refreshKey]);

  const fetchBotUsername = async (botToken: string) => {
    try {
      const resp = await fetch(`https://api.telegram.org/bot${botToken}/getMe`);
      const data = await resp.json();
      if (data.ok && data.result?.username) {
        setBotUsername(data.result.username);
      }
    } catch { /* ignore */ }
  };

  const fetchLogs = async (sid: string) => {
    setLogsLoading(true);
    try {
      const data = await studioApi.e2bPreviewLogs(projectId, sid);
      setLogs(data.lines ?? []);
      setTimeout(() => logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    } catch { /* ignore */ } finally { setLogsLoading(false); }
  };

  const startBot = async () => {
    if (!token.trim()) return;
    const myGen = ++genRef.current;
    setBotState('starting');
    setError(null);
    setWarning(null);
    setLogs([]);
    setShowLogs(false);
    try {
      const r = await studioApi.e2bBotStart(projectId, token.trim());
      if (genRef.current !== myGen) {
        if (r?.session_id) { try { await studioApi.e2bPreviewStop(projectId, r.session_id); } catch {} }
        return;
      }
      sessionRef.current = r.session_id;
      setSessionId(r.session_id);
      setWarning(r.warning ?? null);
      setExpiresAt(Date.now() / 1000 + BOT_TTL);
      if (r.state === 'running') {
        setBotState('running');
        fetchBotUsername(token.trim());
        return;
      }
      const id = setInterval(async () => {
        try {
          const s = await studioApi.e2bPreviewStatus(projectId, r.session_id);
          if (s.state === 'running') {
            setBotState('running');
            clearPoll();
            fetchBotUsername(token.trim());
          } else if (s.state === 'failed' || s.state === 'stopped' || s.state === 'expired') {
            setBotState('failed');
            setError('Бот завершился или не смог запуститься. Проверьте логи.');
            setShowLogs(true);
            fetchLogs(r.session_id);
            clearPoll();
          }
        } catch { /* keep polling */ }
      }, 5000);
      pollRef.current = id;
    } catch (e: unknown) {
      setBotState('failed');
      setError(e instanceof Error ? e.message : 'Ошибка запуска бота');
    }
  };

  const stopBot = async () => {
    genRef.current++;
    clearPoll();
    const sid = sessionRef.current ?? sessionId;
    sessionRef.current = null;
    setBotState('idle');
    setSessionId(null);
    setToken('');
    setWarning(null);
    setError(null);
    setExpiresAt(0);
    setLogs([]);
    setShowLogs(false);
    setBotUsername(null);
    if (sid) {
      try { await studioApi.e2bPreviewStop(projectId, sid); } catch { /* best effort */ }
    }
  };

  const tabs: [Tab, string][] = [
    ['emulator', 'AI-эмулятор'],
    ['live', 'Живой бот (E2B)'],
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-[var(--border)] shrink-0">
        {tabs.map(([t, label]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs border-b-2 transition-colors ${
              tab === t
                ? 'border-blue-500 text-blue-500'
                : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'emulator' && (
        <div className="flex-1 overflow-hidden">
          <BotEmulator projectId={projectId} />
        </div>
      )}

      {tab === 'live' && (
        <div className="flex flex-col gap-4 p-4 flex-1 overflow-y-auto">
          <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
            <AlertTriangle size={15} className="text-amber-500 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-200 leading-relaxed">
              Используйте только тестовый токен, созданный у @BotFather специально для разработки. Токен передаётся в изолированную E2B среду и хранится только в памяти sandbox — не в базе данных. Сессия автоматически завершится через 15 мин.
            </p>
          </div>

          {(botState === 'idle' || botState === 'failed') ? (
            <div className="flex flex-col gap-3">
              {error && (
                <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
                  {error}
                </p>
              )}
              <label className="text-xs text-[var(--text-secondary)]">Токен тестового бота</label>
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                className="bg-[var(--hover)] border border-[var(--border)] rounded px-3 py-2 text-sm text-[var(--text)] outline-none focus:border-blue-500 transition-colors"
              />
              <button
                onClick={startBot}
                disabled={!token.trim()}
                className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-500 text-white text-sm rounded disabled:opacity-40 hover:bg-blue-400 transition-colors"
              >
                <Bot size={15} />
                Запустить в E2B
              </button>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {warning && (
                <p className="text-xs text-[var(--text-secondary)] bg-[var(--hover)] border border-[var(--border)] rounded p-2 leading-relaxed">
                  {warning}
                </p>
              )}

              <div className="flex items-center gap-2">
                {botState === 'starting' && <Loader2 size={15} className="animate-spin text-blue-500" />}
                {botState === 'running' && <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />}
                <span className="text-sm text-[var(--text)]">
                  {botState === 'starting' ? 'Запускаю бота в E2B…' : 'Бот работает в изолированной среде'}
                </span>
                {botState === 'running' && expiresAt > 0 && (
                  <span className="ml-auto flex items-center gap-1 text-[10px] text-[var(--text-secondary)]">
                    до: <SessionTimer expiresAt={expiresAt} onExpired={stopBot} />
                  </span>
                )}
              </div>

              {botState === 'starting' && (
                <p className="text-xs text-[var(--text-secondary)]">
                  pip install + delete_webhook + python bot.py — до 60 с
                </p>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={stopBot}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 border border-red-400/30 rounded hover:bg-red-500/10 transition-colors"
                >
                  <StopCircle size={14} />
                  Остановить сессию
                </button>
                {sessionId && (
                  <button
                    onClick={() => { setShowLogs(!showLogs); if (!showLogs && sessionId) fetchLogs(sessionId); }}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded transition-colors ${showLogs ? 'border-blue-500/40 text-blue-400' : 'border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
                  >
                    <Terminal size={13} />
                    Логи
                  </button>
                )}
                {botState === 'running' && botUsername && (
                  <a
                    href={`https://t.me/${botUsername}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-green-400 border border-green-400/30 rounded hover:bg-green-500/10 transition-colors"
                  >
                    <ExternalLink size={14} />
                    @{botUsername}
                  </a>
                )}
              </div>

              {showLogs && sessionId && (
                <div className="border border-[var(--border)] rounded bg-[#0d1117] overflow-hidden">
                  <div className="flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)]">
                    <span className="text-xs text-[var(--text-secondary)]">Логи бота</span>
                    <button
                      onClick={() => fetchLogs(sessionId)}
                      className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                      disabled={logsLoading}
                    >
                      {logsLoading ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                      Обновить
                    </button>
                  </div>
                  <pre className="text-[11px] font-mono text-green-300 p-3 max-h-48 overflow-y-auto whitespace-pre-wrap break-all leading-relaxed">
                    {logs.length === 0
                      ? (logsLoading ? 'Загрузка…' : 'Логи ещё не появились')
                      : logs.join('\n')}
                  </pre>
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
