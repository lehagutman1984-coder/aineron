'use client';

import { useState, useEffect } from 'react';
import { Play, Pause, Files, Code2, Monitor, CheckCircle, Download, ArrowLeft, Rocket, Share2, HelpCircle, Settings, GitBranch } from 'lucide-react';
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
  const [logOpen, setLogOpen] = useState(false);
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
  const [timelineOpen, setTimelineOpen] = useState(false);

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

  const handlePause = async () => {
    await studioApi.pause(project.id);
    onRefresh();
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

  const isPaused = pipeline.status === 'paused_on_loop' || pipeline.status === 'paused_manual';
  const isAwaitingApproval = pipeline.status === 'paused_manual';
  const isRunning = pipeline.status === 'running';
  const isCompleted = pipeline.status === 'completed';

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
        <SandboxStatusBadge projectId={project.id} projectStatus={project.status} />
        <div className={layout.divider} />
        <PipelineStatus
          projectStatus={project.status}
          pipelineStatus={pipeline.status}
          onStepClick={(key) => setDrawerAgent(key)}
        />
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
              className={btn.ghostXs}
            >
              <Pause size={14} />
              Пауза
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
      <div className="flex-1 overflow-hidden flex flex-col">
          {/* Desktop: resizable 3 columns */}
          <PanelGroup orientation="horizontal" className="hidden md:flex flex-1 overflow-hidden">
            <Panel defaultSize={18} minSize={12} className="overflow-hidden flex flex-col border-r border-[var(--border)]">
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
            <Panel defaultSize={41} minSize={20} className="overflow-hidden flex flex-col">
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
                <CodeViewer
                  content={fileDetail?.content ?? ''}
                  language={fileDetail?.language ?? 'text'}
                  path={fileDetail?.path}
                  editable={project.status !== 'completed'}
                  onSave={handleSaveFile}
                  projectId={project.id}
                />
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
            <Panel defaultSize={41} minSize={20} className="overflow-hidden flex flex-col">
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} githubUrl={project.github_repo_url || undefined} onRefresh={onRefresh} />
            </Panel>
          </PanelGroup>

          {/* Mobile: single active tab */}
          <div className="md:hidden flex-1 overflow-hidden">
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
              />
            )}
            {mobileTab === 'preview' && (
              <PreviewPanel projectId={project.id} hasSandbox={!!project.sandbox_container_id} status={project.status} githubUrl={project.github_repo_url || undefined} onRefresh={onRefresh} />
            )}
          </div>

          {/* Timeline drawer */}
          <div className="border-t border-[var(--border)] shrink-0">
            <button
              onClick={() => setTimelineOpen(!timelineOpen)}
              className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--hover)] transition-colors"
            >
              <span className="flex items-center gap-1.5"><GitBranch size={12} /> Таймлайн шагов</span>
              <span>{timelineOpen ? '▼' : '▲'}</span>
            </button>
            {timelineOpen && (
              <div className="border-t border-[var(--border)] max-h-40 overflow-auto">
                <StepTimeline projectId={project.id} />
              </div>
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

      {/* Status bar */}
      <div className={layout.statusBar}>
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
    </div>
  );
}
