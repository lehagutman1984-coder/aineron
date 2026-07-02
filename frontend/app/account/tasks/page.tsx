"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock,
  Plus,
  Trash2,
  Play,
  Pause,
  Zap,
  Globe,
} from "lucide-react";
import { request, APIError } from "@/lib/api/client";

interface AITask {
  id: number;
  title: string;
  prompt: string;
  schedule_type: "once" | "daily" | "weekly" | "cron";
  run_time: string | null;
  weekday: number | null;
  use_web_search: boolean;
  is_active: boolean;
  paused_reason: string;
  last_run_at: string | null;
  runs_count: number;
  created_from: string;
  schedule_human: string;
}

interface TasksResponse {
  tasks: AITask[];
  active_count: number;
  limit: number;
}

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

const listTasks = () => request<TasksResponse>("/tasks/");
const createTask = (body: Partial<AITask>) =>
  request<AITask>("/tasks/", { method: "POST", body: JSON.stringify(body) });
const patchTask = (id: number, body: Partial<AITask>) =>
  request<AITask>(`/tasks/${id}/`, { method: "PATCH", body: JSON.stringify(body) });
const deleteTask = (id: number) =>
  request<void>(`/tasks/${id}/`, { method: "DELETE" });
const runTaskNow = (id: number) =>
  request<{ status: string }>(`/tasks/${id}/run/`, { method: "POST" });

