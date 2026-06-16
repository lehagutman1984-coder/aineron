'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import type { PipelineState } from '@/lib/api/studio';
import { ReviewerMode } from './ReviewerMode';
import { drawer, modal, text } from './styles';

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
    <div className={drawer.rootMd}>
      <div className={drawer.header}>
        <h2 className={modal.title}>{agentLabel}</h2>
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
      <div className={drawer.body}>
        {tab === 'info' ? (
          <>
            {stepText && (
              <section>
                <h3 className="font-medium mb-1 text-[var(--text-secondary)]">Планировалось (COMMITS.md)</h3>
                <pre className={text.codeBlock}>{stepText}</pre>
              </section>
            )}
            <Report title="Review report" data={pipeline.review_report} />
            <Report title="Test report" data={pipeline.test_report} />
            <Report title="Fix plan" data={pipeline.fix_plan} />
            {pipeline.last_error && (
              <section>
                <h3 className="font-medium mb-1 text-red-500">Ошибка</h3>
                <pre className={text.codeBlockError}>{pipeline.last_error}</pre>
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
      <pre className={text.codeBlock}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}
