'use client';

import { useState, useEffect } from 'react';
import { Play, Pause, X, RotateCcw, Files, Code2, Monitor, CheckCircle, Download, ArrowLeft, Rocket, Share2, HelpCircle, Settings, GitBranch, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { FileTree } from './FileTree';
import { CodeViewer } from './CodeViewer';
import { PreviewPanel } from './PreviewPanel';
import { AgentLog } from './AgentLog';
import { PipelineStatus } from './PipelineStatus';
import { ContextChat } from './ContextChat';
import { GitHistory } from './GitHistory';
import { SandboxStatusBadge } from './SandboxStatusBadge';
import { StepDetailDrawer } from './StepDetailDrawer';
import { DiffViewer } from './DiffViewer';
import { ShortcutsModal } from './ShortcutsModal';
import { SearchFilesModal } from './SearchFilesModal';
import { ProjectSettingsModal } from './ProjectSettingsModal';
import { StepTimeline } from './StepTimeline';
import { PipelineTimeline } from './PipelineTimeline';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle } from 'react-resizable-panels';
import type { StudioProject, StudioFileNode, StudioFileDetail, PipelineState } from '@/lib/api/studio';
import { studioApi } from '@/lib/api/studio';
import { layout, btn, banner, form, drawer } from './styles';

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
  const [logOpen, setLogOpen] = useState(pipeline.status === 'running' || pipeline.status === 'paused_on_loop');
  const [mobileTab, setMobileTab] = useState<MobileTab>('files');
  const [running, setRunning] = useState(false);
  const [approving, setApproving] = useState(false);
  const [drawerAgent, setDrawerAgent] = useState<string | null>(null);
  const [centerTab, setCenterTab] = useState<'code' | 'diff'>('code');
  const [diff, setDiff] = useState<{ old: string; new: string; path: string } | null>(null);
  const [hintOpen, setHintOpen] = useState(false);
  const [hintText, setHintText] = useState('');
  const [resuming, setResuming] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [timelineOpen, setTimelineOpen] = useState(pipeline.status === 'running');
  const [currentAgent, setCurrentAgent] = useState('');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  // Live streaming: path → accumulated chunk text while coder is writing
  const [streamBuffers, setStreamBuffers] = useState<Record<string, string>>({});
  const [streamingPath, setStreamingPath] = useState<string | null>(null);
  // Single SSE feeds both PreviewPanel (previewKey) and AgentLog (agentLogLines)
  const [previewKey, setPreviewKey] = useState(0);
  const [agentLogLines, setAgentLogLines] = useState<{ agent: string; level: string; text: string; type?: string }[]>([]);

  const AGENT_LABELS: Record<string, string> = {
    interviewer: 'Интервью', analyst: 'Анализ', planner: 'План',
    coder: 'Кодинг', reviewer: 'Ревью', tester: 'Тест', fixer: 'Фикс',
  };

  const stepText = (() => {
    const md = project.commits_md_content || '';
    const parts = md.split(/\n(?=#{2,3}\s)/).filter((p) => p.trim());
    return parts[pipeline.step_index] ?? '';
  })();

  const handleApprove = async () => {
    setApproving(true);
    try {
      await studioApi.approve(project.id);
      onRefresh();
    } finally {
      setApproving(false);
    }
  };

  const handleFileSelect = async (fileId: number) => {
    setSelectedFileId(fileId);
    const detail = await studioApi.fileDetail(project.id, fileId);
    setFileDetail(detail);
    setMobileTab('code');
  };

  // Auto-select a meaningful file on first load so the editor isn't empty
  useEffect(() => {
    if (selectedFileId === null && files.length > 0) {
      const priority = [
        'index.html', 'app/page.tsx', 'src/App.tsx', 'src/App.jsx',
        'README.md', 'COMMITS.md',
      ];
      const pick =
        priority.map((p) => files.find((f) => f.path.endsWith(p))).find(Boolean) ?? files[0];
      if (pick) handleFileSelect(pick.id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [files, selectedFileId]);

  const handleRun = async () => {
    setRunning(true);
    try {
      await studioApi.run(project.id);
      onRefresh();
    } finally {
      setRunning(false);
    }
  };

  const [pausing, setPausing] = useState(false);
  const handlePause = async () => {
    setPausing(true);
    try {
      await studioApi.pause(project.id);
      onRefresh();
    } finally {
      setPausing(false);
    }
  };

  const [resetting, setResetting] = useState(false);
  const handleReset = async (restart = false) => {
    if (restart && !window.confirm('Сбросить пайплайн и вернуть в статус "Готов к запуску"?')) return;
    setResetting(true);
    try {
      await studioApi.reset(project.id, restart);
      onRefresh();
    } finally {
      setResetting(false);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key === '`') { e.preventDefault(); setLogOpen((v) => !v); }
      else if (mod && e.key === 'Enter' && pipeline.status === 'paused_on_loop') { e.preventDefault(); doResume('continue'); }
      else if (mod && (e.key === 'k' || (e.shiftKey && e.key.toLowerCase() === 'f'))) { e.preventDefault(); setSearchOpen(true); }
      else if (e.key === 'Escape') { setShortcutsOpen(false); setDrawerAgent(null); setChatOpen(false); setSearchOpen(false); }
      else if (e.key === '?' && !mod) { setShortcutsOpen(true); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipeline.status]);

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      await studioApi.deploy(project.id);
      onRefresh();
    } finally {
      setDeploying(false);
    }
  };

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
  };

  const doResume = async (action: 'continue' | 'with_hint' | 'skip_step', hint?: string) => {
    setResuming(true);
    try {
      await studioApi.resume(project.id, { action, hint });
      setHintOpen(false);
      setHintText('');
      onRefresh();
    } finally {
      setResuming(false);
    }
  };

  const handleCreateFile = async () => {
    const path = window.prompt('Путь нового файла (например: src/components/Button.tsx)');
    if (!path?.trim()) return;
    const newFile = await studioApi.createFile(project.id, path.trim());
    onRefresh();
    handleFileSelect(newFile.id);
  };

  const handleDeleteFile = async (fileId: number) => {
    if (!window.confirm('Удалить файл?')) return;
    await studioApi.deleteFile(project.id, fileId);
    if (selectedFileId === fileId) { setSelectedFileId(null); setFileDetail(null); }
    onRefresh();
  };

  const handleSaveFile = async (newContent: string) => {
    if (!selectedFileId) return;
    const updated = await studioApi.updateFile(project.id, selectedFileId, newContent);
    setFileDetail(updated);
    onRefresh();
  };

  const loadDiff = async () => {
    if (!selectedFileId) return;
    const versions = await studioApi.commits(project.id);
    const ref = (versions[0] as { git_sha?: string })?.git_sha;
    if (!ref) {
      setDiff({ old: '', new: fileDetail?.content ?? '', path: fileDetail?.path ?? '' });
      return;
    }
    const d = await studioApi.fileDiff(project.id, selectedFileId, ref);
    setDiff(d);
  };

  // Single SSE connection shared by the whole Studio page.
  // Feeds: currentAgent (PipelineTimeline), streamBuffers (CodeViewer),
  //        previewKey (PreviewPanel), agentLogLines (AgentLog).
  // This replaces the 3 separate SSE connections that previously existed
  // (StudioLayout + PreviewPanel + AgentLog), reducing Gunicorn thread load by 3×.
  useEffect(() => {
    let src: EventSource | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      if (closed) return;
      src = new EventSource(
        `${process.env.NEXT_PUBLIC_API_URL}/studio/projects/${project.id}/events/`,
        { withCredentials: true },
      );
      src.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (d.type === 'connected') return;

          // PipelineTimeline: track current agent
          if (d.agent && d.agent !== 'system') setCurrentAgent(d.agent);

          // CodeViewer: live file streaming
          if (d.type === 'file_delta' && d.path && d.chunk) {
            setStreamingPath(d.path);
            setStreamBuffers((prev) => ({ ...prev, [d.path]: (prev[d.path] ?? '') + d.chunk }));
          }
          if (d.type === 'file_delta_done' && d.path) {
            setStreamingPath(null);
            setStreamBuffers((prev) => { const n = { ...prev }; delete n[d.path]; return n; });
          }

          // PreviewPanel: bump key to reload Sandpack/iframe when step completes
          if (d.type === 'step_completed' || d.type === 'coder_done' || d.type === 'preview_restart') {
            setPreviewKey((k) => k + 1);
          }
          if (d.type === 'preview_restart') onRefresh();

          // AgentLog: accumulate all events (cap at 500 to avoid memory growth)
          setAgentLogLines((prev) => [...prev, d].slice(-500));
        } catch { /* noop */ }
      };
      src.onerror = () => {
        src?.close();
        if (!closed) retryTimer = setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      src?.close();
    };
  }, [project.id]);

  // Clear currentAgent when pipeline is no longer running
  useEffect(() => {
    if (pipeline.status !== 'running') setCurrentAgent('');
  }, [pipeline.status]);

  // Elapsed seconds counter while pipeline is running
  useEffect(() => {
    if (pipeline.status !== 'running') { setElapsedSeconds(0); return; }
    const t = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [pipeline.status]);

  const isPaused = pipeline.status === 'paused_on_loop' || pipeline.status === 'paused_manual';
  const isAwaitingApproval = pipeline.status === 'paused_manual';
  const isRunning = pipeline.status === 'running';
  const isCompleted = pipeline.status === 'completed';
  const isFailed = pipeline.status === 'failed';

  const MOBILE_TABS: { key: MobileTab; label: string; icon: React.ReactNode }[] = [
    { key: 'files', label: 'Файлы', icon: <Files size={16} /> },
    { key: 'code', label: 'Код', icon: <Code2 size={16} /> },
    { key: 'preview', label: 'Preview', icon: <Monitor size={16} /> },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Top bar */}
      <div className={layout.topbar}>
        <Link
          href="/studio"
          className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors shrink-0"
        >
          <ArrowLeft size={16} /> Проекты
        </Link>
        <div className={layout.divider} />
        <SandboxStatusBadge projectId={project.id} projectStatus={project.status} stack={project.target_stack} />
        <div className={layout.divider} />
        <PipelineStatus
          projectStatus={project.status}
          pipelineStatus={pipeline.status}
          onStepClick={(key) => setDrawerAgent(key)}
        />
        {isRunning && currentAgent && (
          <span className="flex items-center gap-1.5 text-xs text-blue-400 shrink-0">
            <Loader2 size={11} className="animate-spin" />
            {AGENT_LABELS[currentAgent] ?? currentAgent}
            {elapsedSeconds > 0 && <span className="opacity-60 hidden sm:inline">{Math.floor(elapsedSeconds / 60)}:{String(elapsedSeconds % 60).padStart(2, '0')}</span>}
          </span>
        )}
        {isCompleted && (
          <span className="md:hidden flex items-center gap-1 text-[11px] text-green-500 shrink-0">
            <CheckCircle size={11} />
            {project.stars_spent ? `${project.stars_spent}★` : 'Готово'}
          </span>
        )}
        <div className={layout.rightGroup}>
          <button onClick={() => setSettingsOpen(true)} title="Настройки проекта" className="text-[var(--text-secondary)] hover:text-[var(--text)] p-1.5">
            <Settings size={16} />
          </button>
          <button onClick={() => setShortcutsOpen(true)} title="Горячие клавиши" className="text-[var(--text-secondary)] hover:text-[var(--text)] p-1.5">
            <HelpCircle size={16} />
          </button>
          {!isCompleted && !isRunning && !isPaused && (
            <button
              onClick={handleRun}
              disabled={running}
              className={btn.primaryXs}
            >
              <Play size={14} />
              Запустить
            </button>
          )}
          {isRunning && (
            <button
              onClick={handlePause}
              disabled={pausing}
              className={btn.ghostXs}
            >
              <Pause size={14} />
              {pausing ? 'Пауза...' : 'Пауза'}
            </button>
          )}
          {isRunning && (
            <button
              onClick={() => handleReset(false)}
              disabled={resetting}
              title="Прервать выполнение"
              className="flex items-center gap-1 px-2 py-1 text-xs rounded text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-colors"
            >
              <X size={14} />
              Прервать
            </button>
          )}
          {isFailed && (
            <button
              onClick={() => handleReset(true)}
              disabled={resetting}
              className={btn.ghostXs}
            >
              <RotateCcw size={14} />
              {resetting ? 'Сброс...' : 'Попробовать снова'}
            </button>
          )}
          {isCompleted && (
            <a
              href={studioApi.exportUrl(project.id)}
              download
              className={btn.ghostXs}
            >
              <Download size={14} />
              Скачать ZIP
            </a>
          )}
          {isCompleted && (
            <button
              onClick={handleDeploy}
              disabled={deploying}
              className={btn.ghostXsDisabled}
            >
              <Rocket size={14} />
              {deploying ? 'Публикуем...' : 'Развернуть на Vercel'}
            </button>
          )}
          <button
            onClick={handleShare}
            title="Скопировать ссылку"
            className={btn.ghostXs}
          >
            <Share2 size={14} />
            Поделиться
          </button>
        </div>
      </div>

      {/* Completed status — desktop only, 1-row compact bar (replaces the tall BillingEstimate card) */}
      {isCompleted && (
        <div className="hidden md:flex shrink-0 items-center gap-2.5 px-4 h-8 border-b border-green-900/40 bg-green-950/20 text-xs text-green-300/80">
          <CheckCircle size={12} className="text-green-500 shrink-0" />
          <span className="font-medium text-green-400">Проект завершён</span>
          <span className="opacity-30 mx-0.5">·</span>
          <span>{project.stars_spent ?? 0} звёзд</span>
          {(project.interview_data?.planned_steps as number | undefined) && (
            <>
              <span className="opacity-30 mx-0.5">·</span>
              <span>{project.interview_data?.planned_steps as number} шагов</span>
            </>
          )}
          <a
            href={studioApi.exportUrl(project.id)}
            download
            className="ml-auto flex items-center gap-1 text-green-400/60 hover:text-green-300 transition-colors"
          >
            <Download size={11} /> Скачать ZIP
          </a>
        </div>
      )}

      {/* Approval banner for semi/manual mode */}
      {isAwaitingApproval && (
        <div className={banner.amber}>
          <CheckCircle size={16} className="text-amber-400 shrink-0" />
          <p className="text-xs text-amber-300 flex-1">{pipeline.pause_reason || 'Шаг завершён — подтвердите продолжение'}</p>
          <button
            onClick={handleApprove}
            disabled={approving}
            className={btn.amberXs}
          >
            <Play size={12} />
            {approving ? 'Запускаем...' : 'Подтвердить'}
          </button>
        </div>
      )}

      {/* Failed banner */}
      {isFailed && (
        <div className={banner.red}>
          <X size={16} className="text-red-400 shrink-0 mt-0.5" />
          <p className="text-xs text-red-300 flex-1">{pipeline.pause_reason || 'Пайплайн завершился с ошибкой'}</p>
          <button
            onClick={() => handleReset(true)}
            disabled={resetting}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-red-700/50 text-red-300 hover:bg-red-800/30 transition-colors shrink-0"
          >
            <RotateCcw size={12} />
            {resetting ? 'Сброс...' : 'Попробовать снова'}
          </button>
        </div>
      )}

      {/* Inline pause banner for paused_on_loop */}
      {pipeline.status === 'paused_on_loop' && (
        <div className={banner.amberCol}>
          <div className="flex items-center gap-3">
            <CheckCircle size={16} className="text-amber-400 shrink-0" />
            <p className="text-xs text-amber-300 flex-1">{pipeline.pause_reason || 'Пайплайн на паузе'}</p>
            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              <button onClick={() => doResume('continue')} disabled={resuming} className={btn.amberXsCompact}>Продолжить</button>
              <button onClick={() => setHintOpen((v) => !v)} className={btn.amberOutlineXs}>Подсказать</button>
              <button onClick={() => doResume('skip_step')} disabled={resuming} className={btn.amberOutlineXs}>Пропустить шаг</button>
              <button onClick={() => setChatOpen((v) => !v)} className={btn.amberOutlineXs}>Чат с агентом</button>
            </div>
          </div>
          {hintOpen && (
            <div className="flex gap-2">
              <textarea
                value={hintText}
                onChange={(e) => setHintText(e.target.value)}
                placeholder="Подсказка агенту..."
                className={form.textareaXs}
              />
              <button onClick={() => doResume('with_hint', hintText)} disabled={resuming || !hintText.trim()} className={btn.amberSendXs}>Отправить</button>
            </div>
          )}
        </div>
      )}

      {/* Three-panel layout (always shown; pause handled by inline banner) */}
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">

          {/* Desktop: resizable 3 columns.
              IMPORTANT: PanelGroup sets display:flex via inline style — wrapping in a plain
              div is the only way to correctly hide it on mobile with Tailwind hidden/md:flex. */}
          <div className="hidden md:flex flex-1 min-h-0 overflow-hidden">
            <PanelGroup orientation="horizontal" className="flex-1 overflow-hidden">
              <Panel defaultSize={15} minSize={10} className="overflow-hidden flex flex-col border-r border-[var(--border)]">
                <div className="flex-1 overflow-hidden">
                  <FileTree
                    files={files}
                    selectedId={selectedFileId}
                    onSelect={handleFileSelect}
                    onCreate={handleCreateFile}
                    onDelete={handleDeleteFile}
                  />
                </div>
                <div className={`${layout.borderTop} overflow-auto max-h-48`}>
                  <GitHistory projectId={project.id} />
                </div>
              </Panel>
              <PanelResizeHandle className={layout.resizeHandle} />
              <Panel defaultSize={33} minSize={18} className="overflow-hidden flex flex-col">
                <div className="flex border-b border-[var(--border)] shrink-0 text-xs">
                  <button
                    onClick={() => setCenterTab('code')}
                    className={`px-3 py-1.5 ${centerTab === 'code' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-[var(--text-secondary)]'}`}
                  >Код</button>
                  <button
                    onClick={() => { setCenterTab('diff'); loadDiff(); }}
                    className={`px-3 py-1.5 ${centerTab === 'diff' ? 'border-b-2 border-blue-500 text-blue-500' : 'text-[var(--text-secondary)]'}`}
                  >Diff</button>
                </div>
                {centerTab === 'code' ? (
                  !fileDetail && isRunning ? (
                    <div className="flex flex-col items-center justify-center h-full gap-3 text-[var(--text-secondary)]">
                      <Loader2 size={20} className="animate-spin text-blue-500" />
                      <p className="text-sm font-medium text-[var(--text)]">
                        {currentAgent ? (AGENT_LABELS[currentAgent] ?? 'Агент') + ' работает...' : 'Агент пишет код...'}
                      </p>
                      <p className="text-xs opacity-60 text-center max-w-xs">
                        Файлы появятся после завершения первого шага.<br/>
                        Следите за прогрессом в логе ниже.
                      </p>
                    </div>
                  ) : (
                  <CodeViewer
                    content={fileDetail?.content ?? ''}
                    language={fileDetail?.language ?? 'text'}
                    path={fileDetail?.path}
                    editable={project.status !== 'completed'}
                    onSave={handleSaveFile}
                    projectId={project.id}
                    streaming={streamingPath === fileDetail?.path}
                    streamContent={fileDetail?.path ? streamBuffers[fileDetail.path] : undefined}
                  />
                  )
                ) : (
                  <div className="flex-1 overflow-auto">
                    {diff ? (
                      <DiffViewer oldContent={diff.old} newContent={diff.new} path={diff.path} />
                    ) : (
                      <div className="flex items-center justify-center h-full text-xs text-[var(--text-secondary)]">Нет diff</div>
                    )}
                  </div>
                )}
              </Panel>
              <PanelResizeHandle className={layout.resizeHandle} />
              <Panel defaultSize={52} minSize={24} className="overflow-hidden flex flex-col">
                <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} githubUrl={project.github_repo_url || undefined} onRefresh={onRefresh} stack={project.target_stack} previewKey={previewKey} />
              </Panel>
            </PanelGroup>
          </div>

          {/* Mobile: single active tab — full height, no side-by-side panels */}
          <div className="flex md:hidden flex-1 min-h-0 overflow-hidden">
            {mobileTab === 'files' && (
              <FileTree
                files={files}
                selectedId={selectedFileId}
                onSelect={handleFileSelect}
                onCreate={handleCreateFile}
                onDelete={handleDeleteFile}
              />
            )}
            {mobileTab === 'code' && (
              <CodeViewer
                content={fileDetail?.content ?? ''}
                language={fileDetail?.language ?? 'text'}
                path={fileDetail?.path}
                editable={project.status !== 'completed'}
                onSave={handleSaveFile}
                projectId={project.id}
                streaming={streamingPath === fileDetail?.path}
                streamContent={fileDetail?.path ? streamBuffers[fileDetail.path] : undefined}
              />
            )}
            {mobileTab === 'preview' && (
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} githubUrl={project.github_repo_url || undefined} onRefresh={onRefresh} stack={project.target_stack} previewKey={previewKey} />
            )}
          </div>

          {/* Bottom drawers: desktop only — on mobile tabs provide navigation */}
          <div className="hidden md:block shrink-0">
            {/* Pipeline timeline drawer */}
            <div className="border-t border-[var(--border)]">
              <button
                onClick={() => setTimelineOpen(!timelineOpen)}
                className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] transition-colors"
              >
                <span className="flex items-center gap-1.5"><GitBranch size={12} /> Прогресс</span>
                <span>{timelineOpen ? '▼' : '▲'}</span>
              </button>
              {timelineOpen && (
                <div className="border-t border-[var(--border)] max-h-52 overflow-auto p-3">
                  {(() => {
                    const md = project.commits_md_content || '';
                    const parts = md.split(/\n(?=#{2,3}\s)/).filter((p) => p.trim());
                    const steps = parts.map((p, i) => {
                      const title = p.split('\n')[0].replace(/^#{2,3}\s+/, '').trim();
                      let status: 'done' | 'active' | 'waiting' | 'error' = 'waiting';
                      if (i < pipeline.step_index) status = 'done';
                      else if (i === pipeline.step_index) {
                        if (pipeline.status === 'running') status = 'active';
                        else if (pipeline.status === 'failed') status = 'error';
                      }
                      return { title, status };
                    });
                    const maxIter = (pipeline as { max_iterations?: number }).max_iterations ?? 3;
                    return parts.length > 0 ? (
                      <PipelineTimeline
                        steps={steps}
                        currentAgent={pipeline.status === 'running' ? currentAgent : ''}
                        iterationCount={pipeline.iteration_count}
                        maxIterations={maxIter}
                        elapsedSeconds={elapsedSeconds}
                      />
                    ) : (
                      <StepTimeline projectId={project.id} />
                    );
                  })()}
                </div>
              )}
            </div>

            {/* Agent log drawer */}
            <div className="border-t border-[var(--border)]">
              <button
                onClick={() => setLogOpen(!logOpen)}
                className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] transition-colors"
              >
                <span>Лог агентов</span>
                <span>{logOpen ? '▼' : '▲'}</span>
              </button>
              {logOpen && (
                <div className="h-40 border-t border-[var(--border)]">
                  <AgentLog projectId={project.id} lines={agentLogLines} />
                </div>
              )}
            </div>
          </div>
        </div>

      {chatOpen && (
        <div className={drawer.rootSm}>
          <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)]">
            <span className="text-sm font-medium">Чат с агентом</span>
            <button onClick={() => setChatOpen(false)} className="text-[var(--text-secondary)] hover:text-[var(--text)] text-xs">Закрыть</button>
          </div>
          <div className="flex-1 overflow-hidden">
            <ContextChat
              projectId={project.id}
              pauseReason={pipeline.pause_reason}
              resumeHint={pipeline.resume_hint}
              onResume={onRefresh}
            />
          </div>
        </div>
      )}

      {drawerAgent && (
        <StepDetailDrawer
          agentKey={drawerAgent}
          agentLabel={AGENT_LABELS[drawerAgent] ?? drawerAgent}
          pipeline={pipeline}
          stepText={stepText}
          onClose={() => setDrawerAgent(null)}
          projectId={project.id}
          stepIndex={pipeline.step_index}
        />
      )}

      {shortcutsOpen && <ShortcutsModal onClose={() => setShortcutsOpen(false)} />}

      {searchOpen && (
        <SearchFilesModal
          projectId={project.id}
          onClose={() => setSearchOpen(false)}
          onPick={(fileId) => handleFileSelect(fileId)}
        />
      )}

      {settingsOpen && (
        <ProjectSettingsModal
          project={project}
          onClose={() => setSettingsOpen(false)}
          onSaved={onRefresh}
        />
      )}

      {/* Status bar — desktop only */}
      <div className="hidden md:flex shrink-0 h-6 items-center gap-4 px-3 border-t border-[var(--border)] bg-[var(--hover)] text-xs text-[var(--text-secondary)] select-none">
        <span className={layout.statusBarItem}>{project.name}</span>
        <span className={layout.divider} />
        <span className={layout.statusBarItem}>
          Шаг {pipeline.step_index + 1}{' / '}{String(project.interview_data?.planned_steps ?? '?')}
        </span>
        <span className={layout.divider} />
        <span className={layout.statusBarItem}>
          {pipeline.status === 'running' ? 'Выполняется' :
           pipeline.status === 'completed' ? 'Завершён' :
           pipeline.status === 'paused_on_loop' || pipeline.status === 'paused_manual' ? 'Пауза' :
           pipeline.status === 'failed' ? 'Ошибка' : pipeline.status}
        </span>
        {!!project.stars_spent && (
          <>
            <span className={layout.divider} />
            <span className={layout.statusBarItem}>{project.stars_spent} звёзд</span>
          </>
        )}
      </div>

      {/* Mobile bottom tab bar — native-app style navigation */}
      <nav className="md:hidden shrink-0 flex items-stretch border-t border-[var(--border)] bg-[var(--bg)] z-10" style={{ height: '56px', paddingBottom: 'env(safe-area-inset-bottom)' }}>
        {MOBILE_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMobileTab(tab.key)}
            className={`flex-1 flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors ${
              mobileTab === tab.key
                ? 'text-blue-500'
                : 'text-[var(--text-secondary)]'
            }`}
          >
            <span className={`transition-transform ${mobileTab === tab.key ? 'scale-110' : ''}`}>
              {tab.icon}
            </span>
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
