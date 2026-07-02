from django.db import models
from django.utils import timezone
from datetime import timedelta
import secrets


class TelegramUser(models.Model):
    user = models.OneToOneField(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='telegram',
        verbose_name='Пользователь',
    )
    telegram_id = models.BigIntegerField(unique=True, verbose_name='Telegram ID')
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name='Username')
    telegram_first_name = models.CharField(max_length=100, blank=True, verbose_name='Имя')
    linked_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата привязки')

    default_network = models.ForeignKey(
        'aitext.NeuralNetwork',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_users_text',
        verbose_name='Текстовая модель по умолчанию',
    )
    default_image_network = models.ForeignKey(
        'aitext.NeuralNetwork',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_users_image',
        verbose_name='Image-модель по умолчанию',
    )
    default_video_network = models.ForeignKey(
        'aitext.NeuralNetwork',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_users_video',
        verbose_name='Дефолтная видео модель',
    )
    active_project = models.ForeignKey(
        'aitext.Project',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_users',
        verbose_name='Активный проект',
    )
    voice_responses = models.BooleanField(default=False, verbose_name='Голосовые ответы')
    web_search = models.BooleanField(default=False, verbose_name='Веб-поиск')
    system_prompt = models.TextField(blank=True, verbose_name='Системный промт')
    streaming = models.BooleanField(default=True, verbose_name='Streaming (edit_message)')

    # Daily digest settings
    digest_enabled = models.BooleanField(default=False, verbose_name='Дайджест включён')
    digest_hour = models.SmallIntegerField(default=9, verbose_name='Час дайджеста (МСК)')
    digest_minute = models.SmallIntegerField(default=0, verbose_name='Минута дайджеста (МСК)')

    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='Последнее сообщение')
    messages_today = models.PositiveIntegerField(default=0, verbose_name='Сообщений сегодня')
    messages_today_date = models.DateField(null=True, blank=True, verbose_name='Дата счётчика')

    class Meta:
        verbose_name = 'Telegram пользователь'
        verbose_name_plural = 'Telegram пользователи'

    def __str__(self):
        return f"@{self.telegram_username or self.telegram_id} → {self.user.email}"


class TelegramChat(models.Model):
    tg_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='telegram_chats',
        verbose_name='TG пользователь',
    )
    chat = models.ForeignKey(
        'aitext.Chat',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Чат',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активный')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Чат бота'
        verbose_name_plural = 'Чаты бота'
        indexes = [
            models.Index(fields=['tg_user', 'is_active'], name='tg_chat_active_idx'),
        ]

    def __str__(self):
        return f"{self.tg_user} — чат #{self.chat_id}"


class TelegramLinkToken(models.Model):
    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='telegram_link_tokens',
        verbose_name='Пользователь',
    )
    token = models.CharField(max_length=64, unique=True, verbose_name='Токен')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name='Истекает')
    used = models.BooleanField(default=False, verbose_name='Использован')

    class Meta:
        verbose_name = 'Токен привязки Telegram'
        verbose_name_plural = 'Токены привязки Telegram'

    def __str__(self):
        return f"{self.user.email} — {'использован' if self.used else 'активен'}"

    @classmethod
    def create_for_user(cls, user, ttl_minutes=15):
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=ttl_minutes)
        return cls.objects.create(user=user, token=token, expires_at=expires_at)

    @property
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()


class TelegramEvent(models.Model):
    class EventType(models.TextChoices):
        MESSAGE = 'message', 'Сообщение'
        IMAGE = 'image', 'Изображение'
        VIDEO = 'video', 'Видео'
        PAYMENT = 'payment', 'Оплата'
        INLINE = 'inline', 'Inline-запрос'
        ERROR = 'error', 'Ошибка'
        ONBOARDING = 'onboarding', 'Онбординг'

    telegram_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='events',
        verbose_name='TG пользователь',
    )
    event_type = models.CharField(
        max_length=20, choices=EventType.choices, verbose_name='Тип события',
    )
    network = models.ForeignKey(
        'aitext.NeuralNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Модель',
    )
    cost = models.IntegerField(default=0, verbose_name='Стоимость (зв., legacy)')
    cost_kopecks = models.BigIntegerField(default=0, verbose_name='Стоимость, копейки')
    meta = models.JSONField(default=dict, blank=True, verbose_name='Доп. данные')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время')

    class Meta:
        verbose_name = 'Событие бота'
        verbose_name_plural = 'События бота'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at'], name='tg_event_type_idx'),
            models.Index(fields=['telegram_user', 'created_at'], name='tg_event_user_idx'),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.telegram_user}'


