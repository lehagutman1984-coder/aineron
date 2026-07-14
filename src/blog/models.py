from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from aitext.models import NeuralNetwork

User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Название')
    slug = models.SlugField(unique=True, verbose_name='URL')
    description = models.TextField(blank=True, verbose_name='Описание')
    created_at = models.DateTimeField(auto_now_add=True)
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='SEO заголовок (title)',
        help_text='Если не указано, будет использовано название категории'
    )
    seo_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='SEO описание (description)',
        help_text='Если не указано, будет использовано описание категории'
    )
    seo_keywords = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='SEO ключевые слова (keywords)',
        help_text='Ключевые слова через запятую'
    )

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f'/blog/category/{self.slug}/'


class Post(models.Model):
    LANGUAGE_CHOICES = [
        ('ru', 'Русский'),
        ('en', 'English'),
        ('fa', 'Persian'),
        ('tr', 'Turkish'),
        ('id', 'Indonesian'),
        ('ar', 'Arabic'),
    ]

    title = models.CharField(max_length=200, verbose_name='Заголовок')
    slug = models.SlugField(unique=True, verbose_name='URL')
    language = models.CharField(
        max_length=8,
        choices=LANGUAGE_CHOICES,
        default='ru',
        db_index=True,
        verbose_name='Язык',
        help_text='Статьи под разные рынки — самостоятельный контент, не перевод одного источника (GLOBAL_EXPANSION_PLAN.md §4.3)'
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='posts',
                                 verbose_name='Категория')
    preview_image = models.ImageField(upload_to='blog/previews/', blank=True, null=True,
                                      verbose_name='Превью (изображение)')
    preview_text = models.TextField(max_length=300, verbose_name='Краткое описание')
    content = models.TextField(verbose_name='Полный текст')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Автор')
    published_at = models.DateTimeField(default=timezone.now, verbose_name='Дата публикации')
    is_published = models.BooleanField(default=True, verbose_name='Опубликовано')
    show_in_notification = models.BooleanField(default=False, verbose_name='Показывать в уведомлении')
    show_on_main = models.BooleanField(default=False, verbose_name='Добавить на главную')
    views_count = models.PositiveIntegerField(default=0, verbose_name='Количество просмотров')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    neural_networks = models.ManyToManyField(
        NeuralNetwork,
        blank=True,
        related_name='related_posts',
        verbose_name='Связанные нейросети'
    )
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='SEO заголовок (title)',
        help_text='Если не указано, будет использовано название статьи'
    )
    seo_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='SEO описание (description)',
        help_text='Если не указано, будет использован preview_text статьи'
    )
    seo_keywords = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='SEO ключевые слова (keywords)',
        help_text='Ключевые слова через запятую'
    )
    faq_items = models.JSONField(
        default=list,
        blank=True,
        verbose_name='FAQ (для FAQPage schema)',
        help_text='Список {"question": ..., "answer": ...} для структурированных данных'
    )

    class Meta:
        verbose_name = 'Статья'
        verbose_name_plural = 'Статьи'
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f'/blog/{self.slug}/'