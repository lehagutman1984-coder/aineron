"""
Диагностика веб-поиска через Tavily.
Запуск: docker-compose exec web python manage.py test_search "ваш вопрос"
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import requests


class Command(BaseCommand):
    help = "Тестирует Tavily и показывает результаты поиска"

    def add_arguments(self, parser):
        parser.add_argument("query", nargs="?", default="что сегодня в новостях в России")

    def handle(self, *args, **options):
        query = options["query"]
        self.stdout.write(f"\nТест веб-поиска для: «{query}»\n" + "=" * 60)

        tavily_key = getattr(settings, "TAVILY_API_KEY", "")
        self.stdout.write(f"\nTavily ключ: {'ДА' if tavily_key else 'НЕТ — добавь TAVILY_API_KEY в .env'}")
        if not tavily_key:
            return

        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": tavily_key, "query": query, "search_depth": "basic", "max_results": 5},
                timeout=12,
            )
            r.raise_for_status()
            items = r.json().get("results", [])
            self.stdout.write(self.style.SUCCESS(f"OK: {len(items)} результатов\n"))
            for i, item in enumerate(items, 1):
                self.stdout.write(f"[{i}] {item['title']}")
                self.stdout.write(f"    {item['url']}")
                if item.get("published_date"):
                    self.stdout.write(f"    Дата: {item['published_date']}")
                self.stdout.write("")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"ОШИБКА: {e}"))

        self.stdout.write("=" * 60 + "\n")
