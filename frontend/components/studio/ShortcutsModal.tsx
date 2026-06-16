'use client';

import { X } from 'lucide-react';
import { modal, badge } from './styles';

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
    <div className={modal.overlay} onClick={onClose}>
      <div className={modal.box} onClick={(e) => e.stopPropagation()}>
        <div className={modal.header}>
          <h2 className={modal.title}>Горячие клавиши</h2>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text)]"><X size={18} /></button>
        </div>
        <ul className="space-y-2">
          {SHORTCUTS.map((s) => (
            <li key={s.keys} className="flex items-center justify-between text-xs">
              <span className="text-[var(--text-secondary)]">{s.action}</span>
              <kbd className={badge.kbd}>{s.keys}</kbd>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
