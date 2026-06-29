// ─────────────────────────────────────────────────────────
// Studio Design Tokens
// Все Tailwind-классы студии собраны здесь.
// Импортируй нужную группу: import { btn, card, form } from './styles'
// ─────────────────────────────────────────────────────────

// ─── Layout ──────────────────────────────────────────────
export const layout = {
  // Корень workspace (вычитаем высоту navbar)
  root: 'flex flex-col overflow-hidden',
  // Верхняя панель инструментов
  topbar: 'flex items-center gap-4 px-4 py-2 border-b border-[var(--border)] shrink-0',
  // Вертикальный разделитель в topbar
  divider: 'w-px h-4 bg-[var(--border)]',
  // Группа кнопок справа
  rightGroup: 'ml-auto flex items-center gap-2',
  // Заголовок панели (flex, justify-between, border-b)
  panelHeader:
    'flex items-center justify-between px-4 py-2 border-b border-[var(--border)] shrink-0',
  panelHeaderLg:
    'flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0',
  // Скроллируемая область (занимает всё доступное место)
  scrollArea: 'flex-1 overflow-auto',
  scrollAreaHidden: 'flex-1 overflow-hidden',
  // Полная колонка
  col: 'flex flex-col h-full',
  colOverflow: 'flex flex-col h-full overflow-hidden',
  // Resize-хэндл между панелями
  resizeHandle:
    'w-1 bg-[var(--border)] hover:bg-blue-500 transition-colors cursor-col-resize',
  // Горизонтальный border
  borderTop: 'border-t border-[var(--border)]',
  borderBottom: 'border-b border-[var(--border)]',
  // Статус-бар (футер workspace)
  statusBar: 'shrink-0 h-6 flex items-center gap-4 px-3 border-t border-[var(--border)] bg-[var(--hover)] text-xs text-[var(--text-secondary)] select-none',
  statusBarItem: 'flex items-center gap-1',
};

// ─── Overlay & Modals ────────────────────────────────────
export const modal = {
  // Затемнение фона
  overlay: 'fixed inset-0 bg-black/40 z-50 flex items-center justify-center',
  overlayTop: 'fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-24',
  // Контейнер модального окна
  box: 'bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-sm',
  boxMd: 'bg-[var(--bg)] border border-[var(--border)] rounded-xl p-5 w-full max-w-md space-y-4',
  boxLg: 'bg-[var(--bg)] border border-[var(--border)] rounded-xl w-full max-w-lg overflow-hidden',
  // Шапка модалки
  header: 'flex items-center justify-between mb-3',
  title: 'text-sm font-medium',
};

// ─── Drawers (боковые панели) ────────────────────────────
export const drawer = {
  // Drawer md — шаг, ревьюер
  rootMd:
    'fixed inset-y-0 right-0 w-full max-w-md bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-50 flex flex-col',
  // Drawer sm — чат
  rootSm:
    'fixed inset-y-0 right-0 w-full max-w-sm bg-[var(--bg)] border-l border-[var(--border)] shadow-xl z-40 flex flex-col',
  header:
    'flex items-center justify-between px-4 py-3 border-b border-[var(--border)] shrink-0',
  body: 'flex-1 overflow-auto p-4 space-y-4 text-xs',
};

// ─── Buttons ─────────────────────────────────────────────
export const btn = {
  // Основная синяя кнопка (разные размеры)
  primaryXs:
    'flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
  primarySm:
    'flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors',
  primaryMd:
    'flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors',
  primaryLg:
    'flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-6 py-3 rounded-xl text-sm font-medium transition-colors',
  // Amber-кнопки (подтверждение, пауза)
  amberXs:
    'flex items-center gap-1.5 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0',
  amberXsCompact:
    'bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium',
  amberOutlineXs:
    'border border-amber-700 hover:bg-amber-900/40 text-amber-200 px-3 py-1.5 rounded-lg text-xs font-medium',
  amberSendXs:
    'bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white px-3 rounded-lg text-xs font-medium self-stretch',
  // Призрачные/вторичные кнопки
  ghostXs:
    'flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
  ghostXsDisabled:
    'flex items-center gap-1.5 border border-[var(--border)] hover:bg-[var(--hover)] disabled:opacity-50 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
  ghostSm:
    'flex items-center gap-2 border border-[var(--border)] hover:bg-[var(--hover)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
  ghostMd: 'px-4 py-2 rounded-lg text-sm border border-[var(--border)] hover:bg-[var(--hover)] transition-colors',
  ghostLg: 'px-5 py-2 rounded-lg text-sm border border-[var(--border)] hover:bg-[var(--hover)] transition-colors',
  // Иконочные кнопки
  icon: 'text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors',
  iconP: 'p-1.5 text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors',
  iconPSm: 'p-1 text-[var(--text-secondary)] hover:text-[var(--text)] transition-colors',
  // Специальные
  greenSm:
    'flex items-center gap-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors',
  redSm: 'px-2 py-1 text-xs bg-red-600 hover:bg-red-700 text-white rounded-md transition-colors',
  blackDeploy:
    'mt-3 flex items-center gap-2 bg-black hover:bg-gray-900 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-xs font-medium transition-colors',
  // Текстовые ссылки-кнопки
  textBlue: 'text-xs text-blue-500 hover:underline',
  textMuted: 'text-[var(--text-secondary)] hover:text-[var(--text)] text-xs',
};

