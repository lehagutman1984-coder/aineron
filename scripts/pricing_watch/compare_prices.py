#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Еженедельная сверка наших цен с RouterAI (routerai.ru) по всем моделям,
где есть соответствие. Полностью автономный скрипт — не требует Docker,
SSH или доступа к нашей БД: наши текущие цены берутся с ПУБЛИЧНОГО API
aineron.ru, цены конкурента — с ПУБЛИЧНЫХ страниц routerai.ru (обычный
requests.get, JS не нужен — цены отдаются в серверном HTML).

Установка (один раз):
    pip install requests beautifulsoup4

Запуск:
    python compare_prices.py                  # отчёт в консоль
    python compare_prices.py --out report.csv # + сохранить в CSV
    python compare_prices.py --threshold 10    # показывать только |откл.| > 10% (по умолчанию 15%)

Что делает:
1. Читает routerai_mapping.json (наш slug -> URL модели на routerai.ru,
   плюс для видео — реальная длительность нашего сообщения в секундах,
   для текста — профиль токенов для пересчёта в "цену сообщения").
2. Тянет наши текущие цены с https://aineron.ru/api/v1/catalog/networks/
   (публичный, без авторизации).
3. Для каждой модели с известным URL — парсит routerai.ru (requests +
   BeautifulSoup, без headless-браузера) и вычисляет цену в тех же
   единицах, что наша (₽/сообщение для текста, ₽/фото для картинок,
   ₽/сообщение = ₽/сек × наша_длительность для видео).
4. Показывает отклонение и предлагаемую новую цену = RouterAI × 0.95.

ВАЖНО — про Gen-API (второй конкурент): у него нет стабильного публичного
URL на модель (общий текстовый дамп прайс-листа), поэтому автоматически
не сверяется. Раз в 1-2 месяца стоит попросить Claude Code заново снять
genapi.txt и пересчитать — RouterAI дешевле Gen-API в ~93% случаев
(39 из 42 при последней сверке 2026-09-07), так что еженедельно достаточно
следить только за RouterAI, а Gen-API держать в уме как редкую проверку.

ВАЖНО — этот скрипт НИЧЕГО не меняет в БД. Он только показывает отчёт.
Применение цен — отдельный осознанный шаг (см. README.md рядом).
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MAPPING_FILE = Path(__file__).parent / "routerai_mapping.json"
OUR_API_URL = "https://aineron.ru/api/v1/catalog/networks/"
CATEGORY_MAP = {"text": "tekst", "image": "izobrazheniya", "video": "video"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; aineron-price-watch/1.0)"}


