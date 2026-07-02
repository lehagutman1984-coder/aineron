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
        # TELEGRAM_SUPREMACY_PLAN §4 — метрики супер-фич
        TASK_RUN = 'task_run', 'AI-задача (запуск)'
        RESEARCH = 'research', 'Deep Research'
        BUSINESS_REPLY = 'business_reply', 'AI-секретарь (ответ)'
        SUBSCRIPTION = 'subscription', 'Stars-подписка'
        AFFILIATE_JOIN = 'affiliate_join', 'Партнёрская регистрация'
        AGENT = 'agent', 'Agent Mode (запуск)'

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


class AITask(models.Model):
    """S2 — проактивная AI-задача по расписанию (TELEGRAM_SUPREMACY_PLAN).

    Обобщает Reminder (напоминание = задача без LLM) и digest (дайджест =
    встроенная задача). Задачи общие для веба и бота, поэтому FK на CustomUser.
    Времена run_time/weekday задаются по Москве, next_run_at хранится в UTC.
    """
    class Schedule(models.TextChoices):
        ONCE = 'once', 'Один раз'
        DAILY = 'daily', 'Ежедневно'
        WEEKLY = 'weekly', 'Еженедельно'
        CRON = 'cron', 'Cron-выражение'

    class CreatedFrom(models.TextChoices):
        BOT = 'bot', 'Telegram-бот'
        WEB = 'web', 'Веб'

    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='ai_tasks',
        verbose_name='Пользователь',
    )
    title = models.CharField(max_length=120, blank=True, verbose_name='Название')
    prompt = models.TextField(verbose_name='Промт задачи')
    schedule_type = models.CharField(
        max_length=10, choices=Schedule.choices, default=Schedule.DAILY,
        verbose_name='Тип расписания',
    )
    run_time = models.TimeField(null=True, blank=True, verbose_name='Время запуска (МСК)')
    weekday = models.SmallIntegerField(
        null=True, blank=True, verbose_name='День недели (0=пн, для weekly)',
    )
    cron = models.CharField(max_length=120, blank=True, verbose_name='Cron-выражение (5 полей)')
    next_run_at = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name='Следующий запуск (UTC)',
    )
    use_web_search = models.BooleanField(default=True, verbose_name='Веб-поиск (Tavily)')
    network = models.ForeignKey(
        'aitext.NeuralNetwork',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ai_tasks',
        verbose_name='Модель (пусто = самая дешёвая текстовая)',
    )
    deliver_chat_id = models.BigIntegerField(
        null=True, blank=True,
        verbose_name='Чат доставки (пусто = личка пользователя)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    paused_reason = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Причина паузы (balance/user/max_runs)',
    )
    last_run_at = models.DateTimeField(null=True, blank=True, verbose_name='Последний запуск')
    runs_count = models.PositiveIntegerField(default=0, verbose_name='Запусков всего')
    max_runs = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Максимум запусков (пусто = без лимита)',
    )
    created_from = models.CharField(
        max_length=10, choices=CreatedFrom.choices, default=CreatedFrom.BOT,
        verbose_name='Создана из',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'AI-задача'
        verbose_name_plural = 'AI-задачи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'next_run_at'], name='aitask_due_idx'),
            models.Index(fields=['user', 'is_active'], name='aitask_user_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} — {self.title or self.prompt[:40]}'

    MOSCOW_TZ = 'Europe/Moscow'

    def compute_next_run(self, after=None):
        """Следующий запуск в UTC после момента `after` (по умолчанию — сейчас).

        once → None после первого запуска (вызывающий код деактивирует задачу).
        """
        import pytz
        from datetime import datetime, timedelta

        moscow = pytz.timezone(self.MOSCOW_TZ)
        after = after or timezone.now()
        after_msk = after.astimezone(moscow)

        if self.schedule_type == self.Schedule.ONCE:
            # Разовая задача: next_run_at задаётся при создании и не пересчитывается
            return None

        if self.schedule_type == self.Schedule.CRON and self.cron:
            try:
                from celery.schedules import crontab
                fields = self.cron.split()
                if len(fields) == 5:
                    entry = crontab(
                        minute=fields[0], hour=fields[1], day_of_month=fields[2],
                        month_of_year=fields[3], day_of_week=fields[4],
                        nowfun=lambda: after_msk,
                    )
                    delta = entry.remaining_estimate(after_msk)
                    if delta is not None:
                        next_msk = after_msk + max(delta, timedelta(minutes=1))
                        return next_msk.astimezone(pytz.UTC)
            except Exception:
                pass
            return None

        run_time = self.run_time
        if run_time is None:
            return None

        candidate = moscow.localize(datetime.combine(after_msk.date(), run_time))
        if self.schedule_type == self.Schedule.DAILY:
            if candidate <= after_msk:
                candidate += timedelta(days=1)
            return candidate.astimezone(pytz.UTC)

        if self.schedule_type == self.Schedule.WEEKLY:
            target = self.weekday if self.weekday is not None else 0
            days_ahead = (target - candidate.weekday()) % 7
            candidate += timedelta(days=days_ahead)
            if candidate <= after_msk:
                candidate += timedelta(days=7)
            return candidate.astimezone(pytz.UTC)

        return None

    def schedule_human(self) -> str:
        """Человекочитаемое расписание для карточек."""
        t = self.run_time.strftime('%H:%M') if self.run_time else '—'
        if self.schedule_type == self.Schedule.ONCE:
            if self.next_run_at:
                import pytz
                msk = self.next_run_at.astimezone(pytz.timezone(self.MOSCOW_TZ))
                return f'один раз, {msk.strftime("%d.%m %H:%M")} МСК'
            return 'один раз'
        if self.schedule_type == self.Schedule.DAILY:
            return f'ежедневно в {t} МСК'
        if self.schedule_type == self.Schedule.WEEKLY:
            days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
            d = days[self.weekday] if self.weekday is not None and 0 <= self.weekday <= 6 else '?'
            return f'еженедельно ({d}) в {t} МСК'
        return f'cron: {self.cron}'


class StarsSubscription(models.Model):
    """S4 — подписка на тариф через Telegram Stars (Bot API 8.0).

    Продление приходит successful_payment с is_recurring=True; начисление
    идемпотентно по telegram_payment_charge_id (механизм BalanceTransaction).
    Связка с UserSubscription — через activate_paid_tariff (invoice_id=charge_id).
    """
    tg_user = models.OneToOneField(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='stars_subscription',
        verbose_name='TG пользователь',
    )
    tariff = models.ForeignKey(
        'users.Tariff',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Тариф',
    )
    telegram_charge_id = models.CharField(
        max_length=128, blank=True,
        verbose_name='Последний telegram_payment_charge_id',
    )
    xtr_amount = models.PositiveIntegerField(default=0, verbose_name='Цена, XTR/мес')
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name='Оплачено до')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Stars-подписка'
        verbose_name_plural = 'Stars-подписки'

    def __str__(self):
        return f'{self.tg_user} — {self.tariff} до {self.expires_at}'


class BusinessConnection(models.Model):
    """S5 — AI-секретарь: подключение Telegram Business аккаунта к боту.

    Приватность: переписка клиентов не логируется — хранится только очередь
    черновиков (BusinessDraft) с TTL-очисткой.
    """
    class Mode(models.TextChoices):
        DRAFTS = 'drafts', 'Черновики (подтверждение владельцем)'
        AUTOPILOT = 'autopilot', 'Автопилот (типовые вопросы)'

    tg_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='business_connections',
        verbose_name='Владелец (TG пользователь)',
    )
    connection_id = models.CharField(max_length=128, unique=True,
                                     verbose_name='business_connection_id')
    is_enabled = models.BooleanField(default=True, verbose_name='Подключение активно')
    secretary_on = models.BooleanField(default=True, verbose_name='Секретарь включён')
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.DRAFTS,
                            verbose_name='Режим')
    scope_all = models.BooleanField(default=True, verbose_name='Работать во всех чатах')
    allowed_chat_ids = models.JSONField(default=list, blank=True,
                                        verbose_name='Белый список чатов')
    tone = models.TextField(blank=True, verbose_name='Тон ответов (инструкция AI)')
    stop_word = models.CharField(max_length=50, default='оператор',
                                 verbose_name='Стоп-слово клиента (передать человеку)')
    can_reply = models.BooleanField(default=False, verbose_name='Право отвечать (rights)')
    replies_month = models.CharField(max_length=7, blank=True, default='',
                                     verbose_name='Месяц счётчика (YYYY-MM)')
    replies_this_month = models.PositiveIntegerField(default=0,
                                                     verbose_name='Ответов за месяц')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Business-подключение'
        verbose_name_plural = 'Business-подключения'

    def __str__(self):
        return f'{self.tg_user} — {self.connection_id[:12]} ({self.mode})'


