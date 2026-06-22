"""
Sprint 4.1 — Backfill embeddings for all existing ProjectFile(status='ready').

Usage:
    docker-compose exec web python manage.py backfill_embeddings
    docker-compose exec web python manage.py backfill_embeddings --dry-run
    docker-compose exec web python manage.py backfill_embeddings --project-id 42
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Backfill vector embeddings for all ready ProjectFiles'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Только показать, не запускать задачи')
        parser.add_argument('--project-id', type=int, help='Только для конкретного проекта')
        parser.add_argument('--force', action='store_true', help='Перезаписать уже эмбеддированные (embed_status=done)')
        parser.add_argument('--status', help='Фильтр по embed_status (error, none, pending). Пример: --status=error')

    def handle(self, *args, **options):
        from aitext.models import ProjectFile
        from aitext.tasks import embed_project_file

        qs = ProjectFile.objects.filter(status='ready').exclude(extracted_text='')
        if options.get('project_id'):
            qs = qs.filter(project_id=options['project_id'])
        if options.get('status'):
            qs = qs.filter(embed_status=options['status'])
        elif not options.get('force'):
            qs = qs.exclude(embed_status='done')

        total = qs.count()
        self.stdout.write(f'Найдено файлов для эмбеддинга: {total}')

        if options.get('dry_run'):
            self.stdout.write('[dry-run] Задачи не запущены')
            return

        queued = 0
        for pf in qs.iterator():
            embed_project_file.delay(pf.id)
            queued += 1
            if queued % 10 == 0:
                self.stdout.write(f'  В очереди: {queued}/{total}')

        self.stdout.write(self.style.SUCCESS(f'Готово: {queued} задач поставлено в очередь'))
