export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(" ");
}

/**
 * 2026-10-02 (аудит безопасности, HIGH): ?next= на /login/ и /register/
 * передавался в router.replace/push как есть — open redirect
 * (?next=https://evil.tld) и потенциальный DOM-XSS (?next=javascript:...,
 * Next 14.2.20 не блокирует javascript: в клиентской навигации). Разрешаем
 * ТОЛЬКО путь, начинающийся с одного '/' (не '//' — протокол-относительный
 * URL вида //evil.com тоже считается "начинается с /", но ведёт на другой
 * хост). Любое другое значение — на дефолт.
 */
export function safeNextPath(next: string | null | undefined, fallback = "/account/"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) {
    return fallback;
  }
  return next;
}
