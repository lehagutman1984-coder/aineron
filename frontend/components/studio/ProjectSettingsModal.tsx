'use client';

import { useState } from 'react';
import { X, Zap, Code2, Compass, ShieldCheck, ChevronDown, Database } from 'lucide-react';
import { studioApi, type StudioProject } from '@/lib/api/studio';
import { useQuery } from '@tanstack/react-query';
import type { StudioModel } from '@/lib/api/studio';
import { kopecksToRub, rubToKopecks } from '@/lib/money';
import { modal, form } from './styles';
import { AGENTS } from './agentConfig';
import { DatabasePanel } from './DatabasePanel';

interface Props {
  project: StudioProject;
  onClose: () => void;
  onSaved: () => void;
}

const AGENT_ICONS: Record<string, React.ReactNode> = {
  architect: <Compass size={14} />,
  coder: <Code2 size={14} />,
  guardian: <ShieldCheck size={14} />,
};

const TIER_BADGE: Record<string, string> = {
  fast: 'bg-green-500/15 text-green-400',
  smart: 'bg-purple-500/15 text-purple-400',
  coder: 'bg-blue-500/15 text-blue-400',
  reasoning: 'bg-amber-500/15 text-amber-400',
};

export function ProjectSettingsModal({ project, onClose, onSaved }: Props) {
  const [activeTab, setActiveTab] = useState<'settings' | 'database'>('settings');
  const [aiModel, setAiModel] = useState(project.ai_model ?? 'claude-sonnet-4-6');
  const [agentModels, setAgentModels] = useState<Record<string, string>>(project.agent_models ?? {});
  const [iterations, setIterations] = useState(project.max_iterations ?? 0);
  const [budget, setBudget] = useState(kopecksToRub(project.max_kopecks_budget ?? 0));
  const [mode, setMode] = useState(project.mode);
  const [saving, setSaving] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const { data: models = [] } = useQuery<StudioModel[]>({
    queryKey: ['studio-models'],
    queryFn: studioApi.getModels,
  });

  const modelById = Object.fromEntries(models.map((m) => [m.id, m]));

  const effectiveModel = (agentKey: string) => agentModels[agentKey] ?? aiModel;

  const setAgentModel = (agentKey: string, modelId: string) => {
    setAgentModels((prev) => {
      if (modelId === aiModel) {
        const next = { ...prev };
        delete next[agentKey];
        return next;
      }
      return { ...prev, [agentKey]: modelId };
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      await studioApi.updateSettings(project.id, {
        ai_model: aiModel,
        agent_models: agentModels,
        max_iterations: iterations,
        max_kopecks_budget: rubToKopecks(budget),
        mode,
      });
      onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={modal.overlay} onClick={onClose}>
      <div
        className="bg-[var(--bg)] border border-[var(--border)] rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
          <h2 className={modal.title}>Настройки проекта</h2>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text)]">
            <X size={18} />
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-[var(--border)] shrink-0">
          <button
            onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-1.5 px-5 py-2.5 text-xs border-b-2 transition-colors ${activeTab === 'settings' ? 'border-blue-500 text-blue-500' : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
          >
            <Code2 size={13} />
            Модели и режим
          </button>
          <button
            onClick={() => setActiveTab('database')}
            className={`flex items-center gap-1.5 px-5 py-2.5 text-xs border-b-2 transition-colors ${activeTab === 'database' ? 'border-blue-500 text-blue-500' : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
          >
            <Database size={13} />
            База данных
          </button>
        </div>

        {activeTab === 'database' && (
          <div className="p-5">
            <DatabasePanel projectId={project.id} />
          </div>
        )}

        {activeTab === 'settings' && (
        <div className="p-5 space-y-6">
          {/* Default model */}
          <div>
            <label className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
              Модель по умолчанию
            </label>
            <p className="text-xs text-[var(--text-secondary)] opacity-70 mb-2">
              Используется для агентов без персонального выбора
            </p>
            <ModelSelect
              value={aiModel}
              models={models}
              modelById={modelById}
              onChange={setAiModel}
            />
          </div>

          {/* Per-agent models */}
          <div>
            <p className="text-xs font-medium text-[var(--text-secondary)] mb-3">
              Модели по агентам
            </p>
            <div className="space-y-2">
              {AGENTS.map((agent) => {
                const current = effectiveModel(agent.key);
                const isOverridden = !!agentModels[agent.key];
                const currentMeta = modelById[current];
                const isExpanded = expandedAgent === agent.key;

                return (
                  <div
                    key={agent.key}
                    className="border border-[var(--border)] rounded-lg overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedAgent(isExpanded ? null : agent.key)}
                      className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-[var(--hover)] transition-colors text-start"
                    >
                      <span className="text-[var(--text-secondary)]">{AGENT_ICONS[agent.key]}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium">{agent.label}</span>
                          {isOverridden && (
                            <span className="text-[12px] px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400">
                              переопределено
                            </span>
                          )}
                        </div>
                        <p className="text-[12px] text-[var(--text-secondary)] truncate">{agent.desc}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {currentMeta && (
                          <span className={`text-[12px] px-1.5 py-0.5 rounded ${TIER_BADGE[currentMeta.tier] ?? ''}`}>
                            {currentMeta.label}
                          </span>
                        )}
                        <ChevronDown
                          size={14}
                          className={`text-[var(--text-secondary)] transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                        />
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="px-3 pb-3 space-y-2 border-t border-[var(--border)] pt-2">
                        {/* Recommendation */}
                        <div className="flex items-start gap-2 p-2 rounded bg-[var(--hover)] text-[12px]">
                          <Zap size={11} className="text-amber-400 shrink-0 mt-0.5" />
                          <div>
                            <span className="text-amber-400 font-medium">
                              Рекомендуем: {modelById[agent.recommended]?.label ?? agent.recommended}
                            </span>
                            <span className="text-[var(--text-secondary)] ms-1">— {agent.recommendedReason}</span>
                          </div>
                        </div>

                        <ModelSelect
                          value={current}
                          models={models}
                          modelById={modelById}
                          onChange={(v) => setAgentModel(agent.key, v)}
                          showDefault={aiModel}
                        />

                        {isOverridden && (
                          <button
                            type="button"
                            onClick={() => setAgentModel(agent.key, aiModel)}
                            className="text-[12px] text-[var(--text-secondary)] hover:text-[var(--text)] underline"
                          >
                            Сбросить к умолчанию ({modelById[aiModel]?.label ?? aiModel})
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Other settings */}
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-xs space-y-1">
              <span className="text-[var(--text-secondary)]">Режим</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as StudioProject['mode'])}
                className={form.inputXs}
              >
                <option value="auto">Авто</option>
                <option value="semi">Полу-авто</option>
                <option value="manual">Ручной</option>
              </select>
            </label>
            <label className="block text-xs space-y-1">
              <span className="text-[var(--text-secondary)]">Макс. итераций (0 = авто)</span>
              <input
                type="number"
                min={0}
                value={iterations}
                onChange={(e) => setIterations(Number(e.target.value))}
                className={form.inputXs}
              />
            </label>
            <label className="block col-span-2 text-xs space-y-1">
              <span className="text-[var(--text-secondary)]">Бюджет, ₽ (0 = без лимита)</span>
              <input
                type="number"
                min={0}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
                className={form.inputXs}
              />
            </label>
          </div>
        </div>
        )}

        {activeTab === 'settings' && (
        <div className="px-5 pb-5">
          <button
            onClick={save}
            disabled={saving}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-xs font-medium transition-colors"
          >
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
        )}
      </div>
    </div>
  );
}

