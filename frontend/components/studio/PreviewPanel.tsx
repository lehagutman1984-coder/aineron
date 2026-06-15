'use client';

import { useState } from 'react';
import { RefreshCw, ExternalLink } from 'lucide-react';

interface PreviewPanelProps {
  containerId: string | null;
}

export function PreviewPanel({ containerId }: PreviewPanelProps) {
  const [key, setKey] = useState(0);

  if (!containerId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60 p-6 text-center">
        Preview появится после запуска кодинга
      </div>
    );
  }

  const src = `/studio/preview/${containerId}/`;

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
        <span className="text-xs text-[var(--text-secondary)] font-mono truncate">{src}</span>
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
