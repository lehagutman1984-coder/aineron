'use client';

import { useEffect, useState, useCallback } from 'react';
import { RefreshCw, ExternalLink, CheckCircle, Download, Smartphone, Tablet, Monitor, Rocket, RotateCw, AlertTriangle, Wrench, Github, Loader2 } from 'lucide-react';
import { studioApi, SANDPACK_STACKS } from '@/lib/api/studio';
import { btn, empty, text } from './styles';
import { SandpackPreviewPanel } from './SandpackPreviewPanel';
import { E2BPreview } from './E2BPreview';

const E2B_STACKS = ['nextjs', 'python', 'django'] as const;
type E2BStack = typeof E2B_STACKS[number];

interface ConsoleError {
  message: string;
  file?: string;
  line?: number;
  stack?: string;
}

interface PreviewPanelProps {
  projectId: string;
  hasSandbox: boolean;
  status?: string;
  githubUrl?: string;
  onRefresh?: () => void;
  stack?: string;
  previewKey?: number; // bumped by StudioLayout SSE (replaces own SSE connection)
}

export function PreviewPanel({ projectId, hasSandbox, status, githubUrl, onRefresh, stack, previewKey }: PreviewPanelProps) {
  const [key, setKey] = useState(0);
  const isSandpackStack = SANDPACK_STACKS.includes(stack as any);
  const isE2BStack = E2B_STACKS.includes(stack as E2BStack) && !!process.env.NEXT_PUBLIC_E2B_PREVIEW;
  const [width, setWidth] = useState<'100%' | '768px' | '375px'>('100%');
  const [errors, setErrors] = useState<ConsoleError[]>([]);
  const [fixing, setFixing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [restartSeconds, setRestartSeconds] = useState(0);
  // После перезапуска — показываем iframe даже если status=completed
  const [previewForced, setPreviewForced] = useState(false);

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      const data = e.data || {};
      if (data.type !== 'studio-console-error') return;
      // Support both legacy flat format and new {payload: {...}} format from injected hook
      const p = data.payload || data.error || data;
      const ce: ConsoleError = {
        message: p.message || '',
        file: p.file || '',
        line: p.line ?? undefined,
        stack: p.stack || '',
      };
      setErrors((prev) => [...prev, ce].slice(-20));
      // Auto-capture: store only (no autofix). User triggers fix via button.
      studioApi.reportConsoleError(projectId, { ...ce, autofix: false });
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [projectId]);

  // Reload preview when parent SSE signals step_completed / coder_done.
  // previewKey is bumped by StudioLayout's single shared SSE connection.
  useEffect(() => {
    if (previewKey) setKey((k) => k + 1);
  }, [previewKey]);

  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const showInfo = (msg: string) => { setInfoMsg(msg); setTimeout(() => setInfoMsg(null), 4000); };
  const showError = (msg: string) => { setErrorMsg(msg); setTimeout(() => setErrorMsg(null), 6000); };

  const handleGithubExport = async () => {
    const repoName = window.prompt('Имя репозитория GitHub', `aineron-${projectId.slice(0, 8)}`);
    if (!repoName?.trim()) return;
    setExporting(true);
    try {
      await studioApi.exportGithub(projectId, repoName.trim(), true);
      showInfo('Экспорт запущен. Репозиторий появится на GitHub через несколько секунд.');
      onRefresh?.();
    } catch {
      showError('Ошибка экспорта. Проверьте GITHUB_TOKEN в .env или войдите через GitHub.');
    } finally {
      setExporting(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await studioApi.deploy(projectId);
      showInfo('Деплой запущен. URL появится в логе агентов через ~30 сек.');
    } catch {
      showError('Ошибка деплоя. Проверьте STUDIO_VERCEL_TOKEN в .env.');
    } finally {
      setDeploying(false);
    }
  };

  const handleRestartPreview = async () => {
    setRestarting(true);
    setRestartSeconds(0);
    try {
      await studioApi.restartPreview(projectId);
      // Поллим /sandbox/ пока alive не станет true (Docker + npm install ~30-60 сек)
      const MAX_ATTEMPTS = 40; // 40 × 3 сек = 2 мин
      for (let i = 0; i < MAX_ATTEMPTS; i++) {
        await new Promise((r) => setTimeout(r, 3000));
        setRestartSeconds((i + 1) * 3);
        try {
          const status = await studioApi.sandbox(projectId);
          if (status.alive) {
            onRefresh?.();
            setPreviewForced(true);
            setKey((k) => k + 1);
            return;
          }
        } catch {
          // sandbox endpoint временно недоступен — продолжаем ждать
        }
      }
      showError('Превью не удалось запустить за 2 минуты. Проверьте логи.');
    } catch {
      showError('Не удалось перезапустить превью.');
    } finally {
      setRestarting(false);
      setRestartSeconds(0);
    }
  };

  const handleAutofix = async () => {
    const last = errors[errors.length - 1];
    if (!last) return;
    setFixing(true);
    try {
      await studioApi.reportConsoleError(projectId, { ...last, autofix: true });
    } finally {
      setFixing(false);
    }
  };

  const Toast = () => (
    <>
      {infoMsg && (
        <div className="fixed bottom-4 right-4 z-50 bg-[var(--sidebar)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-xs text-[var(--text)] shadow-lg max-w-xs">
          {infoMsg}
        </div>
      )}
      {errorMsg && (
        <div className="fixed bottom-4 right-4 z-50 bg-red-900/80 border border-red-500/40 rounded-lg px-4 py-2.5 text-xs text-red-200 shadow-lg max-w-xs">
          {errorMsg}
        </div>
      )}
    </>
  );

  // E2B стеки (nextjs/python/django): превью через E2B Firecracker sandbox
  if (isE2BStack) {
    return (
      <div className="flex flex-col h-full">
        <E2BPreview projectId={projectId} refreshKey={key} stack={stack} />
        <Toast />
      </div>
    );
  }

  // Sandpack стеки (react/vue/html/tma): превью в браузере, Docker не нужен
  if (isSandpackStack) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] shrink-0">
          <button
            onClick={() => setKey((k) => k + 1)}
            title="Обновить"
            className="hover:text-blue-500 transition-colors"
          >
            <RefreshCw size={16} />
          </button>
          <span className="text-xs text-[var(--text-secondary)] font-mono">sandpack</span>
          <div className="ml-auto flex items-center gap-1">
            {status === 'completed' && (
              <>
                <a href={studioApi.exportUrl(projectId)} download className={btn.ghostXs}>
                  <Download size={14} /> ZIP
                </a>
                <button onClick={handleDeploy} disabled={deploying} className={btn.ghostXsDisabled}>
                  {deploying ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
                  {deploying ? 'Публикуем…' : 'Vercel'}
                </button>
                {!githubUrl && (
                  <button onClick={handleGithubExport} disabled={exporting} className={btn.ghostXsDisabled}>
                    {exporting ? <Loader2 size={14} className="animate-spin" /> : <Github size={14} />}
                    {exporting ? 'Экспорт…' : 'GitHub'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <SandpackPreviewPanel projectId={projectId} stack={stack!} refreshKey={key} />
        </div>
        <Toast />
      </div>
    );
  }

  if (status === 'completed' && !previewForced) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 p-6 text-center">
        <CheckCircle size={48} className="text-green-500" />
        <div>
          <p className="text-sm font-medium text-[var(--text)]">Проект завершён</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            Превью-сервер песочницы остановлен для экономии ресурсов.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <a
            href={studioApi.exportUrl(projectId)}
            download
            className={btn.ghostXs}
          >
            <Download size={14} /> Скачать ZIP
          </a>
          <button
            onClick={handleDeploy}
            disabled={deploying}
            className={btn.ghostXsDisabled}
          >
            {deploying ? <Loader2 size={14} className="animate-spin" /> : <Rocket size={14} />}
            {deploying ? 'Публикуем…' : 'Развернуть на Vercel'}
          </button>
          <button
            onClick={handleRestartPreview}
            disabled={restarting}
            className={btn.ghostXsDisabled}
          >
            {restarting ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />}
            {restarting
              ? `Запускаем… ${restartSeconds > 0 ? `${restartSeconds}с` : ''}`
              : 'Перезапустить превью'}
          </button>
          {githubUrl ? (
            <a
              href={githubUrl}
              target="_blank"
              rel="noreferrer"
              className={btn.ghostXs}
            >
              <Github size={14} /> Открыть репозиторий
            </a>
          ) : (
            <button
              onClick={handleGithubExport}
              disabled={exporting}
              className={btn.ghostXsDisabled}
            >
              {exporting ? <Loader2 size={14} className="animate-spin" /> : <Github size={14} />}
              {exporting ? 'Экспортируем…' : 'Экспорт в GitHub'}
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!hasSandbox && !previewForced) {
    return (
      <div className={empty.centerP}>
        Preview появится после запуска кодинга
      </div>
    );
  }

  const base = process.env.NEXT_PUBLIC_API_URL ?? '';
  const src = `${base}/studio/projects/${projectId}/preview/`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] shrink-0">
        <button
          onClick={() => setKey((k) => k + 1)}
          title="Обновить"
          className="hover:text-blue-500 transition-colors"
        >
          <RefreshCw size={16} />
        </button>
        <a
          href={src}
          target="_blank"
          rel="noreferrer"
          title="Открыть в новой вкладке"
          className="hover:text-blue-500 transition-colors"
        >
          <ExternalLink size={16} />
        </a>
        <span className="text-xs text-[var(--text-secondary)] font-mono truncate">preview</span>

        {/* Вернуться в completion card */}
        {previewForced && (
          <button
            onClick={() => setPreviewForced(false)}
            title="Вернуться"
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--text)] ml-1"
          >
            ← Завершён
          </button>
        )}

        {/* Error indicator */}
        {errors.length > 0 && (
          <button
            onClick={handleAutofix}
            disabled={fixing}
            title="Исправить автоматически"
            className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 disabled:opacity-50 transition-colors"
          >
            <AlertTriangle size={14} />
            {errors.length}
            <Wrench size={13} />
            {fixing ? 'Исправляю…' : 'Исправить'}
          </button>
        )}

        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => setWidth('375px')}
            title="375px"
            className={width === '375px' ? text.blue : text.muted}
          >
            <Smartphone size={16} />
          </button>
          <button
            onClick={() => setWidth('768px')}
            title="768px"
            className={width === '768px' ? text.blue : text.muted}
          >
            <Tablet size={16} />
          </button>
          <button
            onClick={() => setWidth('100%')}
            title="100%"
            className={width === '100%' ? text.blue : text.muted}
          >
            <Monitor size={16} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto flex justify-center bg-[var(--hover)]">
        <iframe
          key={key}
          src={src}
          style={{ width }}
          className="h-full border-0 bg-white"
          title="Sandbox preview"
        />
      </div>
      <Toast />
    </div>
  );
}