function ModelSelect({
  value,
  models,
  modelById,
  onChange,
  showDefault,
}: {
  value: string;
  models: StudioModel[];
  modelById: Record<string, StudioModel>;
  onChange: (v: string) => void;
  showDefault?: string;
}) {
  const grouped = (['smart', 'coder', 'fast', 'reasoning'] as const)
    .map((cat) => ({ cat, items: models.filter((m) => m.category === cat) }))
    .filter((g) => g.items.length > 0);

  const CAT_LABELS: Record<string, string> = {
    smart: 'Smart — качество',
    fast: 'Fast — скорость/цена',
    coder: 'Coder — специализированные',
    reasoning: 'Reasoning — рассуждения',
  };

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-xs bg-[var(--hover)] border border-[var(--border)] rounded-lg px-3 py-2 pe-8 appearance-none focus:outline-none focus:border-blue-500"
      >
        {showDefault && (
          <option value={showDefault}>
            По умолчанию ({modelById[showDefault]?.label ?? showDefault})
          </option>
        )}
        {grouped.map((g) => (
          <optgroup key={g.cat} label={CAT_LABELS[g.cat] ?? g.cat}>
            {g.items.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label} — {m.description}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {modelById[value] && (
        <span className={`absolute right-7 top-1/2 -translate-y-1/2 text-[12px] px-1.5 py-0.5 rounded ${TIER_BADGE[modelById[value].tier] ?? ''}`}>
          {modelById[value].tier}
        </span>
      )}
    </div>
  );
}
