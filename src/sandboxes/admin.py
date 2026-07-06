import logging

from django.contrib import admin, messages

from .models import SandboxSession

logger = logging.getLogger(__name__)


@admin.register(SandboxSession)
class SandboxSessionAdmin(admin.ModelAdmin):
    list_display = ['public_id', 'user', 'template', 'size', 'state',
                    'exec_count', 'abuse_flagged', 'reserved_kopecks',
                    'charged_kopecks', 'created_at']
    list_filter = ['state', 'template', 'size', 'abuse_flagged']
    search_fields = ['id', 'user__email']
    readonly_fields = [f.name for f in SandboxSession._meta.fields]
    actions = ['kill_sessions']

    @admin.action(description='Убить выбранные сессии (kill + финальный биллинг)')
    def kill_sessions(self, request, queryset):
        from . import billing, client
        killed = 0
        for session in queryset.filter(state__in=SandboxSession.ACTIVE_STATES):
            duration = float(session.ttl_seconds)
            try:
                result = client.kill(str(session.id))
                if result.get('duration_seconds'):
                    duration = float(result['duration_seconds'])
            except Exception as exc:
                logger.warning('[sandbox] admin kill %s: %s', session.public_id, exc)
            billing.settle(session, duration)
            session.state = SandboxSession.State.STOPPED
            session.save(update_fields=['state'])
            killed += 1
        self.message_user(request, f'Остановлено сессий: {killed}', messages.SUCCESS)

    def has_add_permission(self, request):
        return False
