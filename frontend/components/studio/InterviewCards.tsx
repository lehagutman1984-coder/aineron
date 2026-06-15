'use client';

import { useState } from 'react';
import { MessageCircleQuestion, ArrowRight, Check } from 'lucide-react';
import type { InterviewQuestion } from '@/lib/api/studio';

interface InterviewCardsProps {
  questions: InterviewQuestion[];
  onSubmit: (answers: { id: string; answer: string }[]) => void;
  loading?: boolean;
}

export function InterviewCards({ questions, onSubmit, loading }: InterviewCardsProps) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});

  const question = questions[current];
  const answer = answers[question?.id] ?? '';
  const isLast = current === questions.length - 1;
  const allAnswered = questions.every((q) => answers[q.id]?.trim());

  const handleNext = () => {
    if (current < questions.length - 1) {
      setCurrent((c) => c + 1);
    }
  };

  const handleBack = () => {
    if (current > 0) setCurrent((c) => c - 1);
  };

  const handleSubmit = () => {
    const result = questions.map((q) => ({ id: q.id, answer: answers[q.id] ?? '' }));
    onSubmit(result);
  };

  if (!question) return null;

  return (
    <div className="max-w-xl mx-auto">
      <div className="flex items-center gap-2 mb-6 text-sm text-[var(--text-secondary)]">
        <MessageCircleQuestion size={16} />
        <span>
          Вопрос {current + 1} из {questions.length}
        </span>
        <div className="flex-1 h-1 bg-[var(--border)] rounded-full overflow-hidden ml-2">
          <div
            className="h-full bg-blue-500 transition-all"
            style={{ width: `${((current + 1) / questions.length) * 100}%` }}
          />
        </div>
      </div>

      <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-6 mb-4">
        <p className="text-base font-medium mb-4">{question.question}</p>

        {question.type === 'choice' && question.options ? (
          <div className="space-y-2">
            {question.options.map((opt) => (
              <button
                key={opt}
                onClick={() => setAnswers((a) => ({ ...a, [question.id]: opt }))}
                className={`w-full text-left px-4 py-3 rounded-lg border text-sm transition-colors ${
                  answer === opt
                    ? 'border-blue-500 bg-blue-600/10 text-blue-400'
                    : 'border-[var(--border)] hover:border-blue-400'
                }`}
              >
                {answer === opt && <Check size={14} className="inline mr-2" />}
                {opt}
              </button>
            ))}
          </div>
        ) : (
          <textarea
            value={answer}
            onChange={(e) => setAnswers((a) => ({ ...a, [question.id]: e.target.value }))}
            placeholder="Ваш ответ..."
            rows={3}
            className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        )}
      </div>

      <div className="flex gap-3">
        {current > 0 && (
          <button
            onClick={handleBack}
            className="px-4 py-2 rounded-lg text-sm border border-[var(--border)] hover:bg-[var(--hover)] transition-colors"
          >
            Назад
          </button>
        )}
        {!isLast ? (
          <button
            onClick={handleNext}
            disabled={!answer.trim()}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Далее
            <ArrowRight size={14} />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!allAnswered || loading}
            className="flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Check size={14} />
            Готово
          </button>
        )}
      </div>
    </div>
  );
}
