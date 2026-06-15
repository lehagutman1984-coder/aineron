'use client';

import { Coins, CheckCircle2, GitBranch } from 'lucide-react';

interface BillingEstimateProps {
  estimatedStars?: number;
  spentStars?: number;
  plannedSteps?: number;
  repoUrl?: string;
  completed?: boolean;
}

export function BillingEstimate({
  estimatedStars,
  spentStars,
  plannedSteps,
  repoUrl,
  completed,
}: BillingEstimateProps) {
  if (completed) {
    return (
      <div className="p-6 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl">
        <div className="flex items-center gap-3 mb-4">
          <CheckCircle2 size={20} className="text-green-500 shrink-0" />
          <h3 className="text-base font-semibold">Проект завершён</h3>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2 text-[var(--text-secondary)]">
            <Coins size={14} className="text-yellow-400" />
            Потрачено звёзд: <strong className="text-[var(--text)]">{spentStars ?? 0}</strong>
          </div>
          {plannedSteps !== undefined && (
            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <CheckCircle2 size={14} className="text-green-400" />
              Шагов выполнено: <strong className="text-[var(--text)]">{plannedSteps}</strong>
            </div>
          )}
          {repoUrl && (
            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <GitBranch size={14} />
              <a
                href={repoUrl.replace('http://gitea:3001', '/git')}
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:underline truncate"
              >
                Репозиторий Git
              </a>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl text-sm">
      <Coins size={18} className="text-yellow-400 shrink-0" />
      <div className="flex-1">
        {spentStars !== undefined ? (
          <span>
            Потрачено: <strong>{spentStars}</strong> звёзд
          </span>
        ) : (
          <span>
            Примерная стоимость: <strong>~{estimatedStars ?? '?'}</strong> звёзд
            {plannedSteps ? ` за ${plannedSteps} шагов` : ''}
          </span>
        )}
      </div>
    </div>
  );
}
