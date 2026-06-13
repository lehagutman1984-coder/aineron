from django.db import models
from django.conf import settings
from users.models import CustomUser
from django.core.files.storage import default_storage
import uuid
import io


class Category(models.Model):
    """Категория нейросетей (Фото, Видео, Аудио, Учеба, Развлечения)"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Название категории')
    slug = models.SlugField(unique=True, verbose_name='URL')
    icon = models.CharField(max_length=50, default='fas fa-cube', verbose_name='Иконка (FontAwesome)')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class NeuralNetwork(models.Model):
    PROVIDER_CHOICES = [
        ('openrouter', 'laozhang.ai (текст)'),
        ('fal-ai', 'laozhang.ai (изображения/видео)'),
    ]
    """Модель нейросети"""
    name = models.CharField(max_length=100, verbose_name='Название нейросети')
    slug = models.SlugField(unique=True, verbose_name='URL')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='networks', verbose_name='Категория')
    avatar = models.ImageField(upload_to='neural_avatars/', blank=True, null=True, verbose_name='Аватар')
    avatar_url = models.URLField(blank=True, null=True, verbose_name='URL аватара')
    description = models.TextField(blank=True, verbose_name='Краткое описание')
    cost_per_message = models.PositiveIntegerField(default=30, verbose_name='Стоимость за одно сообщение (зв.)')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    model_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Название модели',
        help_text='Например: gpt-4o, claude-sonnet-4-6, deepseek-v3, flux-2-pro'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='По умолчанию',
        help_text='Выберите одну модель, которая будет показываться в шапке по умолчанию'
    )
    has_prompt = models.BooleanField(
        default=False,
        verbose_name='Встроенный промт',
        help_text='Использовать системный промт для этой нейросети'
    )
    prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name='Промт нейросети',
        help_text='Системное сообщение, которое будет отправляться вместе с каждым запросом'
    )

    unlimited = models.BooleanField(
        default=False,
        verbose_name='Безлимит',
        help_text='Если включено, пользователи с указанным тарифом могут отправлять сообщения бесплатно (в пределах дневного лимита)'
    )
    tariffs = models.ManyToManyField(
        'users.Tariff',
        blank=True,
        related_name='unlimited_networks',
        verbose_name='Тарифы для безлимита',
        help_text='Пользователи с выбранными тарифами получают бесплатные сообщения в рамках дневного лимита'
    )
    messages_limit = models.PositiveIntegerField(
        default=0,
        verbose_name='Лимит сообщений в день',
        help_text='Максимальное количество бесплатных сообщений в день для пользователей с указанным тарифом. 0 = без лимита.'
    )

    handle_archive = models.BooleanField(
        default=False,
        verbose_name='Обработка архивов',
        help_text='Поддерживает архивы (.zip, .rar, .7z и т.д.)'
    )
    handle_text_files = models.BooleanField(
        default=False,
        verbose_name='Обработка текстовых файлов',
        help_text='Поддерживает .txt, .pdf, .doc, .docx, .odt и т.д.'
    )
    handle_photo = models.BooleanField(
        default=False,
        verbose_name='Обработка фото',
        help_text='Поддерживает изображения (.jpg, .png, .gif, .webp и т.д.)'
    )
    handle_video = models.BooleanField(
        default=False,
        verbose_name='Обработка видео',
        help_text='Поддерживает видео (.mp4, .avi, .mov и т.д.)'
    )

    # Новые поля для fal.ai
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='openrouter',
        verbose_name='Провайдер'
    )
    config_json = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Конфигурация модели (изображения)',
        help_text='JSON конфигурация для моделей изображений. api_defaults: {size, quality, style, n}. ui_settings, constraints, metadata'
    )

    is_popular = models.BooleanField(
        default=False,
        verbose_name='Популярная модель',
        help_text='Отображать в блоке "Популярные модели" на странице выбора'
    )
    translate_to_english = models.BooleanField(
        default=False,
        verbose_name='Перевод запросов на английский',
        help_text='Если включено, перед отправкой в fal.ai промт пользователя будет переведён на английский (через DeepSeek)'
    )
    seo_title = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='SEO заголовок (title)',
        help_text='Если не указано, будет использовано название нейросети'
    )
    seo_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='SEO описание (description)',
        help_text='Если не указано, будет использовано описание нейросети'
    )
    seo_keywords = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='SEO ключевые слова (keywords)',
        help_text='Ключевые слова через запятую'
    )
    is_direct = models.BooleanField(
        default=False,
        verbose_name='Прямые нейросети',
        help_text='Показывать в футере в разделе "Прямые нейросети"'
    )
    is_custom = models.BooleanField(
        default=False,
        verbose_name='Кастомные модели',
        help_text='Показывать в футере в разделе "Кастомные модели"'
    )
    max_tokens = models.PositiveIntegerField(
        default=0,
        verbose_name='Максимум токенов в ответе',
        help_text='0 = без ограничений'
    )
    max_input_tokens = models.PositiveIntegerField(
        default=0,
        verbose_name='Максимум токенов в запросе пользователя',
        help_text='0 = без ограничений. Обрезает текст сообщения пользователя до указанного количества символов.'
    )
    stars_per_1k_tokens = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
        verbose_name='Звёзд за 1000 токенов (dev-API)',
        help_text='Для токенного биллинга через API-ключи. 0 = авто-расчёт из cost_per_message.'
    )

    class Meta:
        verbose_name = 'Нейросеть'
        verbose_name_plural = 'Нейросети'
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def get_avatar(self):
        if self.avatar and self.avatar.url:
            return self.avatar.url
        if self.avatar_url:
            return self.avatar_url
        return f"https://ui-avatars.com/api/?name={self.name}&background=0a7cff&color=fff&size=64"

class NeuralNetworkDailyUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_network_usage'
    )
    network = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.CASCADE,
        related_name='daily_usage'
    )
    date = models.DateField(auto_now_add=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'network', 'date')
        verbose_name = 'Ежедневное использование нейросети'
        verbose_name_plural = 'Ежедневное использование нейросетей'

    def __str__(self):
        return f"{self.user} - {self.network} - {self.date} - {self.count}"

class Chat(models.Model):
    """Чат пользователя с нейросетью"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats')
    network = models.ForeignKey(NeuralNetwork, on_delete=models.CASCADE, related_name='chats')
    title = models.CharField(max_length=255, blank=True, verbose_name='Название чата')
    settings = models.JSONField(default=dict, blank=True, verbose_name='Настройки генерации для чата')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Чат'
        verbose_name_plural = 'Чаты'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.network.name} - {self.created_at.strftime('%d.%m.%Y')}"

    def get_title(self):
        return self.title or f"{self.network.name} ({self.created_at.strftime('%d.%m.%Y')})"

    def preview_text(self):
        """Возвращает текст для отображения в сайдбаре"""
        last_message = self.messages.order_by('-created_at').first()
        if not last_message:
            return "Нет сообщений"
        if last_message.role == 'assistant' and last_message.status == 'pending':
            return "Печатает..."
        # Для ассистента используем plain_text (без HTML-разметки), для пользователя - content
        if last_message.role == 'assistant' and last_message.plain_text:
            text = last_message.plain_text
        else:
            text = last_message.content
        # Обрезаем длинные тексты
        if len(text) > 30:
            return text[:27] + "..."
        return text


