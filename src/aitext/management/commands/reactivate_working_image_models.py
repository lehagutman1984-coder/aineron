"""
Реактивирует 3 модели изображений, найденные деактивированными в живой БД
2026-09-06 (is_active=False до какого-либо действия в этой сессии — причина
неизвестна, не связана с текущей работой над провайдерами) — по прямому
запросу пользователя: "главное чтобы работала модель хотя бы от одного
провайдера... если резерва нет оставь без резерва".

Все три подтверждены рабочими минимум у одного провайдера:
  gemini-2-5-flash-image (Nano Banana v1) — APIMart (nano-banana-ext) +
    CometAPI (через chat/completions, см. add_nano_banana_cometapi_fallback) —
    полный резерв
  seedream-4-0 — APIMart + CometAPI (doubao-seedream-4-0-250828, точное
    совпадение id) — полный резерв
  qwen-image-2-0 — только APIMart (CometAPI: "Coming soon", недоступна) —
    без резерва, что допустимо по прямому решению пользователя

Вместе с добавлением Midjourney (replace_dalle3_with_midjourney.py) и
деактивацией DALL-E 3 это даёт ровно 23 активные модели изображений.

Запуск: docker-compose exec web python manage.py reactivate_working_image_models
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

SLUGS = ['gemini-2-5-flash-image', 'seedream-4-0', 'qwen-image-2-0']


class Command(BaseCommand):
    help = "Реактивирует Nano Banana v1 / Seedream 4.0 / Qwen Image 2.0 — все работают минимум у одного провайдера"

    def handle(self, *args, **options):
        for slug in SLUGS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            if network.is_active:
                self.stdout.write(f'{slug}: уже активна, пропуск')
                continue
            network.is_active = True
            network.save(update_fields=['is_active'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: активирована'))