export default function TasksPage() {
  const qc = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const { data, isLoading } = useQuery<TasksResponse>({
    queryKey: ["ai-tasks"],
    queryFn: listTasks,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["ai-tasks"] });

  const toggleMutation = useMutation({
    mutationFn: (t: AITask) => patchTask(t.id, { is_active: !t.is_active }),
    onSuccess: invalidate,
    onError: (err) =>
      setError(err instanceof APIError ? err.message : "Ошибка изменения задачи"),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: invalidate,
  });

  const runMutation = useMutation({
    mutationFn: runTaskNow,
    onSuccess: () => setNotice("Задача запущена — результат придёт в Telegram"),
    onError: (err) =>
      setError(err instanceof APIError ? err.message : "Ошибка запуска"),
  });

  const tasks = data?.tasks ?? [];

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <div className="mb-2 flex items-center justify-between">
        <h1 className="text-[22px] font-bold text-[#1A1A1A]">AI-задачи</h1>
        {data && (
          <span className="text-[14px] text-[rgba(13,13,13,0.45)]">
            Активных: {data.active_count} из {data.limit}
          </span>
        )}
      </div>
      <p className="mb-8 text-[15px] leading-relaxed text-[rgba(13,13,13,0.55)]">
        Проактивный AI-агент по расписанию: утренние брифы, мониторинг новостей,
        курсы валют. Результаты приходят в Telegram. Каждый запуск оплачивается
        по цене сообщения модели.
      </p>

      {notice && (
        <div className="mb-4 rounded-[10px] border border-[rgba(46,160,67,0.3)] bg-[rgba(46,160,67,0.06)] px-4 py-3 text-[15px] text-[#2ea043]">
          {notice}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-[10px] border border-[rgba(231,76,60,0.3)] bg-[rgba(231,76,60,0.06)] px-4 py-3 text-[15px] text-[#e74c3c]">
          {error}
        </div>
      )}

      {formOpen ? (
        <CreateTaskForm
          onDone={() => {
            setFormOpen(false);
            invalidate();
          }}
          onCancel={() => setFormOpen(false)}
          onError={(msg) => setError(msg)}
        />
      ) : (
        <button
          onClick={() => { setFormOpen(true); setError(null); setNotice(null); }}
          className="mb-5 flex items-center gap-2 rounded-[8px] border border-[rgba(13,13,13,0.15)] bg-white px-4 py-2.5 text-[15px] text-[rgba(13,13,13,0.7)] hover:bg-[rgba(13,13,13,0.04)] hover:text-[#1A1A1A] transition-colors"
        >
          <Plus size={15} />
          Создать задачу
        </button>
      )}

      {isLoading ? (
        <div className="py-8 text-center text-[16px] text-[rgba(13,13,13,0.45)]">
          Загрузка...
        </div>
      ) : tasks.length === 0 ? (
        <div className="rounded-[12px] border border-dashed border-[rgba(13,13,13,0.18)] py-12 text-center">
          <CalendarClock size={28} className="mx-auto mb-3 text-[rgba(13,13,13,0.25)]" />
          <p className="text-[16px] text-[rgba(13,13,13,0.5)]">Нет AI-задач</p>
          <p className="mt-1 text-[15px] text-[rgba(13,13,13,0.38)]">
            Создайте здесь или в боте: /task каждое утро присылай новости AI
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {tasks.map((t) => (
            <TaskRow
              key={t.id}
              task={t}
              onToggle={() => toggleMutation.mutate(t)}
              onDelete={() => deleteMutation.mutate(t.id)}
              onRun={() => { setNotice(null); setError(null); runMutation.mutate(t.id); }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TaskRow({
  task,
  onToggle,
  onDelete,
  onRun,
}: {
  task: AITask;
  onToggle: () => void;
  onDelete: () => void;
  onRun: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const status = task.is_active
    ? "активна"
    : task.paused_reason === "balance"
      ? "пауза — нет средств"
      : task.paused_reason === "max_runs"
        ? "завершена"
        : task.paused_reason === "completed"
          ? "выполнена"
          : "на паузе";

  return (
    <div className="rounded-[10px] border border-[rgba(13,13,13,0.10)] bg-white px-4 py-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-2 text-[15px] font-medium text-[#1A1A1A]">
            {task.title || "AI-задача"}
            {task.use_web_search && (
              <Globe size={13} className="shrink-0 text-[rgba(13,13,13,0.35)]" />
            )}
          </p>
          <p className="mt-0.5 line-clamp-2 text-[14px] text-[rgba(13,13,13,0.55)]">
            {task.prompt}
          </p>
          <p className="mt-1 text-[13px] text-[rgba(13,13,13,0.4)]">
            {task.schedule_human} · {status} · запусков: {task.runs_count}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={onRun}
            title="Запустить сейчас"
            className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A] transition-all"
          >
            <Zap size={14} />
          </button>
          <button
            onClick={onToggle}
            title={task.is_active ? "Пауза" : "Включить"}
            className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(13,13,13,0.05)] hover:text-[#1A1A1A] transition-all"
          >
            {task.is_active ? <Pause size={14} /> : <Play size={14} />}
          </button>
          {confirming ? (
            <>
              <button
                onClick={() => { onDelete(); setConfirming(false); }}
                className="rounded-[6px] bg-[#e74c3c] px-2 py-1 text-[13px] font-medium text-white hover:bg-[#c0392b] transition-colors"
              >
                Да
              </button>
              <button
                onClick={() => setConfirming(false)}
                className="rounded-[6px] border border-[rgba(13,13,13,0.15)] px-2 py-1 text-[13px] text-[rgba(13,13,13,0.6)] transition-colors"
              >
                Нет
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              title="Удалить"
              className="flex h-7 w-7 items-center justify-center rounded-[6px] text-[rgba(13,13,13,0.35)] hover:bg-[rgba(231,76,60,0.08)] hover:text-[#e74c3c] transition-all"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CreateTaskForm({
  onDone,
  onCancel,
  onError,
}: {
  onDone: () => void;
  onCancel: () => void;
  onError: (msg: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [scheduleType, setScheduleType] = useState<"daily" | "weekly">("daily");
  const [time, setTime] = useState("09:00");
  const [weekday, setWeekday] = useState(0);
  const [webSearch, setWebSearch] = useState(true);

  const createMutation = useMutation({
    mutationFn: () =>
      createTask({
        title: title.trim(),
        prompt: prompt.trim(),
        schedule_type: scheduleType,
        run_time: time,
        weekday: scheduleType === "weekly" ? weekday : null,
        use_web_search: webSearch,
      }),
    onSuccess: onDone,
    onError: (err) =>
      onError(err instanceof APIError ? err.message : "Ошибка создания задачи"),
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (!prompt.trim()) return;
        createMutation.mutate();
      }}
      className="mb-5 flex flex-col gap-4 rounded-[12px] border border-[rgba(13,13,13,0.12)] bg-white p-4"
    >
      <div>
        <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.6)]">
          Название
        </label>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Утренний бриф"
          className="w-full rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
      </div>
      <div>
        <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.6)]">
          Что должен делать AI при каждом запуске
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Пришли 3 главные новости AI за сутки и курс доллара"
          rows={3}
          autoFocus
          className="w-full resize-y rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[16px] text-[#1A1A1A] placeholder-[rgba(13,13,13,0.38)] outline-none focus:border-[#D97757] focus:ring-2 focus:ring-[rgba(217,119,87,0.12)] transition-all"
        />
      </div>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.6)]">
            Расписание
          </label>
          <select
            value={scheduleType}
            onChange={(e) => setScheduleType(e.target.value as "daily" | "weekly")}
            className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all"
          >
            <option value="daily">Ежедневно</option>
            <option value="weekly">Еженедельно</option>
          </select>
        </div>
        {scheduleType === "weekly" && (
          <div>
            <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.6)]">
              День
            </label>
            <select
              value={weekday}
              onChange={(e) => setWeekday(Number(e.target.value))}
              className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all"
            >
              {WEEKDAYS.map((d, i) => (
                <option key={d} value={i}>{d}</option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="mb-1.5 block text-[14px] font-medium text-[rgba(13,13,13,0.6)]">
            Время (МСК)
          </label>
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 py-2 text-[15px] text-[#1A1A1A] outline-none focus:border-[#D97757] transition-all"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2 pb-2 text-[15px] text-[rgba(13,13,13,0.7)]">
          <input
            type="checkbox"
            checked={webSearch}
            onChange={(e) => setWebSearch(e.target.checked)}
            className="h-4 w-4 accent-[#D97757]"
          />
          Веб-поиск
        </label>
      </div>
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={!prompt.trim() || createMutation.isPending}
          className="h-9 rounded-[8px] bg-[#D97757] px-4 text-[15px] font-medium text-white hover:bg-[#C4623E] disabled:opacity-50 transition-colors"
        >
          {createMutation.isPending ? "Создание..." : "Создать"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-9 rounded-[8px] border border-[rgba(13,13,13,0.15)] px-3 text-[15px] text-[rgba(13,13,13,0.6)] hover:bg-[rgba(13,13,13,0.04)] transition-colors"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}
