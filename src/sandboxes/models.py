import uuid

from django.conf import settings
from django.db import models


class SandboxSession(models.Model):
    """Сессия публичного Sandbox API (/api/v1/sandboxes/).

    Durable-источник истины для биллинга и истории. Оперативное состояние VM
    живёт в Redis preview-service; здесь — деньги, владелец и жизненный цикл.
    Наружу id отдаётся с префиксом sbx_ (см. public_id).
    """

    class State(models.TextChoices):
        STARTING = 'starting', 'Запускается'
        RUNNING = 'running', 'Работает'
        STOPPED = 'stopped', 'Остановлена'
        EXPIRED = 'expired', 'Истекла'
        FAILED = 'failed', 'Ошибка'

    class Template(models.TextChoices):
        BASE = 'base', 'Base (Node 20 + Python 3.11)'
        PYTHON = 'python', 'Python'
        NODEJS = 'nodejs', 'Node.js'
        NEXTJS = 'nextjs', 'Next.js'
        DJANGO = 'django', 'Django'

    class Size(models.TextChoices):
        SMALL = 'small', 'Small (1 vCPU / 1 GiB)'
        STANDARD = 'standard', 'Standard (2 vCPU / 2 GiB)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sandbox_sessions',
        verbose_name='Пользователь',
    )
    api_key = models.ForeignKey(
        'api.APIKey',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sandbox_sessions',
        verbose_name='API-ключ',
    )
    template = models.CharField(max_length=20, choices=Template.choices, default=Template.BASE, verbose_name='Шаблон')
    size = models.CharField(max_length=20, choices=Size.choices, default=Size.STANDARD, verbose_name='Размер')
    state = models.CharField(max_length=20, choices=State.choices, default=State.STARTING, db_index=True, verbose_name='Состояние')
    public_host = models.CharField(max_length=255, blank=True, verbose_name='Публичный хост')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Запущена')
    stopped_at = models.DateTimeField(null=True, blank=True, verbose_name='Остановлена')
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name='Истекает')
    ttl_seconds = models.PositiveIntegerField(default=300, verbose_name='TTL, сек')
    reserved_kopecks = models.BigIntegerField(default=0, verbose_name='Резерв, коп.')
    charged_kopecks = models.BigIntegerField(default=0, verbose_name='Списано, коп.')
    exec_count = models.PositiveIntegerField(default=0, verbose_name='Число exec')
    abuse_flagged = models.BooleanField(default=False, verbose_name='Флаг abuse')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='Метаданные клиента')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Sandbox-сессия'
        verbose_name_plural = 'Sandbox-сессии'
        ordering = ['-created_at']

    ACTIVE_STATES = (State.STARTING, State.RUNNING)

    @property
    def public_id(self) -> str:
        return f'sbx_{self.id.hex}'

    @staticmethod
    def parse_public_id(public_id: str):
        """sbx_<32hex> → UUID | None."""
        if not public_id.startswith('sbx_'):
            return None
        try:
            return uuid.UUID(public_id[4:])
        except (ValueError, AttributeError):
            return None

    def __str__(self):
        return f'{self.public_id} — {self.user} — {self.state}'
