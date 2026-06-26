'use client';

// Sprint 3 — code-complete, not integration-tested.
// "База данных" tab for Studio settings. Lets the user bind a preview database
// (Aineron schema / Neon / external). Secrets are write-only: the API never
// returns the Neon key or DSN in clear, only has_neon_key / has_external_conn.

import { useCallback, useEffect, useState } from 'react';
import {
  Database,
  Key,
  Link as LinkIcon,
  CheckCircle,
  AlertCircle,
  Loader2,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { studioApi, type ProjectDatabaseInfo, type ProjectDbMode } from '@/lib/api/studio';

interface DatabasePanelProps {
  projectId: string;
}

const MODES: {
  value: Exclude<ProjectDbMode, 'none'>;
  icon: typeof Database;
  label: string;
  description: string;
}[] = [
  {
    value: 'aineron',
    icon: Database,
    label: 'Aineron Schema',
    description: 'Бесплатная PostgreSQL-схема на инфраструктуре Aineron. Ничего не нужно настраивать.',
  },
  {
    value: 'neon',
    icon: Key,
    label: 'Neon',
    description: 'Создаётся проект в вашем аккаунте Neon. Нужен API-ключ Neon.',
  },
  {
    value: 'external',
    icon: LinkIcon,
    label: 'Внешняя БД',
    description: 'Подключение к вашей существующей PostgreSQL по строке подключения.',
  },
];

export function DatabasePanel({ projectId }: DatabasePanelProps) {
  const [info, setInfo] = useState<ProjectDatabaseInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [testResult, setTestResult] = useState<{ ok: boolean; error: string | null } | null>(null);
  const [testing, setTesting] = useState(false);

  const [selectedMode, setSelectedMode] = useState<Exclude<ProjectDbMode, 'none'>>('aineron');
  const [neonKey, setNeonKey] = useState('');
  const [externalConn, setExternalConn] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await studioApi.dbGet(projectId);
      setInfo(data);
      if (data.mode !== 'none') {
        setSelectedMode(data.mode);
      }
    } catch {
      setError('Не удалось загрузить настройки базы данных');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleProvision = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload: { mode: string; neon_api_key?: string; external_conn?: string } = {
        mode: selectedMode,
      };
      if (selectedMode === 'neon' && neonKey.trim()) {
        payload.neon_api_key = neonKey.trim();
      }
      if (selectedMode === 'external' && externalConn.trim()) {
        payload.external_conn = externalConn.trim();
      }
      await studioApi.dbProvision(projectId, payload);
      setNeonKey('');
      setExternalConn('');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка подключения базы данных');
    } finally {
      setBusy(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const data = await studioApi.dbTest(projectId);
      setTestResult(data);
    } catch {
      setTestResult({ ok: false, error: 'Не удалось проверить подключение' });
    } finally {
      setTesting(false);
    }
  };

  const handleDeprovision = async () => {
    setBusy(true);
    setError(null);
    try {
      await studioApi.dbDeprovision(projectId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка отключения базы данных');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] p-4">
        <Loader2 size={14} className="animate-spin" />
        Загрузка…
      </div>
    );
  }

  const currentMode = info?.mode ?? 'none';
  const isActive = currentMode !== 'none';

  return (
    <div className="space-y-4">
      {/* Current status */}
      <div className="flex items-center justify-between rounded-lg border border-[var(--border)] p-3">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-[var(--text-secondary)]" />
          <div>
            <p className="text-sm font-medium flex items-center gap-1.5">
              {isActive ? MODES.find((m) => m.value === currentMode)?.label ?? currentMode : 'База не подключена'}
              {isActive && (
                <span className={`text-[10px] font-mono px-1 py-0.5 rounded border ${
                  currentMode === 'aineron'
                    ? 'text-green-400 border-green-500/30 bg-green-500/10'
                    : 'text-[var(--text-secondary)] border-[var(--border)] bg-[var(--hover)]'
                }`}>
                  {currentMode === 'aineron' ? 'RU' : currentMode === 'neon' ? 'US' : 'Ext'}
                </span>
              )}
            </p>
            {isActive && (
              <p className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
                {info?.provisioned ? (
                  <>
                    <CheckCircle size={12} className="text-[var(--success)]" />
                    Провижининг выполнен
                  </>
                ) : (
                  <>
                    <Loader2 size={12} />
                    Будет создана при первом запуске превью
                  </>
                )}
              </p>
            )}
          </div>
        </div>
        {isActive && info?.mode === 'aineron' && (
          <a
            href={studioApi.dbExportUrl(projectId)}
            download
            className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Экспортировать данные
          </a>
        )}
        {isActive && (
          <button
            type="button"
            onClick={handleDeprovision}
            disabled={busy}
            className="flex items-center gap-1 text-xs text-[var(--danger)] hover:underline disabled:opacity-50"
          >
            <Trash2 size={12} />
            Отключить
          </button>
        )}
        {isActive && info?.provisioned && (
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] disabled:opacity-50 transition-colors"
          >
            {testing ? <Loader2 size={12} className="animate-spin" /> : <ShieldAlert size={12} />}
            Проверить
          </button>
        )}
      </div>

      {testResult !== null && (
        <div className={`flex items-center gap-1.5 text-xs p-2 rounded border ${testResult.ok ? 'text-green-400 border-green-500/20 bg-green-500/5' : 'text-red-400 border-red-500/20 bg-red-500/5'}`}>
          {testResult.ok ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
          {testResult.ok ? 'Подключение успешно' : (testResult.error ?? 'Ошибка подключения')}
        </div>
      )}

      {/* Mode selector */}
      <div className="grid grid-cols-1 gap-2">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            onClick={() => setSelectedMode(m.value)}
            className={`text-left p-3 rounded-lg border transition-colors ${
              selectedMode === m.value
                ? 'border-blue-500 bg-blue-600/10'
                : 'border-[var(--border)] hover:border-[var(--text-secondary)]'
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <m.icon
                size={14}
                className={selectedMode === m.value ? 'text-blue-400' : 'text-[var(--text-secondary)]'}
              />
              <span className="font-medium text-sm">{m.label}</span>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">{m.description}</p>
          </button>
        ))}
      </div>

      {/* Neon key input */}
      {selectedMode === 'neon' && (
        <div className="space-y-1">
          <label className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
            <Key size={12} />
            Neon API-ключ
            {info?.has_neon_key && <span className="text-[var(--success)]">(сохранён)</span>}
          </label>
          <input
            type="password"
            value={neonKey}
            onChange={(e) => setNeonKey(e.target.value)}
            placeholder={info?.has_neon_key ? '•••••••• (оставьте пустым, чтобы не менять)' : 'napi_...'}
            autoComplete="off"
            className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--bg)]"
          />
        </div>
      )}

      {/* External DSN input */}
      {selectedMode === 'external' && (
        <div className="space-y-1">
          <label className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
            <LinkIcon size={12} />
            Строка подключения
            {info?.has_external_conn && <span className="text-[var(--success)]">(сохранена)</span>}
          </label>
          <input
            type="password"
            value={externalConn}
            onChange={(e) => setExternalConn(e.target.value)}
            placeholder={
              info?.has_external_conn
                ? '•••••••• (оставьте пустым, чтобы не менять)'
                : 'postgresql://user:pass@host:5432/db'
            }
            autoComplete="off"
            className="w-full px-3 py-2 text-sm rounded-lg border border-[var(--border)] bg-[var(--bg)]"
          />
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 text-xs text-[var(--danger)]">
          <AlertCircle size={14} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <button
        type="button"
        onClick={handleProvision}
        disabled={busy}
        className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Database size={14} />}
        {isActive && currentMode === selectedMode ? 'Обновить базу' : 'Создать/Подключить базу'}
      </button>
    </div>
  );
}
