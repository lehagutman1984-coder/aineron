'use client';

import { useEffect, useState } from 'react';
import { RefreshCw, ExternalLink, CheckCircle, Download, Smartphone, Tablet, Monitor, Rocket, RotateCw, AlertTriangle, Wrench } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

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
}

export function PreviewPanel({ projectId, hasSandbox, status }: PreviewPanelProps) {
  const [key, setKey] = useState(0);
  const [width, setWidth] = useState<'100%' | '768px' | '375px'>('100%');
  const [errors, setErrors] = useState<ConsoleError[]>([]);
  const [fixing, setFixing] = useState(false);

  useEffect(() => {
    const onMsg = (e: MessageEvent) => {
      if (e.data?.type === 'studio-console-error') {
        const err: ConsoleError = e.data.error;
        setErrors((prev) => [...prev, err].slice(-20));
        studioApi.reportConsoleError(projectId, err);
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, [projectId]);

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

  if (status === 'completed') {
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
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          >
            <Download size={14} /> Скачать ZIP
          </a>
          <button
            onClick={() => studioApi.deploy(projectId)}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          >
            <Rocket size={14} /> Развернуть на Vercel
          </button>
          <button
            onClick={() => studioApi.restartPreview(projectId)}
            className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
          >
            <RotateCw size={14} /> Перезапустить превью
          </button>
        </div>
      </div>
    );
  }

  if (!hasSandbox) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60 p-6 text-center">
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
            className={width === '375px' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}
          >
            <Smartphone size={16} />
          </button>
          <button
            onClick={() => setWidth('768px')}
            title="768px"
            className={width === '768px' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}
          >
            <Tablet size={16} />
          </button>
          <button
            onClick={() => setWidth('100%')}
            title="100%"
            className={width === '100%' ? 'text-blue-500' : 'text-[var(--text-secondary)]'}
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
    </div>
  );
}
