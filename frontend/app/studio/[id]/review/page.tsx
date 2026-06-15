'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Loader2, Play, Edit3, Check } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { BillingEstimate } from '@/components/studio/BillingEstimate';

function MarkdownBlock({ title, content, onSave }: { title: string; content: string; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(content);

  const handleSave = () => {
    onSave(value);
    setEditing(false);
  };

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl overflow-hidden mb-4">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h2 className="text-sm font-semibold">{title}</h2>
        <button
          onClick={() => (editing ? handleSave() : setEditing(true))}
          className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors"
        >
          {editing ? <Check size={14} /> : <Edit3 size={14} />}
          {editing ? 'Сохранить' : 'Редактировать'}
        </button>
      </div>
      {editing ? (
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          rows={20}
          className="w-full p-4 font-mono text-xs bg-[var(--input-bg)] resize-none focus:outline-none"
        />
      ) : (
        <pre className="p-4 text-xs font-mono overflow-auto whitespace-pre-wrap max-h-80">
          {content || <span className="opacity-40">Ещё не сгенерировано...</span>}
        </pre>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: project, isLoading, refetch } = useQuery({
    queryKey: ['studio-project-review', id],
    queryFn: () => studioApi.get(id),
    refetchInterval: 3000,
  });

  const runMutation = useMutation({
    mutationFn: () => studioApi.run(id),
    onSuccess: () => router.push(`/studio/${id}`),
  });

  const saveMd = async (field: 'project_md_content' | 'commits_md_content', value: string) => {
    await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/studio/projects/${id}/`,
      {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      },
    );
    refetch();
  };

  const isReady = project?.status === 'ready';
  const isPlanning = project?.status === 'planning' || project?.status === 'interview';

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3">
        <Loader2 size={24} className="animate-spin text-blue-500" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center min-h-screen text-sm text-[var(--text-secondary)]">
        Проект не найден
      </div>
    );
  }

  const plannedSteps = project.interview_data?.planned_steps as number | undefined;

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">{project.name}</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Проверьте документы перед запуском кодинга
        </p>
      </div>

      {isPlanning && (
        <div className="flex items-center gap-3 p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl mb-6">
          <Loader2 size={16} className="animate-spin text-blue-500" />
          <span className="text-sm">Аналитик готовит документы...</span>
        </div>
      )}

      <MarkdownBlock
        title="PROJECT.md"
        content={project.project_md_content}
        onSave={(v) => saveMd('project_md_content', v)}
      />

      <MarkdownBlock
        title="COMMITS.md (план реализации)"
        content={project.commits_md_content}
        onSave={(v) => saveMd('commits_md_content', v)}
      />

      <BillingEstimate estimatedStars={50} plannedSteps={plannedSteps} />

      <div className="mt-6">
        <button
          onClick={() => runMutation.mutate()}
          disabled={!isReady || runMutation.isPending}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-3 rounded-xl text-sm font-medium transition-colors"
        >
          {runMutation.isPending ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <Play size={16} />
          )}
          Начать кодинг
        </button>
        {!isReady && !isPlanning && (
          <p className="mt-2 text-xs text-[var(--text-secondary)]">
            Статус проекта: {project.status}. Запуск доступен после планирования.
          </p>
        )}
      </div>
    </div>
  );
}
