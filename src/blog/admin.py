from django.contrib import admin
from .models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'seo_title', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'slug')}),
        ('SEO', {'fields': ('seo_title', 'seo_description', 'seo_keywords'), 'classes': ('wide',)}),
        ('Дата', {'fields': ('created_at',)}),
    )
    readonly_fields = ('created_at',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_published', 'show_in_notification', 'show_on_main', 'views_count', 'published_at')
    list_filter = ('category', 'is_published', 'show_in_notification', 'show_on_main', 'published_at', 'neural_networks')
    search_fields = ('title', 'preview_text', 'content')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('created_at', 'updated_at', 'views_count')
    exclude = ('author',)
    filter_horizontal = ('neural_networks',)

    fieldsets = (
        (None, {'fields': ('title', 'slug', 'category', 'is_published', 'show_in_notification', 'show_on_main')}),
        ('Контент', {'fields': ('preview_image', 'preview_text', 'content')}),
        ('Связанные нейросети', {'fields': ('neural_networks',)}),
        ('SEO', {'fields': ('seo_title', 'seo_description', 'seo_keywords'), 'classes': ('wide',)}),
        ('Даты', {'fields': ('published_at', 'created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.author = request.user
        super().save_model(request, obj, form, change)