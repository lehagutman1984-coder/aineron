'use client';

import { useEffect, useState } from 'react';
import { Check, Loader2, Circle, AlertCircle } from 'lucide-react';

interface Step {
  title: string;
  status: 'done' | 'active' | 'waiting' | 'error';
}

interface PipelineTimelineProps {
  steps: Step[];
  currentAgent: string;
  iterationCount: number;
  maxIterations: number;
  elapsedSeconds: number;
}

const AGENT_LABELS: Record<string, string> = {
  analyst: 'Разбираю, что нужно построить',
  planner: 'Составляю план по шагам',
  coder: 'Пишу код',
  reviewer: 'Проверяю код на ошибки',
  tester: 'Запускаю сборку',
  fixer: 'Готовлю исправления',
  sandbox: 'Запускаю среду разработки',
  interviewer: 'Уточняю детали проекта',
};

export function PipelineTimeline({
  steps,
  currentAgent,
  iterationCount,
  maxIterations,
  elapsedSeconds,
}: PipelineTimelineProps) {
  return (
    <div className="space-y-1">
      {currentAgent && (
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] mb-3 px-1">
          <Loader2 size={14} className="animate-spin shrink-0" />
          <span>{AGENT_LABELS[currentAgent] ?? currentAgent}</span>
          {iterationCount > 0 && (
            <span className="text-xs text-[var(--muted)] ml-auto shrink-0">
              Попытка {iterationCount + 1} из {maxIterations}
            </span>
          )}
        </div>
      )}
      {steps.map((step, i) => (
        <div key={i} className="flex items-start gap-2 py-1 px-1 rounded text-sm">
          <div className="mt-0.5 shrink-0">
            {step.status === 'done' && <Check size={14} className="text-[var(--success)]" />}
            {step.status === 'active' && <Loader2 size={14} className="animate-spin text-[var(--text-secondary)]" />}
            {step.status === 'waiting' && <Circle size={14} className="text-[var(--muted)] opacity-40" />}
            {step.status === 'error' && <AlertCircle size={14} className="text-[var(--danger)]" />}
          </div>
          <span
            className={
              step.status === 'waiting'
                ? 'text-[var(--text-secondary)] opacity-50'
                : 'text-[var(--text)]'
            }
          >
            {step.title}
          </span>
          {step.status === 'active' && elapsedSeconds > 5 && (
            <span className="ml-auto text-xs text-[var(--muted)] shrink-0">{elapsedSeconds}с</span>
          )}
        </div>
      ))}
    </div>
  );
}
