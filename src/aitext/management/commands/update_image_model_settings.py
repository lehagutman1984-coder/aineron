"""Sprint 4: добавляет Creative Controls (seed / negative_prompt / num_images)
в ui_settings уже задеплоенных моделей изображений.

Безопасно (идемпотентно) — добавляет поле только если его ещё нет (по name).
Применяется ТОЛЬКО к Flux-моделям (FLUX_MODEL_SLUGS): seed/negative_prompt
не поддерживаются OpenAI-бэкендом (dall-e/gpt_image) и могут вызвать 400.

Канонический источник конфигурации — IMAGE_CONFIG в add_laozhang_models.py
(там те же поля добавлены в config['flux']), поэтому повторный запуск
add_laozhang_models не сотрёт эти настройки. Эта команда нужна для строк,
созданных ДО Sprint 4.
"""
from django.core.management.base import BaseCommand

from aitext.models import NeuralNetwork
from aitext.management.commands.add_laozhang_models import (
    CREATIVE_CONTROL_FIELDS, FLUX_MODEL_SLUGS,
)


class Command(BaseCommand):
    help = 'Добавляет seed/negative_prompt/num_images в ui_settings Flux-моделей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all-fal',
            action='store_true',
            help='Применить ко всем fal-ai моделям (по умолчанию только Flux-слаги)',
        )

    def handle(self, *args, **options):
        if options.get('all_fal'):
            qs = NeuralNetwork.objects.filter(provider='fal-ai', is_active=True)
        else:
            qs = NeuralNetwork.objects.filter(slug__in=FLUX_MODEL_SLUGS)

        if not qs.exists():
            self.stdout.write('Подходящие модели не найдены.')
            return

        updated = 0
        for network in qs:
            config = dict(network.config_json or {})
            ui = config.setdefault('ui_settings', {})
            sections = ui.setdefault('sections', [])
            if not sections:
                sections.append({'title': 'Настройки изображения', 'fields': []})
            fields = sections[0].setdefault('fields', [])

            existing_names = {f.get('name') for f in fields}
            added = []
            for fld in CREATIVE_CONTROL_FIELDS:
                if fld['name'] not in existing_names:
                    # копия, чтобы не делить mutable-словарь между строками БД
                    fields.append(dict(fld))
                    added.append(fld['name'])

            if added:
                network.config_json = config
                network.save(update_fields=['config_json'])
                updated += 1
                self.stdout.write(
                    f'  обновлена: {network.name} ({network.slug}) — добавлено: {", ".join(added)}'
                )
            else:
                self.stdout.write(f'  без изменений: {network.name} ({network.slug})')

        self.stdout.write(f'\nГотово! Обновлено моделей: {updated}')
