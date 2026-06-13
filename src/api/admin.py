from django.contrib import admin
from api.models import APIKey, TokenUsage, BatchJob, BatchJobItem, Webhook, AuditLog


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'key_prefix', 'is_active', 'created_at', 'last_used_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'name', 'key_prefix']
    readonly_fields = ['key_prefix', 'hashed_key', 'created_at', 'last_used_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False  # ключи создаются только через API


@admin.register(TokenUsage)
class TokenUsageAdmin(admin.ModelAdmin):
    list_display = ['user', 'network', 'total_tokens', 'stars_charged', 'created_at']
    list_filter = ['network', 'created_at']
    search_fields = ['user__email', 'request_id']
    readonly_fields = ['user', 'network', 'api_key', 'prompt_tokens', 'completion_tokens',
                       'total_tokens', 'stars_charged', 'request_id', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BatchJob)
class BatchJobAdmin(admin.ModelAdmin):
    list_display = ['pk', 'user', 'status', 'request_counts_total', 'request_counts_completed', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__email']
    readonly_fields = ['user', 'api_key', 'organization', 'created_at', 'in_progress_at', 'completed_at', 'cancelled_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ['user', 'url', 'events', 'is_active', 'created_at', 'last_triggered_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'url']
    readonly_fields = ['secret', 'created_at', 'last_triggered_at']
    ordering = ['-created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'resource_type', 'resource_id', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'resource_id', 'ip_address']
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
