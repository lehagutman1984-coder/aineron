'use client';

import { useState } from 'react';
import { AlertTriangle, Bot, Loader2, StopCircle } from 'lucide-react';
import { BotEmulator } from './BotEmulator';
import { studioApi } from '@/lib/api/studio';

type Tab = 'emulator' | 'live';
type BotState = 'idle' | 'starting' | 'running' | 'failed';

interface Props {
  projectId: string;
  refreshKey: number;
}

export function TelegramBotPanel({ projectId, refreshKey }: Props) {
  const [tab, setTab] = useState<Tab>('emulator');
  const [token, setToken] = useState('');
  const [botState, setBotState] = useState<BotState>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const startBot = async () => {
    if (!token.trim()) return;
    setBotState('starting');
    setError(null);
    setWarning(null);
    try {
      const r = await studioApi.e2bBotStart(projectId, token.trim());
      setSessionId(r.session_id);
      setWarning(r.warning ?? null);
      if (r.state === 'running') {
        setBotState('running');
        return;
      }
      // Poll for RUNNING
      const poll = setInterval(async () => {
        if (!r.session_id) return;
        try {
          const s = await studioApi.e2bPreviewStatus(projectId, r.session_id);
          if (s.state === 'running') {
            setBotState('running');
            clearInterval(poll);
          } else if (s.state === 'failed' || s.state === 'stopped' || s.state === 'expired') {
            setBotState('failed');
            setError('Бот завершился или не смог запуститься. Проверьте файлы проекта.');
            clearInterval(poll);
          }
        } catch { /* keep polling */ }
      }, 5000);
    } catch (e: unknown) {
      setBotState('failed');
      setError(e instanceof Error ? e.message : 'Ошибка запуска бота');
    }
  };

  const stopBot = async () => {
    if (sessionId) {
      try {
        await studioApi.e2bPreviewStop(projectId, sessionId);
      } catch { /* best effort */ }
    }
    setBotState('idle');
    setSessionId(null);
    setToken('');
    setWarning(null);
    setError(null);
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
              <label className="text-xs text-[var(--text-secondary)]">
                Токен тестового бота
              </label>
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
                {botState === 'starting' && (
                  <Loader2 size={15} className="animate-spin text-blue-500" />
                )}
                {botState === 'running' && (
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                )}
                <span className="text-sm text-[var(--text)]">
                  {botState === 'starting' ? 'Запускаю бота в E2B…' : 'Бот работает в изолированной среде'}
                </span>
              </div>
              {botState === 'starting' && (
                <p className="text-xs text-[var(--text-secondary)]">
                  pip install + delete_webhook + python bot.py — до 60 с
                </p>
              )}
              <button
                onClick={stopBot}
                className="flex items-center gap-2 px-3 py-1.5 w-fit text-xs text-red-400 border border-red-400/30 rounded hover:bg-red-500/10 transition-colors"
              >
                <StopCircle size={14} />
                Остановить сессию
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
