#!/usr/bin/env python3
"""
Проверка страниц из sitemap.xml: код ответа каждого адреса и наличие canonical.

Печатает только проблемные адреса; код возврата 1, если найдены проблемы (можно вешать на CI/cron).
Редиректы НЕ считаются успехом: адрес в sitemap должен сам отвечать 200 (иначе это
«URL в карте сайта - редирект»). Зависимостей нет (только стандартная библиотека).

Использование:
    python scripts/check_sitemap_status.py                       # оба сайта
    python scripts/check_sitemap_status.py https://aineron.net   # один сайт
    python scripts/check_sitemap_status.py --delay 0.5           # пауза между запросами (сек)
    python scripts/check_sitemap_status.py --retries 3           # повторы при не-200 (отсеивает сбои)
    python scripts/check_sitemap_status.py --no-canonical        # только коды ответа

Почему повторы: страницы получают данные от API; кратковременный сбой (перезапуск контейнера,
лимит запросов) даёт разовый 404. Адрес считается проблемным, только если не-200 на ВСЕХ попытках.
"""
import argparse
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_SITES = ["https://aineron.ru", "https://aineron.net"]
UA = "aineron-sitemap-check/1.0"
CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]*>', re.I)
HREF_RE = re.compile(r'href="([^"]+)"', re.I)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # 3xx возвращаем как есть


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(url: str, timeout: int = 30):
    """(status, body_text, location). Сетевая ошибка -> (0, '', ошибка)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body, e.headers.get("Location", "")
    except Exception as e:  # таймаут, DNS, TLS
        return 0, "", str(e)[:80]


def sitemap_urls(site: str):
    status, body, _ = fetch(f"{site}/sitemap.xml")
    if status != 200:
        raise SystemExit(f"{site}/sitemap.xml -> HTTP {status}")
    root = ET.fromstring(body.encode("utf-8"))
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [el.text.strip() for el in root.findall("s:url/s:loc", ns) if el.text]


def check_url(url: str, retries: int, delay: float, want_canonical: bool):
    """Возвращает список проблем по адресу (пусто = всё хорошо)."""
    last = None
    for attempt in range(1, retries + 1):
        status, body, extra = fetch(url)
        if status == 200:
            if want_canonical:
                m = CANONICAL_RE.search(body)
                if not m:
                    return ["нет <link rel=canonical>"]
                href = HREF_RE.search(m.group(0))
                canon = href.group(1) if href else ""
                # canonical на себя (допускаем разницу только в слеше корня)
                if canon.rstrip("/") != url.rstrip("/"):
                    return [f"canonical указывает на другой адрес: {canon}"]
            return []
        last = f"HTTP {status}" + (f" -> {extra}" if extra else "")
        if attempt < retries:
            time.sleep(max(delay, 1.0))
    return [last]


def main() -> int:
    ap = argparse.ArgumentParser(description="Проверка страниц из sitemap.xml")
    ap.add_argument("sites", nargs="*", default=DEFAULT_SITES)
    ap.add_argument("--delay", type=float, default=0.3, help="пауза между запросами, сек (по умолчанию 0.3)")
    ap.add_argument("--retries", type=int, default=2, help="попыток на адрес при не-200 (по умолчанию 2)")
    ap.add_argument("--no-canonical", action="store_true", help="не проверять canonical")
    args = ap.parse_args()

    total_bad = 0
    for site in args.sites:
        site = site.rstrip("/")
        urls = sitemap_urls(site)
        print(f"== {site}: {len(urls)} адресов в sitemap.xml")
        bad = []
        for i, url in enumerate(urls, 1):
            problems = check_url(url, args.retries, args.delay, not args.no_canonical)
            if problems:
                bad.append((url, problems[0]))
                print(f"  ПРОБЛЕМА  {url}  ->  {problems[0]}", flush=True)
            time.sleep(args.delay)
        ok = len(urls) - len(bad)
        print(f"   итого: {ok} из {len(urls)} в порядке, проблем: {len(bad)}\n")
        total_bad += len(bad)
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
