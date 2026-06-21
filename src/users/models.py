from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid


class Tariff(models.Model):
    """
    Модель тарифов
    """
    display_name = models.CharField(
        max_length=100,
        verbose_name='Название тарифа'
    )
    pages_count = models.PositiveIntegerField(
        verbose_name='Количество звезд'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Стоимость тарифа'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    is_free = models.BooleanField(
        default=False,
        verbose_name='Бесплатный тариф'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    duration_days = models.PositiveIntegerField(
        default=30,
        verbose_name='Срок действия (дней)'
    )
    next_tariff = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Следующий тариф (для пробных)'
    )
    is_trial = models.BooleanField(
        default=False,
        verbose_name='Пробный тариф'
    )
    referral_bonus = models.PositiveIntegerField(
        default=0,
        verbose_name='Реферальный бонус',
        help_text='Сколько рублей получит пригласивший пользователь при покупке этого тарифа'
    )
    referral_bonus_stars = models.PositiveIntegerField(
        default=0,
        verbose_name='Реферальный бонус (звёзд)',
        help_text='Сколько звёзд получит пригласивший пользователь при покупке этого тарифа'
    )

    class Meta:
        verbose_name = 'Тариф'
        verbose_name_plural = 'Тарифы'
        ordering = ['price']

    def __str__(self):
        return f"{self.display_name} - {self.pages_count} стр. - {self.price} руб."

    @classmethod
    def get_default_tariff(cls):
        """Возвращает бесплатный тариф по умолчанию"""
        tariff, created = cls.objects.get_or_create(
            display_name='Бесплатный',  # вместо name
            defaults={
                'pages_count': 10,
                'price': 0,
                'is_free': True,
                'description': 'Бесплатный тариф для ознакомления с сервисом',
                'duration_days': 36500
            }
        )
        return tariff

    def get_unlimited_networks(self):
        """Возвращает строку с названиями нейросетей, где этот тариф даёт безлимит"""
        networks = self.unlimited_networks.filter(is_active=True, unlimited=True)
        if not networks:
            return "Безлимитный: DeepSeek V3.2"  # значение по умолчанию
        names = [net.name for net in networks]
        if len(names) == 1:
            return f"Безлимитный: {names[0]}"
        return f"Безлимитные: {', '.join(names)}"


class UserSubscription(models.Model):
    """
    Модель подписки пользователя на тариф
    """
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='subscriptions',
        verbose_name='Пользователь'
    )
    tariff = models.ForeignKey(
        Tariff,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Тариф'
    )
    subscription_id = models.CharField(
        max_length=100,
        unique=True,
        default=uuid.uuid4,
        verbose_name='ID подписки'
    )
    robokassa_invoice_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='ID счета Robokassa'
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата начала'
    )
    expires_at = models.DateTimeField(
        verbose_name='Дата окончания'
    )
    last_payment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата последнего платежа'
    )
    next_payment_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата следующего платежа'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )
    auto_renew = models.BooleanField(
        default=True,
        verbose_name='Автопродление'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Активна'),
            ('expired', 'Истекла'),
            ('cancelled', 'Отменена'),
            ('pending', 'Ожидает оплаты'),
        ],
        default='active',
        verbose_name='Статус'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    renewal_attempts = models.PositiveIntegerField(
        default=0,
        verbose_name='Попыток продления'
    )
    max_renewal_attempts = models.PositiveIntegerField(
        default=6,
        verbose_name='Максимум попыток'
    )
    last_renewal_attempt = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Последняя попытка продления'
    )
    last_expiry_notification_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата последнего уведомления об истечении'
    )
    # НОВОЕ ПОЛЕ (для хранения исходного тарифа при пробном периоде)
    original_tariff = models.ForeignKey(
        Tariff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='original_subscriptions',
        verbose_name='Исходный тариф (для пробного)'
    )

    class Meta:
        verbose_name = 'Подписка пользователя'
        verbose_name_plural = 'Подписки пользователей'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active', 'expires_at']),
            models.Index(fields=['robokassa_invoice_id']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.tariff.display_name if self.tariff else 'Нет тарифа'}"

    def save(self, *args, **kwargs):
        if not self.expires_at and self.tariff:
            self.expires_at = timezone.now() + timedelta(days=self.tariff.duration_days)
        super().save(*args, **kwargs)

    def is_expired(self):
        return self.expires_at < timezone.now()

    def days_until_expiration(self):
        if self.is_expired():
            return 0
        return (self.expires_at - timezone.now()).days

    @property
    def expires_display(self):
        """Возвращает строку с правильным склонением дней"""
        if not self.expires_at or self.tariff.is_free:
            return "бессрочно"

        days = self.days_until_expiration()

        if days < 0:
            return "истекла"
        elif days == 0:
            return "последний день"
        elif days % 10 == 1 and days % 100 != 11:
            return f"{days} день"
        elif 2 <= days % 10 <= 4 and (days % 100 < 10 or days % 100 >= 20):
            return f"{days} дня"
        else:
            return f"{days} дней"


