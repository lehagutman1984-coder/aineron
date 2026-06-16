'use client';

import { X } from 'lucide-react';
import type { PipelineState } from '@/lib/api/studio';

interface Props {
  agentKey: string;
  agentLabel: string;
  pipeline: PipelineState;
  stepText: string;
  onClose: () => void;
}

export function StepDetailDrawer({ agentLabel, pipeline, stepText, onClose }: Props) {
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-md bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h2 className="text-sm font-medium">{agentLabel}</h2>
        <button onClick={onClose} className="hover:text-[var(--text)] text-[var(--text-secondary)]">
          <X size={18} />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-4 text-xs">
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
