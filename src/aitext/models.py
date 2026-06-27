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

    # §7.5 Model Arena Elo rating
    elo_rating = models.FloatField(
        default=1500.0,
        verbose_name='Elo-рейтинг (Arena)',
    )
    elo_matches = models.PositiveIntegerField(
        default=0,
        verbose_name='Арена-матчей',
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


class Project(models.Model):
    """Проект — папка для группировки чатов"""
    STATUS_CHOICES = [
        ('active', 'Активный'),
        ('paused', 'Пауза'),
        ('done', 'Завершён'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='projects')
    name = models.CharField(max_length=100, verbose_name='Название')
    system_prompt = models.TextField(blank=True, verbose_name='Системный промт')
    color = models.CharField(max_length=7, default='#0a7cff', verbose_name='Цвет (hex)')
    icon = models.CharField(max_length=30, default='Folder', verbose_name='Иконка (Lucide)')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active', verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True)
    is_public = models.BooleanField(default=False, verbose_name='Публичный')
    public_slug = models.CharField(max_length=22, blank=True, db_index=True, verbose_name='Публичный slug')
    public_show_files = models.BooleanField(default=True, verbose_name='Показывать файлы базы знаний')
    public_show_chats = models.BooleanField(default=False, verbose_name='Показывать чаты')
    public_views = models.PositiveIntegerField(default=0, verbose_name='Просмотры публичного Space')
    yjs_state = models.BinaryField(null=True, blank=True, verbose_name='Yjs документ (бинарный снапшот)')

    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.name}"

    def save(self, *args, **kwargs):
        if self.is_public and not self.public_slug:
            import secrets
            self.public_slug = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)


class ProjectCollaborator(models.Model):
    """Соавтор проекта — пользователь с доступом к чужому проекту."""
    ROLE_CHOICES = [
        ('viewer', 'Наблюдатель'),
        ('editor', 'Редактор'),
    ]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='collaborators')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='project_collaborations'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='viewer')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='project_invitations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('project', 'user')]
        ordering = ['created_at']
        verbose_name = 'Соавтор'
        verbose_name_plural = 'Соавторы'

    def __str__(self):
        return f"{self.user.email} → {self.project.name} ({self.role})"


def project_file_upload_path(instance, filename):
    return f'project_files/{instance.project_id}/{filename}'


class ProjectFile(models.Model):
    """Файл базы знаний проекта"""
    FILE_TYPES = [
        ('pdf', 'PDF'),
        ('doc', 'Документ'),
        ('text', 'Текст'),
        ('code', 'Код'),
        ('other', 'Другой'),
    ]
    STATUS = [
        ('processing', 'Обработка'),
        ('ready', 'Готов'),
        ('error', 'Ошибка'),
    ]
    EMBED_STATUS = [
        ('none', 'Нет'),
        ('pending', 'В очереди'),
        ('done', 'Готово'),
        ('error', 'Ошибка'),
    ]
    SOURCE_CHOICES = [
        ('upload', 'Загружен'),
        ('repo', 'Из репозитория'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='knowledge_files',
        verbose_name='Проект',
    )
    filename = models.CharField(max_length=255, verbose_name='Имя файла')
    file = models.FileField(upload_to=project_file_upload_path, verbose_name='Файл')
    file_size = models.PositiveIntegerField(default=0, verbose_name='Размер (байт)')
    file_type = models.CharField(max_length=10, choices=FILE_TYPES, default='other', verbose_name='Тип файла')
    extracted_text = models.TextField(blank=True, verbose_name='Извлечённый текст')
    status = models.CharField(max_length=15, choices=STATUS, default='processing', verbose_name='Статус')
    enabled = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)
    # Sprint 4.1: векторный RAG
    embed_status = models.CharField(max_length=12, choices=EMBED_STATUS, default='none', verbose_name='Статус эмбеддингов')
    # Sprint 4.2: inbound sync из репозитория
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='upload', verbose_name='Источник')
    connector = models.ForeignKey(
        'ProjectConnector', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='synced_files', verbose_name='Коннектор (для repo-файлов)',
    )
    repo_path = models.CharField(max_length=500, blank=True, verbose_name='Путь в репозитории')
    repo_sha = models.CharField(max_length=64, blank=True, verbose_name='Git blob SHA (для инкрементального синка)')
    # Sprint 6.5 — Two-Level Retrieval
    summary = models.TextField(blank=True, verbose_name='Summary файла (для file-level embeddings)')

    class Meta:
        verbose_name = 'Файл базы знаний'
        verbose_name_plural = 'Файлы базы знаний'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.project.name} / {self.filename}"


