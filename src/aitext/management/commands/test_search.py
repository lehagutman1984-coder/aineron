"""
Диагностика веб-поиска: проверяет Tavily и Brave Search на живом сервере.
Запуск: docker-compose exec web python manage.py test_search "ваш вопрос"
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import requests


class Command(BaseCommand):
    help = "Тестирует Tavily и Brave Search и показывает что работает"

    def add_arguments(self, parser):
        parser.add_argument("query", nargs="?", default="что сегодня в новостях в России")

    def handle(self, *args, **options):
        query = options["query"]
        self.stdout.write(f"\nТест веб-поиска для: «{query}»\n" + "=" * 60)

        # ── Tavily ────────────────────────────────────────────────────────────
        tavily_key = getattr(settings, "TAVILY_API_KEY", "")
        self.stdout.write(f"\n[1] Tavily — ключ: {'ДА' if tavily_key else 'НЕТ (TAVILY_API_KEY не задан)'}")
        if tavily_key:
            try:
                r = requests.post(
                    "https://api.tavily.com/search",
                    json={"api_key": tavily_key, "query": query, "search_depth": "basic", "max_results": 3},
                    timeout=12,
                )
                r.raise_for_status()
                items = r.json().get("results", [])
                self.stdout.write(self.style.SUCCESS(f"   OK: {len(items)} результатов"))
                for i, item in enumerate(items, 1):
                    self.stdout.write(f"   [{i}] {item['title'][:80]}")
                    self.stdout.write(f"       {item['url']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ОШИБКА: {e}"))

        # ── Brave ─────────────────────────────────────────────────────────────
        brave_key = getattr(settings, "BRAVE_SEARCH_API_KEY", "")
        self.stdout.write(f"\n[2] Brave Search — ключ: {'ДА' if brave_key else 'НЕТ (BRAVE_SEARCH_API_KEY не задан)'}")
        if brave_key:
            try:
                r = requests.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
                    params={"q": query, "count": 3},
                    timeout=12,
                )
                r.raise_for_status()
                web = r.json().get("web", {}).get("results", [])
                self.stdout.write(self.style.SUCCESS(f"   OK: {len(web)} результатов"))
                for i, item in enumerate(web, 1):
                    self.stdout.write(f"   [{i}] {item['title'][:80]}")
                    self.stdout.write(f"       {item['url']}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ОШИБКА: {e}"))

        self.stdout.write("\n" + "=" * 60 + "\n")
