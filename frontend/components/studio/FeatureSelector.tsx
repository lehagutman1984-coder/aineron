'use client';

import { ALL_FEATURES, FEATURE_CATEGORIES } from '@/lib/studio/features';

interface FeatureSelectorProps {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function FeatureSelector({ selected, onChange }: FeatureSelectorProps) {
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">Выберите нужные функции</label>
        {selected.length > 0 && (
          <button
            type="button"
            onClick={() => onChange([])}
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--text)]"
          >
            Сбросить ({selected.length})
          </button>
        )}
      </div>
      {FEATURE_CATEGORIES.map((cat) => {
        const items = ALL_FEATURES.filter((f) => f.category === cat.key);
        return (
          <div key={cat.key}>
            <p className="text-xs text-[var(--text-secondary)] uppercase tracking-wide mb-1.5">
              {cat.label}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {items.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => toggle(f.id)}
                  className={`px-2.5 py-1 rounded text-xs border transition-colors ${
                    selected.includes(f.id)
                      ? 'border-blue-500 bg-blue-600/15 text-blue-300'
                      : 'border-[var(--border)] hover:border-[var(--text-secondary)] text-[var(--text-secondary)]'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