class Message(models.Model):
    """Сообщение в чате"""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        COMPLETED = 'completed', 'Завершено'
        FAILED = 'failed', 'Ошибка'

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'Пользователь'), ('assistant', 'Ассистент')])
    content = models.TextField(blank=True, verbose_name='Содержание')  # может быть пустым для pending
    files = models.JSONField(default=list, blank=True, verbose_name='Файлы')
    tokens_used = models.PositiveIntegerField(default=0, verbose_name='Потрачено токенов')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')
    extracted_content = models.TextField(blank=True, null=True,
                                         verbose_name='Извлеченное содержимое файлов')  # ← новое поле
    settings = models.JSONField(default=dict, blank=True, verbose_name='Настройки генерации')
    created_at = models.DateTimeField(auto_now_add=True)
    plain_text = models.TextField(blank=True, verbose_name='Оригинальный текст без форматирования')

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.chat.user.username} - {self.role} - {self.created_at.strftime('%H:%M')}"



class FileAttachment(models.Model):
    """Прикрепленный файл (изображение, видео, аудио, PDF, архив, текст, код и др.)"""
    SOURCES = [
        ('uploaded', 'Загружено пользователем'),
        ('ai_generated', 'Сгенерировано AI'),
    ]

    MEDIA_TYPES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
        ('pdf', 'PDF документ'),
        ('other', 'Другой файл'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Связь с сообщением
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name='Сообщение'
    )

    # Файл
    filename = models.CharField(max_length=255, verbose_name='Имя файла')
    file_path = models.CharField(max_length=500, verbose_name='Путь к файлу')
    file_size = models.IntegerField(verbose_name='Размер (байты)')
    mime_type = models.CharField(max_length=100, verbose_name='MIME тип')

    # Тип медиа
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES, default='image', verbose_name='Тип файла')

    # Извлеченный текст (для other, pdf, архивов)
    extracted_text = models.TextField(blank=True, null=True, verbose_name='Извлеченный текст')

    # Для изображений
    width = models.IntegerField(null=True, blank=True, verbose_name='Ширина')
    height = models.IntegerField(null=True, blank=True, verbose_name='Высота')

    # Для видео/аудио
    duration = models.IntegerField(null=True, blank=True, verbose_name='Длительность (сек)')
    resolution = models.CharField(max_length=20, blank=True, verbose_name='Разрешение')

    # Метаданные
    source = models.CharField(max_length=20, choices=SOURCES, default='uploaded', verbose_name='Источник')
    model_id = models.CharField(max_length=200, blank=True, verbose_name='ID модели (для сгенерированных)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Прикрепленный файл'
        verbose_name_plural = 'Прикрепленные файлы'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_media_type_display()}: {self.filename}"

    @property
    def file_url(self):
        try:
            return default_storage.url(self.file_path)
        except:
            return ''

    @property
    def is_generated(self):
        return self.source == 'ai_generated'

    @property
    def is_uploaded(self):
        return self.source == 'uploaded'

    @property
    def dimensions(self):
        if self.media_type == 'image' and self.width and self.height:
            return f"{self.width}x{self.height}"
        elif self.media_type == 'video' and self.resolution:
            return self.resolution
        return ""

    def get_file_description(self):
        """Возвращает описание файла для AI"""
        if self.media_type == 'other' and self.extracted_text:
            return self.extracted_text
        elif self.media_type == 'pdf' and self.extracted_text:
            return self.extracted_text
        elif self.media_type == 'image':
            return f"Изображение: {self.filename} ({self.dimensions})"
        elif self.media_type == 'video':
            return f"Видео: {self.filename}"
        elif self.media_type == 'audio':
            return f"Аудио: {self.filename}"
        else:
            return f"Файл: {self.filename} ({self.mime_type})"

    def save_file_info(self, file_obj):
        """Сохраняет дополнительную информацию о файле (размеры, извлечение текста)"""
        try:
            if self.media_type == 'image':
                from PIL import Image
                img_data = file_obj.read()
                file_obj.seek(0)
                img = Image.open(io.BytesIO(img_data))
                self.width, self.height = img.size
                if hasattr(file_obj, 'content_type') and file_obj.content_type:
                    self.mime_type = file_obj.content_type
                elif img.format:
                    self.mime_type = f"image/{img.format.lower()}"
        except Exception as e:
            print(f"Ошибка сохранения информации о файле: {e}")


