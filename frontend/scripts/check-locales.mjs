#!/usr/bin/env node
/**
 * CI-проверка словарей i18n: все локали содержат тот же набор ключей,
 * что и источник (ru.json), и те же ICU-плейсхолдеры в каждой строке.
 * Падает с кодом 1 при расхождении. Запуск: node scripts/check-locales.mjs
 */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MESSAGES_DIR = path.join(__dirname, "..", "messages");
const SOURCE = "ru";

function flatten(obj, prefix = "") {
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object") Object.assign(out, flatten(v, key));
    else out[key] = v;
  }
  return out;
}

const placeholders = (s) =>
  [...String(s).matchAll(/\{(\w+)/g)].map((m) => m[1]).sort().join(",");

const load = (locale) =>
  flatten(JSON.parse(readFileSync(path.join(MESSAGES_DIR, `${locale}.json`), "utf8")));

const source = load(SOURCE);
const sourceKeys = new Set(Object.keys(source));

const locales = readdirSync(MESSAGES_DIR)
  .filter((f) => f.endsWith(".json") && !f.startsWith("_") && f !== `${SOURCE}.json`)
  .map((f) => f.replace(".json", ""));

let failed = false;

for (const locale of locales) {
  const target = load(locale);
  const missing = [...sourceKeys].filter((k) => !(k in target));
  const extra = Object.keys(target).filter((k) => !sourceKeys.has(k));
  const badPlaceholders = [...sourceKeys].filter(
    (k) => k in target && placeholders(source[k]) !== placeholders(target[k]),
  );

  if (missing.length || extra.length || badPlaceholders.length) {
    failed = true;
    console.error(`[${locale}] РАСХОЖДЕНИЯ:`);
    missing.forEach((k) => console.error(`  отсутствует: ${k}`));
    extra.forEach((k) => console.error(`  лишний ключ: ${k}`));
    badPlaceholders.forEach((k) =>
      console.error(`  плейсхолдеры: ${k} ("${source[k]}" vs "${target[k]}")`),
    );
  } else {
    console.log(`[${locale}] OK (${Object.keys(target).length} ключей)`);
  }
}

if (failed) process.exit(1);
console.log(`Все локали синхронизированы с ${SOURCE}.json (${sourceKeys.size} ключей).`);
