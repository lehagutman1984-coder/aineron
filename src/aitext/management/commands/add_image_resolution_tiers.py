"""
Добавляет select-поле "Разрешение" модели Qwen Image 3.0 Pro (apimart_async) —
раньше было "ui_settings": {"sections": []}, 2K был физически недоступен,
хотя провайдер отдаёт его за доплату. Значение уходит в параметр `size`,
который forward'ится как есть в generate_image_apimart_async (см. цикл
`for param in ['size', 'n', 'aspect_ratio', 'quality']` в fal_utils.py).

ВАЖНО — проверено живыми вызовами к APIMart 2026-09-06, ДО того как эти
значения были зафиксированы, именно поэтому они такие специфичные:
  - grok-imagine-image-quality: `size` вообще НЕ поддерживается на асинхронных
    xAI-задачах (400 "parameter size is not supported for asynchronous xAI
    image tasks") — резолюция для этой модели программно не выбирается,
    поле для неё НЕ добавляется вообще (изначальный план из аудита ошибочен).
  - qwen-image-3.0-pro: `size` ожидает ЛИБО соотношение ("16:9"), ЛИБО пиксели
    ("1024x1024") — значения "1K"/"2K" отклоняются (400 "invalid size").
    "1024x1024" и "2048x2048" оба приняты (200, submitted) — используются как
    значения полей ниже.

Доплата — из IMAGE_PROVIDER_MIGRATION_PRICING_2026-09-05.html (курс 80 ₽/$):
qwen-image-3.0-pro 1K $0.02857 / 2K $0.05714 → доплата (0.05714-0.02857)×80=
2.29₽, округлено до 4₽ (пол для 2K: 0.05714×80×1.05=4.80₽, итог 4.27+4=8.27₽ —
есть запас над полом).

Запуск: docker-compose exec web python manage.py add_image_resolution_tiers
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

TIERS = {
    'qwen-image-3-0-pro': {
        'name': 'size',
        'label': 'Разрешение',
        'options': [
            {'value': '1024x1024', 'label': '1K (1024×1024)', 'extra_cost': 0},
            {'value': '2048x2048', 'label': '2K (2048×2048)', 'extra_cost': 4},
        ],
    },
}


class Command(BaseCommand):
    help = "Добавляет select 'Разрешение' (1K/2K) для Grok Imagine Quality и Qwen Image 3.0 Pro"

    def handle(self, *args, **options):
        for slug, field in TIERS.items():
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            config = network.config_json or {}
            ui_settings = config.setdefault('ui_settings', {})
            sections = ui_settings.setdefault('sections', [])
            if any(
                f.get('name') == field['name']
                for section in sections
                for f in section.get('fields', [])
            ):
                self.stdout.write(f'{slug}: поле {field["name"]} уже есть, пропуск')
                continue
            sections.append({
                'title': 'Настройки изображения',
                'fields': [{
                    'name': field['name'],
                    'type': 'select',
                    'label': field['label'],
                    'extra_cost': 0,
                    'options': field['options'],
                }],
            })
            network.config_json = config
            network.save(update_fields=['config_json'])
            self.stdout.write(self.style.SUCCESS(f'{slug}: добавлено поле "{field["label"]}"'))
