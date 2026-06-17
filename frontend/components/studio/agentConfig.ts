export const AGENTS = [
  {
    key: 'architect',
    label: 'Архитектор',
    desc: 'Составляет ТЗ (PROJECT.md) и план реализации (COMMITS.md) за один вызов',
    recommended: 'claude-opus-4-8',
    recommendedReason: 'Opus создаёт наиболее детальные и точные планы — ошибка здесь ломает весь проект',
  },
  {
    key: 'coder',
    label: 'Кодировщик',
    desc: 'Пишет код на каждом шаге — основной по затратам',
    recommended: 'claude-opus-4-8',
    recommendedReason: 'Максимальное качество и длинный вывод — не обрезает файлы',
  },
  {
    key: 'guardian',
    label: 'Хранитель',
    desc: 'Проверяет код, анализирует сборку, составляет план исправлений',
    recommended: 'claude-sonnet-4-6',
    recommendedReason: 'Sonnet быстро и точно находит реальные проблемы, не придираясь к стилю',
  },
] as const;

export type AgentKey = typeof AGENTS[number]['key'];

/** Default per-agent models for the 3-role pipeline */
export const DEFAULT_AGENT_MODELS: Record<AgentKey, string> = Object.fromEntries(
  AGENTS.map((a) => [a.key, a.recommended])
) as Record<AgentKey, string>;
