import DOMPurify from "isomorphic-dompurify";

/**
 * 2026-10-02 (аудит безопасности, HIGH): весь HTML, который CodeFormatter
 * (src/aitext/code_formatter.py) собирает из ответа модели, раньше шёл в
 * dangerouslySetInnerHTML как есть — экранируется только содержимое
 * код-блоков, обычный текст ответа нет. Ответ модели — не доверенный ввод:
 * прямая просьба "ответь HTML-кодом" или косвенная prompt-инъекция через
 * веб-поиск/Deep Research/website-коннектор/загруженный файл могли вставить
 * <img onerror=...>/<script> и выполнить код в origin aineron.ru на простом
 * просмотре чата. isomorphic-dompurify — чтобы одна и та же функция
 * работала и при серверном рендере "use client"-компонентов (там нет
 * window/document), и в браузере. Дефолтный профиль DOMPurify уже убирает
 * script/on*-обработчики/javascript: — здесь не нужен кастомный allowlist,
 * форматирование (code_formatter.py) использует обычные теги разметки.
 */
export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html);
}
