'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, RefreshCw } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { InterviewCards } from '@/components/studio/InterviewCards';
import { empty } from '@/components/studio/styles';

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['studio-interview', id],
    queryFn: () => studioApi.interview(id),
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return 3000;
      if ((d.questions?.length ?? 0) > 0) return false;
      if (d.interview_error) return false;
      return 3000;
    },
  });

  const submitMutation = useMutation({
    mutationFn: (answers: { id: string; answer: string }[]) =>
      studioApi.submitInterview(id, answers),
    onSuccess: () => {
      router.push(`/studio/${id}/review`);
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3">
        <Loader2 size={24} className={empty.spinnerBlue} />
        <p className="text-sm text-[var(--text-secondary)]">
          Агент готовит вопросы...
        </p>
      </div>
    );
  }

  const questions = data?.questions ?? [];

  if (data?.interview_error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-sm text-red-500">
          Агент не ответил. Нажмите кнопку чтобы попробовать снова.
        </p>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['studio-interview', id] })}
          className="flex items-center gap-2 px-4 py-2 text-sm bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
        >
          <RefreshCw size={16} />
          Попробовать снова
        </button>
      </div>
    );
  }

  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3">
        <Loader2 size={24} className={empty.spinnerBlue} />
        <p className="text-sm text-[var(--text-secondary)]">
          Агент готовит вопросы...
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold mb-1">Интервью с агентом</h1>
        <p className="text-sm text-[var(--text-secondary)]">
          Ответьте на вопросы, чтобы агент точнее понял ваш проект
        </p>
      </div>
      <InterviewCards
        questions={questions}
        onSubmit={(answers) => submitMutation.mutate(answers)}
        loading={submitMutation.isPending}
      />
      {submitMutation.isError && (
        <p className="mt-4 text-sm text-red-500">
          Ошибка при отправке ответов. Попробуйте ещё раз.
        </p>
      )}
    </div>
  );
}
