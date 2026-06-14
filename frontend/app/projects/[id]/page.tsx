"use client";

import { use, useState } from "react";
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
} from "lucide-react";
import { listProjects, listChats, deleteChat } from "@/lib/api/client";
import type { ChatListItem, Project } from "@/lib/api/types";

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

export default function ProjectDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = parseInt(id, 10);
  const qc = useQueryClient();
  const [deletingId, setDeletingId] = useState<number | null>(null);

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
            <Folder size={18} style={{ color: project?.color ?? "#0a7cff" }} />
          </div>
          <div>
            <h1 className="text-[22px] font-bold text-[#0d0d0d]">
              {project?.name ?? "Проект"}
            </h1>
            {project?.system_prompt && (
              <p className="mt-0.5 text-[13px] text-[rgba(13,13,13,0.50)]">
                {project.system_prompt.length > 120
                  ? project.system_prompt.slice(0, 120) + "..."
                  : project.system_prompt}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* New chat button */}
      <div className="mb-5">
        <Link
          href="/models/"
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
            Чаты в этом проекте появятся здесь
          </p>
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
                    {/* Network avatar */}
                    <div className="mt-0.5 shrink-0">
                      {chat.network.avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={chat.network.avatar}
                          alt=""
                          width={32}
                          height={32}
                          className="rounded-[7px] object-cover"
                        />
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

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="truncate text-[14px] font-medium text-[#0d0d0d]">
                          {chat.title || chat.network.name}
                        </p>
                        <span className="shrink-0 text-[11px] text-[rgba(13,13,13,0.35)]">
                          {timeAgo(chat.updated_at)}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[12px] text-[rgba(13,13,13,0.45)]">
                        {chat.network.name}
                      </p>
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
                    onClick={(e) => {
                      e.preventDefault();
                      setDeletingId(chat.id);
                    }}
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

    </div>
  );
}
