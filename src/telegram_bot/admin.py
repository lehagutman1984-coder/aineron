from django.contrib import admin
from .models import (
    TelegramUser, TelegramChat, TelegramLinkToken, TelegramGroup, AITask,
    StarsSubscription, BusinessConnection, BusinessDraft, TelegramTopic,
    ManagedBot,
)


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


@admin.register(AITask)
class AITaskAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'schedule_type', 'next_run_at', 'is_active',
                    'paused_reason', 'runs_count', 'created_from')
    list_filter = ('schedule_type', 'is_active', 'created_from', 'use_web_search')
    search_fields = ('title', 'prompt', 'user__email')
    raw_id_fields = ('user', 'network')
    readonly_fields = ('created_at', 'last_run_at', 'runs_count')


@admin.register(StarsSubscription)
class StarsSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'tariff', 'xtr_amount', 'expires_at', 'is_active')
    list_filter = ('is_active',)
    raw_id_fields = ('tg_user', 'tariff')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BusinessConnection)
class BusinessConnectionAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'connection_id', 'mode', 'is_enabled', 'secretary_on',
                    'replies_this_month', 'created_at')
    list_filter = ('mode', 'is_enabled', 'secretary_on')
    raw_id_fields = ('tg_user',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(BusinessDraft)
class BusinessDraftAdmin(admin.ModelAdmin):
    list_display = ('connection', 'client_name', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('connection',)
    readonly_fields = ('created_at',)


@admin.register(TelegramTopic)
class TelegramTopicAdmin(admin.ModelAdmin):
    list_display = ('tg_user', 'topic_id', 'title', 'project', 'is_active')
    raw_id_fields = ('tg_user', 'project', 'chat')


@admin.register(ManagedBot)
class ManagedBotAdmin(admin.ModelAdmin):
    list_display = ('bot_username', 'name', 'owner', 'is_active', 'messages_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('bot_username', 'name', 'owner__user__email')
    raw_id_fields = ('owner', 'network', 'project')
    readonly_fields = ('created_at', 'messages_count')
    exclude = ('token',)


@admin.register(TelegramGroup)
class TelegramGroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_title', 'organization', 'enabled', 'created_at')
    list_filter = ('enabled',)
    search_fields = ('group_title', 'organization__name')
    raw_id_fields = ('organization', 'registered_by')
    readonly_fields = ('created_at',)
