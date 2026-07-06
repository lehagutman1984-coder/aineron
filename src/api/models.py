import hashlib
import hmac
import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone


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
    def generate(cls, user, name: str, scopes: list | None = None) -> tuple['APIKey', str]:
        """Создаёт новый ключ. Возвращает (instance, plaintext). Plaintext показывается один раз."""
        raw = 'ak_' + secrets.token_urlsafe(32)
        prefix = raw[3:11]  # 8 символов после ak_
        hashed = cls.hash_key(raw)
        instance = cls.objects.create(
            user=user,
            name=name,
            key_prefix=prefix,
            hashed_key=hashed,
            scopes=scopes or [],
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
    stars_charged = models.PositiveIntegerField(default=0, verbose_name='Списано звёзд (legacy)')
    cost_kopecks = models.BigIntegerField(default=0, verbose_name='Списано, копейки')
    request_id = models.CharField(max_length=64, blank=True, verbose_name='ID запроса')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время запроса', db_index=True)

    class Meta:
        verbose_name = 'Использование токенов'
        verbose_name_plural = 'Использование токенов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} — {self.total_tokens} токенов — {self.created_at.strftime("%d.%m.%Y %H:%M")}'


# ============ Batch API ============

class BatchJob(models.Model):
    class Status(models.TextChoices):
        VALIDATING = 'validating', 'Валидация'
        IN_PROGRESS = 'in_progress', 'В обработке'
        COMPLETED = 'completed', 'Завершён'
        FAILED = 'failed', 'Ошибка'
        CANCELLED = 'cancelled', 'Отменён'
        EXPIRED = 'expired', 'Истёк'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='batch_jobs',
        verbose_name='Пользователь',
    )
    api_key = models.ForeignKey(
        APIKey,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='API-ключ',
    )
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Организация',
    )
    endpoint = models.CharField(max_length=100, default='/v1/chat/completions', verbose_name='Эндпоинт')
    completion_window = models.CharField(max_length=20, default='24h', verbose_name='Окно завершения')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.VALIDATING, verbose_name='Статус', db_index=True)
    request_counts_total = models.PositiveIntegerField(default=0, verbose_name='Всего запросов')
    request_counts_completed = models.PositiveIntegerField(default=0, verbose_name='Выполнено')
    request_counts_failed = models.PositiveIntegerField(default=0, verbose_name='Ошибок')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Метаданные')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан', db_index=True)
    in_progress_at = models.DateTimeField(null=True, blank=True, verbose_name='Начат')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершён')
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name='Отменён')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Истекает')

    class Meta:
        verbose_name = 'Пакетное задание'
        verbose_name_plural = 'Пакетные задания'
        ordering = ['-created_at']

    def __str__(self):
        return f'Batch {self.pk} ({self.status}) — {self.user.email}'


class BatchJobItem(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        IN_PROGRESS = 'in_progress', 'Обрабатывается'
        COMPLETED = 'completed', 'Выполнен'
        FAILED = 'failed', 'Ошибка'

    job = models.ForeignKey(
        BatchJob,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Задание',
    )
    custom_id = models.CharField(max_length=64, blank=True, verbose_name='ID запроса (custom_id)')
    method = models.CharField(max_length=10, default='POST', verbose_name='HTTP метод')
    url = models.CharField(max_length=200, default='/v1/chat/completions', verbose_name='URL')
    body = models.JSONField(default=dict, verbose_name='Тело запроса')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Статус', db_index=True)
    response_body = models.JSONField(null=True, blank=True, verbose_name='Ответ')
    error_message = models.TextField(blank=True, verbose_name='Сообщение об ошибке')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершён')

    class Meta:
        verbose_name = 'Запрос в пакете'
        verbose_name_plural = 'Запросы в пакете'
        ordering = ['created_at']

    def __str__(self):
        return f'Item {self.custom_id or self.pk} ({self.status})'


# ============ Webhooks ============

class Webhook(models.Model):
    EVENTS = [
        ('batch.completed', 'Пакет завершён'),
        ('batch.failed', 'Пакет не выполнен'),
        ('payment.succeeded', 'Платёж прошёл'),
        ('generation.completed', 'Генерация завершена'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='webhooks',
        verbose_name='Пользователь',
    )
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Организация',
    )
    url = models.URLField(verbose_name='URL')
    events = models.JSONField(default=list, verbose_name='События')
    secret = models.CharField(max_length=64, verbose_name='Секрет подписи', editable=False)
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    last_triggered_at = models.DateTimeField(null=True, blank=True, verbose_name='Последний вызов')

    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = secrets.token_hex(32)
        super().save(*args, **kwargs)

    def sign_payload(self, payload: bytes) -> str:
        return hmac.new(self.secret.encode(), payload, hashlib.sha256).hexdigest()

    def __str__(self):
        return f'{self.user.email} → {self.url}'


# ============ Audit Log ============

class AuditLog(models.Model):
    class Action(models.TextChoices):
        KEY_CREATED = 'key.created', 'Ключ создан'
        KEY_DELETED = 'key.deleted', 'Ключ удалён'
        ORG_CREATED = 'org.created', 'Организация создана'
        ORG_UPDATED = 'org.updated', 'Организация обновлена'
        MEMBER_ADDED = 'member.added', 'Участник добавлен'
        MEMBER_REMOVED = 'member.removed', 'Участник удалён'
        INVITE_SENT = 'invite.sent', 'Приглашение отправлено'
        WEBHOOK_CREATED = 'webhook.created', 'Webhook создан'
        WEBHOOK_DELETED = 'webhook.deleted', 'Webhook удалён'
        BATCH_CREATED = 'batch.created', 'Пакет создан'
        BATCH_CANCELLED = 'batch.cancelled', 'Пакет отменён'
        SANDBOX_CREATED = 'sandbox.created', 'Песочница создана'
        SANDBOX_DELETED = 'sandbox.deleted', 'Песочница остановлена'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='Пользователь',
    )
    organization = models.ForeignKey(
        'teams.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='Организация',
    )
    action = models.CharField(max_length=50, choices=Action.choices, verbose_name='Действие', db_index=True)
    resource_type = models.CharField(max_length=50, blank=True, verbose_name='Тип ресурса')
    resource_id = models.CharField(max_length=64, blank=True, verbose_name='ID ресурса')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Детали')
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP-адрес')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время', db_index=True)

    class Meta:
        verbose_name = 'Запись аудита'
        verbose_name_plural = 'Журнал аудита'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} — {self.user} — {self.created_at.strftime("%d.%m.%Y %H:%M")}'

    @classmethod
    def log(cls, user, action, resource_type='', resource_id='', metadata=None, ip_address=None, organization=None):
        return cls.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            metadata=metadata or {},
            ip_address=ip_address,
            organization=organization,
        )