class BusinessDraft(models.Model):
    """S5 — очередь черновиков AI-секретаря (единственное место с текстом
    сообщений клиентов; чистится по TTL задачей cleanup_business_drafts)."""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ждёт решения'
        SENT = 'sent', 'Отправлен'
        IGNORED = 'ignored', 'Игнор'
        AUTO = 'auto', 'Автоответ'

    connection = models.ForeignKey(
        BusinessConnection,
        on_delete=models.CASCADE,
        related_name='drafts',
        verbose_name='Подключение',
    )
    client_chat_id = models.BigIntegerField(verbose_name='Чат клиента')
    client_name = models.CharField(max_length=150, blank=True, verbose_name='Имя клиента')
    incoming_text = models.TextField(verbose_name='Сообщение клиента')
    draft_text = models.TextField(blank=True, verbose_name='Черновик ответа')
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING, verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Черновик секретаря'
        verbose_name_plural = 'Черновики секретаря'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['connection', 'status'], name='bizdraft_conn_idx'),
        ]

    def __str__(self):
        return f'{self.connection} → {self.client_name} ({self.status})'


class TelegramTopic(models.Model):
    """S7 — топик в личке бота (Bot API 9.3+) ↔ проект пользователя.

    Нативные «папки чатов» прямо в Telegram: у каждого топика свой контекст
    (Chat), проект и, через проект, — персона и база знаний.
    """
    tg_user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='topics',
        verbose_name='TG пользователь',
    )
    topic_id = models.IntegerField(verbose_name='message_thread_id топика')
    project = models.ForeignKey(
        'aitext.Project',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_topics',
        verbose_name='Проект',
    )
    chat = models.ForeignKey(
        'aitext.Chat',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='telegram_topics',
        verbose_name='Чат контекста',
    )
    title = models.CharField(max_length=128, blank=True, verbose_name='Название топика')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Топик бота'
        verbose_name_plural = 'Топики бота'
        unique_together = [('tg_user', 'topic_id')]

    def __str__(self):
        return f'{self.tg_user} — топик {self.title or self.topic_id}'


