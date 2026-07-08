#!/usr/bin/env node
/**
 * LLM-пайплайн переводов словарей (GLOBAL_EXPANSION_PLAN.md §4.4).
 *
 * Источник истины — messages/ru.json (язык разработки). Скрипт переводит
 * ключи, которых нет в целевой локали ЛИБО у которых изменилась исходная
 * строка (хэш-кэш в scripts/.translate-cache.json), батчами через
 * laozhang.ai (OpenAI-совместимый API) с глоссарием messages/_glossary.json.
 *
 * Запуск:
 *   LAOZHANG_API_KEY=... node scripts/translate-locales.mjs            # все локали
 *   LAOZHANG_API_KEY=... node scripts/translate-locales.mjs fa tr      # выборочно
 *   ... --force        # перевести всё заново (игнорировать кэш)
 *   ... --dry-run      # показать, что будет переведено, без вызова API
 *
 * en.json авторится вручную (или вычитывается после машинного прохода) —
 * скрипт по умолчанию переводит en тоже, но правки в en.json руками
 * имеют приоритет: перезапись происходит только при изменении ru-источника.
 */
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MESSAGES_DIR = path.join(__dirname, "..", "messages");
const CACHE_FILE = path.join(__dirname, ".translate-cache.json");

const SOURCE_LOCALE = "ru";
const ALL_TARGETS = ["en", "fa", "tr", "id", "ar"];
const LOCALE_NAMES = {
  en: "English",
  fa: "Persian (Farsi)",
  tr: "Turkish",
  id: "Indonesian",
  ar: "Arabic (Modern Standard)",
};

const API_URL = process.env.LAOZHANG_API_URL ?? "https://api.laozhang.ai/v1";
const API_KEY = process.env.LAOZHANG_API_KEY;
const MODEL = process.env.TRANSLATE_MODEL ?? "gpt-4o";
const BATCH_SIZE = 40;

const args = process.argv.slice(2);
const force = args.includes("--force");
const dryRun = args.includes("--dry-run");
const targets = args.filter((a) => !a.startsWith("--"));
const locales = targets.length ? targets : ALL_TARGETS;

// ── helpers ──────────────────────────────────────────────────────────────────

function flatten(obj, prefix = "") {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") Object.assign(out, flatten(v, key));
    else out[key] = v;
  }
  return out;
}

function unflatten(flat) {
  const out = {};
  for (const [key, value] of Object.entries(flat)) {
    const parts = key.split(".");
    let node = out;
    for (let i = 0; i < parts.length - 1; i++) {
      node = node[parts[i]] ??= {};
    }
    node[parts[parts.length - 1]] = value;
  }
  return arrayify(out);
}

// Ключи вида "0","1",...,"n-1" — значит это был массив (flatten() их не различает
// от обычных объектов), восстанавливаем структуру, иначе {"0":x,"1":y} ломает .map()
// на фронте (см. инцидент с en.json / GLOBAL_EXPANSION_PLAN.md G2).
function arrayify(node) {
  if (node === null || typeof node !== "object") return node;
  for (const key of Object.keys(node)) {
    node[key] = arrayify(node[key]);
  }
  const keys = Object.keys(node);
  if (keys.length > 0 && keys.every((k, i) => k === String(i))) {
    return keys.map((k) => node[k]);
  }
  return node;
}

const sha = (s) => createHash("sha256").update(s).digest("hex").slice(0, 16);

