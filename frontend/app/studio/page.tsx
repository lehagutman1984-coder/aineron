"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  LayoutGrid,
  Plus,
  Loader2,
  Cpu,
  Clock,
  ChevronRight,
  FilePlus,
  Link,
  ImagePlus,
  Zap,
  StepForward,
  Hand,
} from "lucide-react";
import { studioApi } from "@/lib/api/studio";
import type { StudioProject, StudioMode, StudioStack, StudioModel } from "@/lib/api/studio";
import { TemplateGallery } from "@/components/studio/TemplateGallery";
import { StudioHero } from "@/components/studio/StudioHero";
import { StackCards } from "@/components/studio/StackCards";
import { card, badge, form, btn } from "@/components/studio/styles";

const STACK_OPTIONS: { value: StudioStack; label: string }[] = [
  { value: "nextjs", label: "Next.js" },
  { value: "react", label: "React" },
  { value: "vue", label: "Vue" },
  { value: "html", label: "HTML" },
];

const STAR_RATE: Record<string, number> = { fast: 1, coder: 1.7, smart: 3 };
const CATEGORY_LABELS: Record<string, string> = {
  smart: "Smart — максимальное качество",
  fast: "Fast — быстро и дёшево",
  coder: "Coder — заточены под код",
  reasoning: "Reasoning — глубокие рассуждения",
};

