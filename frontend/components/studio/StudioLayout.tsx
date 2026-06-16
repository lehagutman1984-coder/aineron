'use client';

import { useState } from 'react';
import { Play, Pause, Files, Code2, Monitor } from 'lucide-react';
import { FileTree } from './FileTree';
import { CodeViewer } from './CodeViewer';
import { PreviewPanel } from './PreviewPanel';
import { AgentLog } from './AgentLog';
import { PipelineStatus } from './PipelineStatus';
import { ContextChat } from './ContextChat';
import { GitHistory } from './GitHistory';
import type { StudioProject, StudioFileNode, StudioFileDetail, PipelineState } from '@/lib/api/studio';
import { studioApi } from '@/lib/api/studio';

type MobileTab = 'files' | 'code' | 'preview';

interface StudioLayoutProps {
  project: StudioProject;
  files: StudioFileNode[];
  pipeline: PipelineState;
  onRefresh: () => void;
}

export function StudioLayout({ project, files, pipeline, onRefresh }: StudioLayoutProps) {
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [fileDetail, setFileDetail] = useState<StudioFileDetail | null>(null);
  const [logOpen, setLogOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<MobileTab>('files');
  const [running, setRunning] = useState(false);

  const handleFileSelect = async (fileId: number) => {
    setSelectedFileId(fileId);
    const detail = await studioApi.fileDetail(project.id, fileId);
    setFileDetail(detail);
    setMobileTab('code');
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      await studioApi.run(project.id);
      onRefresh();
    } finally {
      setRunning(false);
    }
  };

  const handlePause = async () => {
    await studioApi.pause(project.id);
    onRefresh();
  };

  const isPaused = pipeline.status === 'paused_on_loop' || pipeline.status === 'paused_manual';
  const isRunning = pipeline.status === 'running';
  const isCompleted = pipeline.status === 'completed';

  const MOBILE_TABS: { key: MobileTab; label: string; icon: React.ReactNode }[] = [
    { key: 'files', label: 'Файлы', icon: <Files size={16} /> },
    { key: 'code', label: 'Код', icon: <Code2 size={16} /> },
    { key: 'preview', label: 'Preview', icon: <Monitor size={16} /> },
  ];

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-[var(--border)] shrink-0">
        <PipelineStatus projectStatus={project.status} pipelineStatus={pipeline.status} />
        <div className="ml-auto flex items-center gap-2">
          {!isCompleted && !isRunning && !isPaused && (
            <button
              onClick={handleRun}
              disabled={running}
              className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            >
              <Play size={14} />
              Запустить
            </button>
          )}
          {isRunning && (
            <button
              onClick={handlePause}
              className="flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            >
              <Pause size={14} />
              Пауза
            </button>
          )}
        </div>
      </div>

      {/* Mobile tabs */}
      <div className="md:hidden flex border-b border-[var(--border)] shrink-0">
        {MOBILE_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMobileTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium transition-colors ${
              mobileTab === tab.key
                ? 'border-b-2 border-blue-500 text-blue-500'
                : 'text-[var(--text-secondary)]'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ContextChat overlay for paused_on_loop */}
      {pipeline.status === 'paused_on_loop' && (
        <div className="flex-1 overflow-hidden">
          <ContextChat
            projectId={project.id}
            pauseReason={pipeline.pause_reason}
            resumeHint={pipeline.resume_hint}
            onResume={onRefresh}
          />
        </div>
      )}

      {/* Three-panel layout (hidden when paused_on_loop) */}
      {pipeline.status !== 'paused_on_loop' && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Desktop: 3 columns */}
          <div className="hidden md:grid md:grid-cols-[220px_1fr_1fr] flex-1 overflow-hidden divide-x divide-[var(--border)]">
            <div className="overflow-hidden flex flex-col">
              <div className="px-3 py-2 text-xs font-medium text-[var(--text-secondary)] border-b border-[var(--border)]">
                Файлы
              </div>
              <div className="flex-1 overflow-auto">
                <FileTree
                  files={files}
                  selectedId={selectedFileId}
                  onSelect={handleFileSelect}
                />
              </div>
              <div className="border-t border-[var(--border)] overflow-auto max-h-48">
                <GitHistory projectId={project.id} />
              </div>
            </div>
            <div className="overflow-hidden flex flex-col">
              <CodeViewer
                content={fileDetail?.content ?? ''}
                language={fileDetail?.language ?? 'text'}
                path={fileDetail?.path}
              />
            </div>
            <div className="overflow-hidden flex flex-col">
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} />
            </div>
          </div>

          {/* Mobile: single active tab */}
          <div className="md:hidden flex-1 overflow-hidden">
            {mobileTab === 'files' && (
              <FileTree
                files={files}
                selectedId={selectedFileId}
                onSelect={handleFileSelect}
              />
            )}
            {mobileTab === 'code' && (
              <CodeViewer
                content={fileDetail?.content ?? ''}
                language={fileDetail?.language ?? 'text'}
                path={fileDetail?.path}
              />
            )}
            {mobileTab === 'preview' && (
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} />
            )}
          </div>

          {/* Agent log drawer */}
          <div className="border-t border-[var(--border)] shrink-0">
            <button
              onClick={() => setLogOpen(!logOpen)}
              className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] transition-colors"
            >
              <span>Лог агентов</span>
              <span>{logOpen ? '▼' : '▲'}</span>
            </button>
            {logOpen && (
              <div className="h-40 border-t border-[var(--border)]">
                <AgentLog projectId={project.id} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
