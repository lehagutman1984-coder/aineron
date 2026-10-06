# -*- coding: utf-8 -*-
"""
Golden-set «до/после» для веб-поиска в чате (WEB_SEARCH_ACCURACY_PLAN.md).
Переиспользуемый регрессионный тест — прогонять при любом следующем изменении
aitext/web_search.py, не только разово.

Запуск на сервере (копировать в контейнер, т.к. `shell <` не умеет stdin из
хоста напрямую через docker compose exec без -T):
    docker compose cp scripts/web_search_golden_set.py web:/tmp/golden_set_test.py
    docker compose exec -T web python manage.py shell < /tmp/golden_set_test.py

"До" эмулируется напрямую внутри скрипта (без дедупа/буста/рерайта) — поведение
call_web_search ДО 2026-10-06 (коммит 65cce10): сырой последний вопрос как запрос,
max_results=6, без time_range. Не трогает текущий код — эмуляция инлайн в самом
скрипте, безопасно гонять на проде сколько угодно раз.
"После" — текущий пайплайн: rewrite_search_query() + _tavily_search() (дедуп+буст).

Результаты не детерминированы между прогонами (Tavily сам по себе не даёт
стабильную выдачу на идентичный запрос — подтверждено эмпирически 2026-10-06,
см. план раздел «Честно: что считать шумом») — ожидать разброса в районе
30-40% состава доменов между запусками даже без изменений кода, не паниковать
на одиночные расхождения, смотреть на агрегат по категориям.
"""
import json
import re
import time

from django.conf import settings
import requests as _req

from aitext.web_search import rewrite_search_query, _tavily_search, _domain

GOLDEN_SET = [
    # ── follow-up (контекст предыдущей реплики) ──
    {"id": "f1", "cat": "follow-up", "history": [
        ("user", "сколько стоит iPhone 17 Pro в США"),
        ("assistant", "Около 999 долларов"),
        ("user", "а в евро?"),
    ]},
    {"id": "f2", "cat": "follow-up", "history": [
        ("user", "кто сейчас президент Франции"),
        ("assistant", "Эмманюэль Макрон"),
        ("user", "а сколько ему лет?"),
    ]},
    {"id": "f3", "cat": "follow-up", "history": [
        ("user", "расскажи про модель Claude Opus 5.5"),
        ("assistant", "Это топовая модель Anthropic с сильным reasoning"),
        ("user", "а когда вышла?"),
    ]},
    {"id": "f4", "cat": "follow-up", "history": [
        ("user", "какая погода в Москве"),
        ("assistant", "Облачно, около 5 градусов"),
        ("user", "а завтра?"),
    ]},
    {"id": "f5", "cat": "follow-up", "history": [
        ("user", "сравни Tesla Model 3 и BMW i4 по цене"),
        ("assistant", "Tesla Model 3 дешевле примерно на 5000 долларов"),
        ("user", "а по запасу хода?"),
    ]},

    # ── time-sensitive ──
    {"id": "t1", "cat": "time-sensitive", "history": [("user", "какой курс доллара к рублю сегодня")]},
    {"id": "t2", "cat": "time-sensitive", "history": [("user", "какая сейчас ключевая ставка ЦБ РФ")]},
    {"id": "t3", "cat": "time-sensitive", "history": [("user", "последние новости про ИИ за эту неделю")]},
    {"id": "t4", "cat": "time-sensitive", "history": [("user", "какая погода в Санкт-Петербурге сейчас")]},
    {"id": "t5", "cat": "time-sensitive", "history": [("user", "что происходит на бирже сегодня")]},

    # ── RU-специфика ──
    {"id": "r1", "cat": "ru-specific", "history": [("user", "что говорит 152-ФЗ о персональных данных")]},
    {"id": "r2", "cat": "ru-specific", "history": [("user", "какая ставка НДФЛ в России в 2026 году")]},
    {"id": "r3", "cat": "ru-specific", "history": [("user", "как оформить загранпаспорт через Госуслуги")]},
    {"id": "r4", "cat": "ru-specific", "history": [("user", "какие льготы положены многодетным семьям в России")]},
    {"id": "r5", "cat": "ru-specific", "history": [("user", "как зарегистрировать ИП самому")]},

    # ── многоаспектные/сравнительные ──
    {"id": "m1", "cat": "multi-aspect", "history": [("user", "плюсы и минусы ипотеки под материнский капитал")]},
    {"id": "m2", "cat": "multi-aspect", "history": [("user", "сравни Яндекс.Облако и Google Cloud по цене и возможностям")]},
    {"id": "m3", "cat": "multi-aspect", "history": [("user", "что лучше для старта бизнеса — ИП или ООО")]},
    {"id": "m4", "cat": "multi-aspect", "history": [("user", "какие есть способы инвестировать 100000 рублей в 2026 году")]},
    {"id": "m5", "cat": "multi-aspect", "history": [("user", "в чём разница между OSAGO и KASKO")]},

    # ── поиск не нужен (needs_search должен быть False) ──
    {"id": "n1", "cat": "no-search", "history": [("user", "спасибо большое, очень помогло!")]},
    {"id": "n2", "cat": "no-search", "history": [("user", "перепиши функцию выше покороче")]},
    {"id": "n3", "cat": "no-search", "history": [("user", "объясни что такое рекурсия простыми словами")]},
    {"id": "n4", "cat": "no-search", "history": [("user", "напиши короткое стихотворение про осень")]},
    {"id": "n5", "cat": "no-search", "history": [("user", "сколько будет 247 умножить на 13")]},
]


