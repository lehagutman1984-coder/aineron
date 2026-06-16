'use client';

import { useState } from 'react';
import { RefreshCw, ExternalLink, CheckCircle, Download } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';

interface PreviewPanelProps {
  projectId: string;
  hasSandbox: boolean;
  status?: string;
}

export function PreviewPanel({ projectId, hasSandbox, status }: PreviewPanelProps) {
  const [key, setKey] = useState(0);

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
      </div>
      <iframe
        key={key}
        src={src}
        className="flex-1 w-full border-0"
        title="Sandbox preview"
      />
    </div>
  );
}
