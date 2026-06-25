'use client';

import { useEffect, useState } from 'react';

interface SessionTimerProps {
  expiresAt: number; // Unix timestamp (seconds)
  className?: string;
  onExpired?: () => void;
}

export function SessionTimer({ expiresAt, className = '', onExpired }: SessionTimerProps) {
  const [remaining, setRemaining] = useState(0);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    const update = () => {
      const diff = Math.max(0, expiresAt - Date.now() / 1000);
      setRemaining(diff);
      if (diff === 0 && !expired) {
        setExpired(true);
        onExpired?.();
      }
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expiresAt]);

  const m = Math.floor(remaining / 60);
  const s = Math.floor(remaining % 60);
  const urgent = remaining < 120 && remaining > 0; // red under 2 min

  return (
    <span className={`font-mono text-xs tabular-nums ${urgent ? 'text-red-400' : 'text-[var(--text-secondary)]'} ${className}`}>
      {expired ? '0:00' : `${m}:${s.toString().padStart(2, '0')}`}
    </span>
  );
}
