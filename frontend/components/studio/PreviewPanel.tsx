'use client';

import { useState } from 'react';
import { RefreshCw, ExternalLink, CheckCircle, Download, Smartphone, Tablet, Monitor } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface PreviewPanelProps {
  projectId: string;
  hasSandbox: boolean;
  status?: string;
}

export function PreviewPanel({ projectId, hasSandbox, status }: PreviewPanelProps) {
  const [key, setKey] = useState(0);
  const [width, setWidth] = useState<'100%' | '768px' | '375px'>('100%');

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
        <a
          href={studioApi.exportUrl(projectId)}
          download
          className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
        >
          <Download size={14} /> Скачать ZIP
        </a>
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