const MODE_OPTIONS = [
  { value: "auto" as StudioMode, label: "Авто", icon: Zap, desc: "Агенты делают всё сами — вы только описываете. Самый быстрый путь." },
  { value: "semi" as StudioMode, label: "Полу-авто", icon: StepForward, desc: "Подтверждаете каждый шаг — видите прогресс, останавливаетесь когда нужно." },
  { value: "manual" as StudioMode, label: "Ручной", icon: Hand, desc: "Полный контроль: одобряете каждый файл. Для тех, кто хочет вникать." },
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

type EntryTab = "description" | "clone_url";

export default function StudioPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [entryTab, setEntryTab] = useState<EntryTab>("description");

  // "С нуля" form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [mode, setMode] = useState<StudioMode>("auto");
  const [stack, setStack] = useState<StudioStack>("nextjs");

  const [aiModel, setAiModel] = useState("claude-sonnet-4-6");
  const [screenshotLoading, setScreenshotLoading] = useState(false);
  const [screenshotDesc, setScreenshotDesc] = useState('');

  const { data: models = [] } = useQuery<StudioModel[]>({
    queryKey: ["studio-models"],
    queryFn: studioApi.getModels,
  });
  const selectedModel = models.find((m) => m.id === aiModel);
  const starsPerStep = selectedModel ? Math.round(STAR_RATE[selectedModel.tier] * 12) : 12;
  const grouped = (["smart", "fast", "coder", "reasoning"] as const)
    .map((cat) => ({ cat, items: models.filter((m) => m.category === cat) }))
    .filter((g) => g.items.length > 0);

  // "Клон по URL" form state
  const [cloneUrl, setCloneUrl] = useState("");
  const [cloneName, setCloneName] = useState("");
  const [cloneUrlError, setCloneUrlError] = useState("");

  const { data: projects, isLoading } = useQuery({
    queryKey: ["studio-projects"],
    queryFn: studioApi.list,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      studioApi.create({ name, description: screenshotDesc ? `${description}\n\nМакет: ${screenshotDesc}` : description, mode, target_stack: stack, ai_model: aiModel } as Parameters<typeof studioApi.create>[0] & { ai_model: string }),
    onSuccess: (project: StudioProject) => {
      qc.invalidateQueries({ queryKey: ["studio-projects"] });
      router.push(`/studio/${project.id}/interview`);
    },
  });

  const handleScreenshot = async (file: File) => {
    setScreenshotLoading(true);
    try {
      const tmp = await studioApi.create({ name: name || 'tmp', mode, target_stack: stack });
      const res = await studioApi.uploadScreenshot(tmp.id, file);
      setScreenshotDesc(res.description);
      if (!description) setDescription(res.description.slice(0, 500));
    } catch {
      // ignore
    } finally {
      setScreenshotLoading(false);
    }
  };

  const cloneMutation = useMutation({
    mutationFn: () => studioApi.clone({ url: cloneUrl, name: cloneName || undefined }),
    onSuccess: (project: StudioProject) => {
      qc.invalidateQueries({ queryKey: ["studio-projects"] });
      router.push(`/studio/${project.id}/review`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate();
  };

  const validateUrl = (url: string) => {
    try {
      const parsed = new URL(url);
      if (!['http:', 'https:'].includes(parsed.protocol)) {
        return 'URL должен начинаться с http:// или https://';
      }
      return '';
    } catch {
      return 'Введите корректный URL';
    }
  };

  const handleCloneSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateUrl(cloneUrl);
    if (err) { setCloneUrlError(err); return; }
    setCloneUrlError('');
    cloneMutation.mutate();
  };

  const ENTRY_TABS: { key: EntryTab; label: string; icon: React.ReactNode }[] = [
    { key: 'description', label: 'С нуля', icon: <FilePlus size={14} /> },
    { key: 'clone_url', label: 'Клон по URL', icon: <Link size={14} /> },
  ];

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

      {!showForm && (!projects || projects.length === 0) && !isLoading && (
        <StudioHero onStart={() => setShowForm(true)} />
      )}

      {showForm && (
        <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-6 mb-8 space-y-5">
          <h2 className="text-lg font-semibold">Новый проект</h2>

          {/* Entry mode tabs */}
          <div className="flex gap-1 p-1 bg-[var(--hover)] rounded-lg w-fit">
            {ENTRY_TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => setEntryTab(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  entryTab === tab.key
                    ? 'bg-[var(--card-bg)] text-[var(--text)] shadow-sm'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text)]'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {entryTab === 'description' ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <TemplateGallery
                onSelect={(tplName, tplDesc, tplStack) => {
                  setName(tplName);
                  setDescription(tplDesc);
                  setStack(tplStack);
                }}
              />
              <div>
                <label className="block text-sm font-medium mb-1">Название</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Мой стартап"
                  className={form.input}
                  required
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium">Описание</label>
                  <label className={`flex items-center gap-1 text-xs cursor-pointer ${screenshotLoading ? 'opacity-50' : 'text-blue-500 hover:text-blue-400'}`}>
                    {screenshotLoading ? <Loader2 size={12} className="animate-spin" /> : <ImagePlus size={12} />}
                    Загрузить макет
                    <input
                      type="file"
                      accept="image/*"
                      className="hidden"
                      disabled={screenshotLoading}
                      onChange={(e) => { const f = e.target.files?.[0]; if (f) handleScreenshot(f); }}
                    />
                  </label>
                </div>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Опишите что хотите создать..."
                  rows={3}
                  className={form.textarea}
                />
                {screenshotDesc && (
                  <p className={form.helper}>Макет распознан и добавлен в описание</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Режим</label>
                <div className="grid grid-cols-3 gap-2">
                  {MODE_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setMode(opt.value)}
                      className={`p-3 rounded-lg border text-left transition-colors ${
                        mode === opt.value
                          ? 'border-blue-500 bg-blue-600/10'
                          : 'border-[var(--border)] hover:border-[var(--text-secondary)]'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <opt.icon size={13} className={mode === opt.value ? 'text-blue-400' : 'text-[var(--text-secondary)]'} />
                        <span className="text-sm font-medium">{opt.label}</span>
                      </div>
                      <p className="text-xs text-[var(--text-secondary)]">{opt.desc}</p>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">Стек</label>
                <StackCards selected={stack} onSelect={(s) => setStack(s as StudioStack)} />
              </div>

              {models.length > 0 && (
                <div>
                  <label className="block text-sm font-medium mb-1">Модель</label>
                  <select
                    value={aiModel}
                    onChange={(e) => setAiModel(e.target.value)}
                    className={form.select}
                  >
                    {grouped.map((g) => (
                      <optgroup key={g.cat} label={CATEGORY_LABELS[g.cat] ?? g.cat}>
                        {g.items.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.label} — {m.description}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  <p className="text-xs text-[var(--muted)] mt-1">
                    ≈ {starsPerStep} звёзд за шаг
                  </p>
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={createMutation.isPending || !name.trim()}
                  className={btn.primaryMd}
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
                  className={btn.ghostLg}
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
          ) : (
            <form onSubmit={handleCloneSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">URL сайта</label>
                <input
                  type="text"
                  value={cloneUrl}
                  onChange={(e) => { setCloneUrl(e.target.value); setCloneUrlError(''); }}
                  placeholder="https://example.com"
                  className={`${form.inputDynamic} ${
                    cloneUrlError ? 'border-red-500' : 'border-[var(--border)]'
                  }`}
                  required
                />
                {cloneUrlError && (
                  <p className={form.errorXs}>{cloneUrlError}</p>
                )}
                <p className={form.helper}>
                  AI проанализирует сайт и создаст похожий проект
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Название проекта (опционально)</label>
                <input
                  type="text"
                  value={cloneName}
                  onChange={(e) => setCloneName(e.target.value)}
                  placeholder="Клон сайта"
                  className={form.input}
                />
              </div>

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={cloneMutation.isPending || !cloneUrl.trim()}
                  className={btn.primaryMd}
                >
                  {cloneMutation.isPending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Link size={16} />
                  )}
                  Клонировать
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className={btn.ghostLg}
                >
                  Отмена
                </button>
              </div>

              {cloneMutation.isError && (
                <p className="text-red-500 text-sm">
                  Ошибка. Проверьте URL и попробуйте снова.
                </p>
              )}
            </form>
          )}
        </div>
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
                className={card.row}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{project.name}</span>
                    <span className={badge.default}>
                      {STATUS_LABEL[project.status] ?? project.status}
                    </span>
                    {project.entry_mode === 'clone_url' && (
                      <span className={badge.blue}>
                        <Link size={10} />
                        Клон
                      </span>
                    )}
                  </div>
                  {project.description && (
                    <p className="text-sm text-[var(--text-secondary)] truncate mt-0.5">
                      {project.description}
                    </p>
                  )}
                  {project.target_url && (
                    <p className="text-xs text-[var(--text-secondary)] truncate mt-0.5">
                      {project.target_url}
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
