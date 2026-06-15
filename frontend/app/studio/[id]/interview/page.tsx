'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { studioApi } from '@/lib/api/studio';
import { InterviewCards } from '@/components/studio/InterviewCards';

export default function InterviewPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ['studio-interview', id],
    queryFn: () => studioApi.interview(id),
    refetchInterval: (query) =>
      (query.state.data?.questions?.length ?? 0) === 0 ? 3000 : false,
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
        <Loader2 size={24} className="animate-spin text-blue-500" />
        <p className="text-sm text-[var(--text-secondary)]">
          Агент готовит вопросы...
        </p>
      </div>
    );
  }

  const questions = data?.questions ?? [];

  if (questions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3">
        <Loader2 size={24} className="animate-spin text-blue-500" />
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
