'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Loader2, AlertTriangle, RotateCcw } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { StudioLayout } from '@/components/studio/StudioLayout';
import { BillingEstimate } from '@/components/studio/BillingEstimate';
import { empty } from '@/components/studio/styles';

const TERMINAL = ['completed', 'failed'];

export default function StudioProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const {
    data: project,
    isLoading: projectLoading,
    isError: projectError,
    refetch: refetchProject,
  } = useQuery({
    queryKey: ['studio-project', id],
    queryFn: () => studioApi.get(id),
    refetchInterval: (query) =>
      TERMINAL.includes(query.state.data?.status ?? '') ? 30000 : 5000,
    retry: 2,
  });

  const { data: files = [], refetch: refetchFiles } = useQuery({
    queryKey: ['studio-files', id],
    queryFn: () => studioApi.files(id),
    enabled: !!project,
    refetchInterval: (query) => {
      const pStatus = query.state.data;
      return pStatus && TERMINAL.includes(project?.status ?? '') ? 60000 : 10000;
    },
  });

  const {
    data: pipeline,
    isLoading: pipelineLoading,
    isError: pipelineError,
    refetch: refetchPipeline,
  } = useQuery({
    queryKey: ['studio-pipeline', id],
    queryFn: () => studioApi.pipeline(id),
    enabled: !!project,
    refetchInterval: (query) =>
      TERMINAL.includes(query.state.data?.status ?? '') ? 30000 : 3000,
    retry: 2,
  });

  const handleRefresh = () => {
    refetchProject();
    refetchFiles();
    refetchPipeline();
  };

  // Primary: project loading
  if (projectLoading) {
    return (
      <div className={empty.screen}>
        <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
      </div>
    );
  }

  // Project fetch error
  if (projectError || !project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-2">
        <AlertTriangle size={20} className="text-red-400" />
        <p className="text-sm text-[var(--text-secondary)]">Не удалось загрузить проект</p>
        <button
          onClick={() => refetchProject()}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
        >
          <RotateCcw size={12} />
          Повторить
        </button>
      </div>
    );
  }

  // Route early-stage projects to their pages
  if (project.status === 'draft' || project.status === 'interview') {
    router.push(`/studio/${id}/interview`);
    return null;
  }

  // planning/ready without pipeline yet → review page
  if ((project.status === 'planning' || project.status === 'ready') && !pipeline && !pipelineLoading) {
    router.push(`/studio/${id}/review`);
    return null;
  }

  // Secondary: pipeline loading (only brief, not infinite)
  if (pipelineLoading && !pipeline) {
    return (
      <div className={empty.screen}>
        <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
      </div>
    );
  }

  // Pipeline fetch error — show actionable state instead of spinner
  if ((pipelineError || !pipeline) && !pipelineLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-2">
        <AlertTriangle size={20} className="text-amber-400" />
        <p className="text-sm text-[var(--text-secondary)]">Не удалось загрузить состояние пайплайна</p>
        <button
          onClick={() => { refetchProject(); refetchPipeline(); }}
          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300"
        >
          <RotateCcw size={12} />
          Повторить
        </button>
      </div>
    );
  }

  if (!pipeline) return null;

  const plannedSteps = project.interview_data?.planned_steps as number | undefined;

  return (
    <div className="flex flex-col overflow-hidden" style={{ height: 'calc(100vh - 3.5rem)' }}>
      {project.status === 'completed' && (
        <div className="hidden md:block shrink-0 px-4 py-2 border-b border-[var(--border)]">
          <BillingEstimate
            completed
            spentStars={project.stars_spent}
            plannedSteps={plannedSteps}
            repoUrl={project.repo_url}
          />
        </div>
      )}
      <div className="flex-1 min-h-0 overflow-hidden">
        <StudioLayout
          project={project}
          files={files}
          pipeline={pipeline}
          onRefresh={handleRefresh}
        />
      </div>
    </div>
  );
}
