'use client';

import { X } from 'lucide-react';

const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: 'Ctrl/Cmd + S', action: 'Сохранить файл' },
  { keys: 'Ctrl/Cmd + `', action: 'Лог агентов' },
  { keys: 'Ctrl/Cmd + K', action: 'Поиск файлов' },
  { keys: 'Ctrl/Cmd + Enter', action: 'Продолжить на паузе' },
  { keys: 'Esc', action: 'Закрыть панель' },
  { keys: '?', action: 'Горячие клавиши' },
];

export function ShortcutsModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium">Горячие клавиши</h2>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text)]"><X size={18} /></button>
        </div>
        <ul className="space-y-2">
          {SHORTCUTS.map((s) => (
            <li key={s.keys} className="flex items-center justify-between text-xs">
              <span className="text-[var(--text-secondary)]">{s.action}</span>
              <kbd className="font-mono bg-[var(--hover)] px-2 py-0.5 rounded">{s.keys}</kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