def fetch_our_prices():
    """Возвращает {slug: cost_kopecks} со всех трёх категорий с публичного API."""
    prices = {}
    for cat in CATEGORY_MAP.values():
        resp = requests.get(OUR_API_URL, params={"category": cat}, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        for item in resp.json():
            prices[item["slug"]] = item["cost_kopecks"]
    return prices


def parse_routerai_page(url):
    """
    Возвращает список (label, prices, unit) из ПЕРВОЙ ценовой таблицы
    страницы (если тарификация зависит от размера контекста — берётся
    первый, более дешёвый диапазон, который покрывает подавляющее
    большинство наших реальных сообщений).

    prices — словарь {resolution_or_"": price_rub}. Для обычных строк
    (текст/картинки/плоское видео) — один элемент {"": цена}. Для видео
    с разбивкой по разрешению (720p/1080p/4K внутри одного audio-тира,
    см. .model__video-price-row в разметке routerai.ru) — несколько.
    unit — подпись единицы измерения ("/ 1 секунду видео", "/ 1M токенов",
    "/ мегапиксель" и т.п.) — критично для видео: у Seedance-семейства
    есть строка "≈17 ₽ / 1 секунда видео" (готовая оценка) РЯДОМ со
    строками "787 ₽ / 1M токенов" (видео-токены, не ₽/сек напрямую) —
    без разбора unit скрипт может принять токенную ставку за ₽/сек и
    ошибиться на два порядка (проверено вживую 2026-09-07 на Seedance 2.0).
    """
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    table = soup.select_one(".model__price-table")
    if not table:
        return []

    def parse_num(text):
        match = re.search(r"[\d\s]+[.,]?\d*", text.replace("\xa0", " "))
        if not match:
            return None
        return float(match.group(0).replace(" ", "").replace(",", "."))

    rows = []
    label = None
    for item in table.select(".model__price-item"):
        if "price-item_title" in item.get("class", []):
            continue

        label_el = item.select_one(".model__price-item-wrapper .c-text")
        if label_el:
            label = label_el.get_text(strip=True)
            continue

        # Видео с разбивкой по разрешению: несколько .model__video-price-row
        # внутри одного .model__video-price (см. veo-3.1 — "со звуком"/"без
        # звука" тиры, каждый с 720p/1080p/4K).
        video_rows = item.select(".model__video-price-row")
        if video_rows and label:
            unit_el = item.select_one(".model__video-price-unit")
            unit = unit_el.get_text(strip=True) if unit_el else ""
            prices = {}
            for i, vr in enumerate(video_rows):
                price_el = vr.select_one(".c-text_bold")
                if not price_el:
                    continue
                p = parse_num(price_el.get_text(strip=True))
                if p is None:
                    continue
                # Не у всех "video-style" блоков есть подпись разрешения —
                # например, ₽/мегапиксель у Flux использует ту же вложенную
                # разметку, но без .model__video-price-res (проверено вживую
                # 2026-09-07: без этого fallback строка терялась целиком).
                res_el = vr.select_one(".model__video-price-res")
                key = res_el.get_text(strip=True) if res_el else str(i)
                prices[key] = p
            if prices:
                rows.append((label, prices, unit))
            label = None
            continue

        # Обычная строка: одно значение на label (текст/картинки/плоское видео).
        value_el = item.select_one(".model__price-value .c-text_bold")
        if value_el and label:
            unit_el = item.select_one(".model__price-value .c-medium-text, .model__price-value .c-small-text")
            unit = unit_el.get_text(strip=True) if unit_el else ""
            p = parse_num(value_el.get_text(strip=True))
            if p is not None:
                rows.append((label, {"": p}, unit))
            label = None
    return rows


def rub_from_rows(rows, wanted_labels):
    """Достаёт число по совпадению label (регистронезависимо, по вхождению)."""
    out = {}
    for label, prices, _unit in rows:
        low = label.lower()
        price = min(prices.values()) if prices else None
        for key, needles in wanted_labels.items():
            if key not in out and price is not None and any(n in low for n in needles):
                out[key] = price
    return out


TEXT_LABELS = {
    "in": ["входящ"],
    "out": ["исходящ"],
}

# Порядок предпочтения тира для видео. "секунда видео" — готовая оценка
# ₽/сек, которую RouterAI сам считает из видео-токенов для Seedance-семейства
# (см. docstring parse_routerai_page) — если она есть, это самый надёжный
# источник. Иначе — наш продукт всегда генерирует со звуком по умолчанию,
# сравнивать нужно именно с этим тиром конкурента (Veo/Kling/Wan публикуют
# готовый ₽/сек по audio-тирам напрямую, без токенов).
VIDEO_TIER_PRIORITY = ["секунда видео", "со звуком", "с аудио", "текст"]


def compute_router_equivalent(category, rows, spec):
    """Возвращает (router_msg_rub, note) — цена в тех же единицах, что наша."""
    if category == "text":
        vals = rub_from_rows(rows, TEXT_LABELS)
        if "in" not in vals or "out" not in vals:
            return None, "не нашёл вход/выход в таблице"
        p_in, p_out = vals["in"], vals["out"]
        msg = (spec["profile_in"] * p_in + spec["profile_out"] * p_out) / 1_000_000
        return msg, f"{p_in:.0f}/{p_out:.0f} ₽/1М -> профиль {spec['profile_in']}вх/{spec['profile_out']}вых"

    if category == "image":
        if not rows:
            return None, "пустая таблица"
        # Предпочитаем строку с явным упоминанием генерации; если такой нет
        # (бывает у некоторых карточек) — берём первую строку с ненулевой
        # ценой (страхует от случайного попадания на "Исходящие токены: 0₽").
        candidates = [(l, p) for l, p, u in rows if "генерац" in l.lower()]
        if not candidates:
            candidates = [(l, p) for l, p, u in rows if min(p.values()) > 0]
        if not candidates:
            return None, "не нашёл ненулевую цену генерации в таблице"
        label, prices = candidates[0]
        price = min(prices.values())
        if price > 100:  # похоже на ₽/1М токенов, а не ₽/фото — не наш случай, эвристика
            return None, f"похоже на токенную цену ({price}), а не ₽/фото — сверить руками"
        return price, f"{label}: {price} ₽"

    if category == "video":
        if not rows:
            return None, "пустая таблица"
        # Токенные строки (Seedance: "787 ₽ / 1M токенов") — НЕ ₽/сек,
        # исключаем их из выбора тира полностью, иначе цена улетает на
        # два порядка при умножении на длительность напрямую.
        per_sec_rows = [(l, p, u) for l, p, u in rows if "токен" not in u.lower()]
        if not per_sec_rows:
            return None, "нашёл только токенные ставки (₽/1M токенов) — формула другая, сверить руками"
        chosen = None
        for pref in VIDEO_TIER_PRIORITY:
            for label, prices, unit in per_sec_rows:
                if pref in label.lower():
                    chosen = (label, prices)
                    break
            if chosen:
                break
        if not chosen:
            chosen = per_sec_rows[0][:2]
        label, prices = chosen
        price_per_sec = min(prices.values())
        keys = list(prices.keys())
        res_note = ", ".join(f"{k}={v}₽" for k, v in prices.items()) if len(prices) > 1 or keys[0] else str(price_per_sec)
        dur = spec.get("duration_sec", 5)
        return price_per_sec * dur, f'"{label}": {res_note} -> взят {price_per_sec}₽/сек × {dur}с'

    return None, "неизвестная категория"


def main():
    # Консоль Windows по умолчанию (cp1251/cp866) не умеет печатать ₽ — без
    # этого скрипт падает на первом же выводе цены, если запускать не из
    # UTF-8 терминала (обычный `python compare_prices.py` в cmd/PowerShell).
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="сохранить полный отчёт в CSV")
    parser.add_argument("--threshold", type=float, default=15.0, help="порог отклонения %% для показа (по умолч. 15)")
    parser.add_argument("--delay", type=float, default=1.0, help="пауза между запросами к routerai.ru, сек")
    args = parser.parse_args()

    mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    print(f"Загружено {len(mapping)} моделей из карты соответствий.")

    print("Тяну наши текущие цены с aineron.ru...")
    our_prices = fetch_our_prices()

    all_rows = []
    flagged = []

    for slug, spec in mapping.items():
        url = spec.get("router_url")
        our_kop = our_prices.get(slug)
        if our_kop is None:
            print(f"  [{slug}] нет в нашем каталоге (деактивирована?) — пропуск")
            continue
        our_rub = our_kop / 100

        if not url:
            all_rows.append([slug, spec["category"], our_rub, None, None, "нет данных у RouterAI"])
            continue

        try:
            rows = parse_routerai_page(url)
            router_msg, note = compute_router_equivalent(spec["category"], rows, spec)
        except Exception as e:
            router_msg, note = None, f"ошибка запроса: {e}"

        if router_msg is None or router_msg <= 0:
            note = note if router_msg is None else f"router вернул {router_msg} — не с чем делить, пропуск"
            all_rows.append([slug, spec["category"], our_rub, None, None, note])
            print(f"  [{slug}] {note}")
        else:
            delta_pct = (our_rub / router_msg - 1) * 100
            target = round(router_msg * 0.95, 2)
            all_rows.append([slug, spec["category"], our_rub, round(router_msg, 2), round(delta_pct, 1), note])
            if abs(delta_pct) > args.threshold:
                flagged.append((slug, our_rub, router_msg, delta_pct, target))

        time.sleep(args.delay)

    print("\n" + "=" * 78)
    print(f"ОТКЛОНЕНИЯ БОЛЬШЕ {args.threshold:.0f}% (кандидаты на репрайсинг):")
    print("=" * 78)
    if not flagged:
        print("Ничего не нашлось — все проверенные модели в разумных пределах.")
    else:
        for slug, our_rub, router_msg, delta_pct, target in sorted(flagged, key=lambda r: -abs(r[3])):
            direction = "МЫ ДОРОЖЕ" if delta_pct > 0 else "мы дешевле"
            print(f"  {slug:28s} наша={our_rub:>8.2f}₽  router~={router_msg:>8.2f}₽  "
                  f"{delta_pct:+6.1f}%  ({direction})  предложенная цена (-5%) = {target:.2f}₽")

    if args.out:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["slug", "категория", "наша_цена_руб", "router_эквивалент_руб", "отклонение_%", "примечание"])
            w.writerows(all_rows)
        print(f"\nПолный отчёт сохранён: {args.out}")

    print("\nНапоминание: этот скрипт НИЧЕГО не менял в БД — только отчёт.")
    print("Gen-API (второй конкурент) в это сравнение не входит, см. docstring файла.")


if __name__ == "__main__":
    main()
