from django.contrib import admin
from .models import Category, NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage, FileAttachment, GeneratedImage, FAQ
from django.utils.html import format_html

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'order')
    list_editable = ('order',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(NeuralNetwork)
class NeuralNetworkAdmin(admin.ModelAdmin):
    list_display = ('avatar_image', 'name', 'category', 'model_name', 'cost_per_message', 'is_popular', 'unlimited', 'is_default', 'is_active', 'order', 'translate_to_english', 'is_direct', 'is_custom', 'max_tokens', 'max_input_tokens')
    list_editable = ('model_name', 'cost_per_message', 'is_popular', 'unlimited', 'is_default', 'is_active', 'order', 'translate_to_english', 'is_direct', 'is_custom', 'max_tokens', 'max_input_tokens')
    list_filter = ('category', 'provider', 'is_active', 'unlimited', 'is_popular', 'is_default', 'translate_to_english', 'is_direct', 'is_custom')
    search_fields = ('name', 'description', 'seo_title', 'seo_keywords', 'model_name')
    readonly_fields = ('id',)
    filter_horizontal = ('tariffs',)
    fieldsets = (
        (None, {'fields': ('name', 'slug', 'category', 'description')}),
        ('Визуальное оформление', {'fields': ('avatar', 'avatar_url')}),
        ('Стоимость и статус', {
            'fields': ('cost_per_message', 'is_active', 'is_popular', 'is_default', 'order', 'translate_to_english', 'max_tokens', 'max_input_tokens')
        }),
        ('Безлимитные сообщения', {
            'fields': ('unlimited', 'tariffs', 'messages_limit'),
            'description': 'Если включено, пользователи с выбранными тарифами получают бесплатные сообщения в рамках дневного лимита.',
        }),
        ('Поддерживаемые типы файлов', {
            'fields': ('handle_archive', 'handle_text_files', 'handle_photo', 'handle_video'),
            'description': 'Какие типы файлов может обрабатывать нейросеть. Если ни один не выбран, кнопка прикрепления файлов будет скрыта.',
            'classes': ('wide',)
        }),
        ('Модель OpenRouter', {
            'fields': ('model_name',),
            'description': 'Название модели для OpenRouter (например, deepseek/deepseek-chat-v3.1)',
        }),
        ('Встроенный промт', {'fields': ('has_prompt', 'prompt')}),
        ('SEO', {
            'fields': ('seo_title', 'seo_description', 'seo_keywords'),
            'classes': ('wide',),
            'description': 'Мета-теги для страницы нейросети. Если не заполнены, используются значения по умолчанию.',
        }),
        ('Провайдер fal.ai', {
            'fields': ('provider', 'config_json'),
            'classes': ('wide',),
            'description': 'Для fal.ai укажите model_name и заполните config_json'
        }),
        ('Отображение в футере', {
            'fields': ('is_direct', 'is_custom'),
            'classes': ('wide',),
            'description': 'Если включено, нейросеть будет отображаться в соответствующем разделе футера.',
        }),
    )
    prepopulated_fields = {'slug': ('name',)}

    def avatar_image(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 8px; object-fit: cover;" />', obj.avatar.url)
        elif obj.avatar_url:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 8px; object-fit: cover;" />', obj.avatar_url)
        else:
            return format_html('<img src="https://placehold.co/40x40/0a7cff/white?text={}" width="40" height="40" style="border-radius: 8px;" />', obj.name[0])
    avatar_image.short_description = 'Аватар'

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.provider == 'openrouter':
            readonly.append('config_json')
        return readonly

@admin.register(GeneratedImage)
class GeneratedImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'image', 'prompt_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('message__content', 'prompt')
    readonly_fields = ('created_at',)

    def prompt_preview(self, obj):
        return obj.prompt[:50] + ('...' if len(obj.prompt) > 50 else '')
    prompt_preview.short_description = 'Промт (предпросмотр)'

@admin.register(FileAttachment)
class FileAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'message_link', 'filename', 'media_type', 'file_size', 'source', 'created_at')
    list_filter = ('media_type', 'source', 'created_at')
    search_fields = ('filename', 'message__chat__user__username', 'message__chat__user__email')
    readonly_fields = ('id', 'created_at', 'file_url_display', 'extracted_text_preview')
    list_select_related = ('message__chat__user',)
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('message', 'filename', 'file_path', 'file_size', 'mime_type', 'media_type')
        }),
        ('Извлечённый текст', {
            'fields': ('extracted_text',),
            'classes': ('wide',),
        }),
        ('Медиа-информация', {
            'fields': ('width', 'height', 'duration', 'resolution'),
            'classes': ('collapse',),
        }),
        ('Метаданные', {
            'fields': ('source', 'model_id', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def message_link(self, obj):
        from django.urls import reverse
        from django.utils.html import format_html
        if obj.message:
            url = reverse('admin:aitext_message_change', args=[obj.message.id])
            return format_html('<a href="{}">Сообщение #{}</a>', url, obj.message.id)
        return '-'
    message_link.short_description = 'Сообщение'

    def file_url_display(self, obj):
        from django.utils.html import format_html
        if obj.file_path:
            return format_html('<a href="{}" target="_blank">Открыть</a>', obj.file_url)
        return '-'
    file_url_display.short_description = 'URL файла'

    def extracted_text_preview(self, obj):
        if obj.extracted_text:
            preview = obj.extracted_text[:200] + ('...' if len(obj.extracted_text) > 200 else '')
            return preview
        return '-'
    extracted_text_preview.short_description = 'Текст (предпросмотр)'

@admin.register(NeuralNetworkDailyUsage)
class NeuralNetworkDailyUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'network', 'date', 'count')
    list_filter = ('network', 'date')
    search_fields = ('user__username', 'user__email', 'network__name')
    readonly_fields = ('date',)

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'network', 'get_title', 'created_at', 'updated_at')
    list_filter = ('network', 'created_at')
    search_fields = ('user__username', 'user__email', 'title')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('user', 'network', 'title')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_title(self, obj):
        return obj.get_title()
    get_title.short_description = 'Название'
    get_title.admin_order_field = 'title'


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'role', 'short_content', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content',)
    readonly_fields = ('id', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('chat', 'role', 'content', 'files')
        }),
        ('Дата', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def short_content(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    short_content.short_description = 'Содержание'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'show_everywhere', 'show_on_main', 'neural_network', 'order')
    list_filter = ('show_everywhere', 'show_on_main', 'neural_network')
    search_fields = ('question', 'answer')
    list_editable = ('order', 'show_everywhere', 'show_on_main')
    fieldsets = (
        (None, {'fields': ('question', 'answer')}),
        ('Отображение', {'fields': ('show_on_main', 'show_everywhere', 'neural_network')}),
        ('Сортировка', {'fields': ('order',)}),
    )
