export const AGENTS = [
  {
    key: 'interviewer',
    label: 'Интервью',
    desc: 'Задаёт уточняющие вопросы перед стартом',
    recommended: 'deepseek-v3.2',
    recommendedReason: 'Простые Q&A — fast-модель достаточно, экономит бюджет',
  },
  {
    key: 'analyst',
    label: 'Аналитик',
    desc: 'Анализирует требования, составляет ТЗ',
    recommended: 'claude-sonnet-4-6',
    recommendedReason: 'Нужна глубина понимания — ошибка здесь ломает весь план',
  },
  {
    key: 'planner',
    label: 'Планировщик',
    desc: 'Разбивает проект на шаги и коммиты',
    recommended: 'claude-sonnet-4-6',
    recommendedReason: 'Архитектурные решения влияют на все шаги — нужно качество',
  },
  {
    key: 'coder',
    label: 'Кодировщик',
    desc: 'Пишет код на каждом шаге — самый затратный',
    recommended: 'qwen3-coder-plus',
    recommendedReason: 'Специализирован на генерации кода, лучшее качество/цена',
  },
  {
    key: 'reviewer',
    label: 'Ревьюер',
    desc: 'Проверяет код после каждого шага',
    recommended: 'claude-sonnet-4-6',
    recommendedReason: 'Глубокий разбор кода требует умной модели',
  },
  {
    key: 'tester',
    label: 'Тестировщик',
    desc: 'Запускает сборку, анализирует ошибки',
    recommended: 'deepseek-v3.2',
    recommendedReason: 'Анализ логов — рутина, fast-модель справляется',
  },
  {
    key: 'fixer',
    label: 'Фиксер',
    desc: 'Исправляет ошибки из отчёта тестировщика',
    recommended: 'claude-sonnet-4-6',
    recommendedReason: 'Дебаггинг требует рассуждений — smart-модель даёт меньше ретраев',
  },
] as const;

export type AgentKey = typeof AGENTS[number]['key'];

/** Default agent_models map: what runs if the user doesn't override anything */
export const DEFAULT_AGENT_MODELS: Record<AgentKey, string> = Object.fromEntries(
  AGENTS.map((a) => [a.key, a.recommended])
) as Record<AgentKey, string>;