// ─── Form elements ───────────────────────────────────────
export const form = {
  label: 'block text-sm font-medium mb-1',
  labelRow: 'flex items-center justify-between mb-1',
  input:
    'w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
  inputDynamic:
    'w-full border rounded-lg px-3 py-2 text-sm bg-[var(--input-bg)] focus:outline-none focus:ring-2 focus:ring-blue-500',
  textarea:
    'w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500',
  textareaXs:
    'flex-1 text-xs bg-[var(--bg)] border border-amber-800/50 rounded p-2 resize-none h-16',
  inputXs: 'w-full bg-[var(--hover)] border border-[var(--border)] rounded p-2 text-xs',
  select:
    'w-full border border-[var(--border)] bg-[var(--input-bg)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
  error: 'text-red-500 text-sm',
  errorXs: 'text-red-500 text-xs mt-1',
  helper: 'text-xs text-[var(--text-secondary)] mt-1',
};

// ─── Cards ───────────────────────────────────────────────
export const card = {
  // Базовая карточка без паддинга
  base: 'bg-[var(--card-bg)] border border-[var(--border)] rounded-xl',
  // С паддингом
  sm: 'p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl',
  md: 'p-5 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl',
  lg: 'p-6 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl',
  // Строка-карточка (проект в списке, item)
  row: 'flex items-center gap-4 p-4 rounded-xl border border-[var(--border)] bg-[var(--card-bg)] hover:border-blue-400 transition-colors group',
  // Карточка шаблона
  template:
    'flex flex-col items-start p-3 rounded-lg border border-[var(--border)] bg-[var(--card-bg)] hover:border-blue-400 hover:bg-[var(--hover)] transition-colors text-left group',
  // Карточка в гит-истории
  historyItem:
    'flex items-center justify-between p-2 rounded-lg bg-[var(--card-bg)] border border-[var(--border)] text-xs',
};

// ─── Text ────────────────────────────────────────────────
export const text = {
  muted: 'text-[var(--text-secondary)]',
  mutedXs: 'text-xs text-[var(--text-secondary)]',
  mutedSm: 'text-sm text-[var(--text-secondary)]',
  mutedLabel: 'text-[13px] text-[var(--text-secondary)]',
  mutedLabelMd: 'text-[13px] text-[var(--text-secondary)] font-medium mb-1',
  heading: 'text-sm font-medium',
  headingMd: 'text-base font-medium',
  headingLg: 'text-lg font-semibold',
  heading2xl: 'text-2xl font-semibold',
  mono: 'font-mono',
  monoXs: 'font-mono text-xs',
  // Блоки кода
  codeBlock: 'whitespace-pre-wrap font-mono text-[13px] bg-[var(--hover)] rounded p-2',
  codeBlockError: 'whitespace-pre-wrap font-mono text-[13px] bg-red-950/30 text-red-300 rounded p-2',
  // Цвета статусов
  error: 'text-red-400',
  errorSm: 'text-sm text-red-500',
  errorXs: 'text-[13px] text-red-400',
  success: 'text-green-500',
  successXs: 'text-[13px] text-green-500',
  warning: 'text-amber-400',
  blue: 'text-blue-500',
  blueXs: 'text-xs text-blue-500',
};

// ─── Empty & Loading states ──────────────────────────────
export const empty = {
  // По центру внутри flex-контейнера
  center: 'flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60',
  centerXs:
    'flex items-center justify-center h-full text-xs text-[var(--text-secondary)] opacity-60',
  centerP: 'flex items-center justify-center h-full text-sm text-[var(--text-secondary)] opacity-60 p-6 text-center',
  // На весь экран
  screen: 'flex items-center justify-center h-screen',
  screenSm: 'flex items-center justify-center h-screen text-sm text-[var(--text-secondary)]',
  // Спиннеры
  spinner: 'animate-spin',
  spinnerBlue: 'animate-spin text-blue-500',
  spinnerMuted: 'animate-spin text-[var(--text-secondary)]',
};