class ProjectConnector(models.Model):
    """Git-коннектор проекта (GitHub / Gitea)"""
    TYPES = [('github', 'GitHub'), ('gitea', 'Gitea')]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='connectors',
        verbose_name='Проект',
    )
    connector_type = models.CharField(max_length=10, choices=TYPES, verbose_name='Тип')
    repo_url = models.URLField(verbose_name='URL репозитория')
    owner = models.CharField(max_length=100, verbose_name='Владелец')
    repo = models.CharField(max_length=100, verbose_name='Репозиторий')
    branch = models.CharField(max_length=100, default='main', verbose_name='Ветка')
    access_token_enc = models.TextField(verbose_name='Токен (зашифрован)')
    webhook_secret = models.CharField(max_length=64, blank=True, default='', verbose_name='Webhook secret (HMAC)')
    last_synced_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя синхронизация')
    created_at = models.DateTimeField(auto_now_add=True)
    # Sprint 5.4 — Sync hardening
    auto_sync = models.BooleanField(default=True, verbose_name='Авто-синхронизация')
    sync_status = models.CharField(max_length=10, blank=True, default='',
                                   choices=[('ok', 'OK'), ('error', 'Ошибка'), ('running', 'Идёт')],
                                   verbose_name='Статус последнего синка')
    last_sync_report = models.JSONField(default=dict, blank=True, verbose_name='Отчёт последнего синка')
    last_repo_head_sha = models.CharField(max_length=64, blank=True, verbose_name='Последний HEAD SHA')
    # Sprint 7.2 — Deploy hook
    deploy_webhook_url = models.CharField(max_length=500, blank=True, verbose_name='URL deploy-вебхука')
    deploy_secret_enc = models.TextField(blank=True, verbose_name='Deploy secret (зашифрован Fernet)')
    deploy_status = models.CharField(
        max_length=10, blank=True, default='',
        choices=[('', '—'), ('pending', 'Ожидает'), ('running', 'В процессе'),
                 ('success', 'Успешно'), ('error', 'Ошибка')],
        verbose_name='Статус деплоя',
    )
    last_deploy_at = models.DateTimeField(null=True, blank=True, verbose_name='Последний деплой')
    last_deploy_log = models.TextField(blank=True, verbose_name='Лог последнего деплоя')

    class Meta:
        verbose_name = 'Git-коннектор'
        verbose_name_plural = 'Git-коннекторы'
        unique_together = [('project', 'owner', 'repo')]

    def __str__(self):
        return f"{self.project.name} → {self.owner}/{self.repo}"

    def save(self, *args, **kwargs):
        if not self.webhook_secret:
            import secrets
            self.webhook_secret = secrets.token_hex(32)
        super().save(*args, **kwargs)


class ProjectCommit(models.Model):
    """Предложенный AI-коммит, ожидающий подтверждения пользователя"""
    STATUS = [
        ('pending', 'Ожидает'),
        ('pushed', 'Запушен'),
        ('rejected', 'Отклонён'),
        ('failed', 'Ошибка'),
    ]
    KIND = [
        ('commit', 'Коммит'),
        ('pull_request', 'Pull Request'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='commits',
        verbose_name='Проект',
    )
    connector = models.ForeignKey(
        ProjectConnector, on_delete=models.SET_NULL, null=True, related_name='commits',
        verbose_name='Коннектор',
    )
    commit_message = models.CharField(max_length=500, verbose_name='Сообщение коммита')
    files = models.JSONField(default=list, verbose_name='Файлы')  # [{"path": ..., "content": ...}]
    status = models.CharField(max_length=10, choices=STATUS, default='pending', verbose_name='Статус')
    kind = models.CharField(max_length=14, choices=KIND, default='commit', verbose_name='Тип')
    pr_branch = models.CharField(max_length=200, blank=True, verbose_name='Ветка PR')
    pr_url = models.URLField(blank=True, verbose_name='URL Pull Request')
    error_message = models.TextField(blank=True, verbose_name='Ошибка')
    created_at = models.DateTimeField(auto_now_add=True)
    pushed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата пуша')

    class Meta:
        verbose_name = 'Коммит проекта'
        verbose_name_plural = 'Коммиты проекта'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.project.name} — {self.commit_message[:50]}"


