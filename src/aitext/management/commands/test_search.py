"""
Диагностика веб-поиска: пробуем разные механизмы laozhang.ai.
Запуск: docker-compose exec web python manage.py test_search "ваш вопрос"
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from openai import OpenAI


class Command(BaseCommand):
    help = "Тестирует все механизмы веб-поиска и показывает что работает"

    def add_arguments(self, parser):
        parser.add_argument("query", nargs="?", default="что сегодня в новостях в России")

    def handle(self, *args, **options):
        query = options["query"]
        client = OpenAI(base_url=settings.LAOZHANG_API_URL, api_key=settings.LAOZHANG_API_KEY)

        self.stdout.write(f"\nТест веб-поиска для: «{query}»\n" + "=" * 60)

        candidates = [
            {
                "label": "grok-3 + search_parameters (xAI LiveSearch)",
                "model": "grok-3",
                "kwargs": {"extra_body": {"search_parameters": {"mode": "auto"}}},
            },
            {
                "label": "grok-4 + search_parameters (xAI LiveSearch)",
                "model": "grok-4",
                "kwargs": {"extra_body": {"search_parameters": {"mode": "auto"}}},
            },
            {
                "label": "grok-4-fast + search_parameters",
                "model": "grok-4-fast",
                "kwargs": {"extra_body": {"search_parameters": {"mode": "auto"}}},
            },
            {
                "label": "grok-3 (без параметров, baseline)",
                "model": "grok-3",
                "kwargs": {},
            },
            {
                "label": "gemini-2.5-flash (Google Search grounding)",
                "model": "gemini-2.5-flash",
                "kwargs": {
                    "extra_body": {
                        "tools": [{"googleSearch": {}}],
                    }
                },
            },
        ]

        prompt = (
            f"{query}\n\n"
            "Найди актуальную информацию в интернете и дай ответ с источниками. "
            "Если у тебя есть доступ к интернету — покажи это явно: укажи URL и дату публикации хотя бы одного факта."
        )

        for c in candidates:
            self.stdout.write(f"\n[ТЕСТ] {c['label']}")
            try:
                resp = client.chat.completions.create(
                    model=c["model"],
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=800,
                    **c["kwargs"],
                )
                text = resp.choices[0].message.content.strip()
                # Признаки реального поиска: URL, дата 2025/2026, "согласно"
                has_url = "http" in text or "www." in text
                has_recent = any(y in text for y in ["2025", "2026", "июнь", "June", "июль", "July"])
                indicator = "ПОИСК" if (has_url or has_recent) else "БЕЗ ПОИСКА"
                self.stdout.write(self.style.SUCCESS(f"  OK [{indicator}]: {text[:300]}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ОШИБКА: {e}"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Скопируй результаты и покажи их в чате с Claude Code.\n")