class TelegramGroup(models.Model):
    """Telegram-группа или канал, подключённый к организации для оргбиллинга."""
    group_id = models.BigIntegerField(unique=True, verbose_name='Telegram group/channel ID')
    group_title = models.CharField(max_length=255, blank=True, verbose_name='Название группы')
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.CASCADE,
        related_name='telegram_groups',
        verbose_name='Организация',
    )
    registered_by = models.ForeignKey(
        TelegramUser,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registered_groups',
        verbose_name='Кто зарегистрировал',
    )
    enabled = models.BooleanField(default=True, verbose_name='Активна')
    system_prompt = models.TextField(blank=True, verbose_name='Системный промт группы')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')

    class Meta:
        verbose_name = 'Telegram-группа'
        verbose_name_plural = 'Telegram-группы'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.group_title} ({self.group_id}) → {self.organization.name}'


class TelegramGroupChat(models.Model):
    """Per-user chat isolation inside a registered Telegram group.

    Each unique (group, from_user_id, network) gets its own Chat so that
    conversation history is never shared across participants.
    """
    group = models.ForeignKey(
        TelegramGroup,
        on_delete=models.CASCADE,
        related_name='group_chats',
        verbose_name='Telegram-группа',
    )
    from_user_id = models.BigIntegerField(verbose_name='Telegram ID участника')
    network = models.ForeignKey(
        'aitext.NeuralNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Модель',
    )
    chat = models.ForeignKey(
        'aitext.Chat',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='telegram_group_chats',
        verbose_name='Чат',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Чат группы (участник)'
        verbose_name_plural = 'Чаты группы (участники)'
        unique_together = [('group', 'from_user_id', 'network')]
        indexes = [
            models.Index(fields=['group', 'from_user_id'], name='tg_grpchat_user_idx'),
        ]

    def __str__(self):
        return f'{self.group.group_title} / user {self.from_user_id}'


class Reminder(models.Model):
    """Scheduled reminder — text delivered to user at a given time via bot."""
    tg_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='reminders',
        verbose_name='TG пользователь',
    )
    text = models.TextField(verbose_name='Текст напоминания')
    remind_at = models.DateTimeField(verbose_name='Когда напомнить (UTC)')
    is_sent = models.BooleanField(default=False, verbose_name='Отправлено')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Напоминание'
        verbose_name_plural = 'Напоминания'
        ordering = ['remind_at']
        indexes = [
            models.Index(fields=['is_sent', 'remind_at'], name='reminder_unsent_idx'),
        ]

    def __str__(self):
        return f'{self.tg_user} — {self.remind_at}'


class PollSession(models.Model):
    """AI-powered poll: custom question → Telegram native poll → AI summary on close."""
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активный'
        CLOSED = 'closed', 'Закрыт'

    tg_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='poll_sessions',
        verbose_name='Создатель опроса',
    )
    question = models.TextField(verbose_name='Вопрос')
    options = models.JSONField(default=list, verbose_name='Варианты ответа')
    vote_counts = models.JSONField(default=list, verbose_name='Голоса по вариантам')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    ai_summary = models.TextField(blank=True, verbose_name='AI-анализ результатов')
    telegram_poll_id = models.CharField(max_length=100, blank=True, verbose_name='ID опроса в TG')
    chat_id = models.BigIntegerField(verbose_name='Chat ID')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI-опрос'
        verbose_name_plural = 'AI-опросы'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tg_user} — {self.question[:50]}'
