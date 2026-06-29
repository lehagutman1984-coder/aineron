import secrets
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class Organization(models.Model):
    name = models.CharField(max_length=200, verbose_name='Название')
    inn = models.CharField(max_length=12, blank=True, verbose_name='ИНН')
    kpp = models.CharField(max_length=9, blank=True, verbose_name='КПП')
    legal_address = models.TextField(blank=True, verbose_name='Юридический адрес')
    balance_rub = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Баланс (руб.)'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_organizations',
        verbose_name='Владелец',
    )
    meta = models.JSONField(default=dict, blank=True, verbose_name='Мета-данные (токены, настройки)')
    # §7.7 Billing seats
    seats_count = models.PositiveIntegerField(default=5, verbose_name='Лимит мест')
    seat_monthly_stars = models.PositiveIntegerField(
        default=0,
        verbose_name='Звёзд в месяц на участника',
        help_text='0 = без лимита на участника',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Организация'
        verbose_name_plural = 'Организации'

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Владелец'
        ADMIN = 'admin', 'Администратор'
        MEMBER = 'member', 'Участник'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='members'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='org_memberships',
    )
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.MEMBER, verbose_name='Роль'
    )
    # §7.7 Billing seats — monthly quota tracking
    monthly_used = models.PositiveIntegerField(default=0, verbose_name='Использовано звёзд (мес.)')
    monthly_reset_at = models.DateField(null=True, blank=True, verbose_name='Дата сброса квоты')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Добавлен')

    class Meta:
        unique_together = [('organization', 'user')]
        verbose_name = 'Участник организации'
        verbose_name_plural = 'Участники организации'

    def __str__(self):
        return f'{self.user.email} — {self.organization.name} ({self.role})'


class OrganizationInvite(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invites'
    )
    email = models.EmailField(verbose_name='Email приглашённого')
    token = models.CharField(
        max_length=64, unique=True, blank=True, verbose_name='Токен'
    )
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Истекает'
    )
    is_accepted = models.BooleanField(default=False, verbose_name='Принято')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'Приглашение в организацию'
        verbose_name_plural = 'Приглашения в организацию'

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f'Приглашение {self.email} в {self.organization.name}'


class Invoice(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        CANCELLED = 'cancelled', 'Отменён'

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='invoices'
    )
    number = models.CharField(
        max_length=50, unique=True, blank=True, verbose_name='Номер счёта'
    )
    amount_rub = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Сумма (руб.)'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус',
    )
    description = models.TextField(blank=True, verbose_name='Описание')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Оплачен')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Счёт'
        verbose_name_plural = 'Счета'

    def save(self, *args, **kwargs):
        if not self.number:
            year = timezone.now().year
            count = Invoice.objects.filter(created_at__year=year).count()
            self.number = f'INV-{year}-{count + 1:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Счёт {self.number} — {self.amount_rub} руб.'


class OrganizationBranding(models.Model):
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='branding')
    subdomain = models.SlugField(max_length=63, unique=True, verbose_name='Субдомен')
    custom_domain = models.CharField(max_length=253, blank=True, verbose_name='Кастомный домен')
    logo_url = models.URLField(blank=True, verbose_name='URL логотипа')
    primary_color = models.CharField(max_length=7, default='#f0a38a', verbose_name='Основной цвет')
    company_name = models.CharField(max_length=100, blank=True, verbose_name='Название компании')
    support_email = models.EmailField(blank=True, verbose_name='Email поддержки')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Брендинг организации'
        verbose_name_plural = 'Брендинг организаций'

    def __str__(self):
        return f'{self.subdomain}.aineron.ru — {self.organization.name}'