function extractPlaceholders(s) {
  // ICU-плейсхолдеры: {name}, {count, plural, ...} — сравниваем множества имён
  return [...s.matchAll(/\{(\w+)/g)].map((m) => m[1]).sort();
}

function loadJson(file, fallback = {}) {
  return existsSync(file) ? JSON.parse(readFileSync(file, "utf8")) : fallback;
}

// ── translation ─────────────────────────────────────────────────────────────

async function translateBatch(entries, locale, glossary) {
  const systemPrompt = [
    `You are a professional UI localizer translating a SaaS product interface from Russian to ${LOCALE_NAMES[locale]}.`,
    `Tone: ${glossary.tone}`,
    `NEVER translate these terms (keep verbatim): ${glossary.do_not_translate.join(", ")}.`,
    `Glossary (ru term -> en reference, follow the intent in your language):`,
    ...Object.entries(glossary.terms).map(
      ([ru, t]) => `- "${ru}" -> "${t.en}"${t.note ? ` (${t.note})` : ""}`,
    ),
    `Strings use ICU MessageFormat: preserve all {placeholders} and {count, plural, ...} structures exactly (translate only the human-readable words inside plural branches).`,
    `Respond with ONLY a JSON object mapping each input key to its translation. No commentary.`,
  ].join("\n");

  const userPrompt = JSON.stringify(
    Object.fromEntries(entries.map(({ key, value }) => [key, value])),
    null,
    2,
  );

  const res = await fetch(`${API_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: MODEL,
      temperature: 0.2,
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: systemPrompt },
        { role: "user", content: userPrompt },
      ],
    }),
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${(await res.text()).slice(0, 300)}`);
  }
  const data = await res.json();
  return JSON.parse(data.choices[0].message.content);
}

async function processLocale(locale, sourceFlat, glossary, cache) {
  const file = path.join(MESSAGES_DIR, `${locale}.json`);
  const targetFlat = flatten(loadJson(file));
  const cacheKey = (k) => `${locale}:${k}`;

  const pending = Object.entries(sourceFlat)
    .filter(([key, value]) => {
      if (force) return true;
      if (!(key in targetFlat)) return true;
      return cache[cacheKey(key)] !== sha(value); // ru-строка изменилась
    })
    .map(([key, value]) => ({ key, value }));

  // Удаляем из целевой локали ключи, которых больше нет в источнике
  const removed = Object.keys(targetFlat).filter((k) => !(k in sourceFlat));
  removed.forEach((k) => delete targetFlat[k]);

  if (!pending.length && !removed.length) {
    console.log(`[${locale}] актуален (${Object.keys(targetFlat).length} ключей)`);
    return;
  }
  console.log(`[${locale}] к переводу: ${pending.length}, удалено: ${removed.length}`);
  if (dryRun) {
    pending.slice(0, 10).forEach(({ key }) => console.log(`  - ${key}`));
    return;
  }

  for (let i = 0; i < pending.length; i += BATCH_SIZE) {
    const batch = pending.slice(i, i + BATCH_SIZE);
    const translated = await translateBatch(batch, locale, glossary);
    for (const { key, value } of batch) {
      const result = translated[key];
      if (typeof result !== "string" || !result.trim()) {
        console.warn(`  [WARN] ${key}: пустой перевод, пропущен`);
        continue;
      }
      const src = extractPlaceholders(value).join(",");
      const dst = extractPlaceholders(result).join(",");
      if (src !== dst) {
        console.warn(`  [WARN] ${key}: плейсхолдеры не совпали (${src} vs ${dst}), пропущен`);
        continue;
      }
      targetFlat[key] = result;
      cache[cacheKey(key)] = sha(value);
    }
    console.log(`  [${locale}] ${Math.min(i + BATCH_SIZE, pending.length)}/${pending.length}`);
  }

  writeFileSync(file, JSON.stringify(unflatten(targetFlat), null, 2) + "\n", "utf8");
  console.log(`[${locale}] записан: ${file}`);
}

// ── main ─────────────────────────────────────────────────────────────────────

if (!API_KEY && !dryRun) {
  console.error("LAOZHANG_API_KEY не задан (или используйте --dry-run)");
  process.exit(1);
}

const sourceFlat = flatten(loadJson(path.join(MESSAGES_DIR, `${SOURCE_LOCALE}.json`)));
const glossary = loadJson(path.join(MESSAGES_DIR, "_glossary.json"));
const cache = loadJson(CACHE_FILE);

for (const locale of locales) {
  if (!LOCALE_NAMES[locale]) {
    console.error(`Неизвестная локаль: ${locale}. Доступны: ${ALL_TARGETS.join(", ")}`);
    process.exit(1);
  }
  await processLocale(locale, sourceFlat, glossary, cache);
}

if (!dryRun) {
  writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2) + "\n", "utf8");
}
console.log("Готово.");
