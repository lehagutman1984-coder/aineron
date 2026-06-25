'use client';

import { useQuery } from '@tanstack/react-query';
import { studioApi, SANDPACK_STACKS } from '@/lib/api/studio';

interface Props {
  projectId: string;
  projectStatus: string;
  stack?: string;
}

export function SandboxStatusBadge({ projectId, projectStatus, stack }: Props) {
  const isSandpack = SANDPACK_STACKS.includes(stack as any);

  const { data } = useQuery({
    queryKey: ['studio-sandbox', projectId],
    queryFn: () => studioApi.sandbox(projectId),
    refetchInterval: 10000,
    enabled: !isSandpack,
  });

  if (isSandpack) {
    return (
      <span className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] shrink-0" title="Sandpack — превью работает в браузере, сервер не нужен">
        <span className="w-2 h-2 rounded-full bg-green-500" />
        Sandpack — мгновенно
      </span>
    );
  }

  let color = 'bg-[var(--text-secondary)]';
  let label = 'Среда не запущена';
  if (data?.alive) {
    color = 'bg-green-500';
    label = 'Preview готов';
  } else if (projectStatus === 'coding' && !data?.alive) {
    color = 'bg-amber-500 animate-pulse';
    label = 'Подготавливаю среду';
  }

  const title = data?.alive
    ? 'Docker-контейнер с вашим проектом активен — preview доступен'
    : projectStatus === 'coding'
    ? 'Разворачиваю изолированную среду для запуска вашего приложения (30–60 сек)'
    : 'Docker-контейнер остановлен';

  return (
    <span title={title} className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] shrink-0 cursor-help">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      {label}
    </span>
  );
}
