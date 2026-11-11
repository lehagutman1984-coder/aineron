// Подсказка при опечатке в домене email (mai.ru -> mail.ru). Только подсказка:
// пользователь может оставить адрес как есть.
const COMMON_DOMAINS = [
  "mail.ru", "gmail.com", "yandex.ru", "ya.ru", "yandex.com", "bk.ru", "inbox.ru",
  "list.ru", "internet.ru", "outlook.com", "hotmail.com", "icloud.com", "rambler.ru",
  "proton.me", "protonmail.com", "yahoo.com",
];

function distance(a: string, b: string): number {
  const dp: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i]);
  for (let j = 1; j <= b.length; j++) dp[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
  }
  return dp[a.length][b.length];
}

/** Возвращает исправленный адрес, если домен похож на популярный (расстояние 1-2), иначе null. */
export function suggestEmail(email: string): string | null {
  const at = email.lastIndexOf("@");
  if (at < 1) return null;
  const local = email.slice(0, at);
  const domain = email.slice(at + 1).toLowerCase();
  if (!domain || COMMON_DOMAINS.includes(domain)) return null;
  let best: string | null = null;
  let bestDist = 3;
  for (const d of COMMON_DOMAINS) {
    const dist = distance(domain, d);
    if (dist < bestDist) {
      bestDist = dist;
      best = d;
    }
  }
  // Короткие домены (ya.ru) дают ложные срабатывания при расстоянии 2.
  if (best && bestDist <= (best.length <= 6 ? 1 : 2)) return `${local}@${best}`;
  return null;
}