class PaymentHistory(models.Model):
    # ... (остаётся без изменений, как в исходном файле)
    class PaymentType(models.TextChoices):
        SUBSCRIPTION = 'subscription', 'Оплата подписки'
        PAGES = 'pages', 'Покупка звезд'
        PROMO = 'promo', 'Активация промокода'

    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Пользователь'
    )
    subscription = models.ForeignKey(
        'UserSubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
        verbose_name='Подписка'
    )
    parent_payment = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Материнский платеж'
    )
    tariff = models.ForeignKey(
        'Tariff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Тариф'
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.SUBSCRIPTION,
        verbose_name='Тип платежа'
    )
    invoice_id = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name='ID счета'
    )
    payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='ID платежа'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Сумма'
    )
    pages_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Куплено звезд'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Ожидает'),
            ('success', 'Успешно'),
            ('failed', 'Ошибка'),
            ('refunded', 'Возврат'),
        ],
        default='pending',
        verbose_name='Статус'
    )
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Способ оплаты'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата оплаты'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'История платежей'
        verbose_name_plural = 'История платежей'
        ordering = ['-created_at']

    def __str__(self):
        payment_type_display = dict(self.PaymentType.choices).get(self.payment_type, 'Платеж')
        return f"{self.user.email} - {self.amount} руб. - {payment_type_display} - {self.get_status_display()}"


class PageSaleSettings(models.Model):
    # ... (без изменений)
    price_per_page = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Цена за 1 звезду'
    )
    min_pages_for_purchase = models.PositiveIntegerField(
        default=1,
        verbose_name='Минимальное количество звезд для покупки'
    )
    max_pages_for_purchase = models.PositiveIntegerField(
        default=100,
        verbose_name='Максимальное количество звезд для покупки'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна продажа'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Настройка продажи звезд'
        verbose_name_plural = 'Настройки продажи звезд'

    def __str__(self):
        return f"Цена за звезду: {self.price_per_page} руб."

    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'price_per_page': 10.00,
                'min_pages_for_purchase': 1,
                'max_pages_for_purchase': 100
            }
        )
        return settings


