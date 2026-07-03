"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  PenSquare,
  LayoutGrid,
  Search,
  Trash2,
  Edit3,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Code2,
  ImageIcon,
  X,
  Check,
  MessageSquare,
  Folder,
  Plus,
  MoreHorizontal,
  BookOpen,
  Briefcase,
  Zap,
  Globe,
  Palette,
} from "lucide-react";
import { listChats, deleteChat, renameChat, listProjects, createProject, updateProject, deleteProject, listNetworks } from "@/lib/api/client";
import type { ChatListItem, Project } from "@/lib/api/types";

// ── Project constants ────────────────────────────────────────

const PROJECT_ICON_MAP: Record<string, React.ElementType> = {
  Folder, Code2, BookOpen, Briefcase, Zap, Globe, Palette, MessageSquare,
};
const PROJECT_ICONS = Object.keys(PROJECT_ICON_MAP);
const PROJECT_COLORS = ["#D97757", "#22a85a", "#e67e22", "#E8C9A0", "#e74c3c", "#C4623E", "#1A1A1A", "#8B7E77"];

function ProjectIcon({ name, size = 12 }: { name: string; size?: number }) {
  const Icon = PROJECT_ICON_MAP[name] ?? Folder;
  return <Icon size={size} />;
}

// ── Project modal (create / edit) ────────────────────────────

