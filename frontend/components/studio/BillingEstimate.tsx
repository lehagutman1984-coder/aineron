'use client';

import { useState } from 'react';
import { Coins, CheckCircle2, GitBranch, Globe, Loader2, ExternalLink } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { formatRub } from '@/lib/money';
import { card, btn } from './styles';

interface BillingEstimateProps {
  estimatedKopecks?: number;
  spentKopecks?: number;
  plannedSteps?: number;
  repoUrl?: string;
  completed?: boolean;
  projectId?: string;
  deploymentUrl?: string;
}

export function BillingEstimate({
  estimatedKopecks,
  spentKopecks,
  plannedSteps,
  repoUrl,
  completed,
  projectId,
  deploymentUrl,
}: BillingEstimateProps) {
  const [deploying, setDeploying] = useState(false);
  const [localDeployUrl, setLocalDeployUrl] = useState(deploymentUrl ?? '');

  const handleDeploy = async () => {
    if (!projectId) return;
    setDeploying(true);
    try {
      await studioApi.deploy(projectId);
    } finally {
      setDeploying(false);
    }
  };

  if (completed) {
    return (
      <div className={card.lg}>
        <div className="flex items-center gap-3 mb-4">
          <CheckCircle2 size={20} className="text-green-500 shrink-0" />
          <h3 className="text-base font-semibold">Проект завершён</h3>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2 text-[var(--text-secondary)]">
            <Coins size={14} className="text-yellow-400" />
            Потрачено: <strong className="text-[var(--text)]">{formatRub(spentKopecks ?? 0)}</strong>
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
                href={repoUrl.replace('http://gitea:3000', '/git')}
                target="_blank"
                rel="noreferrer"
                className="text-blue-500 hover:underline truncate"
              >
                Репозиторий Git
              </a>
            </div>
          )}
          {localDeployUrl ? (
            <div className="flex items-center gap-2 text-[var(--text-secondary)]">
              <ExternalLink size={14} className="text-green-400" />
              <a
                href={localDeployUrl}
                target="_blank"
                rel="noreferrer"
                className="text-green-500 hover:underline truncate"
              >
                {localDeployUrl}
              </a>
            </div>
          ) : projectId ? (
            <button
              onClick={handleDeploy}
              disabled={deploying}
              className={btn.blackDeploy}
            >
              {deploying ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Globe size={14} />
              )}
              {deploying ? 'Публикуем...' : 'Опубликовать на Vercel'}
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl text-sm">
      <Coins size={18} className="text-yellow-400 shrink-0" />
      <div className="flex-1">
        {spentKopecks !== undefined ? (
          <span>
            Потрачено: <strong>{formatRub(spentKopecks)}</strong>
          </span>
        ) : (
          <span>
            Примерная стоимость: <strong>~{estimatedKopecks !== undefined ? formatRub(estimatedKopecks) : '?'}</strong>
            {plannedSteps ? ` за ${plannedSteps} шагов` : ''}
          </span>
        )}
      </div>
    </div>
  );
}
