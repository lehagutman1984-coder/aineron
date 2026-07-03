"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  ArrowLeft,
  Folder,
  MessageSquare,
  Plus,
  Trash2,
  Code2,
  ImageIcon,
  Settings,
  X,
  BookOpen,
  Briefcase,
  Zap,
  Globe,
  Palette,
  FileText,
  Eye,
  Pencil,
  Info,
  Check,
  ChevronDown,
  ChevronRight,
  Upload,
  File,
  FileCode2,
  FileType2,
  Loader2,
  AlertCircle,
  ToggleLeft,
  ToggleRight,
  GitBranch,
  Github,
  Link2,
  Link2Off,
  Share2,
  Lock,
  Copy,
  Send,
  Clock,
  CheckCircle2,
  XCircle,
  RefreshCw,
  FolderOpen,
  FileCode,
  Search,
  History,
  Users,
  UserPlus,
  ShieldCheck,
  ShieldOff,
  UserMinus,
  GitPullRequest,
  ExternalLink,
  Database,
  Rss,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  listProjects, listChats, deleteChat, updateProject,
  listProjectFiles, uploadProjectFile, deleteProjectFile, toggleProjectFile, searchProjectFiles,
  listConnectors, createConnector, deleteConnector,
  listRepoFiles, getRepoFileContent,
  listCommits, createCommit, confirmCommit, deleteCommit,
  publishProject, syncConnector, patchConnector,
  triggerDeploy, getDeployStatus,
  listFileVersions, restoreFileVersion,
  listCollaborators, addCollaborator, updateCollaboratorRole, removeCollaborator,
  listProjectAudit,
} from "@/lib/api/client";
import type { ChatListItem, Project, ProjectFile, ProjectConnector, ProjectCollaborator, ProjectAuditEntry, RepoTreeItem, ProjectCommit, CommitFile, DeployStatusResponse } from "@/lib/api/types";
import dynamic from "next/dynamic";

const CodeEditor = dynamic(() => import("@/components/projects/CodeEditor"), { ssr: false });

const ICON_MAP: Record<string, React.ElementType> = {
  Folder, Code2, BookOpen, Briefcase, Zap, Globe, Palette, MessageSquare,
};
const ICONS = Object.keys(ICON_MAP);
const COLORS = [
  "#D97757", "#22a85a", "#e67e22", "#E8C9A0",
  "#e74c3c", "#C4623E", "#1A1A1A", "#8B7E77",
];

const INSTRUCTION_TEMPLATES = [
  {
    label: "Программист",
    text: "Ты — опытный программист. Отвечай конкретно и кратко, приводи примеры кода. Предпочтительный язык — Python, если не указано иное.",
  },
  {
    label: "Переводчик",
    text: "Ты — профессиональный переводчик. Переводи точно и естественно, сохраняй стиль оригинала. При необходимости давай варианты перевода.",
  },
  {
    label: "Аналитик",
    text: "Ты — аналитик данных. Структурируй ответы, используй списки и таблицы. Опирайся на факты, избегай предположений без оговорок.",
  },
  {
    label: "Редактор",
    text: "Ты — опытный редактор текстов. Улучшай ясность, стиль и грамматику. Объясняй каждое изменение кратко.",
  },
  {
    label: "Исследователь",
    text: "Ты — исследователь. Изучай вопросы глубоко, приводи источники и разные точки зрения. Разграничивай установленные факты и гипотезы.",
  },
  {
    label: "Ассистент",
    text: "Ты — вежливый и точный ассистент. Отвечай на русском языке. Уточняй задачу, если она неоднозначна. Структурируй ответы для лёгкого чтения.",
  },
];

const CHAR_SOFT_LIMIT = 4000;

function ProjectIcon({ name, size = 16 }: { name: string; size?: number }) {
  const Icon = ICON_MAP[name] ?? Folder;
  return <Icon size={size} />;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  const h = Math.floor(diff / 3600000);
  const d = Math.floor(diff / 86400000);
  if (m < 1) return "только что";
  if (m < 60) return `${m} мин.`;
  if (h < 24) return `${h} ч.`;
  if (d < 7) return `${d} дн.`;
  return new Date(dateStr).toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
}

