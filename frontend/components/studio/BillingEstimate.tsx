'use client';

import { Coins } from 'lucide-react';

interface BillingEstimateProps {
  estimatedStars: number;
  spentStars?: number;
  plannedSteps?: number;
}

export function BillingEstimate({ estimatedStars, spentStars, plannedSteps }: BillingEstimateProps) {
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
            Примерная стоимость: <strong>~{estimatedStars}</strong> звёзд
            {plannedSteps ? ` за ${plannedSteps} шагов` : ''}
          </span>
        )}
      </div>
    </div>
  );
}