class ProjectFileVersion(models.Model):
    """Sprint 5.4: снапшот версии файла базы знаний.

    Создаётся при каждом обновлении файла через синк (source='repo') или ручной загрузке.
    Ретеншн: последние 10 версий на файл.
    """
    VERSION_LIMIT = 10

    file = models.ForeignKey(
        ProjectFile, on_delete=models.CASCADE, related_name='versions',
        verbose_name='Файл',
    )
    content_snapshot = models.TextField(verbose_name='Содержимое (снапшот)')
    repo_sha = models.CharField(max_length=64, blank=True, verbose_name='Git SHA (для repo-файлов)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Версия файла'
        verbose_name_plural = 'Версии файлов'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.file.filename} @ {self.created_at:%Y-%m-%d %H:%M}"


class ProjectChunk(models.Model):
    """Чанк текста из файла базы знаний с векторным эмбеддингом (Sprint 4.1 — Vector RAG)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chunks')
    file = models.ForeignKey(ProjectFile, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    token_count = models.PositiveIntegerField(default=0)
    # VectorField добавляется миграцией при включённом pgvector (dimensions=1536)
    # Хранится как отдельное поле в БД; здесь описывается без Django-декларации
    # чтобы не ломать SQLite в тестах. Запросы к вектору — через django.db.connection.cursor().

    class Meta:
        verbose_name = 'Чанк файла'
        verbose_name_plural = 'Чанки файлов'
        ordering = ['file', 'chunk_index']
        indexes = [
            models.Index(fields=['project'], name='chunk_project_idx'),
            models.Index(fields=['file'], name='chunk_file_idx'),
        ]

    def __str__(self):
        return f"{self.file.filename}[{self.chunk_index}]"


class KBUsageStat(models.Model):
    """Sprint 5.3: счётчик цитирований файлов базы знаний.

    Инкрементируется в build_project_knowledge_context при PROJECT_KB_METRICS=1.
    """
    file = models.OneToOneField(
        ProjectFile, on_delete=models.CASCADE, related_name='usage_stat',
        verbose_name='Файл',
    )
    hits = models.PositiveIntegerField(default=0, verbose_name='Использований в контексте')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Последнее использование')

    class Meta:
        verbose_name = 'Статистика использования файла'
        verbose_name_plural = 'Статистика использования файлов'

    def __str__(self):
        return f"{self.file.filename}: {self.hits} hits"


class ProjectAuditEntry(models.Model):
    """Sprint 5.5: запись журнала аудита проекта."""
    ACTION_CHOICES = [
        ('chat_message', 'Сообщение в чате'),
        ('file_upload', 'Загрузка файла'),
        ('file_delete', 'Удаление файла'),
        ('commit_push', 'Коммит в репозиторий'),
        ('pr_open', 'Открытие Pull Request'),
        ('member_invite', 'Приглашение участника'),
        ('member_remove', 'Удаление участника'),
        ('published', 'Публикация Space'),
        ('unpublished', 'Снятие с публикации'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='audit_entries',
        verbose_name='Проект',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='project_audit_entries', verbose_name='Участник',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name='Действие')
    target = models.CharField(max_length=500, blank=True, verbose_name='Объект')
    files_used = models.JSONField(default=list, blank=True, verbose_name='Файлы базы знаний в контексте')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Запись аудита'
        verbose_name_plural = 'Журнал аудита'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['project', '-created_at'])]

    def __str__(self):
        actor = self.actor.email if self.actor else 'system'
        return f"{actor} {self.action} в {self.project}"


class Chat(models.Model):
    """Чат пользователя с нейросетью"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chats')
    network = models.ForeignKey(NeuralNetwork, on_delete=models.CASCADE, related_name='chats')
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='chats', verbose_name='Проект',
    )
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
    search_context = models.TextField(blank=True, default='', verbose_name='Результаты веб-поиска')
    kb_sources = models.JSONField(default=list, blank=True, verbose_name='Источники базы знаний')

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

    # Связь с сообщением (null=True для временных загрузок до отправки)
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='attachments',
        null=True,
        blank=True,
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


class PromptTemplate(models.Model):
    CATEGORY_CHOICES = [
        ('code', 'Код'),
        ('translate', 'Перевод'),
        ('analyze', 'Анализ'),
        ('email', 'Письма'),
        ('study', 'Учёба'),
        ('creative', 'Творчество'),
        ('other', 'Другое'),
    ]

    title = models.CharField(max_length=100, verbose_name='Название')
    content = models.TextField(verbose_name='Текст промта')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other', verbose_name='Категория')
    icon = models.CharField(max_length=50, default='FileText', verbose_name='Иконка (Lucide)')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name='prompt_templates',
        verbose_name='Пользователь',
    )
    is_public = models.BooleanField(default=True, verbose_name='Публичный')
    order = models.IntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True)
    # Smart variables: [{name, label, type, options?, default?}]
    variables = models.JSONField(default=list, blank=True, verbose_name='Переменные шаблона')

    class Meta:
        verbose_name = 'Шаблон промта'
        verbose_name_plural = 'Шаблоны промтов'
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.title


