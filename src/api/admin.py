from django.contrib import admin
from api.models import APIKey, TokenUsage


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
