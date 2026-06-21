"use client";

import { useState } from "react";
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
} from "lucide-react";
import { listProjects, listChats, deleteChat, updateProject } from "@/lib/api/client";
import type { ChatListItem, Project } from "@/lib/api/types";

const ICON_MAP: Record<string, React.ElementType> = {
  Folder, Code2, BookOpen, Briefcase, Zap, Globe, Palette, MessageSquare,
};
const ICONS = Object.keys(ICON_MAP);
const COLORS = ["#0a7cff", "#22a85a", "#e67e22", "#9b59b6", "#e74c3c", "#1dd6c1", "#0d0d0d", "#6366f1"];

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
  const [systemPrompt, setSystemPrompt] = useState(project.system_prompt ?? "");
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
      const updated = await updateProject(project.id, {
        name: name.trim(),
        system_prompt: systemPrompt.trim(),
        color,
        icon,
      });
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
        className="w-full max-w-[440px] rounded-[18px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#0d0d0d]">Настройки проекта</h2>
          <button onClick={onClose} className="rounded-[7px] p-1 text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">Название</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[14px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">Иконка</label>
              <div className="flex flex-wrap gap-1.5">
                {ICONS.map((ic) => {
                  const Icon = ICON_MAP[ic];
                  return (
                    <button key={ic} type="button" onClick={() => setIcon(ic)}
                      className={["flex h-8 w-8 items-center justify-center rounded-[7px] transition-colors", icon === ic ? "ring-2 ring-[#0a7cff] ring-offset-1" : "border border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.05)]"].join(" ")}
                      style={{ color: icon === ic ? color : "rgba(13,13,13,0.45)" }}
                    >
                      <Icon size={15} />
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">Цвет</label>
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

          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">
              Системный промт <span className="text-[rgba(13,13,13,0.35)]">(необязательно)</span>
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Ты — помощник-программист, отвечай только на русском..."
              rows={3}
              className="w-full resize-none rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[13px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
            />
            <p className="mt-1 text-[11px] text-[rgba(13,13,13,0.38)]">
              Применяется ко всем чатам в проекте автоматически
            </p>
          </div>

          {error && (
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[13px] text-[#e74c3c]">{error}</div>
          )}

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose}
              className="rounded-[8px] px-4 py-2 text-[13px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.06)] transition-colors">
              Отмена
            </button>
            <button type="submit" disabled={!name.trim() || loading}
              className="rounded-[8px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] disabled:opacity-50 transition-colors">
              {loading ? "Сохранение..." : "Сохранить"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ProjectDetailPage({ params }: { params: { id: string } }) {
  const projectId = parseInt(params.id, 10);
  const qc = useQueryClient();
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [showEdit, setShowEdit] = useState(false);

  const { data: projects = [] } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
  });

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

  const project: Project | undefined = projects.find((p) => p.id === projectId);

  const handleProjectSaved = (updated: Project) => {
    qc.setQueryData<Project[]>(["projects"], (prev) =>
      prev?.map((p) => (p.id === updated.id ? updated : p)) ?? []
    );
    setShowEdit(false);
  };

  return (
    <div className="mx-auto max-w-[760px] px-4 py-8">
      {/* Back + header */}
      <div className="mb-6">
        <Link
          href="/projects/"
          className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-[rgba(13,13,13,0.50)] hover:text-[#0d0d0d] transition-colors"
        >
          <ArrowLeft size={14} />
          Все проекты
        </Link>

        <div className="flex items-start gap-3">
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px]"
            style={{ background: project ? `${project.color}18` : "rgba(10,124,255,0.08)" }}
          >
            <span style={{ color: project?.color ?? "#0a7cff" }}>
              <ProjectIcon name={project?.icon ?? "Folder"} size={18} />
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-[22px] font-bold text-[#0d0d0d]">{project?.name ?? "Проект"}</h1>
            {project?.system_prompt && (
              <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.50)]">
                {project.system_prompt.length > 120
                  ? project.system_prompt.slice(0, 120) + "..."
                  : project.system_prompt}
              </p>
            )}
          </div>
          <button
            onClick={() => setShowEdit(true)}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] border border-[rgba(13,13,13,0.11)] text-[rgba(13,13,13,0.42)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#0d0d0d] transition-colors"
            title="Настройки проекта"
          >
            <Settings size={14} />
          </button>
        </div>
      </div>

      {/* New chat button */}
      <div className="mb-5">
        <Link
          href={`/models/?project_id=${projectId}`}
          className="inline-flex items-center gap-1.5 rounded-[9px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          <Plus size={14} />
          Новый чат в проекте
        </Link>
      </div>

      {/* Chat list */}
      {isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-[12px] bg-[rgba(13,13,13,0.05)]" />
          ))}
        </div>
      ) : chats.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-[16px] border border-dashed border-[rgba(13,13,13,0.15)] py-14 text-center">
          <MessageSquare size={28} className="mb-3 text-[rgba(13,13,13,0.25)]" />
          <p className="mb-1 text-[14px] font-medium text-[#0d0d0d]">Нет чатов</p>
          <p className="mb-4 text-[13px] text-[rgba(13,13,13,0.45)]">
            Нажмите "Новый чат в проекте" чтобы начать
          </p>
          <Link
            href={`/models/?project_id=${projectId}`}
            className="inline-flex items-center gap-1.5 rounded-[9px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
          >
            <Plus size={14} />
            Новый чат
          </Link>
        </div>
      ) : (
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
                    <p className="flex-1 text-[13px] text-[rgba(13,13,13,0.65)]">Удалить чат?</p>
                    <button
                      onClick={() => deleteMutation.mutate(chat.id)}
                      disabled={deleteMutation.isPending}
                      className="rounded-[6px] bg-[#e74c3c] px-2.5 py-1 text-[12px] font-medium text-white hover:bg-[#c0392b] disabled:opacity-50 transition-colors"
                    >
                      Удалить
                    </button>
                    <button
                      onClick={() => setDeletingId(null)}
                      className="rounded-[6px] px-2.5 py-1 text-[12px] text-[rgba(13,13,13,0.50)] hover:bg-[rgba(13,13,13,0.06)] transition-colors"
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
                        <div className="flex h-8 w-8 items-center justify-center rounded-[7px] bg-[rgba(10,124,255,0.10)]">
                          {chat.network.handle_photo || chat.network.handle_video ? (
                            <ImageIcon size={14} className="text-[#0a7cff]" />
                          ) : (
                            <Code2 size={14} className="text-[#0a7cff]" />
                          )}
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="truncate text-[14px] font-medium text-[#0d0d0d]">
                          {chat.title || chat.network.name}
                        </p>
                        <span className="shrink-0 text-[11px] text-[rgba(13,13,13,0.35)]">
                          {timeAgo(chat.updated_at)}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.45)]">{chat.network.name}</p>
                      {chat.last_message && (
                        <p className="mt-1 truncate text-[12px] text-[rgba(13,13,13,0.40)]">
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
      )}

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