class GroupMessageLog(models.Model):
    """S7 — короткий лог сообщений зарегистрированной группы для /summary.

    Только для групп с орг-биллингом (владелец включил бота осознанно).
    TTL 48 часов — чистится задачей cleanup_group_message_logs.
    """
    group = models.ForeignKey(
        TelegramGroup,
        on_delete=models.CASCADE,
        related_name='message_logs',
        verbose_name='Группа',
    )
    from_name = models.CharField(max_length=150, blank=True, verbose_name='Автор')
    text = models.CharField(max_length=500, verbose_name='Текст (обрезан)')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Лог сообщения группы'
        verbose_name_plural = 'Логи сообщений групп'
        indexes = [
            models.Index(fields=['group', 'created_at'], name='grouplog_idx'),
        ]

    def __str__(self):
        return f'{self.group} — {self.from_name}: {self.text[:40]}'


class AgentRun(models.Model):
    """S9 — Agent Mode: многошаговое выполнение задачи с инструментами.

    Агент планирует и исполняет шаги (веб-поиск, вычисления) в цикле LLM,
    прогресс пишется в steps (живой прогресс в боте, как у DeepResearch).
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает'
        RUNNING = 'running', 'Выполняется'
        DONE = 'done', 'Готово'
        ERROR = 'error', 'Ошибка'

    user = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='agent_runs',
        verbose_name='Пользователь',
    )
    goal = models.TextField(verbose_name='Задача')
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING, verbose_name='Статус')
    steps = models.JSONField(default=list, blank=True, verbose_name='Шаги выполнения')
    result_md = models.TextField(blank=True, verbose_name='Итоговый отчёт (markdown)')
    error = models.TextField(blank=True, verbose_name='Ошибка')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Agent Mode запуск'
        verbose_name_plural = 'Agent Mode запуски'
        ordering = ['-created_at']

    def __str__(self):
        return f'AgentRun #{self.pk} — {self.status} — {self.goal[:50]}'

    def append_step(self, kind: str, text: str):
        self.steps = list(self.steps) + [{'kind': kind, 'text': text}]
        self.save(update_fields=['steps'])


class ManagedBot(models.Model):
    """S8 — персональный AI-бот пользователя («фабрика агентов», за флагом).

    Пользователь получает СВОЕГО бота (@his_name_bot) с персоной, базой знаний
    (проект/RAG) и моделью. Апдейты всех managed-ботов мультиплексируются
    одним webhook-роутером (views.managed_bot_webhook). Сообщения гостей
    оплачиваются с баланса владельца (идемпотентно).
    """
    owner = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name='managed_bots',
        verbose_name='Владелец',
    )
    bot_username = models.CharField(max_length=100, blank=True, verbose_name='Username бота')
    token = models.CharField(max_length=100, verbose_name='Токен бота')
    name = models.CharField(max_length=100, verbose_name='Имя агента')
    greeting = models.TextField(
        blank=True, default='Привет! Я AI-ассистент. Задайте вопрос.',
        verbose_name='Приветствие (/start)',
    )
    system_prompt = models.TextField(blank=True, verbose_name='Персона / системный промт')
    network = models.ForeignKey(
        'aitext.NeuralNetwork',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_bots',
        verbose_name='Модель (пусто = самая дешёвая)',
    )
    project = models.ForeignKey(
        'aitext.Project',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='managed_bots',
        verbose_name='Проект (база знаний RAG)',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    messages_count = models.PositiveIntegerField(default=0, verbose_name='Сообщений гостей')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Персональный бот'
        verbose_name_plural = 'Персональные боты'

    def __str__(self):
        return f'@{self.bot_username or "?"} ({self.owner})'

    def webhook_secret(self) -> str:
        """Секрет вебхука, детерминированный от токена (не храним отдельно)."""
        import hashlib
        return hashlib.sha256(f'managed:{self.token}'.encode()).hexdigest()[:32]


def ai_task_limit(user) -> int:
    """S2 — лимит активных AI-задач по тарифу: free 1, Старт 3, Стандарт 10, Про 30."""
    tariff = getattr(user, 'tariff', None)
    if tariff is None or getattr(tariff, 'is_free', True):
        return 1
    name = (getattr(tariff, 'display_name', '') or '').lower()
    if 'про' in name or 'pro' in name:
        return 30
    if 'старт' in name or 'start' in name:
        return 3
    return 10


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