class CustomUser(AbstractUser):
    """
    Кастомная модель пользователя - УПРОЩЕННАЯ ВЕРСИЯ
    """
    email = models.EmailField(unique=True)

    # Подтверждение email
    email_verified = models.BooleanField(
        default=False,
        verbose_name='Email подтвержден'
    )
    email_verification_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Токен подтверждения'
    )
    email_verification_code = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name='Код подтверждения'
    )

    # Звезды
    pages_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Количество звезд'
    )
    tariff = models.ForeignKey(
        'Tariff',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name='Текущий тариф'
    )
    active_subscription = models.OneToOneField(
        'UserSubscription',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_user',
        verbose_name='Активная подписка'
    )

    # Безопасность
    shadow_banned = models.BooleanField(
        default=False,
        verbose_name='Теневой бан'
    )

    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    rub_balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Баланс в рублях'
    )
    can_convert_to_rub = models.BooleanField(
        default=False,
        verbose_name='Можно конвертировать звёзды в рубли'
    )
    gitea_username = models.CharField(max_length=64, blank=True, verbose_name='Gitea username')
    gitea_password = models.CharField(max_length=128, blank=True, verbose_name='Gitea password')
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        verbose_name='Реферальный код'
    )
    referrer = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals',
        verbose_name='Пригласивший пользователь'
    )
    referral_clicks = models.PositiveIntegerField(default=0, verbose_name='Количество переходов по ссылке')
    memory_enabled = models.BooleanField(
        default=True,
        verbose_name='Память включена',
        help_text='Глобальный переключатель долговременной памяти',
    )

    # Фикс конфликтов с allauth
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='customuser_groups',
        related_query_name='customuser',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='customuser_permissions',
        related_query_name='customuser',
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-date_joined']

    def __str__(self):
        return self.username or self.email

    def save(self, *args, **kwargs):
        from .models import Tariff, UserSubscription
        from django.utils import timezone
        from datetime import timedelta

        if not self.username and self.email:
            self.username = self.email.split('@')[0]

        super().save(*args, **kwargs)

        # Если пользователь без тарифа - назначаем бесплатный
        if not self.tariff:
            free_tariff = Tariff.get_default_tariff()
            self.tariff = free_tariff
            self.pages_count = free_tariff.pages_count

            if not self.active_subscription:
                free_subscription = UserSubscription.objects.create(
                    user=self,
                    tariff=free_tariff,
                    is_active=True,
                    status='active',
                    expires_at=timezone.now() + timedelta(days=365 * 100)
                )
                self.active_subscription = free_subscription

            self.save(update_fields=['tariff', 'pages_count', 'active_subscription'])

    def has_enough_pages(self, required_pages):
        return self.pages_count >= required_pages

    def spend_pages(self, pages_count):
        if self.has_enough_pages(pages_count):
            self.pages_count -= pages_count
            self.save(update_fields=['pages_count'])
            return True
        return False

    def add_pages(self, pages_count):
        self.pages_count += pages_count
        self.save(update_fields=['pages_count'])
        return True

    def set_pages(self, pages_count):
        self.pages_count = pages_count
        self.save(update_fields=['pages_count'])
        return True

    def activate_paid_tariff(self, tariff, payment_data=None):
        """
        Активирует платный тариф - ДОБАВЛЯЕТ звезды к существующим
        """
        # Деактивируем старую подписку
        if self.active_subscription:
            old_subscription = self.active_subscription
            old_subscription.is_active = False
            old_subscription.status = 'cancelled'
            old_subscription.save()

        # Создаём новую подписку
        expires_at = timezone.now() + timedelta(days=tariff.duration_days)
        subscription = UserSubscription.objects.create(
            user=self,
            tariff=tariff,
            is_active=True,
            status='active',
            started_at=timezone.now(),
            expires_at=expires_at,
            next_payment_date=expires_at,
            auto_renew=True,
            robokassa_invoice_id=payment_data.get('invoice_id') if payment_data else None,
            original_tariff=tariff if tariff.is_trial else None
        )

        # Обновляем пользователя
        self.tariff = tariff
        self.active_subscription = subscription
        self.pages_count += tariff.pages_count
        self.save(update_fields=['tariff', 'active_subscription', 'pages_count'])

        # Создаём запись в истории платежей
        if payment_data:
            PaymentHistory.objects.create(
                user=self,
                subscription=subscription,
                tariff=tariff,
                invoice_id=payment_data.get('invoice_id'),
                payment_id=payment_data.get('payment_id'),
                amount=tariff.price,
                pages_count=tariff.pages_count,
                status='success',
                paid_at=timezone.now(),
                description=f"Активация тарифа {tariff.display_name}"
            )
        return subscription

    def return_to_free_tariff(self):
        free_tariff = Tariff.get_default_tariff()
        if self.active_subscription:
            old_subscription = self.active_subscription
            old_subscription.is_active = False
            old_subscription.status = 'expired'
            old_subscription.save()
        free_subscription = UserSubscription.objects.create(
            user=self,
            tariff=free_tariff,
            is_active=True,
            status='active',
            expires_at=timezone.now() + timedelta(days=365 * 100)
        )
        self.tariff = free_tariff
        self.active_subscription = free_subscription
        self.pages_count = free_tariff.pages_count
        self.save(update_fields=['tariff', 'active_subscription', 'pages_count'])
        return free_subscription

    def verify_email(self):
        self.email_verified = True
        self.email_verification_token = None
        self.email_verification_code = None
        self.save(update_fields=['email_verified', 'email_verification_token', 'email_verification_code'])
        return True

    def apply_shadow_ban(self):
        self.shadow_banned = True
        self.save(update_fields=['shadow_banned'])
        return True

    def remove_shadow_ban(self):
        self.shadow_banned = False
        self.save(update_fields=['shadow_banned'])
        return True

    @classmethod
    def create_social_user(cls, email, provider, uid):
        from .models import Tariff, UserSubscription
        from django.utils import timezone
        from datetime import timedelta

        try:
            username = email.split('@')[0] if email else f"{provider}_{uid[:8]}"
            free_tariff = Tariff.get_default_tariff()
            user, created = cls.objects.get_or_create(
                email=email if email else f"{provider}_{uid}@temp.erogent.com",
                defaults={
                    'username': username,
                    'email_verified': True,
                    'tariff': free_tariff,
                    'pages_count': free_tariff.pages_count,
                }
            )
            if created:
                import secrets
                import string
                alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
                random_password = ''.join(secrets.choice(alphabet) for _ in range(16))
                user.set_password(random_password)
                subscription = UserSubscription.objects.create(
                    user=user,
                    tariff=free_tariff,
                    is_active=True,
                    status='active',
                    expires_at=timezone.now() + timedelta(days=365 * 100)
                )
                user.active_subscription = subscription
                user.save()
            return user
        except Exception as e:
            print(f"[ERROR] Ошибка создания социального пользователя: {e}")
            return None


