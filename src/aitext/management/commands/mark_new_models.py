"""
Проставляет NeuralNetwork.is_new=True на кураторский список новейших моделей
каталога — для блока "Новинки" на лендинге. В БД нет даты добавления модели,
поэтому список подобран вручную по признаку "самый свежий тир в линейке
провайдера" (GPT-6 vs GPT-5.x, Claude Opus 5 vs 4.x, Gemini 3.7 vs 3.6/3.5,
Qwen 3.8 vs 3.6, Grok 4.6 vs 4.5, Seedream 5.0 vs 4.x, Veo 3.1 vs 3, Kling v3
vs v2.6) — по 2-3 модели на категорию (текст/изображения/видео), 2026-09-07.

При следующем обновлении каталога отредактируйте список NEW_SLUGS вручную
(снимите флаг со старых через админку/shell, если модель перестала быть
новинкой) — команда идемпотентна и безопасна перезапускать.

Запуск: docker-compose exec web python manage.py mark_new_models
        docker-compose exec web python manage.py mark_new_models --dry-run
"""
from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

NEW_SLUGS = [
    'gpt-6-astra',
    'claude-opus-5',
    'gemini-3-7-flash',
    'qwen3-8-max',
    'grok-4-6',
    'seedream-5-0',
    'veo-3-1',
    'kling-v3',
]


class Command(BaseCommand):
    help = "Проставляет is_new=True на кураторский список новейших моделей (см. docstring файла)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать изменения, не сохранять')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        found = []
        for slug in NEW_SLUGS:
            network = NeuralNetwork.objects.filter(slug=slug).first()
            if not network:
                self.stdout.write(self.style.WARNING(f'{slug}: не найдена в БД, пропуск'))
                continue
            found.append(network)
            if network.is_new:
                self.stdout.write(f'{slug}: уже is_new=True, пропуск')
                continue
            self.stdout.write(f'{slug}: is_new False -> True')
            if not dry_run:
                network.is_new = True
                network.save(update_fields=['is_new'])

        if dry_run:
            self.stdout.write(self.style.WARNING(f'\n--dry-run: изменения НЕ сохранены ({len(found)}/{len(NEW_SLUGS)} найдено)'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nГотово, сохранено в БД ({len(found)}/{len(NEW_SLUGS)} найдено)'))
