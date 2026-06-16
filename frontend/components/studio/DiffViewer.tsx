'use client';

import { GitCompare } from 'lucide-react';
import { code } from './styles';

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  content: string;
  lineNum: number;
}

function computeDiff(oldContent: string, newContent: string): DiffLine[] {
  const oldLines = oldContent.split('\n');
  const newLines = newContent.split('\n');
  const result: DiffLine[] = [];
  const maxLen = Math.max(oldLines.length, newLines.length);

  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    if (oldLine === undefined) {
      result.push({ type: 'added', content: newLine, lineNum: i + 1 });
    } else if (newLine === undefined) {
      result.push({ type: 'removed', content: oldLine, lineNum: i + 1 });
    } else if (oldLine !== newLine) {
      result.push({ type: 'removed', content: oldLine, lineNum: i + 1 });
      result.push({ type: 'added', content: newLine, lineNum: i + 1 });
    } else {
      result.push({ type: 'unchanged', content: oldLine, lineNum: i + 1 });
    }
  }
  return result;
}

interface DiffViewerProps {
  oldContent: string;
  newContent: string;
  path: string;
}

export function DiffViewer({ oldContent, newContent, path }: DiffViewerProps) {
  const lines = computeDiff(oldContent, newContent);
  const hasChanges = lines.some((l) => l.type !== 'unchanged');

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--border)] text-xs text-[var(--text-secondary)] shrink-0">
        <GitCompare size={14} />
        <span className="font-mono">{path}</span>
        {!hasChanges && <span className="ml-auto opacity-60">Нет изменений</span>}
      </div>
      <div className="flex-1 overflow-auto font-mono text-xs">
        {lines.map((line, i) => (
          <div
            key={i}
            className={
              line.type === 'added'
                ? code.diffLine.added
                : line.type === 'removed'
                ? code.diffLine.removed
                : code.diffLine.normal
            }
          >
            <span className="select-none opacity-30 w-10 shrink-0 text-right mr-4">
              {line.lineNum}
            </span>
            <span className="select-none w-4 shrink-0 mr-2">
              {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
            </span>
            <span className="whitespace-pre-wrap break-all">{line.content}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