// ─── Banners (уведомления вверху workspace) ──────────────
export const banner = {
  // Amber: подтверждение шага
  amber: 'flex items-center gap-3 px-4 py-2.5 bg-amber-950/40 border-b border-amber-800/50 shrink-0',
  // Amber: пауза (несколько строк)
  amberCol: 'flex flex-col gap-2 px-4 py-2.5 bg-amber-950/40 border-b border-amber-800/50 shrink-0',
  // Красный: ошибка/предупреждение
  red: 'flex items-start gap-3 p-4 border-b border-[var(--border)] bg-red-950/30 shrink-0',
};

// ─── Badges & Tags ───────────────────────────────────────
export const badge = {
  default: 'text-xs px-2 py-0.5 rounded-full bg-[var(--hover)] text-[var(--text-secondary)]',
  blue: 'text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 flex items-center gap-1',
  stack: 'mt-2 text-xs px-1.5 py-0.5 rounded bg-[var(--hover)] text-[var(--text-secondary)]',
  kbd: 'font-mono bg-[var(--hover)] px-2 py-0.5 rounded',
};

// ─── Code / Diff ─────────────────────────────────────────
export const code = {
  root: 'flex flex-col h-full relative',
  pathBar:
    'flex items-center justify-between px-4 py-2 border-b border-[var(--border)] text-xs text-[var(--text-secondary)] shrink-0',
  editor: 'flex-1 overflow-auto',
  // Floating объяснение
  explainBtn:
    'flex items-center gap-1.5 bg-[var(--bg)] border border-[var(--border)] shadow-lg hover:bg-[var(--hover)] disabled:opacity-60 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
  popover:
    'absolute bottom-4 right-4 z-20 w-80 max-h-64 overflow-auto bg-[var(--bg)] border border-[var(--border)] rounded-lg shadow-xl p-3 text-xs',
  diffLine: {
    added: 'flex px-4 py-0.5 bg-green-950 text-green-300',
    removed: 'flex px-4 py-0.5 bg-red-950 text-red-300 line-through opacity-70',
    normal: 'flex px-4 py-0.5',
  },
};

// ─── Pipeline / Agent Log ────────────────────────────────
export const pipeline = {
  // Строка агентов
  root: 'flex items-center gap-1 overflow-x-auto',
  agentItem: 'flex items-center gap-1 shrink-0',
  connector: 'w-3 h-px',
  // Лог
  log: 'font-mono text-xs overflow-auto p-3 h-full bg-[var(--card-bg)]',
  logLine: {
    error: 'text-red-400',
    warning: 'text-yellow-400',
    success: 'text-green-400',
    default: 'text-[var(--text)]',
  },
};

// ─── File Tree ───────────────────────────────────────────
export const tree = {
  root: 'flex flex-col h-full overflow-hidden',
  header:
    'flex items-center justify-between px-3 py-1.5 border-b border-[var(--border)] shrink-0',
  scrollArea: 'flex-1 overflow-auto p-1',
  emptyState: 'p-3 text-xs text-[var(--text-secondary)] opacity-60',
  folderBtn:
    'flex items-center gap-1.5 w-full text-left py-0.5 pr-2 text-xs hover:bg-[var(--hover)] rounded transition-colors',
  deleteBtn:
    'absolute right-1 top-0.5 p-0.5 text-[var(--text-secondary)] hover:text-red-400 transition-colors',
};

// ─── Chat / ContextChat ──────────────────────────────────
export const chat = {
  inputRow:
    'flex items-center gap-2 px-3 py-2 border-b border-[var(--border)] shrink-0',
  input:
    'flex-1 bg-[var(--input-bg)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500',
  sendBtn: 'p-1.5 text-blue-500 hover:text-blue-400 disabled:opacity-40 transition-colors',
  // Пузыри сообщений
  bubbleBase: 'inline-block px-3 py-1.5 rounded-lg text-xs max-w-[85%]',
  bubbleUser: 'bg-blue-600 text-white',
  bubbleAssistant: 'bg-[var(--card-bg)] border border-[var(--border)] text-[var(--text)]',
};

// ─── Reviewer Mode ───────────────────────────────────────
export const reviewer = {
  // Карточки отклонений по серьёзности
  severityHigh: 'border-red-500/40 bg-red-500/5 text-red-400',
  severityMedium: 'border-amber-500/40 bg-amber-500/5 text-amber-400',
  severityLow: 'border-[var(--border)] text-[var(--text-secondary)]',
};

// ─── Interview ───────────────────────────────────────────
export const interview = {
  progressTrack: 'flex-1 h-1 bg-[var(--border)] rounded-full overflow-hidden ml-2',
  progressFill: 'h-full bg-blue-500 transition-all',
};
