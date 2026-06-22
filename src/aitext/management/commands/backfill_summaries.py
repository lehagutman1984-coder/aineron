"""Sprint 6.5: Бэкфилл summary-эмбеддингов для существующих файлов базы знаний.

Использование:
    python manage.py backfill_summaries [--project-id=N] [--limit=N] [--dry-run]
"""

import time

from django.core.management.base import BaseCommand

from aitext.models import ProjectFile


class Command(BaseCommand):
    help = 'Backfill summary embeddings (chunk_index=-1) for project knowledge files (Sprint 6.5)'

    def add_arguments(self, parser):
        parser.add_argument('--project-id', type=int, default=None,
                            help='Process only this project')
        parser.add_argument('--limit', type=int, default=None,
                            help='Max files to process')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be processed, do not embed')

    def handle(self, *args, **options):
        from django.db import connection

        qs = ProjectFile.objects.filter(
            status='ready', embed_status='done',
        ).exclude(extracted_text='')

        if options['project_id']:
            qs = qs.filter(project_id=options['project_id'])

        # Exclude files that already have summary chunk
        with connection.cursor() as cur:
            cur.execute(
                'SELECT DISTINCT file_id FROM aitext_projectchunk WHERE chunk_index = -1'
            )
            already_done = {row[0] for row in cur.fetchall()}

        qs = qs.exclude(id__in=already_done).select_related('project')

        if options['limit']:
            qs = qs[:options['limit']]

        total = qs.count()
        self.stdout.write(f'Files to process: {total}')

        if options['dry_run']:
            for f in qs:
                self.stdout.write(f'  [dry-run] {f.project.name} / {f.filename}')
            return

        ok = 0
        errors = 0
        for i, f in enumerate(qs, 1):
            try:
                from aitext.embeddings import embed_file_summary
                success = embed_file_summary(f)
                if success:
                    ok += 1
                    self.stdout.write(f'[{i}/{total}] OK: {f.project.name} / {f.filename}')
                else:
                    errors += 1
                    self.stdout.write(
                        self.style.WARNING(f'[{i}/{total}] SKIP: {f.project.name} / {f.filename}')
                    )
            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f'[{i}/{total}] ERROR: {f.filename}: {e}')
                )
            time.sleep(0.2)  # avoid rate-limit

        self.stdout.write(self.style.SUCCESS(
            f'Done. OK={ok}, errors={errors}, total={total}'
        ))