class UserIPAddress(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='ip_addresses',
        verbose_name='Пользователь'
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='IP-адрес',
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )

    class Meta:
        verbose_name = 'IP-адрес пользователя'
        verbose_name_plural = 'IP-адреса пользователей'
        unique_together = ['user', 'ip_address']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.ip_address}"


class UserActivityLog(models.Model):
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        verbose_name='Пользователь'
    )
    date = models.DateField(
        'Дата активности',
        db_index=True,
        default=timezone.now
    )
    login_count = models.IntegerField(
        'Количество заходов',
        default=0
    )
    last_login_time = models.DateTimeField(
        'Время последнего захода',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Создано'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлено'
    )

    class Meta:
        verbose_name = 'Журнал активности пользователя'
        verbose_name_plural = 'Журнал активности пользователей'
        unique_together = ['user', 'date']
        ordering = ['-date', '-last_login_time']

    def __str__(self):
        return f"{self.user.username} - {self.date} ({self.login_count} заходов)"

    def increment_login(self, login_time=None):
        if login_time is None:
            login_time = timezone.now()
        self.login_count += 1
        self.last_login_time = login_time
        self.save(update_fields=['login_count', 'last_login_time', 'updated_at'])
        return self.login_count


class LegalDocument(models.Model):
    DOCUMENT_TYPES = [
        ('privacy', 'Политика конфиденциальности'),
        ('terms', 'Пользовательское соглашение'),
    ]
    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPES,
        unique=True,
        verbose_name='Тип документа'
    )
    title = models.CharField(
        max_length=200,
        verbose_name='Заголовок'
    )
    content = models.TextField(
        verbose_name='Содержание'
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name='Последнее обновление'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Юридический документ'
        verbose_name_plural = 'Юридические документы'

    def __str__(self):
        return self.get_document_type_display()

    @classmethod
    def get_privacy(cls):
        doc, created = cls.objects.get_or_create(
            document_type='privacy',
            defaults={
                'title': 'Политика конфиденциальности',
                'content': '<!-- Содержание будет добавлено через админку -->'
            }
        )
        return doc

    @classmethod
    def get_terms(cls):
        doc, created = cls.objects.get_or_create(
            document_type='terms',
            defaults={
                'title': 'Пользовательское соглашение',
                'content': '<!-- Содержание будет добавлено через админку -->'
            }
        )
        return doc

class PromoCode(models.Model):
    """
    Модель промокодов для начисления звезд
    """
    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Промокод'
    )
    stars = models.PositiveIntegerField(
        verbose_name='Количество звезд'
    )
    usage_limit = models.PositiveIntegerField(
        default=1,
        verbose_name='Лимит использований (0 - безлимит)'
    )
    used_count = models.PositiveIntegerField(
        default=0,
        verbose_name='Уже использовано'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Действителен до'
    )

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'

    def __str__(self):
        return f"{self.code} (+{self.stars} зв.) использован {self.used_count}/{self.usage_limit if self.usage_limit > 0 else 'inf'}"

    def is_valid(self):
        if not self.is_active:
            return False
        if self.usage_limit > 0 and self.used_count >= self.usage_limit:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class UsedPromoCode(models.Model):
    """
    Связь пользователя с использованным промокодом
    """
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='used_promocodes'
    )
    promo_code = models.ForeignKey(
        PromoCode,
        on_delete=models.CASCADE,
        related_name='used_by'
    )
    used_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        unique_together = ['user', 'promo_code']
        verbose_name = 'Использованный промокод'
        verbose_name_plural = 'Использованные промокоды'

