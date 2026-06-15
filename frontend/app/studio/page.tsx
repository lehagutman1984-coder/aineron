"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { LayoutGrid, Plus, Loader2, Cpu, Clock, ChevronRight } from "lucide-react";
import { studioApi } from "@/lib/api/studio";
import type { StudioProject, StudioMode, StudioStack } from "@/lib/api/studio";

const STACK_OPTIONS: { value: StudioStack; label: string }[] = [
  { value: "nextjs", label: "Next.js" },
  { value: "react", label: "React" },
  { value: "vue", label: "Vue" },
  { value: "html", label: "HTML" },
];

const MODE_OPTIONS: { value: StudioMode; label: string; hint: string }[] = [
  { value: "auto", label: "Авто", hint: "Агенты работают без остановок" },
  { value: "semi", label: "Полу-авто", hint: "Подтверждение перед каждым шагом" },
  { value: "manual", label: "Ручной", hint: "Полный контроль над каждым файлом" },
];

const STATUS_LABEL: Record<string, string> = {
  draft: "Черновик",
  interview: "Интервью",
  planning: "Планирование",
  ready: "Готов",
  coding: "Кодинг",
  paused: "Пауза",
  completed: "Завершён",
  failed: "Ошибка",
};

export default function StudioPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<StudioMode>("auto");
  const [stack, setStack] = useState<StudioStack>("nextjs");

  const { data: projects, isLoading } = useQuery({
    queryKey: ["studio-projects"],
    queryFn: studioApi.list,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      studioApi.create({ name, description, mode, target_stack: stack }),
    onSuccess: (project: StudioProject) => {
      qc.invalidateQueries({ queryKey: ["studio-projects"] });
      router.push(`/studio/${project.id}/interview`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate();
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <LayoutGrid size={24} className="text-blue-500" />
          <h1 className="text-2xl font-semibold">Vibe-Coding Studio</h1>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Создать проект
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-6 mb-8 space-y-5"
        >
          <h2 className="text-lg font-semibold">Новый проект</h2>

          <div>
            <label className="block text-sm font-medium mb-1">Название</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Мой стартап"
              className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Описание</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Опишите что хотите создать..."
              rows={3}
              className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Режим</label>
            <div className="flex gap-2">
              {MODE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setMode(opt.value)}
                  title={opt.hint}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    mode === opt.value
                      ? "border-blue-500 bg-blue-600 text-white"
                      : "border-[var(--border)] hover:border-blue-400"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Стек</label>
            <select
              value={stack}
              onChange={(e) => setStack(e.target.value as StudioStack)}
              className="w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {STACK_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={createMutation.isPending || !name.trim()}
              className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {createMutation.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Cpu size={16} />
              )}
              Создать
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-5 py-2 rounded-lg text-sm border border-[var(--border)] hover:bg-[var(--hover)] transition-colors"
            >
              Отмена
            </button>
          </div>

          {createMutation.isError && (
            <p className="text-red-500 text-sm">
              Ошибка при создании проекта. Попробуйте ещё раз.
            </p>
          )}
        </form>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-[var(--text-secondary)]" />
        </div>
      ) : !projects || projects.length === 0 ? (
        <div className="text-center py-16 text-[var(--text-secondary)]">
          <LayoutGrid size={40} className="mx-auto mb-4 opacity-30" />
          <p className="text-sm">Проектов пока нет. Создайте первый!</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {projects.map((project) => (
            <li key={project.id}>
              <a
                href={`/studio/${project.id}`}
                className="flex items-center gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card-bg)] hover:border-blue-400 transition-colors group"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{project.name}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--hover)] text-[var(--text-secondary)]">
                      {STATUS_LABEL[project.status] ?? project.status}
                    </span>
                  </div>
                  {project.description && (
                    <p className="text-sm text-[var(--text-secondary)] truncate mt-0.5">
                      {project.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)] shrink-0">
                  <span className="flex items-center gap-1">
                    <Clock size={12} />
                    {new Date(project.created_at).toLocaleDateString("ru-RU")}
                  </span>
                  <ChevronRight
                    size={16}
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                  />
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
