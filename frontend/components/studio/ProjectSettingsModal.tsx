'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import { studioApi, type StudioProject } from '@/lib/api/studio';

interface Props {
  project: StudioProject;
  onClose: () => void;
  onSaved: () => void;
}

export function ProjectSettingsModal({ project, onClose, onSaved }: Props) {
  const [model, setModel] = useState<'fast' | 'smart'>(project.coder_model ?? 'fast');
  const [iterations, setIterations] = useState(project.max_iterations ?? 0);
  const [budget, setBudget] = useState(project.max_stars_budget ?? 0);
  const [mode, setMode] = useState(project.mode);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await studioApi.updateSettings(project.id, {
        coder_model: model,
        max_iterations: iterations,
        max_stars_budget: budget,
        mode,
      });
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div
        className="bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-sm space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Настройки проекта</h2>
          <button onClick={onClose}>
            <X size={18} className="text-[var(--text-secondary)]" />
          </button>
        </div>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Модель Coder</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value as 'fast' | 'smart')}
            className="w-full bg-[var(--hover)] border border-[var(--border)] rounded p-2 text-xs"
          >
            <option value="fast">DeepSeek V3 (быстро)</option>
            <option value="smart">Opus 4.8 (качество)</option>
          </select>
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Режим</span>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as StudioProject['mode'])}
            className="w-full bg-[var(--hover)] border border-[var(--border)] rounded p-2 text-xs"
          >
            <option value="auto">Авто</option>
            <option value="semi">Полу-авто</option>
            <option value="manual">Ручной</option>
          </select>
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Макс. итераций на шаг (0 = по умолчанию)</span>
          <input
            type="number"
            min={0}
            value={iterations}
            onChange={(e) => setIterations(Number(e.target.value))}
            className="w-full bg-[var(--hover)] border border-[var(--border)] rounded p-2 text-xs"
          />
        </label>
        <label className="block text-xs space-y-1">
          <span className="text-[var(--text-secondary)]">Бюджет звёзд (0 = без лимита)</span>
          <input
            type="number"
            min={0}
            value={budget}
            onChange={(e) => setBudget(Number(e.target.value))}
            className="w-full bg-[var(--hover)] border border-[var(--border)] rounded p-2 text-xs"
          />
        </label>
        <button
          onClick={save}
          disabled={saving}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-xs font-medium"
        >
          {saving ? 'Сохранение…' : 'Сохранить'}
        </button>
      </div>
    </div>
  );
}
