from django.contrib import admin
from .models import TelegramUser, TelegramChat, TelegramLinkToken


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'telegram_username', 'telegram_first_name', 'user', 'linked_at', 'voice_responses', 'web_search')
    list_filter = ('voice_responses', 'web_search', 'streaming')
    search_fields = ('telegram_username', 'telegram_first_name', 'user__email')
    raw_id_fields = ('user', 'default_network', 'default_image_network')
    readonly_fields = ('linked_at',)


@admin.register(TelegramChat)
class TelegramChatAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'chat', 'updated_at')
    raw_id_fields = ('tg_user', 'chat')


@admin.register(TelegramLinkToken)
class TelegramLinkTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'used')
    list_filter = ('used',)
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)