def _old_raw_search(raw_query, log_prefix=""):
    """Эмуляция СТАРОГО call_web_search() — без дедупа, без буста, без time_range."""
    tavily_key = getattr(settings, "TAVILY_API_KEY", "")
    if not tavily_key:
        return []
    proxy_url = getattr(settings, "TAVILY_PROXY_URL", "")
    try:
        r = _req.post(
            "https://api.tavily.com/search",
            json={"api_key": tavily_key, "query": raw_query[:400], "search_depth": "basic",
                  "max_results": 6, "include_answer": False},
            timeout=12,
            proxies={"https": proxy_url} if proxy_url else None,
        )
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        print(f"{log_prefix}OLD search FAILED: {e}")
        return []


results = []
for entry in GOLDEN_SET:
    msgs = [{"role": r, "content": c} for r, c in entry["history"]]
    raw_last = entry["history"][-1][1]
    eid, cat = entry["id"], entry["cat"]

    if cat == "no-search":
        rewrite = rewrite_search_query(msgs, log_prefix=f"[{eid}] ")
        row = {
            "id": eid, "cat": cat, "raw": raw_last,
            "needs_search_new": rewrite["needs_search"],
            "needs_search_old": True,  # старый код ВСЕГДА искал при включённом тоггле
            "correct": rewrite["needs_search"] is False,
        }
        results.append(row)
        print(f"[{eid}] needs_search_old=True(всегда) needs_search_new={rewrite['needs_search']} "
              f"{'OK' if row['correct'] else 'MISS'}  raw='{raw_last}'")
        continue

    # OLD: сырой последний вопрос
    old_items = _old_raw_search(raw_last, log_prefix=f"[{eid}-old] ")
    old_domains = [_domain(it.get("url", "")) for it in old_items]

    # NEW: рерайт + дедуп/буст + time_sensitive
    rewrite = rewrite_search_query(msgs, log_prefix=f"[{eid}-new] ")
    new_items = _tavily_search(rewrite["query"], max_results=6,
                                time_sensitive=rewrite["time_sensitive"], log_prefix=f"[{eid}-new] ")
    new_domains = [_domain(it.get("url", "")) for it in new_items]

    dom_counts_new = {}
    for d in new_domains:
        dom_counts_new[d] = dom_counts_new.get(d, 0) + 1
    dedup_ok = all(c <= 2 for c in dom_counts_new.values())

    query_changed = rewrite["query"].strip().lower() != raw_last.strip().lower()

    row = {
        "id": eid, "cat": cat,
        "raw_query": raw_last,
        "rewritten_query": rewrite["query"],
        "query_changed": query_changed,
        "time_sensitive": rewrite["time_sensitive"],
        "old_count": len(old_items), "old_domains": old_domains,
        "new_count": len(new_items), "new_domains": new_domains,
        "dedup_ok": dedup_ok,
    }
    results.append(row)
    print(f"[{eid}] cat={cat}")
    print(f"   RAW:   '{raw_last}'")
    print(f"   REWR:  '{rewrite['query']}'  (changed={query_changed}, time_sensitive={rewrite['time_sensitive']})")
    print(f"   OLD domains ({len(old_items)}): {old_domains}")
    print(f"   NEW domains ({len(new_items)}): {new_domains}  dedup_ok={dedup_ok}")
    time.sleep(0.3)

print("\n\n=== СВОДКА ===")
followups = [r for r in results if r["cat"] == "follow-up"]
print(f"follow-up: {len(followups)} запросов, рерайт изменил запрос в {sum(r['query_changed'] for r in followups)}/{len(followups)}")

ts = [r for r in results if r["cat"] == "time-sensitive"]
print(f"time-sensitive: {sum(r['time_sensitive'] for r in ts)}/{len(ts)} корректно помечены как time_sensitive")

ns = [r for r in results if r["cat"] == "no-search"]
print(f"no-search: {sum(r['correct'] for r in ns)}/{len(ns)} корректно пропустили поиск (needs_search=False)")

dedup_checked = [r for r in results if "dedup_ok" in r]
print(f"dedup: {sum(r['dedup_ok'] for r in dedup_checked)}/{len(dedup_checked)} прошли проверку max 2 на домен")

with open("/tmp/golden_set_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\nРезультаты сохранены в /tmp/golden_set_results.json")