class SiteCounter(models.Model):
    counter_text = models.TextField(
        verbose_name="Текст счетчика",
        help_text="Вставьте код счетчика"
    )

    class Meta:
        verbose_name = "Счетчик сайта"
        verbose_name_plural = "Счетчики сайта"

    def __str__(self):
        return self.counter_text

class UserSpending(models.Model):
    """Модель для записи списаний звезд (сообщения, генерации и т.д.)"""
    user = models.ForeignKey(
        'CustomUser',
        on_delete=models.CASCADE,
        related_name='spendings',
        verbose_name='Пользователь'
    )
    amount = models.PositiveIntegerField(
        verbose_name='Количество звезд'
    )
    description = models.CharField(
        max_length=255,
        verbose_name='Описание'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата списания'
    )

    class Meta:
        verbose_name = 'Списание звезд'
        verbose_name_plural = 'Списания звезд'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.amount} зв. - {self.created_at.strftime('%d.%m.%Y %H:%M')}"


class SiteSettings(models.Model):
    """Настройки сайта"""
    title = models.CharField(
        max_length=200,
        default='LUMEN',
        verbose_name='Заголовок главной страницы'
    )
    description = models.TextField(
        blank=True,
        default='Нейросети без VPN и сложностей',
        verbose_name='Описание для главной страницы'
    )
    keywords = models.CharField(
        max_length=500,
        blank=True,
        default='нейросети, AI, искусственный интеллект, генерация изображений, чат с AI',
        verbose_name='Ключевые слова (через запятую)'
    )
    inn = models.CharField(
        max_length=100,
        blank=True,
        default='ИНН: 1234567890',
        verbose_name='ИНН для футера'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')
    vk_url = models.URLField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Ссылка на группу ВКонтакте'
    )
    telegram_url = models.URLField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Ссылка на Telegram-канал'
    )
    # SEO для блога
    blog_title = models.CharField(
        max_length=200,
        blank=True,
        default='Блог | LUMEN',
        verbose_name='Заголовок страницы блога'
    )
    blog_description = models.TextField(
        blank=True,
        default='Новости, статьи и обзоры нейросетей',
        verbose_name='Описание для страницы блога'
    )
    blog_keywords = models.CharField(
        max_length=500,
        blank=True,
        default='нейросети, искусственный интеллект, AI, новости, статьи',
        verbose_name='Ключевые слова для блога (через запятую)'
    )

    # SEO для каталога
    catalog_title = models.CharField(
        max_length=200,
        blank=True,
        default='Каталог нейросетей | LUMEN',
        verbose_name='Заголовок страницы каталога'
    )
    catalog_description = models.TextField(
        blank=True,
        default='Все нейросети в одном месте. Выбирайте и начинайте работу.',
        verbose_name='Описание для страницы каталога'
    )
    catalog_keywords = models.CharField(
        max_length=500,
        blank=True,
        default='нейросети, каталог AI, искусственный интеллект, модели',
        verbose_name='Ключевые слова для каталога (через запятую)'
    )
    support_email = models.EmailField(
        blank=True,
        default='support@example.com',
        verbose_name='Email поддержки'
    )

    class Meta:
        verbose_name = 'Настройка сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    @classmethod
    def get_settings(cls):
        """Возвращает единственный экземпляр настроек"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings

class ReferralEarning(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referral_earnings')
    amount_rub = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Сумма в рублях')
    amount_stars = models.PositiveIntegerField(default=0, verbose_name='Сумма в звёздах')
    tariff = models.ForeignKey('Tariff', on_delete=models.SET_NULL, null=True, verbose_name='Тариф')
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Реферальное начисление'
        verbose_name_plural = 'Реферальные начисления'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.amount_rub} руб / {self.amount_stars} зв."


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Ожидает'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Сумма вывода')
    card_number = models.CharField(max_length=20, verbose_name='Номер карты')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='Статус')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, verbose_name='Примечание администратора')

    class Meta:
        verbose_name = 'Запрос на вывод'
        verbose_name_plural = 'Запросы на вывод'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.amount} руб - {self.get_status_display()}"