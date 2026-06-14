"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import {
  Folder,
  Plus,
  Trash2,
  MessageSquare,
  ChevronRight,
  Code2,
  BookOpen,
  Briefcase,
  Zap,
  Globe,
  Palette,
  X,
} from "lucide-react";
import { listProjects, createProject, deleteProject } from "@/lib/api/client";
import type { Project } from "@/lib/api/types";

// ── Icon map ──────────────────────────────────────────────────
const ICON_MAP: Record<string, React.ElementType> = {
  Folder,
  Code2,
  BookOpen,
  Briefcase,
  Zap,
  Globe,
  Palette,
  MessageSquare,
};

const ICONS = Object.keys(ICON_MAP) as (keyof typeof ICON_MAP)[];

const COLORS = [
  "#0a7cff",
  "#22a85a",
  "#e67e22",
  "#9b59b6",
  "#e74c3c",
  "#1dd6c1",
  "#0d0d0d",
  "#6366f1",
];

function ProjectIcon({ name, size = 16 }: { name: string; size?: number }) {
  const Icon = ICON_MAP[name] ?? Folder;
  return <Icon size={size} />;
}

// ── Create modal ──────────────────────────────────────────────

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (p: Project) => void }) {
  const [name, setName] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [color, setColor] = useState(COLORS[0]);
  const [icon, setIcon] = useState("Folder");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const project = await createProject({ name: name.trim(), system_prompt: systemPrompt.trim(), color, icon });
      onCreated(project);
    } catch {
      setError("Не удалось создать проект");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[440px] rounded-[18px] border border-[rgba(13,13,13,0.10)] bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-[16px] font-semibold text-[#0d0d0d]">Новый проект</h2>
          <button onClick={onClose} className="rounded-[7px] p-1 text-[rgba(13,13,13,0.4)] hover:bg-[rgba(13,13,13,0.06)] hover:text-[#0d0d0d] transition-colors">
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Name */}
          <div>
            <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">
              Название
            </label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Мой проект"
              maxLength={100}
              className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[14px] text-[#0d0d0d] outline-none focus:border-[#0a7cff] focus:ring-2 focus:ring-[rgba(10,124,255,0.12)] transition-all"
            />
          </div>

          {/* Icon + Color row */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">
                Иконка
              </label>
              <div className="flex flex-wrap gap-1.5">
                {ICONS.map((ic) => (
                  <button
                    key={ic}
                    type="button"
                    onClick={() => setIcon(ic)}
                    className={[
                      "flex h-8 w-8 items-center justify-center rounded-[7px] transition-colors",
                      icon === ic
                        ? "ring-2 ring-[#0a7cff] ring-offset-1"
                        : "border border-[rgba(13,13,13,0.12)] hover:bg-[rgba(13,13,13,0.05)]",
                    ].join(" ")}
                    style={{ color: icon === ic ? color : "rgba(13,13,13,0.45)" }}
                  >
                    <ProjectIcon name={ic} size={15} />
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1.5 block text-[12px] font-medium text-[rgba(13,13,13,0.55)]">
                Цвет
              </label>
              <div className="flex flex-wrap gap-1.5">
                {COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    className={[
                      "h-7 w-7 rounded-full transition-transform",
                      color === c ? "scale-110 ring-2 ring-offset-1 ring-[rgba(13,13,13,0.25)]" : "hover:scale-105",
                    ].join(" ")}
                    style={{ background: c }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* System prompt */}
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
            <div className="rounded-[8px] bg-[rgba(231,76,60,0.08)] px-3 py-2 text-[13px] text-[#e74c3c]">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-[8px] px-4 py-2 text-[13px] text-[rgba(13,13,13,0.55)] hover:bg-[rgba(13,13,13,0.06)] transition-colors"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="rounded-[8px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] disabled:opacity-50 transition-colors"
            >
              {loading ? "Создание..." : "Создать"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Project card ──────────────────────────────────────────────

function ProjectCard({
  project,
  onDelete,
}: {
  project: Project;
  onDelete: (id: number) => void;
}) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <div className="group relative rounded-[14px] border border-[rgba(13,13,13,0.09)] bg-white p-5 transition-shadow hover:shadow-md">
      {/* Icon + color dot */}
      <div
        className="mb-3 flex h-10 w-10 items-center justify-center rounded-[10px]"
        style={{ background: `${project.color}18` }}
      >
        <span style={{ color: project.color }}>
          <ProjectIcon name={project.icon} size={18} />
        </span>
      </div>

      <h3 className="mb-1 text-[14px] font-semibold text-[#0d0d0d]">{project.name}</h3>

      {project.system_prompt ? (
        <p className="mb-3 line-clamp-2 text-[12px] leading-[1.5] text-[rgba(13,13,13,0.50)]">
          {project.system_prompt}
        </p>
      ) : (
        <p className="mb-3 text-[12px] text-[rgba(13,13,13,0.32)]">Без системного промта</p>
      )}

      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[12px] text-[rgba(13,13,13,0.45)]">
          <MessageSquare size={12} />
          {project.chat_count} чатов
        </span>

        <Link
          href={`/projects/${project.id}/`}
          className="flex items-center gap-0.5 text-[12px] font-medium text-[#0a7cff] hover:text-[#0066cc] transition-colors"
        >
          Открыть
          <ChevronRight size={13} />
        </Link>
      </div>

      {/* Delete button — hover reveal */}
      {!confirmDelete ? (
        <button
          onClick={() => setConfirmDelete(true)}
          className="absolute right-3 top-3 hidden h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] opacity-0 transition-all hover:bg-[rgba(231,76,60,0.09)] hover:text-[#e74c3c] group-hover:flex group-hover:opacity-100"
        >
          <Trash2 size={13} />
        </button>
      ) : (
        <div className="absolute right-3 top-3 flex items-center gap-1 rounded-[8px] border border-[rgba(231,76,60,0.20)] bg-white p-1.5 shadow-lg">
          <span className="px-1 text-[11px] text-[rgba(13,13,13,0.55)]">Удалить?</span>
          <button
            onClick={() => onDelete(project.id)}
            className="rounded-[5px] bg-[#e74c3c] px-2 py-0.5 text-[11px] font-medium text-white hover:bg-[#c0392b] transition-colors"
          >
            Да
          </button>
          <button
            onClick={() => setConfirmDelete(false)}
            className="rounded-[5px] px-1.5 py-0.5 text-[11px] text-[rgba(13,13,13,0.45)] hover:bg-[rgba(13,13,13,0.07)] transition-colors"
          >
            Нет
          </button>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function ProjectsPage() {
  const qc = useQueryClient();
  const [showModal, setShowModal] = useState(false);

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 60_000,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteProject,
    onSuccess: (_, id) => {
      qc.setQueryData<Project[]>(["projects"], (prev) => prev?.filter((p) => p.id !== id) ?? []);
    },
  });

  const handleCreated = (project: Project) => {
    qc.setQueryData<Project[]>(["projects"], (prev) => [project, ...(prev ?? [])]);
    setShowModal(false);
  };

  return (
    <div className="mx-auto max-w-[960px] px-4 py-8">
      {/* Header */}
      <div className="mb-7 flex items-center justify-between">
        <div>
          <h1 className="text-[24px] font-bold text-[#0d0d0d]">Проекты</h1>
          <p className="mt-0.5 text-[14px] text-[rgba(13,13,13,0.50)]">
            Группируйте чаты по задачам и задавайте общий системный промт
          </p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 rounded-[9px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
        >
          <Plus size={15} />
          Новый проект
        </button>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-44 animate-pulse rounded-[14px] bg-[rgba(13,13,13,0.05)]" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-[16px] border border-dashed border-[rgba(13,13,13,0.15)] py-16 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-[rgba(10,124,255,0.08)]">
            <Folder size={22} className="text-[#0a7cff]" />
          </div>
          <p className="mb-1 text-[15px] font-medium text-[#0d0d0d]">Нет проектов</p>
          <p className="mb-4 text-[13px] text-[rgba(13,13,13,0.45)]">
            Создайте первый проект, чтобы группировать чаты
          </p>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 rounded-[9px] bg-[#0a7cff] px-4 py-2 text-[13px] font-medium text-white hover:bg-[#0066cc] transition-colors"
          >
            <Plus size={15} />
            Создать проект
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onDelete={(id) => deleteMutation.mutate(id)}
            />
          ))}
        </div>
      )}

      {showModal && (
        <CreateModal onClose={() => setShowModal(false)} onCreated={handleCreated} />
      )}
    </div>
  );
}
