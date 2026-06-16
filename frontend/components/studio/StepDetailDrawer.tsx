'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import type { PipelineState } from '@/lib/api/studio';
import { ReviewerMode } from './ReviewerMode';

interface Props {
  agentKey: string;
  agentLabel: string;
  pipeline: PipelineState;
  stepText: string;
  onClose: () => void;
  projectId?: string;
  stepIndex?: number;
}

type DrawerTab = 'info' | 'reviewer';

export function StepDetailDrawer({ agentLabel, pipeline, stepText, onClose, projectId, stepIndex }: Props) {
  const [tab, setTab] = useState<DrawerTab>('info');

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0">
        <h2 className="text-sm font-medium">{agentLabel}</h2>
        <div className="flex items-center gap-2">
          {projectId && stepIndex !== undefined && (
            <div className="flex gap-1 text-xs">
              <button
                onClick={() => setTab('info')}
                className={`px-2 py-0.5 rounded ${tab === 'info' ? 'bg-blue-600 text-white' : 'text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
              >
                Инфо
              </button>
              <button
                onClick={() => setTab('reviewer')}
                className={`px-2 py-0.5 rounded ${tab === 'reviewer' ? 'bg-blue-600 text-white' : 'text-[var(--text-secondary)] hover:text-[var(--text)]'}`}
              >
                Ревьюер
              </button>
            </div>
          )}
          <button onClick={onClose} className="hover:text-[var(--text)] text-[var(--text-secondary)]">
            <X size={18} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-4 text-xs">
        {tab === 'info' ? (
          <>
            {stepText && (
              <section>
                <h3 className="font-medium mb-1 text-[var(--text-secondary)]">Планировалось (COMMITS.md)</h3>
                <pre className="whitespace-pre-wrap font-mono text-[11px] bg-[var(--hover)] rounded p-2">{stepText}</pre>
              </section>
            )}
            <Report title="Review report" data={pipeline.review_report} />
            <Report title="Test report" data={pipeline.test_report} />
            <Report title="Fix plan" data={pipeline.fix_plan} />
            {pipeline.last_error && (
              <section>
                <h3 className="font-medium mb-1 text-red-500">Ошибка</h3>
                <pre className="whitespace-pre-wrap font-mono text-[11px] bg-red-950/30 text-red-300 rounded p-2">{pipeline.last_error}</pre>
              </section>
            )}
          </>
        ) : (
          projectId && stepIndex !== undefined ? (
            <ReviewerMode
              projectId={projectId}
              stepIndex={stepIndex}
              plannedText={stepText}
            />
          ) : null
        )}
      </div>
    </div>
  );
}

function Report({ title, data }: { title: string; data: Record<string, unknown> }) {
  if (!data || Object.keys(data).length === 0) return null;
  return (
    <section>
      <h3 className="font-medium mb-1 text-[var(--text-secondary)]">{title}</h3>
      <pre className="whitespace-pre-wrap font-mono text-[11px] bg-[var(--hover)] rounded p-2">
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}