class Persona(models.Model):
    """AI persona — a named character with its own system prompt and optional model binding."""
    name = models.CharField(max_length=100, verbose_name='Имя персоны')
    slug = models.SlugField(max_length=120, unique=True, verbose_name='Slug')
    description = models.CharField(max_length=255, blank=True, verbose_name='Описание')
    system_prompt = models.TextField(verbose_name='Системный промт')
    avatar_url = models.URLField(blank=True, verbose_name='URL аватара')
    network = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='personas',
        verbose_name='Модель по умолчанию',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='personas',
        verbose_name='Владелец (null = системная)',
    )
    is_public = models.BooleanField(default=False, verbose_name='Публичная (системная)')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.IntegerField(default=0, verbose_name='Порядок')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI-персона'
        verbose_name_plural = 'AI-персоны'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


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


# ──────────────────────────────────────────────────────────────────────────────
# Persistent Memory
# ──────────────────────────────────────────────────────────────────────────────

class UserMemory(models.Model):
    """Долговременный факт о пользователе. Общий для всех каналов (web, Telegram, Studio)."""

    class Category(models.TextChoices):
        PROFILE    = 'profile',    'Профиль'
        PREFERENCE = 'preference', 'Предпочтения'
        PROJECT    = 'project',    'Проекты'
        FACT       = 'fact',       'Факты'
        SKILL      = 'skill',      'Навыки'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memories',
        verbose_name='Пользователь',
    )
    category = models.CharField(
        max_length=20, choices=Category.choices,
        default=Category.FACT, verbose_name='Категория',
    )
    content = models.TextField(verbose_name='Факт')
    content_key = models.CharField(
        max_length=255, db_index=True, blank=True,
        verbose_name='Ключ дедупликации',
    )
    source = models.CharField(
        max_length=10, default='auto',
        choices=[('auto', 'Авто'), ('user', 'Вручную')],
        verbose_name='Источник',
    )
    source_chat = models.ForeignKey(
        'Chat', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='extracted_memories',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    is_pinned = models.BooleanField(default=False, verbose_name='Закреплён')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Факт о пользователе'
        verbose_name_plural = 'Факты о пользователях'
        ordering = ['-is_pinned', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'content_key'],
                name='unique_user_memory_content_key',
                condition=models.Q(content_key__gt=''),
            )
        ]

    def __str__(self):
        return f"{self.user_id} | {self.category} | {self.content[:60]}"

    def save(self, *args, **kwargs):
        if not self.content_key and self.content:
            from aitext.memory import normalize_fact
            self.content_key = normalize_fact(self.content)
        super().save(*args, **kwargs)


class ChatSummary(models.Model):
    """Сжатое резюме чата. Хранит rolling_summary (текущая сессия) и финальное summary."""

    chat = models.OneToOneField(
        'Chat', on_delete=models.CASCADE, related_name='summary',
        verbose_name='Чат',
    )
    summary_text = models.TextField(verbose_name='Резюме сессии')
    rolling_summary = models.TextField(
        blank=True, default='',
        verbose_name='Сжатое начало текущей сессии',
    )
    message_count = models.PositiveIntegerField(default=0, verbose_name='Кол-во сообщений')
    last_compressed_message_id = models.BigIntegerField(
        null=True, blank=True,
        verbose_name='ID последнего сжатого сообщения',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        verbose_name = 'Резюме чата'
        verbose_name_plural = 'Резюме чатов'

    def __str__(self):
        return f"Summary for chat {self.chat_id}"


class UsageEvent(models.Model):
    """Унифицированное событие использования платформы — веб + бот в одной схеме."""

    class Channel(models.TextChoices):
        WEB = 'web', 'Веб'
        BOT = 'bot', 'Telegram-бот'
        API = 'api', 'API'

    class EventType(models.TextChoices):
        MESSAGE = 'message', 'Сообщение (текст)'
        IMAGE = 'image', 'Генерация изображения'
        VIDEO = 'video', 'Генерация видео'
        PAYMENT = 'payment', 'Оплата'
        INLINE = 'inline', 'Inline-запрос'
        SEARCH = 'search', 'Веб-поиск'
        VOICE = 'voice', 'Голос (ASR/TTS)'
        EXPORT = 'export', 'Экспорт чата'
        IMG2IMG = 'img2img', 'Image-to-Image'
        ERROR = 'error', 'Ошибка'
        ONBOARDING = 'onboarding', 'Онбординг'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usage_events',
        verbose_name='Пользователь',
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.WEB,
        verbose_name='Канал',
    )
    event_type = models.CharField(
        max_length=20, choices=EventType.choices,
        verbose_name='Тип события',
    )
    network = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Модель',
    )
    cost = models.IntegerField(default=0, verbose_name='Стоимость (зв.)')
    meta = models.JSONField(default=dict, blank=True, verbose_name='Доп. данные')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время')

    class Meta:
        verbose_name = 'Событие использования'
        verbose_name_plural = 'События использования'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['channel', 'event_type', 'created_at'], name='usage_event_channel_idx'),
            models.Index(fields=['user', 'created_at'], name='usage_event_user_idx'),
            models.Index(fields=['created_at'], name='usage_event_ts_idx'),
        ]

    def __str__(self):
        return f"{self.channel}/{self.event_type} — {self.created_at.strftime('%d.%m %H:%M')}"