/* ── Модальное окно редактирования основных настроек проекта ── */
function EditProjectModal({
  project,
  onClose,
  onSaved,
}: {
  project: Project;
  onClose: () => void;
  onSaved: (p: Project) => void;
}) {
  const [name, setName] = useState(project.name);
  const [color, setColor] = useState(project.color ?? COLORS[0]);
  const [icon, setIcon] = useState(project.icon ?? "Folder");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await updateProject(project.id, { name: name.trim(), color, icon });
      onSaved(updated);
    } catch {
      setError("Не удалось сохранить изменения");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-[400px] rounded-[18px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[17px] font-semibold text-[#1A1A1A]">Настройки проекта</h2>
          <button onClick={onClose} className="rounded-[7px] p-1 text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
            <X size={15} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Название</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[16px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Иконка</label>
              <div className="flex flex-wrap gap-1.5">
                {ICONS.map((ic) => {
                  const Icon = ICON_MAP[ic];
                  return (
                    <button key={ic} type="button" onClick={() => setIcon(ic)}
                      className={["flex h-8 w-8 items-center justify-center rounded-[7px] transition-colors", icon === ic ? "ring-2 ring-[#D97757] ring-offset-1" : "border border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.05)]"].join(" ")}
                      style={{ color: icon === ic ? color : "var(--text-tertiary)" }}
                    >
                      <Icon size={15} />
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Цвет</label>
              <div className="flex flex-wrap gap-1.5">
                {COLORS.map((c) => (
                  <button key={c} type="button" onClick={() => setColor(c)}
                    className={["h-7 w-7 rounded-full transition-transform", color === c ? "scale-110 ring-2 ring-offset-1 ring-[rgba(13,13,13,0.25)]" : "hover:scale-105"].join(" ")}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[15px] text-[#e74c3c]">{error}</div>
          )}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose}
              className="rounded-[8px] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
              Отмена
            </button>
            <button type="submit" disabled={!name.trim() || loading}
              className="rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors">
              {loading ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── Вкладка "Чаты" ── */
function ChatsTab({ projectId, project }: { projectId: number; project: Project | undefined }) {
  const qc = useQueryClient();
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const { data: chats = [], isLoading } = useQuery({
    queryKey: ["chats", "project", projectId],
    queryFn: () => listChats({ project_id: projectId }),
    staleTime: 30_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteChat,
    onSuccess: (_, chatId) => {
      qc.setQueryData<ChatListItem[]>(["chats", "project", projectId], (prev) =>
        prev?.filter((c) => c.id !== chatId) ?? []
      );
      qc.invalidateQueries({ queryKey: ["chats"] });
      setDeletingId(null);
    },
  });

  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-16 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)]" />
        ))}
      </div>
    );
  }

  if (chats.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-[16px] border border-dashed border-[rgba(13,13,13,0.15)] py-14 text-center">
        <MessageSquare size={28} className="mb-3 text-[rgba(13,13,13,0.22)]" />
        <p className="mb-1 text-[16px] font-semibold text-[#1A1A1A]">Нет чатов</p>
        <p className="text-[15px] text-[rgba(13,13,13,0.45)]">
          Нажмите «Новый чат» выше, чтобы начать
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {chats.map((chat) => {
        const isDeleting = deletingId === chat.id;
        return (
          <div
            key={chat.id}
            className="group relative rounded-[12px] border border-[rgba(13,13,13,0.09)] bg-white p-4 transition-shadow hover:shadow-sm"
          >
            {isDeleting ? (
              <div className="flex items-center gap-2">
                <p className="flex-1 text-[15px] text-[rgba(13,13,13,0.65)]">Удалить этот чат?</p>
                <button
                  onClick={() => deleteMutation.mutate(chat.id)}
                  disabled={deleteMutation.isPending}
                  className="rounded-[6px] bg-[#e74c3c] px-2.5 py-1 text-[14px] font-medium text-white hover:bg-[#c0392b] disabled:opacity-50 transition-colors"
                >
                  Удалить
                </button>
                <button
                  onClick={() => setDeletingId(null)}
                  className="rounded-[6px] px-2.5 py-1 text-[14px] text-[rgba(13,13,13,0.50)] hover:bg-[rgba(13,13,13,0.06)] transition-colors"
                >
                  Отмена
                </button>
              </div>
            ) : (
              <Link href={`/chat/${chat.id}/`} className="flex items-start gap-3">
                <div className="mt-0.5 shrink-0">
                  {chat.network.avatar ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={chat.network.avatar} alt="" width={32} height={32} className="rounded-[7px] object-cover" />
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-[7px] bg-[rgba(217,119,87,0.10)]">
                      {chat.network.handle_photo || chat.network.handle_video ? (
                        <ImageIcon size={14} className="text-[#D97757]" />
                      ) : (
                        <Code2 size={14} className="text-[#D97757]" />
                      )}
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="truncate text-[16px] font-medium text-[#1A1A1A]">
                      {chat.title || chat.network.name}
                    </p>
                    <span className="shrink-0 text-[13px] text-[rgba(13,13,13,0.35)]">
                      {timeAgo(chat.updated_at)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.45)]">{chat.network.name}</p>
                  {chat.last_message && (
                    <p className="mt-1 truncate text-[14px] text-[rgba(13,13,13,0.40)]">
                      {chat.last_message.role === "user" ? "Вы: " : ""}
                      {chat.last_message.preview}
                    </p>
                  )}
                </div>
              </Link>
            )}
            {!isDeleting && (
              <button
                onClick={(e) => { e.preventDefault(); setDeletingId(chat.id); }}
                className="absolute right-3 top-3 hidden h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] transition-colors group-hover:flex"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Вкладка "Инструкции" ── */
function InstructionsTab({ project, onSaved }: { project: Project; onSaved: (p: Project) => void }) {
  const [value, setValue] = useState(project.system_prompt ?? "");
  const [preview, setPreview] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const charCount = value.length;
  const isOverLimit = charCount > CHAR_SOFT_LIMIT;

  // Сброс состояния "Сохранено" через 2 сек
  useEffect(() => {
    if (!saved) return;
    const t = setTimeout(() => setSaved(false), 2000);
    return () => clearTimeout(t);
  }, [saved]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const updated = await updateProject(project.id, { system_prompt: value.trim() });
      onSaved(updated);
      setSaved(true);
    } catch {
      setError("Не удалось сохранить инструкции");
    } finally {
      setSaving(false);
    }
  };

  const applyTemplate = (text: string) => {
    setValue(text);
    setPreview(false);
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Description */}
      <div className="flex items-start gap-2.5 rounded-[10px] bg-[rgba(217,119,87,0.06)] px-4 py-3">
        <Info size={14} className="mt-0.5 shrink-0 text-[#D97757]" />
        <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          Инструкции применяются ко всем чатам в этом проекте как системный промт.
          AI будет следовать им автоматически при каждом ответе.
        </p>
      </div>

      {/* Template chips */}
      <div>
        <p className="mb-2 text-[14px] font-medium text-[rgba(13,13,13,0.45)] uppercase tracking-wide">
          Шаблоны
        </p>
        <div className="flex flex-wrap gap-2">
          {INSTRUCTION_TEMPLATES.map((tpl) => (
            <button
              key={tpl.label}
              onClick={() => applyTemplate(tpl.text)}
              className="rounded-full border border-[rgba(13,13,13,0.14)] bg-white px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-all hover:border-[#D97757] hover:bg-[rgba(217,119,87,0.05)] hover:text-[#D97757]"
            >
              {tpl.label}
            </button>
          ))}
        </div>
      </div>

      {/* Editor / Preview toggle */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[14px] font-medium text-[rgba(13,13,13,0.45)] uppercase tracking-wide">
            Инструкции
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPreview(false)}
              className={["flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors", !preview ? "bg-[rgba(13,13,13,0.07)] text-[#1A1A1A]" : "text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A]"].join(" ")}
            >
              <Pencil size={11} />
              Редактор
            </button>
            <button
              onClick={() => setPreview(true)}
              className={["flex items-center gap-1 rounded-[6px] px-2.5 py-1 text-[14px] font-medium transition-colors", preview ? "bg-[rgba(13,13,13,0.07)] text-[#1A1A1A]" : "text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A]"].join(" ")}
            >
              <Eye size={11} />
              Предпросмотр
            </button>
          </div>
        </div>

        {preview ? (
          <div className="min-h-[220px] rounded-[10px] border border-[rgba(13,13,13,0.12)] bg-[rgba(13,13,13,0.02)] px-4 py-3">
            {value.trim() ? (
              <div className="prose prose-sm max-w-none text-[15px] text-[#1A1A1A]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-[15px] text-[rgba(13,13,13,0.35)] italic">Инструкции не заданы</p>
            )}
          </div>
        ) : (
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={`Ты — опытный программист. Отвечай на русском языке, приводи примеры кода...\n\nМожно описать:\n• Роль и стиль ответов AI\n• Предпочтительный формат вывода\n• Язык, тональность, ограничения`}
              rows={10}
              className="w-full resize-none rounded-[10px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-3 text-[15px] leading-relaxed text-[#1A1A1A] outline-none placeholder-[rgba(13,13,13,0.32)] focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
            <span
              className={[
                "absolute bottom-3 right-3 text-[13px] tabular-nums transition-colors",
                isOverLimit ? "text-[#e74c3c] font-medium" : "text-[rgba(13,13,13,0.32)]",
              ].join(" ")}
            >
              {charCount.toLocaleString("ru-RU")} / {CHAR_SOFT_LIMIT.toLocaleString("ru-RU")}
            </span>
          </div>
        )}
      </div>

      {/* Soft limit warning */}
      {isOverLimit && (
        <div className="flex items-start gap-2 rounded-[8px] bg-[rgba(231,76,60,0.07)] px-3 py-2.5">
          <Info size={13} className="mt-0.5 shrink-0 text-[#e74c3c]" />
          <p className="text-[14px] text-[#e74c3c]">
            Инструкция превышает рекомендуемый лимит 4 000 символов. Длинный промт уменьшает доступный контекст для диалога.
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[15px] text-[#e74c3c]">{error}</div>
      )}

      {/* Save button */}
      <div className="flex items-center justify-between">
        <p className="text-[14px] text-[rgba(13,13,13,0.40)]">
          Применяется ко всем чатам в проекте автоматически
        </p>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
        >
          {saved ? (
            <>
              <Check size={13} />
              Сохранено
            </>
          ) : saving ? (
            "Сохранение..."
          ) : (
            "Сохранить инструкции"
          )}
        </button>
      </div>
    </div>
  );
}

/* ── Вкладка "Файлы" ── */
function FilesTab({ projectId }: { projectId: number }) {
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [versionFileId, setVersionFileId] = useState<number | null>(null);
  const [restoringVersionId, setRestoringVersionId] = useState<number | null>(null);

  const { data: files = [], isLoading } = useQuery({
    queryKey: ["project-files", projectId],
    queryFn: () => listProjectFiles(projectId),
    staleTime: 30_000,
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      return data.some((f: ProjectFile) => f.status === "processing") ? 3000 : false;
    },
  });

  const { data: searchResults, isLoading: isSearching } = useQuery({
    queryKey: ["project-files-search", projectId, searchQuery],
    queryFn: () => searchProjectFiles(projectId, searchQuery),
    enabled: searchActive && searchQuery.trim().length >= 2,
    staleTime: 10_000,
  });

  const displayedFiles = searchActive && searchQuery.trim().length >= 2
    ? (searchResults ?? [])
    : files;

  const { data: fileVersions = [], isLoading: versionsLoading } = useQuery({
    queryKey: ["file-versions", projectId, versionFileId],
    queryFn: () => listFileVersions(projectId, versionFileId!),
    enabled: versionFileId !== null,
    staleTime: 30_000,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadProjectFile(projectId, file),
    onSuccess: (newFile) => {
      qc.setQueryData<ProjectFile[]>(["project-files", projectId], (prev) =>
        prev ? [...prev, newFile] : [newFile]
      );
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      toggleProjectFile(projectId, id, enabled),
    onSuccess: (updated) => {
      qc.setQueryData<ProjectFile[]>(["project-files", projectId], (prev) =>
        prev?.map((f) => (f.id === updated.id ? updated : f)) ?? []
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteProjectFile(projectId, id),
    onSuccess: (_, id) => {
      qc.setQueryData<ProjectFile[]>(["project-files", projectId], (prev) =>
        prev?.filter((f) => f.id !== id) ?? []
      );
      setDeletingId(null);
    },
  });

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    Array.from(fileList).forEach((f) => uploadMutation.mutate(f));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  function FileTypeIcon({ type }: { type: ProjectFile["file_type"] }) {
    if (type === "pdf") return <FileType2 size={16} className="text-[#e74c3c]" />;
    if (type === "code") return <FileCode2 size={16} className="text-[#D97757]" />;
    if (type === "doc") return <File size={16} className="text-[#D97757]" />;
    if (type === "text") return <FileText size={16} className="text-[rgba(13,13,13,0.45)]" />;
    return <File size={16} className="text-[rgba(13,13,13,0.35)]" />;
  }

  function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} Б`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
    return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Description */}
      <div className="flex items-start gap-2.5 rounded-[10px] bg-[rgba(217,119,87,0.06)] px-4 py-3">
        <Info size={14} className="mt-0.5 shrink-0 text-[#D97757]" />
        <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          Загруженные файлы автоматически читаются AI в каждом чате проекта как база знаний.
          Поддерживаются PDF, Word, текст, код (до 20 МБ, макс. 20 файлов).
        </p>
      </div>

      {/* Search */}
      {files.length > 0 && (
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)]" />
          <input
            type="text"
            placeholder="Поиск по файлам..."
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setSearchActive(true); }}
            onBlur={() => { if (!searchQuery.trim()) setSearchActive(false); }}
            className="w-full rounded-[8px] border border-[rgba(13,13,13,0.1)] bg-white py-2 pl-8 pr-3 text-[15px] text-[#1A1A1A] placeholder:text-[rgba(13,13,13,0.35)] focus:border-[rgba(13,13,13,0.25)] focus:outline-none"
          />
          {isSearching && (
            <Loader2 size={12} className="absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-[rgba(13,13,13,0.35)]" />
          )}
        </div>
      )}

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={[
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-[12px] border-2 border-dashed py-8 transition-all",
          dragOver
            ? "border-[#D97757] bg-[rgba(217,119,87,0.06)]"
            : "border-[rgba(13,13,13,0.14)] bg-[rgba(13,13,13,0.01)] hover:border-[rgba(13,13,13,0.25)] hover:bg-[rgba(13,13,13,0.02)]",
        ].join(" ")}
      >
        <Upload size={22} className={dragOver ? "text-[#D97757]" : "text-[rgba(13,13,13,0.30)]"} />
        <p className="text-[15px] font-medium text-[rgba(13,13,13,0.65)]">
          {dragOver ? "Отпустите для загрузки" : "Перетащите файлы или нажмите для выбора"}
        </p>
        <p className="text-[13px] text-[rgba(13,13,13,0.35)]">
          PDF, DOCX, TXT, MD, PY, JS, TS, JSON и другие — до 20 МБ
        </p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.txt,.md,.rst,.py,.js,.ts,.tsx,.jsx,.html,.css,.json,.yaml,.yml,.toml,.ini,.sh,.sql,.doc,.docx,.odt,.rtf,.csv,.xml"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Upload error */}
      {uploadMutation.error && (
        <div className="flex items-center gap-2 rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[15px] text-[#e74c3c]">
          <AlertCircle size={14} />
          {(uploadMutation.error as Error).message ?? "Ошибка загрузки"}
        </div>
      )}

      {/* File list */}
      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-[10px] bg-[rgba(13,13,13,0.05)]" />
          ))}
        </div>
      ) : displayedFiles.length === 0 ? (
        <p className="py-4 text-center text-[15px] text-[rgba(13,13,13,0.38)]">
          {searchActive && searchQuery.trim() ? "Ничего не найдено" : "Файлы не загружены"}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          {displayedFiles.map((f) => {
            const isDeleting = deletingId === f.id;
            return (
              <div key={f.id}>
              <div
                className={[
                  "group flex items-center gap-3 rounded-[10px] border p-3.5 transition-all",
                  f.enabled
                    ? "border-[rgba(13,13,13,0.09)] bg-white"
                    : "border-[rgba(13,13,13,0.06)] bg-[rgba(13,13,13,0.02)] opacity-60",
                ].join(" ")}
              >
                <div className="shrink-0">
                  <FileTypeIcon type={f.file_type} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-medium text-[#1A1A1A]">{f.filename}</p>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="text-[13px] text-[rgba(13,13,13,0.40)]">{formatBytes(f.file_size)}</span>
                    {f.status === "processing" && (
                      <span className="flex items-center gap-1 text-[13px] text-[rgba(13,13,13,0.45)]">
                        <Loader2 size={10} className="animate-spin" />
                        Обработка...
                      </span>
                    )}
                    {f.status === "ready" && (
                      <span className="flex items-center gap-1 text-[13px] text-[#22a85a]">
                        <Check size={10} />
                        Готов
                      </span>
                    )}
                    {f.status === "error" && (
                      <span className="flex items-center gap-1 text-[13px] text-[#e74c3c]">
                        <AlertCircle size={10} />
                        Ошибка
                      </span>
                    )}
                    {f.embed_status === "error" && (
                      <span className="flex items-center gap-1 text-[13px] text-[rgba(231,76,60,0.7)]">
                        <AlertCircle size={10} />
                        Индекс: ошибка
                      </span>
                    )}
                    {f.usage_hits > 0 && (
                      <span className="text-[13px] text-[rgba(13,13,13,0.35)]">
                        {f.usage_hits} {f.usage_hits === 1 ? "использование" : f.usage_hits < 5 ? "использования" : "использований"}
                      </span>
                    )}
                  </div>
                </div>

                {isDeleting ? (
                  <div className="flex shrink-0 items-center gap-1">
                    <button
                      onClick={() => deleteMutation.mutate(f.id)}
                      disabled={deleteMutation.isPending}
                      className="rounded-[6px] bg-[#e74c3c] px-2.5 py-1 text-[13px] font-medium text-white hover:bg-[#c0392b] disabled:opacity-50 transition-colors"
                    >
                      Удалить
                    </button>
                    <button
                      onClick={() => setDeletingId(null)}
                      className="rounded-[6px] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.45)] hover:bg-[rgba(13,13,13,0.06)] transition-colors"
                    >
                      Отмена
                    </button>
                  </div>
                ) : (
                  <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    {/* Toggle enabled */}
                    <button
                      onClick={() => toggleMutation.mutate({ id: f.id, enabled: !f.enabled })}
                      className="rounded-[6px] p-1.5 text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] transition-colors"
                      title={f.enabled ? "Отключить" : "Включить"}
                    >
                      {f.enabled
                        ? <ToggleRight size={16} className="text-[#D97757]" />
                        : <ToggleLeft size={16} />
                      }
                    </button>
                    {/* Version history (only for repo files) */}
                    {f.source === "repo" && (
                      <button
                        onClick={() => setVersionFileId(versionFileId === f.id ? null : f.id)}
                        className={[
                          "rounded-[6px] p-1.5 transition-colors",
                          versionFileId === f.id
                            ? "bg-[rgba(217,119,87,0.12)] text-[#D97757]"
                            : "text-[rgba(13,13,13,0.35)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A]",
                        ].join(" ")}
                        title="История версий"
                      >
                        <History size={14} />
                      </button>
                    )}
                    {/* Delete */}
                    <button
                      onClick={() => setDeletingId(f.id)}
                      className="rounded-[6px] p-1.5 text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] transition-colors"
                      title="Удалить файл"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                )}
              </div>

              {/* Inline version history panel */}
              {versionFileId === f.id && (
                <div className="mt-1 rounded-[8px] border border-[rgba(13,13,13,0.09)] bg-[rgba(13,13,13,0.02)] p-3">
                  <p className="mb-2 text-[13px] font-semibold text-[rgba(13,13,13,0.6)]">История версий</p>
                  {versionsLoading ? (
                    <div className="h-10 animate-pulse rounded-[6px] bg-[rgba(13,13,13,0.06)]" />
                  ) : fileVersions.length === 0 ? (
                    <p className="text-[13px] text-[rgba(13,13,13,0.40)]">Снапшотов нет</p>
                  ) : (
                    <div className="flex flex-col gap-1.5">
                      {fileVersions.map((v) => (
                        <div key={v.id} className="flex items-center gap-3 rounded-[6px] bg-white px-2.5 py-1.5">
                          <div className="min-w-0 flex-1">
                            <p className="text-[13px] font-medium text-[#1A1A1A]">
                              {new Date(v.created_at).toLocaleString("ru")}
                              {v.repo_sha && <span className="ml-1.5 text-[rgba(13,13,13,0.40)]">· {v.repo_sha.slice(0, 7)}</span>}
                            </p>
                            <p className="truncate text-[12px] text-[rgba(13,13,13,0.40)]">{v.content_preview}</p>
                          </div>
                          <span className="shrink-0 text-[12px] text-[rgba(13,13,13,0.35)]">{(v.size / 1024).toFixed(1)} KB</span>
                          <button
                            onClick={async () => {
                              setRestoringVersionId(v.id);
                              try {
                                await restoreFileVersion(projectId, f.id, v.id);
                                qc.invalidateQueries({ queryKey: ["project-files", projectId] });
                                qc.invalidateQueries({ queryKey: ["file-versions", projectId, f.id] });
                                setVersionFileId(null);
                              } finally {
                                setRestoringVersionId(null);
                              }
                            }}
                            disabled={restoringVersionId === v.id}
                            className="shrink-0 rounded-[5px] border border-[rgba(13,13,13,0.14)] px-2 py-0.5 text-[12px] font-medium text-[rgba(13,13,13,0.55)] transition-colors hover:border-[#D97757] hover:text-[#D97757] disabled:opacity-50"
                          >
                            {restoringVersionId === v.id ? "..." : "Восстановить"}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Компоненты браузера файлов (вне ConnectorsTab, иначе React ремаунтит при каждом рендере) ── */
function CommitStatusBadge({ status }: { status: ProjectCommit["status"] }) {
  if (status === "pending") return <span className="flex items-center gap-1 text-[13px] text-[rgba(13,13,13,0.55)]"><Clock size={10} />Ожидает</span>;
  if (status === "pushed") return <span className="flex items-center gap-1 text-[13px] text-[#22a85a]"><CheckCircle2 size={10} />Запушен</span>;
  if (status === "rejected") return <span className="flex items-center gap-1 text-[13px] text-[rgba(13,13,13,0.40)]"><XCircle size={10} />Отклонён</span>;
  if (status === "failed") return <span className="flex items-center gap-1 text-[13px] text-[#e74c3c]"><XCircle size={10} />Ошибка</span>;
  return null;
}

function TreeNode({ item, depth, childrenMap, connId, openDirs, selectedFile, onToggleDir, onSelectFile }: {
  item: RepoTreeItem;
  depth: number;
  childrenMap: Record<string, RepoTreeItem[]>;
  connId: number;
  openDirs: Set<string>;
  selectedFile: string | null;
  onToggleDir: (path: string) => void;
  onSelectFile: (path: string, connId: number) => void;
}) {
  const isDir = item.type === "dir";
  const isOpen = openDirs.has(item.path);
  const children = childrenMap[item.path] ?? [];
  const isSelected = selectedFile === item.path;
  return (
    <div>
      <button
        onClick={() => isDir ? onToggleDir(item.path) : onSelectFile(item.path, connId)}
        className={[
          "flex w-full items-center gap-1.5 rounded-[5px] px-2 py-1 text-left text-[14px] transition-colors",
          isSelected ? "bg-[rgba(217,119,87,0.10)] text-[#D97757]" : "text-[rgba(13,13,13,0.75)] hover:bg-[rgba(13,13,13,0.05)]",
        ].join(" ")}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        {isDir ? (
          <>
            {isOpen ? <ChevronDown size={11} className="shrink-0" /> : <ChevronRight size={11} className="shrink-0" />}
            {isOpen ? <FolderOpen size={12} className="shrink-0 text-[#e67e22]" /> : <Folder size={12} className="shrink-0 text-[#e67e22]" />}
          </>
        ) : (
          <>
            <span className="w-[11px] shrink-0" />
            <FileCode size={11} className="shrink-0 text-[rgba(13,13,13,0.40)]" />
          </>
        )}
        <span className="truncate">{item.path.split("/").pop()}</span>
      </button>
      {isDir && isOpen && children.map((child) => (
        <TreeNode key={child.path} item={child} depth={depth + 1} childrenMap={childrenMap}
          connId={connId} openDirs={openDirs} selectedFile={selectedFile}
          onToggleDir={onToggleDir} onSelectFile={onSelectFile} />
      ))}
    </div>
  );
}

/* ── Вкладка "Коннекторы" (Git) ── */
function ConnectorsTab({ projectId }: { projectId: number }) {
  const qc = useQueryClient();
  const [showConnectForm, setShowConnectForm] = useState(false);
  const [connType, setConnType] = useState<"github" | "gitea" | "website" | "rss">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [pat, setPat] = useState("");
  const [branch, setBranch] = useState("main");
  const [connectErr, setConnectErr] = useState<string | null>(null);
  const [connectLoading, setConnectLoading] = useState(false);

  // File browser state
  const [browsingId, setBrowsingId] = useState<number | null>(null);
  const [openDirs, setOpenDirs] = useState<Set<string>>(new Set());
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string | null>(null);
  const [fileLoading, setFileLoading] = useState(false);

  // New commit state
  const [showCommitModal, setShowCommitModal] = useState(false);
  const [commitConnId, setCommitConnId] = useState<number | null>(null);
  const [commitMsg, setCommitMsg] = useState("");
  const [commitFiles, setCommitFiles] = useState<CommitFile[]>([{ path: "", content: "" }]);
  const [commitLoading, setCommitLoading] = useState(false);
  const [commitErr, setCommitErr] = useState<string | null>(null);
  // Sprint 4.2 — sync state
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [copiedWebhook, setCopiedWebhook] = useState<number | null>(null);
  // Sprint 7.2 — deploy state
  const [deployingId, setDeployingId] = useState<number | null>(null);
  const [deployStatus, setDeployStatus] = useState<Record<number, DeployStatusResponse>>({});
  // Sprint 7.1 — editor state
  const [editorConnId, setEditorConnId] = useState<number | null>(null);

  const handleSync = async (connId: number) => {
    setSyncingId(connId);
    try {
      await syncConnector(projectId, connId);
      // Poll for result up to 45 seconds
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await qc.invalidateQueries({ queryKey: ["connectors", projectId] });
        const updated = qc.getQueryData<typeof connectors>(["connectors", projectId]);
        const conn = updated?.find((c) => c.id === connId);
        if (conn?.last_synced_at || attempts >= 15) {
          clearInterval(poll);
          setSyncingId(null);
        }
      }, 3000);
    } catch {
      setSyncingId(null);
    }
  };

  // Sprint 7.2: Deploy handler
  const handleDeploy = async (connId: number) => {
    setDeployingId(connId);
    setDeployStatus((prev) => ({ ...prev, [connId]: { deploy_status: "pending", last_deploy_at: null, last_deploy_log: "" } }));
    try {
      const result = await triggerDeploy(projectId, connId);
      setDeployStatus((prev) => ({ ...prev, [connId]: result }));
    } catch (e) {
      setDeployStatus((prev) => ({
        ...prev,
        [connId]: { deploy_status: "error", last_deploy_at: null, last_deploy_log: (e as Error).message ?? "Ошибка деплоя" },
      }));
    } finally {
      setDeployingId(null);
    }
  };

  const { data: connectors = [], isLoading: connLoading } = useQuery({
    queryKey: ["connectors", projectId],
    queryFn: () => listConnectors(projectId),
    staleTime: 60_000,
  });

  const { data: treeData, isLoading: treeLoading } = useQuery({
    queryKey: ["repo-tree", projectId, browsingId],
    queryFn: () => browsingId ? listRepoFiles(projectId, browsingId) : null,
    enabled: browsingId !== null,
    staleTime: 120_000,
  });

  const { data: commits = [], isLoading: commitsLoading } = useQuery({
    queryKey: ["commits", projectId],
    queryFn: () => listCommits(projectId),
    staleTime: 15_000,
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      return data.some((c: ProjectCommit) => c.status === "pending") ? 5000 : false;
    },
  });

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setConnectErr(null);
    setConnectLoading(true);
    try {
      const isGit = connType === "github" || connType === "gitea";
      const conn = await createConnector(projectId, {
        connector_type: connType,
        repo_url: repoUrl.trim(),
        access_token: isGit ? pat.trim() : "",
        branch: isGit ? branch.trim() || "main" : "",
      });
      qc.setQueryData<ProjectConnector[]>(["connectors", projectId], (prev) =>
        prev ? [...prev.filter((c) => c.id !== conn.id), conn] : [conn]
      );
      setShowConnectForm(false);
      setRepoUrl(""); setPat(""); setBranch("main");
    } catch (err) {
      setConnectErr((err as Error).message ?? "Не удалось подключить репозиторий");
    } finally {
      setConnectLoading(false);
    }
  };

  const disconnectMutation = useMutation({
    mutationFn: (id: number) => deleteConnector(projectId, id),
    onSuccess: (_, id) => {
      qc.setQueryData<ProjectConnector[]>(["connectors", projectId], (prev) =>
        prev?.filter((c) => c.id !== id) ?? []
      );
      if (browsingId === id) setBrowsingId(null);
    },
  });

  const handleFileClick = async (path: string, connId: number) => {
    if (selectedFile === path) { setSelectedFile(null); setFileContent(null); setEditorConnId(null); return; }
    setSelectedFile(path);
    setFileContent(null);
    setEditorConnId(connId);
    setFileLoading(true);
    try {
      const res = await getRepoFileContent(projectId, connId, path);
      setFileContent(res.content);
    } catch {
      setFileContent("Не удалось загрузить содержимое файла");
    } finally {
      setFileLoading(false);
    }
  };

  const handleConfirm = async (commitId: number, action: "push" | "pr" | "reject") => {
    try {
      await confirmCommit(projectId, commitId, action);
      qc.invalidateQueries({ queryKey: ["commits", projectId] });
    } catch {}
  };

  const handleDelete = async (commitId: number) => {
    try {
      await deleteCommit(projectId, commitId);
      qc.invalidateQueries({ queryKey: ["commits", projectId] });
    } catch {}
  };

  const handlePropose = async (e: React.FormEvent) => {
    e.preventDefault();
    const validFiles = commitFiles.filter((f) => f.path.trim() && f.content.trim());
    if (!commitMsg.trim() || validFiles.length === 0) return;
    setCommitLoading(true);
    setCommitErr(null);
    try {
      const c = await createCommit(projectId, {
        connector_id: commitConnId ?? undefined,
        commit_message: commitMsg.trim(),
        files: validFiles,
      });
      qc.setQueryData<ProjectCommit[]>(["commits", projectId], (prev) =>
        prev ? [c, ...prev] : [c]
      );
      setShowCommitModal(false);
      setCommitMsg(""); setCommitFiles([{ path: "", content: "" }]); setCommitConnId(null);
    } catch (err) {
      setCommitErr((err as Error).message ?? "Ошибка создания коммита");
    } finally {
      setCommitLoading(false);
    }
  };

  function buildTree(items: RepoTreeItem[]) {
    const dirs = new Set(items.filter((i) => i.type === "dir").map((i) => i.path));
    const roots: RepoTreeItem[] = [];
    const childrenMap: Record<string, RepoTreeItem[]> = {};
    for (const item of items) {
      const parts = item.path.split("/");
      if (parts.length === 1) { roots.push(item); continue; }
      const parent = parts.slice(0, -1).join("/");
      if (!childrenMap[parent]) childrenMap[parent] = [];
      childrenMap[parent].push(item);
    }
    return { roots, childrenMap, dirs };
  }

  const activeConnector = browsingId ? connectors.find((c) => c.id === browsingId) : null;
  const tree = treeData ? buildTree(treeData.items) : null;

  return (
    <div className="flex flex-col gap-6">
      {/* Description */}
      <div className="flex items-start gap-2.5 rounded-[10px] bg-[rgba(217,119,87,0.06)] px-4 py-3">
        <Info size={14} className="mt-0.5 shrink-0 text-[#D97757]" />
        <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          Подключите GitHub или Gitea-репозиторий: просматривайте файлы и пушьте изменения прямо из проекта.
        </p>
      </div>

      {/* Connectors list */}
      {connLoading ? (
        <div className="h-16 animate-pulse rounded-[10px] bg-[rgba(13,13,13,0.05)]" />
      ) : (
        <div className="flex flex-col gap-3">
          {connectors.map((conn) => (
            <div key={conn.id} className="rounded-[12px] border border-[rgba(13,13,13,0.10)] bg-white p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                <div className="flex items-start gap-3 min-w-0 flex-1">
                  {conn.connector_type === "github"
                    ? <Github size={16} className="mt-0.5 shrink-0 text-[#1A1A1A]" />
                    : conn.connector_type === "website"
                    ? <Globe size={16} className="mt-0.5 shrink-0 text-[#2980b9]" />
                    : conn.connector_type === "rss"
                    ? <Rss size={16} className="mt-0.5 shrink-0 text-[#e67e22]" />
                    : <GitBranch size={16} className="mt-0.5 shrink-0 text-[#e67e22]" />
                  }
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[16px] font-semibold text-[#1A1A1A] break-all">{conn.owner}/{conn.repo}</p>
                      {conn.sync_status === "ok" && (
                        <span className="rounded-full bg-[rgba(34,168,90,0.12)] px-2 py-0.5 text-[12px] font-medium text-[#22a85a] whitespace-nowrap">
                          синк OK{conn.last_sync_report?.created ? ` · +${conn.last_sync_report.created}` : ""}
                        </span>
                      )}
                      {conn.sync_status === "error" && (
                        <span
                          className="rounded-full bg-[rgba(231,76,60,0.10)] px-2 py-0.5 text-[12px] font-medium text-[#e74c3c] cursor-help whitespace-nowrap"
                          title={conn.last_sync_report?.error_detail || conn.last_sync_report?.error || "Ошибка синхронизации"}
                        >
                          синк ошибка
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[13px] leading-relaxed text-[rgba(13,13,13,0.45)]">
                      {conn.connector_type === "github" ? "GitHub"
                        : conn.connector_type === "website" ? "Сайт"
                        : conn.connector_type === "rss" ? "RSS"
                        : "Gitea"}
                      {(conn.connector_type === "github" || conn.connector_type === "gitea") && <> · ветка {conn.branch}</>}
                      {conn.last_synced_at && <> · синхронизировано {new Date(conn.last_synced_at).toLocaleString("ru")}</>}
                      {conn.last_sync_report?.created != null && conn.last_sync_report.created > 0 && (
                        <> · <span className="text-[#22a85a]">{conn.last_sync_report.created} новых файлов</span></>
                      )}
                      {conn.last_sync_report?.updated != null && conn.last_sync_report.updated > 0 && (
                        <> · {conn.last_sync_report.updated} обновлено</>
                      )}
                      {conn.last_sync_report?.errors != null && conn.last_sync_report.errors > 0 && (
                        <> · <span className="text-[#e74c3c]">{conn.last_sync_report.errors} ошибок</span></>
                      )}
                    </p>
                    {conn.webhook_url && (
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <span className="text-[12px] text-[rgba(13,13,13,0.40)]">Webhook:</span>
                        <code className="max-w-[200px] truncate rounded-[4px] bg-[rgba(13,13,13,0.05)] px-1.5 py-0.5 text-[12px] text-[rgba(13,13,13,0.55)]">{conn.webhook_url}</code>
                        <button
                          onClick={() => { navigator.clipboard.writeText(conn.webhook_url); setCopiedWebhook(conn.id); setTimeout(() => setCopiedWebhook(null), 1800); }}
                          className="text-[rgba(13,13,13,0.35)] hover:text-[#D97757]"
                          title="Скопировать webhook URL"
                        >
                          {copiedWebhook === conn.id ? <CheckCircle2 size={11} /> : <Copy size={11} />}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                {/* Кнопки — переносятся на новую строку на мобильном */}
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => handleSync(conn.id)}
                    disabled={syncingId === conn.id}
                    className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.14)] px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[#D97757] hover:text-[#D97757] disabled:opacity-50 whitespace-nowrap"
                    title="Синхронизировать файлы из репозитория в базу знаний"
                  >
                    <RefreshCw size={11} className={syncingId === conn.id ? "animate-spin" : ""} />
                    {syncingId === conn.id ? "Синхронизация..." : "Синхронизировать"}
                  </button>
                  <button
                    onClick={() => { setBrowsingId(conn.id === browsingId ? null : conn.id); setSelectedFile(null); setFileContent(null); setOpenDirs(new Set()); }}
                    className={[
                      "flex items-center gap-1.5 rounded-[7px] px-3 py-1.5 text-[14px] font-medium transition-colors whitespace-nowrap",
                      browsingId === conn.id
                        ? "bg-[rgba(217,119,87,0.12)] text-[#D97757]"
                        : "border border-[rgba(13,13,13,0.14)] text-[rgba(13,13,13,0.65)] hover:border-[#D97757] hover:text-[#D97757]",
                    ].join(" ")}
                  >
                    <FolderOpen size={12} />
                    Файлы
                  </button>
                  <button
                    onClick={() => { setCommitConnId(conn.id); setShowCommitModal(true); }}
                    className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.14)] px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[#22a85a] hover:text-[#22a85a] whitespace-nowrap"
                  >
                    <Send size={11} />
                    Коммит
                  </button>
                  {conn.deploy_webhook_url && (
                    <button
                      onClick={() => handleDeploy(conn.id)}
                      disabled={deployingId === conn.id}
                      className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.14)] px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[#D97757] hover:text-[#D97757] disabled:opacity-50 whitespace-nowrap"
                      title="Запустить деплой"
                    >
                      {deployingId === conn.id ? (
                        <Loader2 size={11} className="animate-spin" />
                      ) : deployStatus[conn.id]?.deploy_status === "success" ? (
                        <CheckCircle2 size={11} className="text-[#22a85a]" />
                      ) : deployStatus[conn.id]?.deploy_status === "error" ? (
                        <AlertCircle size={11} className="text-red-500" />
                      ) : (
                        <Zap size={11} />
                      )}
                      Deploy
                    </button>
                  )}
                  <button
                    onClick={async () => {
                      await patchConnector(projectId, conn.id, { auto_sync: !conn.auto_sync });
                      qc.invalidateQueries({ queryKey: ["connectors", projectId] });
                    }}
                    className={[
                      "flex items-center gap-1.5 rounded-[7px] px-2.5 py-1.5 text-[13px] font-medium transition-colors",
                      conn.auto_sync
                        ? "bg-[rgba(217,119,87,0.10)] text-[#D97757]"
                        : "border border-[rgba(13,13,13,0.14)] text-[rgba(13,13,13,0.40)]",
                    ].join(" ")}
                    title={conn.auto_sync ? "Авто-синк включён" : "Авто-синк отключён"}
                  >
                    <RefreshCw size={10} />
                    Авто
                  </button>
                  <button
                    onClick={() => disconnectMutation.mutate(conn.id)}
                    disabled={disconnectMutation.isPending}
                    className="flex items-center gap-1 rounded-[7px] p-1.5 text-[rgba(13,13,13,0.35)] transition-colors hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c]"
                    title="Отключить"
                  >
                    <Link2Off size={14} />
                  </button>
                </div>
              </div>

              {/* File browser inline */}
              {browsingId === conn.id && (
                <div className="mt-4 rounded-[8px] border border-[rgba(13,13,13,0.09)] overflow-hidden">
                  <div className="flex flex-col md:flex-row" style={{ minHeight: 400 }}>
                    {/* Tree panel — полная ширина на мобильном, фиксированная на десктопе */}
                    <div className="w-full md:w-[240px] shrink-0 overflow-y-auto border-b border-[rgba(13,13,13,0.08)] md:border-b-0 md:border-r py-1 max-h-[260px] md:max-h-none">
                      {treeLoading ? (
                        <div className="flex items-center justify-center py-8 text-[14px] text-[rgba(13,13,13,0.40)]">
                          <Loader2 size={14} className="mr-1.5 animate-spin" />
                          Загрузка...
                        </div>
                      ) : tree && tree.roots.length > 0 ? (
                        tree.roots.map((item) => (
                          <TreeNode key={item.path} item={item} depth={0} childrenMap={tree.childrenMap}
                            connId={conn.id} openDirs={openDirs} selectedFile={selectedFile}
                            onToggleDir={(p) => setOpenDirs((prev) => { const n = new Set(prev); n.has(p) ? n.delete(p) : n.add(p); return n; })}
                            onSelectFile={handleFileClick} />
                        ))
                      ) : (
                        <p className="px-3 py-6 text-center text-[14px] text-[rgba(13,13,13,0.38)]">Репозиторий пуст</p>
                      )}
                    </div>
                    {/* Content panel */}
                    <div className="flex flex-col flex-1 overflow-hidden min-h-[320px] md:min-h-[500px]">
                      {selectedFile && editorConnId === conn.id ? (
                        fileLoading ? (
                          <div className="flex items-center justify-center py-10 text-[14px] text-[rgba(13,13,13,0.40)]">
                            <Loader2 size={14} className="mr-1.5 animate-spin" />
                            Загрузка...
                          </div>
                        ) : (
                          <CodeEditor
                            filePath={selectedFile}
                            initialContent={fileContent ?? ""}
                            onClose={() => { setSelectedFile(null); setFileContent(null); setEditorConnId(null); }}
                            onCommit={async (content, message) => {
                              await createCommit(projectId, {
                                connector_id: conn.id,
                                commit_message: message,
                                files: [{ path: selectedFile!, content }],
                              });
                              qc.invalidateQueries({ queryKey: ["commits", projectId] });
                            }}
                          />
                        )
                      ) : (
                        <div className="flex h-full items-center justify-center py-10 text-[14px] text-[rgba(13,13,13,0.35)]">
                          Выберите файл в дереве слева
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Connect button */}
          {!showConnectForm && connectors.length < 3 && (
            <button
              onClick={() => setShowConnectForm(true)}
              className="flex items-center gap-2 rounded-[10px] border border-dashed border-[rgba(13,13,13,0.16)] px-4 py-3.5 text-[15px] text-[rgba(13,13,13,0.55)] transition-colors hover:border-[#D97757] hover:text-[#D97757]"
            >
              <Link2 size={14} />
              Подключить репозиторий
            </button>
          )}
        </div>
      )}

      {/* Connect form */}
      {showConnectForm && (
        <form onSubmit={handleConnect} className="rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-white p-5">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-[16px] font-semibold text-[#1A1A1A]">Подключить репозиторий</p>
            <button type="button" onClick={() => { setShowConnectForm(false); setConnectErr(null); }}
              className="rounded-[6px] p-1 text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
              <X size={14} />
            </button>
          </div>
          <div className="flex flex-col gap-4">
            {/* Type */}
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Тип</label>
              <div className="flex flex-wrap gap-2">
                {(["github", "gitea", "website", "rss"] as const).map((t) => (
                  <button key={t} type="button" onClick={() => setConnType(t)}
                    className={[
                      "flex items-center gap-1.5 rounded-[7px] border px-3 py-1.5 text-[15px] font-medium transition-colors",
                      connType === t
                        ? "border-[#D97757] bg-[rgba(217,119,87,0.07)] text-[#D97757]"
                        : "border-[rgba(13,13,13,0.14)] text-[rgba(13,13,13,0.65)] hover:border-[rgba(13,13,13,0.25)]",
                    ].join(" ")}
                  >
                    {t === "github" ? <Github size={13} /> : t === "gitea" ? <GitBranch size={13} />
                      : t === "website" ? <Globe size={13} /> : <Rss size={13} />}
                    {t === "github" ? "GitHub" : t === "gitea" ? "Gitea"
                      : t === "website" ? "Сайт" : "RSS"}
                  </button>
                ))}
              </div>
            </div>
            {/* URL */}
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">
                {connType === "website" ? "URL сайта" : connType === "rss" ? "URL RSS-ленты" : "URL репозитория"}
              </label>
              <input value={repoUrl} onChange={(e) => setRepoUrl(e.target.value)} required
                placeholder={
                  connType === "github" ? "https://github.com/owner/repo"
                    : connType === "gitea" ? "https://gitea.example.com/owner/repo"
                    : connType === "website" ? "https://docs.example.com"
                    : "https://example.com/feed.xml"
                }
                className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all" />
              {connType === "website" && (
                <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.40)]">
                  Страницы сайта попадут в базу знаний и будут пересканироваться раз в сутки
                </p>
              )}
              {connType === "rss" && (
                <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.40)]">
                  Новые записи ленты будут добавляться в базу знаний ежедневно
                </p>
              )}
            </div>
            {(connType === "github" || connType === "gitea") && (<>
            {/* PAT */}
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Personal Access Token</label>
              <input value={pat} onChange={(e) => setPat(e.target.value)} required type="password"
                placeholder="ghp_... или gitea токен"
                className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all" />
              <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.40)]">Токен хранится в зашифрованном виде</p>
            </div>
            {/* Branch */}
            <div>
              <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Ветка</label>
              <input value={branch} onChange={(e) => setBranch(e.target.value)}
                placeholder="main"
                className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all" />
            </div>
            </>)}
            {connectErr && (
              <div className="flex items-center gap-2 rounded-[7px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[14px] text-[#e74c3c]">
                <AlertCircle size={12} /> {connectErr}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => { setShowConnectForm(false); setConnectErr(null); }}
                className="rounded-[7px] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.05)] transition-colors">
                Отмена
              </button>
              <button type="submit"
                disabled={connectLoading || !repoUrl.trim()
                  || ((connType === "github" || connType === "gitea") && !pat.trim())}
                className="flex items-center gap-1.5 rounded-[7px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors">
                {connectLoading ? <><Loader2 size={12} className="animate-spin" />Подключение...</> : <><Link2 size={12} />Подключить</>}
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Commits section */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[14px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.45)]">Коммиты</p>
          <button
            onClick={() => { setCommitConnId(connectors[0]?.id ?? null); setShowCommitModal(true); }}
            className="flex items-center gap-1.5 rounded-[7px] border border-[rgba(13,13,13,0.14)] px-3 py-1.5 text-[14px] font-medium text-[rgba(13,13,13,0.65)] transition-colors hover:border-[#D97757] hover:text-[#D97757]"
          >
            <Plus size={12} />
            Новый коммит
          </button>
        </div>
        {commitsLoading ? (
          <div className="h-12 animate-pulse rounded-[10px] bg-[rgba(13,13,13,0.05)]" />
        ) : commits.length === 0 ? (
          <p className="py-4 text-center text-[15px] text-[rgba(13,13,13,0.38)]">Нет коммитов</p>
        ) : (
          <div className="flex flex-col gap-2">
            {commits.map((c) => (
              <div key={c.id} className="rounded-[10px] border border-[rgba(13,13,13,0.09)] bg-white p-3.5">
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[15px] font-medium text-[#1A1A1A]">{c.commit_message}</p>
                    <div className="mt-1 flex items-center gap-2 flex-wrap">
                      <CommitStatusBadge status={c.status} />
                      {c.kind === "pull_request" && (
                        <span className="flex items-center gap-1 rounded-full bg-[rgba(217,119,87,0.08)] px-2 py-0.5 text-[12px] font-medium text-[#D97757]">
                          <GitPullRequest size={9} />
                          PR
                        </span>
                      )}
                      <span className="text-[13px] text-[rgba(13,13,13,0.35)]">
                        {c.files.length} {c.files.length === 1 ? "файл" : "файлов"}
                      </span>
                      {c.pr_url && (
                        <a href={c.pr_url} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-1 text-[13px] text-[#D97757] hover:underline">
                          <ExternalLink size={9} />
                          Открыть PR
                        </a>
                      )}
                    </div>
                    {c.status === "failed" && c.error_message && (
                      <p className="mt-1 text-[13px] text-[#e74c3c] line-clamp-1">{c.error_message}</p>
                    )}
                  </div>
                  {c.status === "pending" && (
                    <div className="flex shrink-0 items-center gap-1.5 flex-wrap justify-end">
                      <button
                        onClick={() => handleConfirm(c.id, "push")}
                        className="flex items-center gap-1 rounded-[6px] bg-[#22a85a] px-2.5 py-1 text-[13px] font-medium text-white hover:bg-[#1a8a48] transition-colors"
                      >
                        <Send size={10} />
                        Запушить
                      </button>
                      {c.connector_id && (
                        <button
                          onClick={() => handleConfirm(c.id, "pr")}
                          className="flex items-center gap-1 rounded-[6px] border border-[rgba(217,119,87,0.4)] px-2.5 py-1 text-[13px] font-medium text-[#D97757] hover:bg-[rgba(217,119,87,0.06)] transition-colors"
                        >
                          <GitPullRequest size={10} />
                          Pull Request
                        </button>
                      )}
                      <button
                        onClick={() => handleConfirm(c.id, "reject")}
                        className="rounded-[6px] px-2.5 py-1 text-[13px] text-[rgba(13,13,13,0.45)] hover:bg-[rgba(13,13,13,0.06)] transition-colors"
                      >
                        Отклонить
                      </button>
                    </div>
                  )}
                  {c.status === "failed" && (
                    <div className="flex shrink-0 items-center gap-1.5">
                      <button
                        onClick={() => handleConfirm(c.id, "push")}
                        className="flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.14)] px-2.5 py-1 text-[13px] text-[rgba(13,13,13,0.55)] hover:border-[#D97757] hover:text-[#D97757] transition-colors"
                      >
                        <RefreshCw size={10} />
                        Повторить
                      </button>
                      <button
                        onClick={() => handleDelete(c.id)}
                        className="flex items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.35)] hover:border-[rgba(231,76,60,0.4)] hover:text-[#e74c3c] transition-colors"
                        title="Удалить коммит"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  )}
                  {(c.status === "rejected" || c.status === "pushed") && (
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="flex shrink-0 items-center gap-1 rounded-[6px] border border-[rgba(13,13,13,0.10)] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.35)] hover:border-[rgba(231,76,60,0.4)] hover:text-[#e74c3c] transition-colors"
                      title="Удалить коммит"
                    >
                      <Trash2 size={10} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* New commit modal */}
      {showCommitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setShowCommitModal(false)}>
          <div
            className="w-full max-w-[560px] max-h-[90vh] overflow-y-auto rounded-[18px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-[17px] font-semibold text-[#1A1A1A]">Новый коммит</h2>
              <button onClick={() => setShowCommitModal(false)} className="rounded-[7px] p-1 text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
                <X size={15} />
              </button>
            </div>
            <form onSubmit={handlePropose} className="flex flex-col gap-4">
              {/* Connector select */}
              {connectors.length > 0 && (
                <div>
                  <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Репозиторий</label>
                  <select value={commitConnId ?? ""} onChange={(e) => setCommitConnId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all">
                    <option value="">Без репозитория (только запись)</option>
                    {connectors.map((c) => (
                      <option key={c.id} value={c.id}>{c.owner}/{c.repo} ({c.branch})</option>
                    ))}
                  </select>
                </div>
              )}
              {/* Commit message */}
              <div>
                <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Сообщение коммита</label>
                <input value={commitMsg} onChange={(e) => setCommitMsg(e.target.value)} required
                  placeholder="feat: add new feature"
                  className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all" />
              </div>
              {/* Files */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-[14px] font-medium text-[rgba(13,13,13,0.55)]">Файлы</label>
                  <button type="button" onClick={() => setCommitFiles((prev) => [...prev, { path: "", content: "" }])}
                    className="flex items-center gap-1 text-[14px] text-[#D97757] hover:underline">
                    <Plus size={11} />Добавить файл
                  </button>
                </div>
                <div className="flex flex-col gap-3">
                  {commitFiles.map((f, i) => (
                    <div key={i} className="rounded-[8px] border border-[rgba(13,13,13,0.12)] p-3">
                      <div className="mb-2 flex items-center gap-2">
                        <input value={f.path} onChange={(e) => setCommitFiles((prev) => prev.map((x, j) => j === i ? { ...x, path: e.target.value } : x))}
                          placeholder="src/components/Button.tsx"
                          className="flex-1 rounded-[6px] border border-[rgba(13,13,13,0.14)] px-2.5 py-1.5 text-[14px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all" />
                        {commitFiles.length > 1 && (
                          <button type="button" onClick={() => setCommitFiles((prev) => prev.filter((_, j) => j !== i))}
                            className="shrink-0 rounded-[5px] p-1 text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] transition-colors">
                            <X size={12} />
                          </button>
                        )}
                      </div>
                      <textarea value={f.content} onChange={(e) => setCommitFiles((prev) => prev.map((x, j) => j === i ? { ...x, content: e.target.value } : x))}
                        placeholder="Содержимое файла..."
                        rows={5}
                        className="w-full resize-y rounded-[6px] border border-[rgba(13,13,13,0.14)] px-2.5 py-1.5 font-mono text-[13px] leading-relaxed text-[rgba(13,13,13,0.75)] outline-none focus:border-[#D97757] transition-all" />
                    </div>
                  ))}
                </div>
              </div>
              {commitErr && (
                <div className="flex items-center gap-2 rounded-[7px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[14px] text-[#e74c3c]">
                  <AlertCircle size={12} />{commitErr}
                </div>
              )}
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowCommitModal(false)}
                  className="rounded-[7px] px-4 py-2 text-[15px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.05)] transition-colors">
                  Отмена
                </button>
                <button type="submit" disabled={commitLoading || !commitMsg.trim() || commitFiles.every((f) => !f.path.trim())}
                  className="flex items-center gap-1.5 rounded-[7px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors">
                  {commitLoading ? <><Loader2 size={12} className="animate-spin" />Создание...</> : "Создать коммит"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Вкладка "Доступ" (публичный Space) ── */
function AccessTab({ project, onSaved }: { project: Project; onSaved: (p: Project) => void }) {
  const siteUrl = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://aineron.ru").replace(/\/$/, "");
  const publicUrl = `${siteUrl}/s/${project.public_slug}`;
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showFiles, setShowFiles] = useState(project.public_show_files);
  const [showChats, setShowChats] = useState(project.public_show_chats);

  const handleTogglePublic = async () => {
    setLoading(true);
    try {
      const updated = await publishProject(project.id, {
        is_public: !project.is_public,
        public_show_files: showFiles,
        public_show_chats: showChats,
      });
      onSaved(updated);
    } finally {
      setLoading(false);
    }
  };

  const handleVisibilityChange = async (field: "public_show_files" | "public_show_chats", val: boolean) => {
    if (field === "public_show_files") setShowFiles(val);
    else setShowChats(val);
    if (project.is_public) {
      const updated = await publishProject(project.id, {
        is_public: true,
        public_show_files: field === "public_show_files" ? val : showFiles,
        public_show_chats: field === "public_show_chats" ? val : showChats,
      });
      onSaved(updated);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Public toggle */}
      <div className="rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[rgba(13,13,13,0.05)]">
              {project.is_public ? <Share2 size={16} className="text-[#D97757]" /> : <Lock size={16} className="text-[rgba(13,13,13,0.45)]" />}
            </div>
            <div>
              <p className="text-[16px] font-semibold text-[#1A1A1A]">
                {project.is_public ? "Space публичный" : "Space приватный"}
              </p>
              <p className="text-[14px] text-[rgba(13,13,13,0.50)]">
                {project.is_public ? "Доступен по публичной ссылке" : "Только вы видите этот Space"}
              </p>
            </div>
          </div>
          <button
            onClick={handleTogglePublic}
            disabled={loading}
            className={[
              "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none",
              project.is_public ? "bg-[#D97757]" : "bg-[rgba(13,13,13,0.18)]",
              loading ? "opacity-60 cursor-not-allowed" : "",
            ].join(" ")}
          >
            <span
              className={[
                "inline-block h-4.5 w-4.5 transform rounded-full bg-[#fff] shadow-sm transition-transform",
                project.is_public ? "translate-x-5" : "translate-x-1",
              ].join(" ")}
              style={{ height: "18px", width: "18px" }}
            />
          </button>
        </div>

        {/* Public link */}
        {project.is_public && project.public_slug && (
          <div className="mt-4 rounded-[10px] border border-[rgba(217,119,87,0.18)] bg-[rgba(217,119,87,0.04)] p-3">
            <p className="mb-1.5 text-[13px] font-medium text-[rgba(13,13,13,0.50)] uppercase tracking-wide">
              Публичная ссылка
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-[6px] bg-white px-3 py-1.5 text-[14px] font-mono text-[#D97757] border border-[rgba(217,119,87,0.15)]">
                {publicUrl}
              </code>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-[8px] bg-[#D97757] px-3 py-1.5 text-[14px] font-medium text-white hover:bg-[#C4623E] transition-colors"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? "Скопировано" : "Копировать"}
              </button>
            </div>
            {(project.public_views ?? 0) > 0 && (
              <p className="mt-1.5 text-[13px] text-[rgba(13,13,13,0.40)]">
                {project.public_views} {project.public_views === 1 ? "просмотр" : "просмотров"}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Visibility settings */}
      <div className="rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
        <p className="mb-4 text-[15px] font-semibold text-[rgba(13,13,13,0.55)] uppercase tracking-wide">
          Что показывать в публичном Space
        </p>

        <div className="flex flex-col gap-3">
          {[
            { key: "public_show_files" as const, label: "База знаний", desc: "Список загруженных файлов (без содержимого)", value: showFiles },
            { key: "public_show_chats" as const, label: "Чаты", desc: "Последние 10 чатов (только названия)", value: showChats },
          ].map(({ key, label, desc, value }) => (
            <div key={key} className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[15px] font-medium text-[#1A1A1A]">{label}</p>
                <p className="text-[14px] text-[rgba(13,13,13,0.45)]">{desc}</p>
              </div>
              <button
                onClick={() => handleVisibilityChange(key, !value)}
                className={[
                  "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none",
                  value ? "bg-[#D97757]" : "bg-[rgba(13,13,13,0.18)]",
                ].join(" ")}
              >
                <span
                  className={["inline-block transform rounded-full bg-[#fff] shadow-sm transition-transform", value ? "translate-x-5" : "translate-x-1"].join(" ")}
                  style={{ height: "18px", width: "18px" }}
                />
              </button>
            </div>
          ))}
        </div>

        {!project.is_public && (
          <p className="mt-3 flex items-center gap-1.5 text-[14px] text-[rgba(13,13,13,0.40)]">
            <Info size={12} />
            Настройки применятся после включения публичного доступа
          </p>
        )}
      </div>
    </div>
  );
}

/* ── Вкладка "Команда" (соавторы, только для владельца) ── */
function CollaboratorsTab({ projectId }: { projectId: number }) {
  const qc = useQueryClient();
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"viewer" | "editor">("viewer");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const { data: collabs = [], isLoading } = useQuery({
    queryKey: ["collaborators", projectId],
    queryFn: () => listCollaborators(projectId),
    staleTime: 30_000,
  });

  const handleInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviteError(null);
    setInviting(true);
    try {
      const c = await addCollaborator(projectId, inviteEmail.trim(), inviteRole);
      qc.setQueryData<ProjectCollaborator[]>(["collaborators", projectId], (prev) => {
        if (!prev) return [c];
        const existing = prev.find((x) => x.id === c.id);
        return existing ? prev.map((x) => (x.id === c.id ? c : x)) : [...prev, c];
      });
      setInviteEmail("");
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message ?? "Ошибка приглашения";
      setInviteError(msg);
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (collab: ProjectCollaborator, role: "viewer" | "editor") => {
    const updated = await updateCollaboratorRole(projectId, collab.id, role);
    qc.setQueryData<ProjectCollaborator[]>(["collaborators", projectId], (prev) =>
      prev?.map((c) => (c.id === updated.id ? updated : c)) ?? []
    );
  };

  const handleRemove = async (id: number) => {
    setRemovingId(id);
    try {
      await removeCollaborator(projectId, id);
      qc.setQueryData<ProjectCollaborator[]>(["collaborators", projectId], (prev) =>
        prev?.filter((c) => c.id !== id) ?? []
      );
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Info */}
      <div className="flex items-start gap-2.5 rounded-[10px] bg-[rgba(217,119,87,0.06)] px-4 py-3">
        <Info size={14} className="mt-0.5 shrink-0 text-[#D97757]" />
        <p className="text-[15px] leading-relaxed text-[rgba(13,13,13,0.65)]">
          Пригласите коллег по email. Редактор может загружать файлы, синхронизировать репозитории и создавать коммиты.
          Наблюдатель — только читать.
        </p>
      </div>

      {/* Invite form */}
      <div className="rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5">
        <p className="mb-3 text-[15px] font-semibold text-[#1A1A1A]">Пригласить участника</p>
        <form onSubmit={handleInvite} className="flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="email@example.com"
              className="flex-1 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
              required
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as "viewer" | "editor")}
              className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all"
            >
              <option value="viewer">Наблюдатель</option>
              <option value="editor">Редактор</option>
            </select>
          </div>
          {inviteError && (
            <p className="text-[14px] text-[#e74c3c]">{inviteError}</p>
          )}
          <button
            type="submit"
            disabled={inviting || !inviteEmail.trim()}
            className="flex items-center gap-1.5 self-start rounded-[8px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
          >
            {inviting ? (
              <Loader2 size={13} className="animate-spin" />
            ) : (
              <UserPlus size={13} />
            )}
            Пригласить
          </button>
        </form>
      </div>

      {/* Collaborators list */}
      <div className="flex flex-col gap-3">
        <p className="text-[14px] font-medium uppercase tracking-wide text-[rgba(13,13,13,0.40)]">
          Участники ({collabs.length})
        </p>
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-14 animate-pulse rounded-[10px] bg-[rgba(13,13,13,0.05)]" />
            ))}
          </div>
        ) : collabs.length === 0 ? (
          <p className="py-4 text-center text-[15px] text-[rgba(13,13,13,0.38)]">Нет участников</p>
        ) : (
          collabs.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-3 rounded-[10px] border border-[rgba(13,13,13,0.09)] bg-white p-3.5"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[rgba(13,13,13,0.07)] text-[15px] font-semibold text-[rgba(13,13,13,0.50)]">
                {c.email[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-medium text-[#1A1A1A]">{c.email}</p>
                <p className="text-[13px] text-[rgba(13,13,13,0.40)]">{c.username}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="flex items-center gap-1.5 rounded-[6px] border border-[rgba(13,13,13,0.12)] bg-white">
                  <button
                    onClick={() => c.role !== "viewer" && handleRoleChange(c, "viewer")}
                    className={[
                      "flex items-center gap-1 rounded-[5px] px-2.5 py-1 text-[13px] font-medium transition-colors",
                      c.role === "viewer"
                        ? "bg-[rgba(13,13,13,0.07)] text-[#1A1A1A]"
                        : "text-[rgba(13,13,13,0.45)] hover:text-[#1A1A1A]",
                    ].join(" ")}
                    title="Наблюдатель: только чтение"
                  >
                    <ShieldOff size={10} />
                    Наблюдатель
                  </button>
                  <button
                    onClick={() => c.role !== "editor" && handleRoleChange(c, "editor")}
                    className={[
                      "flex items-center gap-1 rounded-[5px] px-2.5 py-1 text-[13px] font-medium transition-colors",
                      c.role === "editor"
                        ? "bg-[rgba(217,119,87,0.10)] text-[#D97757]"
                        : "text-[rgba(13,13,13,0.45)] hover:text-[#D97757]",
                    ].join(" ")}
                    title="Редактор: загрузка файлов, синк, коммиты"
                  >
                    <ShieldCheck size={10} />
                    Редактор
                  </button>
                </div>
                <button
                  onClick={() => handleRemove(c.id)}
                  disabled={removingId === c.id}
                  className="flex items-center gap-1 rounded-[7px] p-1.5 text-[rgba(13,13,13,0.30)] transition-colors hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] disabled:opacity-40"
                  title="Удалить участника"
                >
                  {removingId === c.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <UserMinus size={13} />
                  )}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ── Вкладка "Журнал" (audit log, только для владельца) ── */
function AuditTab({ projectId }: { projectId: number }) {
  const { data, isLoading } = useQuery({
    queryKey: ["project_audit", projectId],
    queryFn: () => listProjectAudit(projectId),
    staleTime: 30_000,
  });
  const entries: ProjectAuditEntry[] = data?.entries ?? [];

  const actionIcon: Record<string, React.ReactNode> = {
    chat_message: <MessageSquare size={12} />,
    file_upload: <Upload size={12} />,
    file_delete: <Trash2 size={12} />,
    commit_push: <GitBranch size={12} />,
    pr_open: <GitPullRequest size={12} />,
    member_invite: <UserPlus size={12} />,
    member_remove: <UserMinus size={12} />,
    published: <Globe size={12} />,
    unpublished: <Lock size={12} />,
  };

  if (isLoading) return <div className="h-32 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)]" />;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[14px] font-semibold uppercase tracking-wide text-[rgba(13,13,13,0.45)]">
        Журнал аудита
      </p>
      {entries.length === 0 ? (
        <p className="py-8 text-center text-[15px] text-[rgba(13,13,13,0.38)]">Событий нет</p>
      ) : (
        <div className="flex flex-col divide-y divide-[rgba(13,13,13,0.06)] rounded-[12px] border border-[rgba(13,13,13,0.09)] bg-white">
          {entries.map((e) => (
            <div key={e.id} className="flex items-start gap-3 px-4 py-3">
              <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[rgba(13,13,13,0.05)] text-[rgba(13,13,13,0.45)]">
                {actionIcon[e.action] ?? <Info size={12} />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-medium text-[#1A1A1A]">{e.action_display}</p>
                {e.target && (
                  <p className="truncate text-[13px] text-[rgba(13,13,13,0.45)]">{e.target}</p>
                )}
                <p className="text-[12px] text-[rgba(13,13,13,0.30)]">
                  {e.actor_email ?? "система"} &middot; {new Date(e.created_at).toLocaleString("ru")}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Главная страница проекта ── */
type Tab = "chats" | "instructions" | "files" | "connectors" | "access" | "team" | "audit";

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const projectId = parseInt(params.id, 10);
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("chats");
  const [showEdit, setShowEdit] = useState(false);
  const [expandInstructions, setExpandInstructions] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
  });

  const project: Project | undefined = projects.find((p) => p.id === projectId);

  const handleProjectSaved = (updated: Project) => {
    qc.setQueryData<Project[]>(["projects"], (prev) =>
      prev?.map((p) => (p.id === updated.id ? updated : p)) ?? []
    );
    setShowEdit(false);
  };

  const handleInstructionsSaved = (updated: Project) => {
    qc.setQueryData<Project[]>(["projects"], (prev) =>
      prev?.map((p) => (p.id === updated.id ? updated : p)) ?? []
    );
  };

  const hasInstructions = Boolean(project?.system_prompt?.trim());

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-8">
      {/* Back */}
      <Link
        href="/projects/"
        className="mb-5 inline-flex items-center gap-1.5 text-[15px] text-[rgba(13,13,13,0.50)] hover:text-[#1A1A1A] transition-colors"
      >
        <ArrowLeft size={14} />
        Все проекты
      </Link>

      {/* Project header */}
      <div className="mb-6 flex items-start gap-3">
        <div
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[11px]"
          style={{ background: project ? `${project.color}18` : "rgba(217,119,87,0.08)" }}
        >
          <span style={{ color: project?.color ?? "#D97757" }}>
            <ProjectIcon name={project?.icon ?? "Folder"} size={20} />
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-[22px] font-bold text-[#1A1A1A]">{project?.name ?? "Проект"}</h1>
            {project?.user_role === "editor" && (
              <span className="rounded-full bg-[rgba(217,119,87,0.10)] px-2 py-0.5 text-[13px] font-medium text-[#D97757]">Редактор</span>
            )}
            {project?.user_role === "viewer" && (
              <span className="rounded-full bg-[rgba(13,13,13,0.07)] px-2 py-0.5 text-[13px] font-medium text-[rgba(13,13,13,0.50)]">Наблюдатель</span>
            )}
          </div>
          {/* Inline instructions preview under project name */}
          {hasInstructions && (
            <button
              onClick={() => setExpandInstructions((v) => !v)}
              className="mt-1 flex items-center gap-1 text-[14px] text-[rgba(13,13,13,0.45)] hover:text-[rgba(13,13,13,0.65)] transition-colors"
            >
              <FileText size={11} />
              <span>Инструкции активны</span>
              <ChevronDown size={11} className={["transition-transform", expandInstructions ? "rotate-180" : ""].join(" ")} />
            </button>
          )}
          {hasInstructions && expandInstructions && (
            <div className="mt-2 rounded-[8px] border border-[rgba(13,13,13,0.10)] bg-[rgba(13,13,13,0.02)] px-3 py-2.5 text-[14px] leading-relaxed text-[rgba(13,13,13,0.60)] line-clamp-4">
              {project?.system_prompt}
            </div>
          )}
        </div>
        <button
          onClick={() => setShowEdit(true)}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A] transition-colors"
          title="Редактировать проект"
        >
          <Settings size={14} />
        </button>
      </div>

      {/* Tabs — горизонтальный скролл на мобильном */}
      <div className="mb-5 overflow-x-auto border-b border-[rgba(13,13,13,0.09)] scrollbar-hide">
        <div className="flex min-w-max items-center gap-0.5">
          <TabButton
            active={tab === "chats"}
            icon={<MessageSquare size={13} />}
            label="Чаты"
            onClick={() => setTab("chats")}
          />
          <TabButton
            active={tab === "instructions"}
            icon={<FileText size={13} />}
            label="Инструкции"
            onClick={() => setTab("instructions")}
            badge={hasInstructions}
          />
          <TabButton
            active={tab === "files"}
            icon={<Upload size={13} />}
            label="Файлы"
            onClick={() => setTab("files")}
          />
          <Link
            href={`/projects/${projectId}/kb/`}
            className="relative flex items-center gap-1.5 border-b-2 -mb-px px-3 py-2.5 text-[15px] font-medium transition-colors border-transparent text-[rgba(13,13,13,0.52)] hover:text-[#1A1A1A] whitespace-nowrap"
          >
            <Database size={13} />
            База знаний
          </Link>
          <TabButton
            active={tab === "connectors"}
            icon={<GitBranch size={13} />}
            label="Git"
            onClick={() => setTab("connectors")}
          />
          <TabButton
            active={tab === "access"}
            icon={<Share2 size={13} />}
            label="Доступ"
            onClick={() => setTab("access")}
            badge={project?.is_public}
          />
          {project?.user_role === "owner" && (
            <TabButton
              active={tab === "team"}
              icon={<Users size={13} />}
              label="Команда"
              onClick={() => setTab("team")}
            />
          )}
          {project?.user_role === "owner" && (
            <TabButton
              active={tab === "audit"}
              icon={<History size={13} />}
              label="Журнал"
              onClick={() => setTab("audit")}
            />
          )}
        </div>
      </div>

      {/* Tab actions row */}
      {tab === "chats" && (
        <div className="mb-4">
          <Link
            href={`/models/?project_id=${projectId}`}
            className="inline-flex items-center gap-1.5 rounded-[9px] bg-[#D97757] px-4 py-2 text-[15px] font-medium text-white hover:bg-[#C4623E] transition-colors"
          >
            <Plus size={14} />
            Новый чат
          </Link>
        </div>
      )}

      {/* Tab content */}
      {tab === "chats" && <ChatsTab projectId={projectId} project={project} />}
      {tab === "instructions" && project && (
        <InstructionsTab project={project} onSaved={handleInstructionsSaved} />
      )}
      {tab === "instructions" && !project && (
        <div className="h-32 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)]" />
      )}
      {tab === "files" && <FilesTab projectId={projectId} />}
      {tab === "connectors" && <ConnectorsTab projectId={projectId} />}
      {tab === "access" && project && (
        <AccessTab project={project} onSaved={handleInstructionsSaved} />
      )}
      {tab === "access" && !project && (
        <div className="h-32 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)]" />
      )}
      {tab === "team" && project?.user_role === "owner" && (
        <CollaboratorsTab projectId={projectId} />
      )}
      {tab === "audit" && project?.user_role === "owner" && (
        <AuditTab projectId={projectId} />
      )}

      {/* Edit modal (name / icon / color) */}
      {showEdit && project && (
        <EditProjectModal
          project={project}
          onClose={() => setShowEdit(false)}
          onSaved={handleProjectSaved}
        />
      )}
    </div>
  );
}

function TabButton({
  active, icon, label, onClick, badge,
}: {
  active: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  badge?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={[
        "relative flex items-center gap-1.5 px-3 py-2.5 text-[15px] font-medium transition-colors border-b-2 -mb-px",
        active
          ? "border-[#D97757] text-[#D97757]"
          : "border-transparent text-[rgba(13,13,13,0.52)] hover:text-[#1A1A1A]",
      ].join(" ")}
    >
      {icon}
      {label}
      {badge && (
        <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-[#D97757]" />
      )}
    </button>
  );
}
