'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { StudioLayout } from '@/components/studio/StudioLayout';
import { BillingEstimate } from '@/components/studio/BillingEstimate';

export default function StudioProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data: project, isLoading: projectLoading, refetch: refetchProject } = useQuery({
    queryKey: ['studio-project', id],
    queryFn: () => studioApi.get(id),
    refetchInterval: 5000,
  });

  const { data: files = [], refetch: refetchFiles } = useQuery({
    queryKey: ['studio-files', id],
    queryFn: () => studioApi.files(id),
    refetchInterval: 10000,
  });

  const { data: pipeline, refetch: refetchPipeline } = useQuery({
    queryKey: ['studio-pipeline', id],
    queryFn: () => studioApi.pipeline(id),
    refetchInterval: 3000,
  });

  const handleRefresh = () => {
    refetchProject();
    refetchFiles();
    refetchPipeline();
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex items-center justify-center h-screen text-sm text-[var(--text-secondary)]">
        Проект не найден
      </div>
    );
  }

  if (project.status === 'draft' || (!project.status || project.status === 'interview')) {
    router.push(`/studio/${id}/interview`);
    return null;
  }

  if ((project.status === 'planning' || project.status === 'ready') && !pipeline?.status) {
    router.push(`/studio/${id}/review`);
    return null;
  }

  if (!pipeline) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
      </div>
    );
  }

  const plannedSteps = project.interview_data?.planned_steps as number | undefined;

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {project.status === 'completed' && (
        <div className="shrink-0 p-4 border-b border-[var(--border)]">
          <BillingEstimate
            completed
            spentStars={project.stars_spent}
            plannedSteps={plannedSteps}
            repoUrl={project.repo_url}
          />
        </div>
      )}
      <div className="flex-1 overflow-hidden">
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
