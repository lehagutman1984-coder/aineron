'use client';

import { Circle, CheckCircle2, Loader2 } from 'lucide-react';

const AGENTS = [
  { key: 'interviewer', label: 'Интервью' },
  { key: 'analyst', label: 'Анализ' },
  { key: 'planner', label: 'План' },
  { key: 'coder', label: 'Кодинг' },
  { key: 'reviewer', label: 'Ревью' },
  { key: 'tester', label: 'Тест' },
  { key: 'fixer', label: 'Фикс' },
];

const STATUS_TO_ACTIVE: Record<string, string> = {
  interview: 'interviewer',
  planning: 'analyst',
  ready: 'planner',
  coding: 'coder',
  paused: 'fixer',
  completed: '',
  failed: '',
};

interface PipelineStatusProps {
  projectStatus: string;
  pipelineStatus: string;
}

export function PipelineStatus({ projectStatus, pipelineStatus }: PipelineStatusProps) {
  const activeAgent = STATUS_TO_ACTIVE[projectStatus] ?? '';
  const isRunning = pipelineStatus === 'running';

  return (
    <div className="flex items-center gap-1 overflow-x-auto">
      {AGENTS.map((agent, i) => {
        const isActive = agent.key === activeAgent;
        const agentIndex = AGENTS.findIndex((a) => a.key === activeAgent);
        const isDone = agentIndex > i || projectStatus === 'completed';

        return (
          <div key={agent.key} className="flex items-center gap-1 shrink-0">
            <div
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : isDone
                  ? 'text-green-500'
                  : 'text-[var(--text-secondary)] opacity-50'
              }`}
            >
              {isActive && isRunning ? (
                <Loader2 size={12} className="animate-spin" />
              ) : isDone ? (
                <CheckCircle2 size={12} />
              ) : (
                <Circle size={12} />
              )}
              <span>{agent.label}</span>
            </div>
            {i < AGENTS.length - 1 && (
              <div className={`w-3 h-px ${isDone ? 'bg-green-500' : 'bg-[var(--border)]'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