class GeneratedImage(models.Model):
    MEDIA_TYPES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
    ]
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='generated_images',
        verbose_name='Сообщение'
    )
    image = models.ImageField(
        upload_to='generated_images/%Y/%m/%d/',
        verbose_name='Файл (изображение или видео)'
    )
    prompt = models.TextField(blank=True, verbose_name='Промт (для генерации)')
    width = models.IntegerField(null=True, blank=True, verbose_name='Ширина')
    height = models.IntegerField(null=True, blank=True, verbose_name='Высота')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image', verbose_name='Тип медиа')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Сгенерированное изображение'
        verbose_name_plural = 'Сгенерированные изображения'

    def __str__(self):
        return f"{self.get_media_type_display()} для сообщения {self.message.id}"


class FAQ(models.Model):
    question = models.CharField(max_length=500, verbose_name='Вопрос')
    answer = models.TextField(verbose_name='Ответ')
    show_on_main = models.BooleanField(default=False, verbose_name='Показывать только на главной')
    show_everywhere = models.BooleanField(default=False, verbose_name='Показывать везде')
    neural_network = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Привязать к нейросети'
    )
    order = models.PositiveIntegerField(default=0, verbose_name='Порядок сортировки')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Часто задаваемый вопрос'
        verbose_name_plural = 'Часто задаваемые вопросы'
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.question[:50]
