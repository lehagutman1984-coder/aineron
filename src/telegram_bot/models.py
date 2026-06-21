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
    voice_responses = models.BooleanField(default=False, verbose_name='Голосовые ответы')
    web_search = models.BooleanField(default=False, verbose_name='Веб-поиск')
    system_prompt = models.TextField(blank=True, verbose_name='Системный промт')
    streaming = models.BooleanField(default=True, verbose_name='Streaming (edit_message)')

    last_message_at = models.DateTimeField(null=True, blank=True, verbose_name='Последнее сообщение')
    messages_today = models.PositiveIntegerField(default=0, verbose_name='Сообщений сегодня')
    messages_today_date = models.DateField(null=True, blank=True, verbose_name='Дата счётчика')

    class Meta:
        verbose_name = 'Telegram пользователь'
        verbose_name_plural = 'Telegram пользователи'

    def __str__(self):
        return f"@{self.telegram_username or self.telegram_id} → {self.user.email}"


class TelegramChat(models.Model):
    tg_user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='active_chat',
        verbose_name='TG пользователь',
    )
    chat = models.ForeignKey(
        'aitext.Chat',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Чат',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Активный чат бота'
        verbose_name_plural = 'Активные чаты бота'

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
