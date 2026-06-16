'use client';

import { useState } from 'react';
import { Search, X } from 'lucide-react';
import { studioApi, type FileSearchResult } from '@/lib/api/studio';

interface Props {
  projectId: string;
  onClose: () => void;
  onPick: (fileId: number) => void;
}

export function SearchFilesModal({ projectId, onClose, onPick }: Props) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<FileSearchResult[]>([]);

  const run = async (value: string) => {
    setQ(value);
    if (value.trim().length < 2) { setResults([]); return; }
    setResults(await studioApi.searchFiles(projectId, value));
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-24" onClick={onClose}>
      <div
        className="bg-[var(--bg)] border border-[var(--border)] rounded-xl w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[var(--border)]">
          <Search size={16} className="text-[var(--text-secondary)]" />
          <input
            autoFocus
            value={q}
            onChange={(e) => run(e.target.value)}
            placeholder="Поиск по файлам..."
            className="flex-1 bg-transparent text-sm outline-none"
          />
          <button onClick={onClose}>
            <X size={16} className="text-[var(--text-secondary)]" />
          </button>
        </div>
        <div className="max-h-80 overflow-auto">
          {results.length === 0 && q.trim().length >= 2 && (
            <div className="px-3 py-4 text-xs text-[var(--text-secondary)] text-center">Ничего не найдено</div>
          )}
          {results.map((r, idx) => (
            <button
              key={`${r.file_id}-${r.line}-${idx}`}
              onClick={() => { onPick(r.file_id); onClose(); }}
              className="w-full text-left px-3 py-2 hover:bg-[var(--hover)] border-b border-[var(--border)] last:border-0"
            >
              <div className="text-xs font-mono text-[var(--text-secondary)]">{r.path}:{r.line}</div>
              <div className="text-xs font-mono truncate">{r.snippet}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
