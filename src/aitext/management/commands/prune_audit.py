"""Sprint 5.5: ретеншн audit-лога — удаление записей старше N дней (по умолчанию 90)."""
from django.core.management.base import BaseCommand
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Prune ProjectAuditEntry records older than N days (default: 90)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90, help='Retention period in days')

    def handle(self, *args, **options):
        from aitext.models import ProjectAuditEntry
        days = options['days']
        cutoff = timezone.now() - datetime.timedelta(days=days)
        deleted, _ = ProjectAuditEntry.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'Pruned {deleted} audit entries older than {days} days.'))
