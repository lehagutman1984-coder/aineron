import hashlib
import secrets
from django.db import models
from django.conf import settings


class APIKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name='Пользователь',
    )
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='api_keys',
        verbose_name='Организация',
    )
    name = models.CharField(max_length=100, verbose_name='Название ключа')
    key_prefix = models.CharField(max_length=8, verbose_name='Префикс (для отображения)', db_index=True)
    hashed_key = models.CharField(max_length=64, unique=True, verbose_name='Хеш ключа')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name='Последнее использование')
    scopes = models.JSONField(default=list, blank=True, verbose_name='Разрешения')

    class Meta:
        verbose_name = 'API-ключ'
        verbose_name_plural = 'API-ключи'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} / {self.name} (ak_{self.key_prefix}...)'

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def generate(cls, user, name: str) -> tuple['APIKey', str]:
        """Создаёт новый ключ. Возвращает (instance, plaintext). Plaintext показывается один раз."""
        raw = 'ak_' + secrets.token_urlsafe(32)
        prefix = raw[3:11]  # 8 символов после ak_
        hashed = cls.hash_key(raw)
        instance = cls.objects.create(
            user=user,
            name=name,
            key_prefix=prefix,
            hashed_key=hashed,
        )
        return instance, raw

    @classmethod
    def authenticate(cls, raw_key: str):
        """Возвращает APIKey или None."""
        if not raw_key.startswith('ak_'):
            return None
        prefix = raw_key[3:11]
        hashed = cls.hash_key(raw_key)
        try:
            return cls.objects.select_related('user').get(
                key_prefix=prefix,
                hashed_key=hashed,
                is_active=True,
            )
        except cls.DoesNotExist:
            return None


class TokenUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='token_usages',
        verbose_name='Пользователь',
    )
    network = models.ForeignKey(
        'aitext.NeuralNetwork',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='token_usages',
        verbose_name='Нейросеть',
    )
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='token_usages',
        verbose_name='API-ключ',
    )
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='token_usages',
        verbose_name='Организация',
    )
    prompt_tokens = models.PositiveIntegerField(default=0, verbose_name='Токены запроса')
    completion_tokens = models.PositiveIntegerField(default=0, verbose_name='Токены ответа')
    total_tokens = models.PositiveIntegerField(default=0, verbose_name='Всего токенов')
    stars_charged = models.PositiveIntegerField(default=0, verbose_name='Списано звёзд')
    request_id = models.CharField(max_length=64, blank=True, verbose_name='ID запроса')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время запроса', db_index=True)

    class Meta:
        verbose_name = 'Использование токенов'
        verbose_name_plural = 'Использование токенов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.total_tokens} токенов — {self.created_at.strftime("%d.%m.%Y %H:%M")}'
