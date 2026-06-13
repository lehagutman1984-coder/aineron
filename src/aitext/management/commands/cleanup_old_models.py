from django.core.management.base import BaseCommand
from aitext.models import NeuralNetwork

KEEP_SLUGS = {
    # Текст
    'gpt-4o', 'gpt-4o-mini', 'gpt-4-1', 'gpt-4-1-mini', 'gpt-5',
    'chatgpt-4o-latest', 'o3', 'o4-mini', 'o1', 'o3-mini',
    'claude-sonnet-4-6', 'claude-opus-4-8', 'claude-haiku-4-5', 'claude-sonnet-4-5',
    'gemini-2-5-flash', 'gemini-2-5-pro', 'gemini-3-flash',
    'deepseek-v3', 'deepseek-r1', 'deepseek-v3-1',
    'qwen3-235b', 'qwen3-max', 'qwq-plus',
    'grok-4', 'grok-3', 'grok-4-fast',
    'kimi-k2', 'glm-4-5', 'gpt-3-5-turbo',
    # Изображения
    'dall-e-3', 'gpt-image-1', 'gpt-image-2', 'gpt-image-1-mini',
    'flux-2-pro', 'flux-2-max', 'flux-kontext-pro', 'flux-kontext-max', 'flux-2-flex',
}


class Command(BaseCommand):
    help = 'Удаляет старые модели, оставляет только добавленные через add_laozhang_models'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, не удалять',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        to_delete = NeuralNetwork.objects.exclude(slug__in=KEEP_SLUGS)
        count = to_delete.count()

        self.stdout.write(f'Будет удалено: {count} моделей')
        self.stdout.write(f'Будет сохранено: {NeuralNetwork.objects.filter(slug__in=KEEP_SLUGS).count()} моделей')

        if dry_run:
            self.stdout.write('\n--- Список для удаления (dry-run) ---')
            for n in to_delete.order_by('name')[:50]:
                self.stdout.write(f'  {n.name} ({n.model_name})')
            if count > 50:
                self.stdout.write(f'  ... и ещё {count - 50}')
            return

        to_delete.delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено {count} старых моделей'))
