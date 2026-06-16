'use client';

import { useQuery } from '@tanstack/react-query';
import { studioApi } from '@/lib/api/studio';

interface Props {
  projectId: string;
  projectStatus: string;
}

export function SandboxStatusBadge({ projectId, projectStatus }: Props) {
  const { data } = useQuery({
    queryKey: ['studio-sandbox', projectId],
    queryFn: () => studioApi.sandbox(projectId),
    refetchInterval: 10000,
  });

  let color = 'bg-[var(--text-secondary)]';
  let label = 'Песочница остановлена';
  if (data?.alive) {
    color = 'bg-green-500';
    label = 'Песочница активна';
  } else if (projectStatus === 'coding' && !data?.alive) {
    color = 'bg-amber-500';
    label = 'Запускается...';
  }

  return (
    <span className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] shrink-0">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