class PromptABTest(models.Model):
    """
    A/B test for system prompts on a NeuralNetwork.
    When active, 50% of requests get prompt_a and 50% get prompt_b as system message.
    The chosen variant ('a' or 'b') is recorded in UsageEvent.meta['ab_test'].
    """
    name = models.CharField(max_length=100, verbose_name='Название теста')
    network = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.CASCADE,
        related_name='ab_tests',
        verbose_name='Нейросеть',
    )
    prompt_a = models.TextField(verbose_name='Вариант A (контроль)')
    prompt_b = models.TextField(verbose_name='Вариант B (тест)')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    # Auto-tracked counters (updated by post_save or analytics)
    sends_a = models.PositiveIntegerField(default=0)
    sends_b = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'A/B тест промтов'
        verbose_name_plural = 'A/B тесты промтов'
        ordering = ['-created_at']

    def __str__(self):
        status = 'active' if self.is_active else 'off'
        return f"{self.name} [{self.network.name}] ({status})"

    def pick_variant(self) -> str:
        """Return 'a' or 'b' with 50/50 probability."""
        import random
        return random.choice(['a', 'b'])

    def get_prompt(self, variant: str) -> str:
        return self.prompt_a if variant == 'a' else self.prompt_b


# ──────────────────────────────────────────────────────────────────────────────
# §7.5 Model Arena — Elo rating matches
# ──────────────────────────────────────────────────────────────────────────────

class ModelMatch(models.Model):
    """Arena match: user chose winner over loser; drives Elo updates."""
    winner = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.CASCADE,
        related_name='arena_wins',
        verbose_name='Победитель',
    )
    loser = models.ForeignKey(
        'NeuralNetwork',
        on_delete=models.CASCADE,
        related_name='arena_losses',
        verbose_name='Проигравший',
    )
    prompt_snippet = models.CharField(max_length=200, blank=True, verbose_name='Промт (фрагмент)')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='arena_matches',
        verbose_name='Пользователь',
    )
    compare_chat_ids = models.JSONField(default=list, verbose_name='Chat IDs сравнения (anti-abuse)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Арена — матч'
        verbose_name_plural = 'Арена — матчи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['winner'], name='arena_winner_idx'),
            models.Index(fields=['loser'], name='arena_loser_idx'),
        ]

    def __str__(self):
        return f'{self.winner.name} > {self.loser.name} ({self.created_at.date()})'


class ModerationLog(models.Model):
    ACTION_ALLOWED = 'allowed'
    ACTION_BLOCKED = 'blocked'
    ACTION_CHOICES = [(ACTION_ALLOWED, 'Разрешено'), (ACTION_BLOCKED, 'Заблокировано')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='moderation_logs')
    message = models.ForeignKey('Message', null=True, blank=True, on_delete=models.SET_NULL)
    input_excerpt = models.CharField(max_length=200)
    flagged = models.BooleanField(default=False)
    categories = models.JSONField(default=dict)
    scores = models.JSONField(default=dict)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default=ACTION_ALLOWED)
    source = models.CharField(max_length=20, default='web_chat')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Лог модерации'
        verbose_name_plural = 'Логи модерации'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['flagged', 'created_at'], name='modlog_flagged_idx')]

    def __str__(self):
        return f'{self.action} | {self.source} | {self.created_at.date()}'
