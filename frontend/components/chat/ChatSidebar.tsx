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
} from "lucide-react";
import { listChats, deleteChat, renameChat, listProjects } from "@/lib/api/client";
import type { ChatListItem, Project } from "@/lib/api/types";

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
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-[rgba(10,124,255,0.10)]">
              {chat.network.handle_photo || chat.network.handle_video ? (
                <ImageIcon size={14} className="text-[#0a7cff]" />
              ) : (
                <Code2 size={14} className="text-[#0a7cff]" />
              )}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-[12px] font-semibold text-[#0d0d0d]">
              {chat.title || chat.network.name}
            </p>
            <p className="text-[10px] text-[rgba(13,13,13,0.42)]">
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
                  className="max-w-[85%] rounded-[10px] rounded-br-[3px] px-3 py-2 text-[11px] leading-[1.5] text-white"
                  style={{ background: "#0d0d0d" }}
                >
                  {chat.last_message.preview}
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[rgba(10,124,255,0.10)]">
                  <MessageSquare size={10} className="text-[#0a7cff]" />
                </div>
                <p className="text-[11px] leading-[1.6] text-[rgba(13,13,13,0.72)]">
                  {chat.last_message.preview}
                </p>
              </div>
            )
          ) : (
            <p className="text-[11px] text-[rgba(13,13,13,0.35)]">Чат пустой</p>
          )}
        </div>

        {/* CTA */}
        <div className="border-t border-[rgba(13,13,13,0.06)] px-3 py-2">
          <p className="text-[10px] font-medium text-[rgba(10,124,255,0.75)]">
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

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const [projectsOpen, setProjectsOpen] = useState(true);

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
            className="flex h-8 w-8 items-center justify-center rounded-[7px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d]"
          >
            <ChevronRight size={15} />
          </button>
          <Link
            href="/models/"
            title="Новый чат"
            className="flex h-8 w-8 items-center justify-center rounded-[7px] bg-[#0a7cff] text-white transition-colors hover:bg-[#0066cc]"
          >
            <PenSquare size={14} />
          </Link>
          <Link
            href="/models/"
            title="Каталог"
            className="flex h-8 w-8 items-center justify-center rounded-[7px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d]"
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
                  active ? "bg-[rgba(10,124,255,0.10)]" : "hover:bg-[rgba(13,13,13,0.05)]",
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
            className="flex h-8 flex-1 items-center gap-1.5 rounded-[7px] bg-[#0a7cff] px-3 text-[12px] font-medium text-white transition-colors hover:bg-[#0066cc]"
          >
            <PenSquare size={13} />
            Новый чат
          </Link>
          <Link
            href="/models/"
            title="Каталог"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d]"
          >
            <LayoutGrid size={14} />
          </Link>
          <button
            onClick={toggleCollapse}
            title="Свернуть"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[7px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.42)] transition-colors hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d]"
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
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.11)] bg-[rgba(13,13,13,0.03)] py-[6px] pl-7 pr-7 text-[12px] text-[#0d0d0d] outline-none placeholder:text-[rgba(13,13,13,0.32)] focus:border-[rgba(10,124,255,0.4)] focus:bg-white"
            />
            {search ? (
              <button
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[rgba(13,13,13,0.35)] transition-colors hover:text-[#0d0d0d]"
              >
                <X size={12} />
              </button>
            ) : (
              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-medium text-[rgba(13,13,13,0.25)]">
                ⌘K
              </span>
            )}
          </div>
        </div>

        {/* Projects section */}
        {projects.length > 0 && (
          <div className="border-b border-[rgba(13,13,13,0.06)] pb-1">
            <button
              onClick={() => setProjectsOpen((v) => !v)}
              className="flex w-full items-center justify-between px-3 pb-1 pt-2.5"
            >
              <span className="text-[10px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.28)]">
                Проекты
              </span>
              <ChevronDown
                size={11}
                className="text-[rgba(13,13,13,0.28)] transition-transform duration-150"
                style={{ transform: projectsOpen ? "none" : "rotate(-90deg)" }}
              />
            </button>
            {projectsOpen && (
              <div className="pb-1">
                {projects.map((project: Project) => (
                  <Link
                    key={project.id}
                    href={`/projects/${project.id}/`}
                    className="mx-1 flex items-center gap-2 rounded-[7px] px-2.5 py-1.5 text-[12px] text-[rgba(13,13,13,0.65)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#0d0d0d] transition-colors"
                  >
                    <span
                      className="flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px]"
                      style={{ background: `${project.color}20`, color: project.color }}
                    >
                      <Folder size={10} />
                    </span>
                    <span className="truncate">{project.name}</span>
                    <span className="ml-auto shrink-0 text-[10px] text-[rgba(13,13,13,0.28)]">
                      {project.chat_count}
                    </span>
                  </Link>
                ))}
                <Link
                  href="/projects/"
                  className="mx-1 flex items-center gap-2 rounded-[7px] px-2.5 py-1.5 text-[11px] text-[rgba(13,13,13,0.40)] hover:text-[#0a7cff] transition-colors"
                >
                  <Plus size={11} />
                  Новый проект
                </Link>
              </div>
            )}
          </div>
        )}

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto">
          {filtered.length === 0 && (
            <div className="px-4 py-10 text-center text-[12px] text-[rgba(13,13,13,0.38)]">
              {search ? (
                "Ничего не найдено"
              ) : (
                <>
                  Чатов пока нет.
                  <br />
                  <Link href="/models/" className="mt-1 inline-block text-[#0a7cff] hover:underline">
                    Выбрать модель
                  </Link>
                </>
              )}
            </div>
          )}

          {grouped.map(({ group, items }) => (
            <div key={group}>
              <p className="px-3 pb-0.5 pt-3 text-[10px] font-semibold uppercase tracking-wider text-[rgba(13,13,13,0.28)]">
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
                      active ? "bg-[rgba(10,124,255,0.07)]" : "hover:bg-[rgba(13,13,13,0.04)]",
                    ].join(" ")}
                  >
                    {/* Active indicator */}
                    {active && (
                      <div
                        className="absolute left-0 top-2 bottom-2 w-[2.5px] rounded-r-full bg-[#0a7cff]"
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
                        <div className="flex h-[22px] w-[22px] items-center justify-center rounded-[5px] bg-[rgba(10,124,255,0.10)]">
                          {chat.network.handle_photo || chat.network.handle_video ? (
                            <ImageIcon size={12} className="text-[#0a7cff]" />
                          ) : (
                            <Code2 size={12} className="text-[#0a7cff]" />
                          )}
                        </div>
                      )}
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      {isDeleting ? (
                        <div className="py-0.5">
                          <p className="mb-1.5 text-[11px] font-medium text-[rgba(13,13,13,0.65)]">
                            Удалить чат?
                          </p>
                          <div className="flex gap-1.5">
                            <button
                              onClick={() => deleteMutation.mutate(chat.id)}
                              disabled={deleteMutation.isPending}
                              className="flex h-[22px] items-center gap-1 rounded-[5px] bg-[#e74c3c] px-2 text-[11px] font-medium text-white transition-colors hover:bg-[#c0392b] disabled:opacity-50"
                            >
                              <Trash2 size={10} />
                              Удалить
                            </button>
                            <button
                              onClick={() => setDeletingId(null)}
                              className="flex h-[22px] items-center rounded-[5px] px-2 text-[11px] text-[rgba(13,13,13,0.5)] transition-colors hover:bg-[rgba(13,13,13,0.06)]"
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
                            className="min-w-0 flex-1 rounded-[5px] border border-[rgba(10,124,255,0.45)] bg-white px-1.5 py-0.5 text-[12px] text-[#0d0d0d] outline-none"
                          />
                          <button
                            onClick={() => submitRename(chat.id)}
                            className="shrink-0 text-[#0a7cff] transition-colors hover:text-[#0066cc]"
                          >
                            <Check size={13} />
                          </button>
                        </div>
                      ) : (
                        <Link href={`/chat/${chat.id}/`} className="block">
                          <div className="flex items-baseline justify-between gap-1">
                            <p
                              className={[
                                "truncate text-[12px] font-medium leading-[1.35]",
                                active ? "text-[#0a7cff]" : "text-[#0d0d0d]",
                              ].join(" ")}
                            >
                              {chat.title || chat.network.name}
                            </p>
                            <span className="shrink-0 text-[10px] text-[rgba(13,13,13,0.28)]">
                              {timeAgo(chat.updated_at)}
                            </span>
                          </div>

                          {chat.last_message ? (
                            <p className="mt-0.5 truncate text-[11px] leading-[1.4] text-[rgba(13,13,13,0.42)]">
                              {chat.last_message.role === "user" ? "Вы: " : ""}
                              {chat.last_message.preview}
                            </p>
                          ) : (
                            <p className="mt-0.5 text-[11px] leading-[1.4] text-[rgba(13,13,13,0.27)]">
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
                          className="flex h-6 w-6 items-center justify-center rounded-[5px] text-[rgba(13,13,13,0.4)] transition-colors hover:bg-[rgba(13,13,13,0.07)] hover:text-[#0d0d0d]"
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

      <style>{`
        @keyframes sidebarPreviewIn {
          from { opacity: 0; transform: translateX(-8px) scale(0.97); }
          to   { opacity: 1; transform: translateX(0)  scale(1);     }
        }
      `}</style>
    </>
  );
}