function ProjectModal({
  mode,
  initial,
  onClose,
  onSave,
}: {
  mode: "create" | "edit";
  initial?: Project;
  onClose: () => void;
  onSave: (data: { name: string; system_prompt: string; color: string; icon: string }) => Promise<unknown>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [systemPrompt, setSystemPrompt] = useState(initial?.system_prompt ?? "");
  const [color, setColor] = useState(initial?.color ?? PROJECT_COLORS[0]);
  const [icon, setIcon] = useState(initial?.icon ?? "Folder");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await onSave({ name: name.trim(), system_prompt: systemPrompt.trim(), color, icon });
    } catch {
      setError(mode === "create" ? "Не удалось создать проект" : "Не удалось сохранить");
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-[420px] rounded-[18px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[17px] font-semibold text-[#1A1A1A]">
            {mode === "create" ? "Новый проект" : "Настройки проекта"}
          </h2>
          <button onClick={onClose} className="rounded-[7px] p-1 text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A] transition-colors">
            <X size={15} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[13px] font-medium text-[rgba(13,13,13,0.55)]">Название</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Мой проект"
              maxLength={100}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-[rgba(13,13,13,0.55)]">Иконка</label>
              <div className="flex flex-wrap gap-1.5">
                {PROJECT_ICONS.map((ic) => {
                  const Icon = PROJECT_ICON_MAP[ic];
                  return (
                    <button key={ic} type="button" onClick={() => setIcon(ic)}
                      className={["flex h-7 w-7 items-center justify-center rounded-[6px] transition-colors", icon === ic ? "ring-2 ring-[#D97757] ring-offset-1" : "border border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.05)]"].join(" ")}
                      style={{ color: icon === ic ? color : "var(--text-tertiary)" }}
                    >
                      <Icon size={13} />
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-[13px] font-medium text-[rgba(13,13,13,0.55)]">Цвет</label>
              <div className="flex flex-wrap gap-1.5">
                {PROJECT_COLORS.map((c) => (
                  <button key={c} type="button" onClick={() => setColor(c)}
                    className={["h-6 w-6 rounded-full transition-transform", color === c ? "scale-110 ring-2 ring-offset-1 ring-[rgba(13,13,13,0.25)]" : "hover:scale-105"].join(" ")}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-[13px] font-medium text-[rgba(13,13,13,0.55)]">
              Системный промт <span className="text-[rgba(13,13,13,0.35)]">(необязательно)</span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Ты — помощник-программист..."
              rows={3}
              className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[14px] text-[#1A1A1A] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
            />
          </div>
          {error && (
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[14px] text-[#e74c3c]">{error}</div>
          )}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose}
              className="rounded-[8px] px-3 py-1.5 text-[14px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
              Отмена
            </button>
            <button type="submit" disabled={!name.trim() || loading}
              className="rounded-[8px] bg-[#D97757] px-3 py-1.5 text-[14px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors">
              {loading ? (mode === "create" ? "Создание..." : "Сохранение...") : (mode === "create" ? "Создать" : "Сохранить")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Project accordion row ────────────────────────────────────

function ProjectSidebarRow({
  project,
  isExpanded,
  onToggle,
  onEdit,
  onDelete,
  currentPath,
}: {
  project: Project;
  isExpanded: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  currentPath: string;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: projectChats = [], isLoading } = useQuery({
    queryKey: ["chats", "project", project.id],
    queryFn: () => listChats({ project_id: project.id }),
    staleTime: 30_000,
    enabled: isExpanded,
  });

  return (
    <div>
      <div className="group mx-1 flex items-center gap-0.5 rounded-[7px] hover:bg-[rgba(13,13,13,0.04)] transition-colors">
        <button
          onClick={onToggle}
          className="flex flex-1 min-w-0 items-center gap-2 px-2 py-1.5"
        >
          <span
            className="flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px]"
            style={{ background: `${project.color}20`, color: project.color }}
          >
            <ProjectIcon name={project.icon} size={10} />
          </span>
          <span className="truncate text-[14px] text-[rgba(13,13,13,0.65)] group-hover:text-[#1A1A1A]">
            {project.name}
          </span>
          <span className="ml-auto shrink-0 text-[12px] text-[rgba(13,13,13,0.28)]">
            {project.chat_count}
          </span>
          <ChevronDown
            size={10}
            className="shrink-0 text-[rgba(13,13,13,0.25)] transition-transform duration-150"
            style={{ transform: isExpanded ? "none" : "rotate(-90deg)" }}
          />
        </button>

        {/* "..." menu */}
        <div className="relative mr-1 shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); setConfirmDelete(false); }}
            className="hidden h-5 w-5 items-center justify-center rounded-[4px] text-[rgba(13,13,13,0.30)] hover:bg-[rgba(13,13,13,0.08)] hover:text-[#1A1A1A] group-hover:flex transition-colors"
          >
            <MoreHorizontal size={11} />
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-6 z-50 w-36 overflow-hidden rounded-[8px] border border-[rgba(13,13,13,0.10)] bg-white shadow-lg">
                <button
                  onClick={() => { setMenuOpen(false); onEdit(); }}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-[14px] text-[rgba(13,13,13,0.70)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
                >
                  <Edit3 size={12} />
                  Переименовать
                </button>
                {!confirmDelete ? (
                  <button
                    onClick={() => setConfirmDelete(true)}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-[14px] text-[#e74c3c] hover:bg-[rgba(231,76,60,0.05)] transition-colors"
                  >
                    <Trash2 size={12} />
                    Удалить
                  </button>
                ) : (
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <span className="flex-1 text-[13px] text-[rgba(13,13,13,0.55)]">Удалить?</span>
                    <button
                      onClick={() => { setMenuOpen(false); onDelete(); }}
                      className="rounded-[4px] bg-[#e74c3c] px-2 py-0.5 text-[13px] font-medium text-white hover:bg-[#c0392b] transition-colors"
                    >
                      Да
                    </button>
                    <button
                      onClick={() => setConfirmDelete(false)}
                      className="rounded-[4px] px-1.5 py-0.5 text-[13px] text-[rgba(13,13,13,0.45)] hover:bg-[rgba(13,13,13,0.07)] transition-colors"
                    >
                      Нет
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Accordion content */}
      {isExpanded && (
        <div className="ml-6 pb-0.5 pt-0.5">
          {isLoading ? (
            <div className="px-2 py-1.5 text-[13px] text-[rgba(13,13,13,0.35)]">Загрузка...</div>
          ) : projectChats.length === 0 ? (
            <p className="px-2 py-1 text-[13px] text-[rgba(13,13,13,0.35)]">Нет чатов</p>
          ) : (
            projectChats.slice(0, 6).map((chat) => {
              const active = currentPath === `/chat/${chat.id}/` || currentPath === `/chat/${chat.id}`;
              return (
                <Link
                  key={chat.id}
                  href={`/chat/${chat.id}/`}
                  className={[
                    "flex items-center rounded-[6px] px-2 py-1 text-[14px] transition-colors",
                    active
                      ? "bg-[rgba(217,119,87,0.08)] text-[#D97757]"
                      : "text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A]",
                  ].join(" ")}
                >
                  <span className="truncate">{chat.title || chat.network.name}</span>
                </Link>
              );
            })
          )}
          {projectChats.length > 6 && (
            <Link
              href={`/projects/${project.id}/`}
              className="flex items-center gap-1 rounded-[6px] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.40)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#D97757] transition-colors"
            >
              Все {projectChats.length} чатов
              <ChevronRight size={10} />
            </Link>
          )}
          <Link
            href={`/models/?project_id=${project.id}`}
            className="flex items-center gap-1.5 rounded-[6px] px-2 py-1.5 text-[13px] text-[rgba(13,13,13,0.38)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#D97757] transition-colors"
          >
            <Plus size={10} />
            Новый чат
          </Link>
        </div>
      )}
    </div>
  );
}

// ── Date grouping ────────────────────────────────────────────

type Group = "Сегодня" | "Вчера" | "Эта неделя" | "Ранее";

function getGroup(dateStr: string): Group {
  const now = new Date();
  const date = new Date(dateStr);
  const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const targetDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.round((nowDay.getTime() - targetDay.getTime()) / 86400000);
  if (diffDays === 0) return "Сегодня";
  if (diffDays === 1) return "Вчера";
  if (diffDays < 7) return "Эта неделя";
  return "Ранее";
}

function groupChats(chats: ChatListItem[]): { group: Group; items: ChatListItem[] }[] {
  const ORDER: Group[] = ["Сегодня", "Вчера", "Эта неделя", "Ранее"];
  const map = new Map<Group, ChatListItem[]>();
  for (const chat of chats) {
    const g = getGroup(chat.updated_at);
    if (!map.has(g)) map.set(g, []);
    map.get(g)!.push(chat);
  }
  return ORDER.filter((g) => map.has(g)).map((g) => ({ group: g, items: map.get(g)! }));
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

// ── Preview card ─────────────────────────────────────────────

interface PreviewState {
  chatId: number;
  y: number;
}

function PreviewCard({
  chat,
  y,
  onMouseEnter,
  onMouseLeave,
}: {
  chat: ChatListItem;
  y: number;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  const clampedY = Math.max(8, Math.min(y - 8, (typeof window !== "undefined" ? window.innerHeight : 600) - 200));

  return (
    <div
      className="fixed z-[100] w-72"
      style={{ left: 260, top: clampedY }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <div
        className="overflow-hidden rounded-[14px] border border-[rgba(13,13,13,0.10)] bg-white"
        style={{
          boxShadow: "0 8px 32px rgba(0,0,0,0.13), 0 2px 8px rgba(0,0,0,0.06)",
          animation: "sidebarPreviewIn 0.15s ease",
        }}
      >
        {/* Header */}
        <div className="flex items-center gap-2.5 border-b border-[rgba(13,13,13,0.06)] px-3 py-2.5">
          {chat.network.avatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={chat.network.avatar} alt="" width={28} height={28} className="rounded-[6px] object-cover" />
          ) : (
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-[rgba(217,119,87,0.10)]">
              {chat.network.handle_photo || chat.network.handle_video ? (
                <ImageIcon size={14} className="text-[#D97757]" />
              ) : (
                <Code2 size={14} className="text-[#D97757]" />
              )}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-[14px] font-semibold text-[#1A1A1A]">
              {chat.title || chat.network.name}
            </p>
            <p className="text-[12px] text-[rgba(13,13,13,0.42)]">
              {chat.network.name} · {timeAgo(chat.updated_at)}
            </p>
          </div>
        </div>

        {/* Message preview */}
        <div className="px-3 py-3">
          {chat.last_message ? (
            chat.last_message.role === "user" ? (
              <div className="flex justify-end">
                <div
                  className="max-w-[85%] rounded-[10px] rounded-br-[3px] px-3 py-2 text-[13px] leading-[1.5] text-white"
                  style={{ background: "var(--surface-inverse)" }}
                >
                  {chat.last_message.preview}
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(217,119,87,0.10)]">
                  <MessageSquare size={10} className="text-[#D97757]" />
                </div>
                <p className="text-[13px] leading-[1.6] text-[rgba(13,13,13,0.72)]">
                  {chat.last_message.preview}
                </p>
              </div>
            )
          ) : (
            <p className="text-[13px] text-[rgba(13,13,13,0.35)]">Чат пустой</p>
          )}
        </div>

        {/* CTA */}
        <div className="border-t border-[rgba(13,13,13,0.06)] px-3 py-2">
          <p className="text-[12px] font-medium text-[rgba(217,119,87,0.75)]">
            Нажмите, чтобы продолжить
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Main component ───────────────────────────────────────────

export function ChatSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();

  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("sidebar-collapsed") === "1";
  });

  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const editRef = useRef<HTMLInputElement>(null);

  // Hover preview state
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const itemRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const { data: chats = [] } = useQuery({
    queryKey: ["chats"],
    queryFn: () => listChats(),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });

  // Prefetch networks so /models catalog opens instantly
  useEffect(() => {
    qc.prefetchQuery({ queryKey: ["networks", {}], queryFn: () => listNetworks(), staleTime: 5 * 60_000 });
  }, [qc]);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const [projectsOpen, setProjectsOpen] = useState(true);
  const [expandedProject, setExpandedProject] = useState<number | null>(null);
  const [showProjectModal, setShowProjectModal] = useState<"create" | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);

  const createProjectMutation = useMutation({
    mutationFn: (data: { name: string; system_prompt: string; color: string; icon: string }) =>
      createProject(data),
    onSuccess: (project) => {
      qc.setQueryData<Project[]>(["projects"], (prev) => [project, ...(prev ?? [])]);
      setShowProjectModal(null);
      setExpandedProject(project.id);
    },
  });

  const updateProjectMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: number; name: string; system_prompt: string; color: string; icon: string }) =>
      updateProject(id, data),
    onSuccess: (project) => {
      qc.setQueryData<Project[]>(["projects"], (prev) =>
        prev?.map((p) => (p.id === project.id ? project : p)) ?? []
      );
      setEditingProject(null);
    },
  });

  const deleteProjectMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: (_, id) => {
      qc.setQueryData<Project[]>(["projects"], (prev) => prev?.filter((p) => p.id !== id) ?? []);
      if (expandedProject === id) setExpandedProject(null);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteChat,
    onSuccess: (_, id) => {
      qc.setQueryData<ChatListItem[]>(["chats"], (prev) => prev?.filter((c) => c.id !== id) ?? []);
      setDeletingId(null);
      if (pathname === `/chat/${id}/` || pathname === `/chat/${id}`) {
        router.push("/models/");
      }
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ id, title }: { id: number; title: string }) => renameChat(id, title),
    onMutate: ({ id, title }) => {
      qc.setQueryData<ChatListItem[]>(["chats"], (prev) =>
        prev?.map((c) => (c.id === id ? { ...c, title } : c)) ?? []
      );
    },
    onError: () => {
      qc.invalidateQueries({ queryKey: ["chats"] });
    },
  });

  const toggleCollapse = () => {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem("sidebar-collapsed", next ? "1" : "0");
      return next;
    });
    setPreview(null);
  };

  // Ctrl+K → focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (collapsed) {
          setCollapsed(false);
          localStorage.setItem("sidebar-collapsed", "0");
        }
        setTimeout(() => searchRef.current?.focus(), 60);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [collapsed]);

  // Auto-focus rename input
  useEffect(() => {
    if (editingId !== null) setTimeout(() => editRef.current?.focus(), 30);
  }, [editingId]);

  const submitRename = useCallback(
    (id: number) => {
      const title = editTitle.trim();
      if (title) renameMutation.mutate({ id, title });
      setEditingId(null);
    },
    [editTitle, renameMutation]
  );

  // Preview hover logic with keep-alive gap
  const scheduleClear = useCallback(() => {
    clearTimer.current = setTimeout(() => setPreview(null), 120);
  }, []);
  const cancelClear = useCallback(() => {
    if (clearTimer.current) clearTimeout(clearTimer.current);
  }, []);

  const handleItemMouseEnter = useCallback(
    (id: number) => {
      if (collapsed) return;
      cancelClear();
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
      hoverTimer.current = setTimeout(() => {
        const el = itemRefs.current.get(id);
        if (el) {
          const rect = el.getBoundingClientRect();
          setPreview({ chatId: id, y: rect.top });
        }
      }, 600);
    },
    [collapsed, cancelClear]
  );

  const handleItemMouseLeave = useCallback(() => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    scheduleClear();
  }, [scheduleClear]);

  // Filter + group
  const q = search.trim().toLowerCase();
  const filtered = q
    ? chats.filter(
        (c) =>
          c.title.toLowerCase().includes(q) ||
          c.network.name.toLowerCase().includes(q) ||
          c.last_message?.preview.toLowerCase().includes(q)
      )
    : chats;
  const grouped = groupChats(filtered);
  const previewChat = preview ? chats.find((c) => c.id === preview.chatId) ?? null : null;

  // ── Collapsed mode ──────────────────────────────────────────
  if (collapsed) {
    return (
      <aside className="hidden md:flex w-12 shrink-0 flex-col border-r border-[rgba(13,13,13,0.08)] bg-white">
        <div className="flex flex-col items-center gap-1 px-1.5 pt-2.5">
          <button
            onClick={toggleCollapse}
            title="Развернуть"
            className="flex h-8 w-8 items-center justify-center rounded-[7px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A]"
          >
            <ChevronRight size={15} />
          </button>
          <Link
            href="/models/"
            title="Новый чат"
            className="flex h-8 w-8 items-center justify-center rounded-[7px] bg-[#D97757] text-white transition-colors hover:bg-[#C4623E]"
          >
            <PenSquare size={14} />
          </Link>
          <Link
            href="/models/"
            title="Каталог"
            className="flex h-8 w-8 items-center justify-center rounded-[7px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#1A1A1A]"
          >
            <LayoutGrid size={14} />
          </Link>
        </div>

        <div className="mt-1 flex-1 overflow-y-auto py-1">
          {chats.slice(0, 30).map((chat) => {
            const active = pathname === `/chat/${chat.id}/` || pathname === `/chat/${chat.id}`;
            return (
              <Link
                key={chat.id}
                href={`/chat/${chat.id}/`}
                title={chat.title || chat.network.name}
                className={[
                  "mx-1 my-0.5 flex h-8 w-8 items-center justify-center rounded-[6px] transition-colors",
                  active ? "bg-[rgba(217,119,87,0.10)]" : "hover:bg-[rgba(13,13,13,0.05)]",
                ].join(" ")}
              >
                {chat.network.avatar ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={chat.network.avatar} alt="" width={20} height={20} className="rounded-[4px] object-cover" />
                ) : (
                  <Code2 size={14} className="text-[rgba(13,13,13,0.4)]" />
                )}
              </Link>
            );
          })}
        </div>
      </aside>
    );
  }

  // ── Expanded mode ───────────────────────────────────────────
  return (
    <>
      {/* Sidebar */}
      <aside className="hidden md:flex w-[260px] shrink-0 flex-col border-r border-[rgba(13,13,13,0.08)] bg-white">
        {/* Header */}
        <div className="flex items-center gap-1.5 px-2.5 pb-2 pt-2.5">
          <Link
            href="/models/"
            className="flex h-8 flex-1 items-center gap-1.5 rounded-[7px] bg-[#D97757] px-3 text-[14px] font-medium text-white transition-colors hover:bg-[#C4623E]"
          >
            <PenSquare size={13} />
            Новый чат
          </Link>
          <Link
            href="/models/"
            title="Каталог"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A]"
          >
            <LayoutGrid size={14} />
          </Link>
          <button
            onClick={toggleCollapse}
            title="Свернуть"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A]"
          >
            <ChevronLeft size={14} />
          </button>
        </div>

        {/* Search */}
        <div className="px-2.5 pb-2">
          <div className="relative">
            <Search
              size={12}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.32)]"
            />
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск чатов…"
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.11)] bg-[rgba(13,13,13,0.03)] py-[6px] pl-7 pr-7 text-[14px] text-[#1A1A1A] outline-none placeholder:text-[rgba(13,13,13,0.32)] focus:border-[rgba(217,119,87,0.4)] focus:bg-white"
            />
            {search ? (
              <button
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)] transition-colors hover:text-[#1A1A1A]"
              >
                <X size={12} />
              </button>
            ) : (
              <button
                onClick={() => window.dispatchEvent(new Event("open-global-search"))}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[12px] font-medium text-[rgba(13,13,13,0.25)] hover:text-[rgba(217,119,87,0.7)] transition-colors"
                title="Поиск по истории (Ctrl+K)"
              >
                ⌘K
              </button>
            )}
          </div>
        </div>

        {/* Projects section — always visible */}
        <div className="border-b border-[rgba(13,13,13,0.06)] pb-1">
          <div className="flex items-center justify-between px-3 pb-1 pt-2.5">
            <button
              onClick={() => setProjectsOpen((v) => !v)}
              className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.28)] hover:text-[rgba(13,13,13,0.5)] transition-colors"
            >
              Проекты
              <ChevronDown
                size={10}
                className="transition-transform duration-150"
                style={{ transform: projectsOpen ? "none" : "rotate(-90deg)" }}
              />
            </button>
            <button
              onClick={() => setShowProjectModal("create")}
              title="Новый проект"
              className="flex h-5 w-5 items-center justify-center rounded-[4px] text-[rgba(13,13,13,0.30)] hover:bg-[rgba(13,13,13,0.07)] hover:text-[#D97757] transition-colors"
            >
              <Plus size={12} />
            </button>
          </div>
          {projectsOpen && (
            <div className="pb-0.5">
              {projects.length === 0 ? (
                <button
                  onClick={() => setShowProjectModal("create")}
                  className="mx-1 flex w-[calc(100%-8px)] items-center gap-2 rounded-[7px] px-2.5 py-1.5 text-[13px] text-[rgba(13,13,13,0.38)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#D97757] transition-colors"
                >
                  <Plus size={11} />
                  Создать проект
                </button>
              ) : (
                projects.map((project: Project) => (
                  <ProjectSidebarRow
                    key={project.id}
                    project={project}
                    isExpanded={expandedProject === project.id}
                    onToggle={() => setExpandedProject(expandedProject === project.id ? null : project.id)}
                    onEdit={() => setEditingProject(project)}
                    onDelete={() => deleteProjectMutation.mutate(project.id)}
                    currentPath={pathname}
                  />
                ))
              )}
            </div>
          )}
        </div>

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 && (
            <div className="px-4 py-10 text-center text-[14px] text-[rgba(13,13,13,0.38)]">
              {search ? (
                "Ничего не найдено"
              ) : (
                <>
                  Чатов пока нет.
                  <br />
                  <Link href="/models/" className="mt-1 inline-block text-[#D97757] hover:underline">
                    Выбрать модель
                  </Link>
                </>
              )}
            </div>
          )}

          {grouped.map(({ group, items }) => (
            <div key={group}>
              <p className="px-3 pb-0.5 pt-3 text-[12px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.28)]">
                {group}
              </p>

              {items.map((chat) => {
                const active = pathname === `/chat/${chat.id}/` || pathname === `/chat/${chat.id}`;
                const isDeleting = deletingId === chat.id;
                const isEditing = editingId === chat.id;

                return (
                  <div
                    key={chat.id}
                    ref={(el) => {
                      if (el) itemRefs.current.set(chat.id, el);
                      else itemRefs.current.delete(chat.id);
                    }}
                    onMouseEnter={() => handleItemMouseEnter(chat.id)}
                    onMouseLeave={handleItemMouseLeave}
                    className={[
                      "group relative mx-1 my-0.5 flex items-start gap-2 rounded-[8px] px-2.5 py-2 transition-colors",
                      active ? "bg-[rgba(217,119,87,0.07)]" : "hover:bg-[rgba(13,13,13,0.04)]",
                    ].join(" ")}
                  >
                    {/* Active indicator */}
                    {active && (
                      <div
                        className="absolute left-0 top-2 bottom-2 w-[2.5px] rounded-r-full bg-[#D97757]"
                      />
                    )}

                    {/* Avatar */}
                    <div className="mt-[2px] shrink-0">
                      {chat.network.avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={chat.network.avatar}
                          alt=""
                          width={22}
                          height={22}
                          className="rounded-[5px] object-cover"
                        />
                      ) : (
                        <div className="flex h-[22px] w-[22px] items-center justify-center rounded-[5px] bg-[rgba(217,119,87,0.10)]">
                          {chat.network.handle_photo || chat.network.handle_video ? (
                            <ImageIcon size={12} className="text-[#D97757]" />
                          ) : (
                            <Code2 size={12} className="text-[#D97757]" />
                          )}
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      {isDeleting ? (
                        <div className="py-0.5">
                          <p className="mb-1.5 text-[13px] font-medium text-[rgba(13,13,13,0.65)]">
                            Удалить чат?
                          </p>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => deleteMutation.mutate(chat.id)}
                              disabled={deleteMutation.isPending}
                              className="flex h-[22px] items-center gap-1 rounded-[5px] bg-[#e74c3c] px-2 text-[13px] font-medium text-white transition-colors hover:bg-[#c0392b] disabled:opacity-50"
                            >
                              <Trash2 size={10} />
                              Удалить
                            </button>
                            <button
                              onClick={() => setDeletingId(null)}
                              className="flex h-[22px] items-center rounded-[5px] px-2 text-[13px] text-[rgba(13,13,13,0.5)] transition-colors hover:bg-[rgba(13,13,13,0.06)]"
                            >
                              Отмена
                            </button>
                          </div>
                        </div>
                      ) : isEditing ? (
                        <div className="flex items-center gap-1">
                          <input
                            ref={editRef}
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") submitRename(chat.id);
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            onBlur={() => submitRename(chat.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="min-w-0 flex-1 rounded-[5px] border border-[rgba(217,119,87,0.45)] bg-white px-1.5 py-0.5 text-[14px] text-[#1A1A1A] outline-none"
                          />
                          <button
                            onClick={() => submitRename(chat.id)}
                            className="shrink-0 text-[#D97757] transition-colors hover:text-[#C4623E]"
                          >
                            <Check size={13} />
                          </button>
                        </div>
                      ) : (
                        <Link href={`/chat/${chat.id}/`} className="block">
                          <div className="flex items-baseline justify-between gap-1">
                            <p
                              className={[
                                "truncate text-[14px] font-medium leading-[1.35]",
                                active ? "text-[#D97757]" : "text-[#1A1A1A]",
                              ].join(" ")}
                            >
                              {chat.title || chat.network.name}
                            </p>
                            <span className="shrink-0 text-[12px] text-[rgba(13,13,13,0.28)]">
                              {timeAgo(chat.updated_at)}
                            </span>
                          </div>

                          {chat.last_message ? (
                            <p className="mt-0.5 truncate text-[13px] leading-[1.4] text-[rgba(13,13,13,0.42)]">
                              {chat.last_message.role === "user" ? "Вы: " : ""}
                              {chat.last_message.preview}
                            </p>
                          ) : (
                            <p className="mt-0.5 text-[13px] leading-[1.4] text-[rgba(13,13,13,0.27)]">
                              Пустой чат
                            </p>
                          )}
                        </Link>
                      )}
                    </div>

                    {/* Action buttons — reveal on hover */}
                    {!isDeleting && !isEditing && (
                      <div className="absolute right-1.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 group-hover:flex">
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setPreview(null);
                            setEditingId(chat.id);
                            setEditTitle(chat.title || chat.network.name);
                          }}
                          title="Переименовать"
                          className="flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.07)] hover:text-[#1A1A1A]"
                        >
                          <Edit3 size={11} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            setPreview(null);
                            setDeletingId(chat.id);
                          }}
                          title="Удалить"
                          className="flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c]"
                        >
                          <Trash2 size={11} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* Bottom padding */}
          <div className="h-4" />
        </div>
      </aside>

      {/* Hover Preview Card — unique feature */}
      {previewChat && preview && (
        <PreviewCard
          chat={previewChat}
          y={preview.y}
          onMouseEnter={cancelClear}
          onMouseLeave={() => setPreview(null)}
        />
      )}

      {/* Project modals */}
      {showProjectModal === "create" && (
        <ProjectModal
          mode="create"
          onClose={() => setShowProjectModal(null)}
          onSave={(data) => createProjectMutation.mutateAsync(data)}
        />
      )}
      {editingProject && (
        <ProjectModal
          mode="edit"
          initial={editingProject}
          onClose={() => setEditingProject(null)}
          onSave={(data) => updateProjectMutation.mutateAsync({ id: editingProject.id, ...data })}
        />
      )}

      <style>{`
        @keyframes sidebarPreviewIn {
          from { opacity: 0; transform: translateX(-8px) scale(0.97); }
          to   { opacity: 1; transform: translateX(0)  scale(1);     }
        }
      `}</style>
    </>
  );
}
