from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
from .models import (
    UserIPAddress, UserActivityLog, Tariff,
    PageSaleSettings, CustomUser,
    UserSubscription, PaymentHistory, LegalDocument, SiteCounter, PromoCode, UserSpending, SiteSettings, ReferralEarning, WithdrawalRequest
)

CustomUser = get_user_model()


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    """
    Админка для управления тарифами
    """
    list_display = ('display_name', 'pages_count', 'price', 'duration_days', 'is_trial', 'next_tariff_link',
                    'is_free', 'is_active', 'users_count', 'referral_bonus', 'referral_bonus_stars', 'created_at')
    list_filter = ('is_active', 'is_free', 'is_trial', 'duration_days', 'created_at')
    search_fields = ('display_name', 'description')
    list_editable = ('is_active', 'is_free', 'is_trial', 'duration_days')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('display_name', 'description')
        }),
        (_('Параметры тарифа'), {
            'fields': ('pages_count', 'price', 'duration_days', 'is_trial', 'next_tariff', 'is_free', 'is_active', 'referral_bonus', 'referral_bonus_stars'),
            'classes': ('wide',),
            'description': 'is_trial — пробный тариф (например, Lite на 7 дней). next_tariff — на какой тариф перейти после пробного (и по какой цене списывать).',
        }),
        (_('Даты'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def next_tariff_link(self, obj):
        if obj.next_tariff:
            url = reverse('admin:users_tariff_change', args=[obj.next_tariff.id])
            return format_html('<a href="{}">{}</a>', url, obj.next_tariff.display_name)
        return '-'
    next_tariff_link.short_description = 'Следующий тариф'
    next_tariff_link.admin_order_field = 'next_tariff'

    def users_count(self, obj):
        count = obj.users.count()
        url = reverse('admin:users_customuser_changelist') + f'?tariff__id__exact={obj.id}'
        return format_html('<a href="{}">{} пользователей</a>', url, count)
    users_count.short_description = 'Пользователей'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('next_tariff').prefetch_related('users')

    actions = ['make_free', 'make_paid', 'make_trial', 'make_regular']

    def make_free(self, request, queryset):
        queryset.update(is_free=True, price=0)
        self.message_user(request, f'✅ {queryset.count()} тарифов помечены как бесплатные')
    make_free.short_description = 'Сделать бесплатными'

    def make_paid(self, request, queryset):
        queryset.update(is_free=False)
        self.message_user(request, f'✅ {queryset.count()} тарифов помечены как платные')
    make_paid.short_description = 'Сделать платными'

    def make_trial(self, request, queryset):
        queryset.update(is_trial=True)
        self.message_user(request, f'✅ {queryset.count()} тарифов помечены как пробные')
    make_trial.short_description = 'Отметить как пробные'

    def make_regular(self, request, queryset):
        queryset.update(is_trial=False)
        self.message_user(request, f'✅ {queryset.count()} тарифов помечены как обычные')
    make_regular.short_description = 'Отметить как обычные'


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """
    Админка для управления подписками пользователей - ПОЛНОСТЬЮ РЕДАКТИРУЕМАЯ
    """
    list_display = ('user_link', 'tariff_info', 'status_colored', 'is_active',
                    'started_at', 'expires_at', 'days_left', 'renewal_info',
                    'auto_renew', 'original_tariff_link', 'last_renewal_attempt',
                    'last_expiry_notification_sent', 'edit_link')
    list_filter = ('status', 'is_active', 'auto_renew', 'tariff', 'original_tariff', 'started_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'subscription_id', 'robokassa_invoice_id')
    readonly_fields = ('subscription_id', 'created_at', 'updated_at', 'days_left_display')
    list_select_related = ('user', 'tariff', 'original_tariff')
    date_hierarchy = 'expires_at'
    list_editable = ('expires_at', 'auto_renew', 'is_active')

    fieldsets = (
        (None, {
            'fields': ('user', 'tariff', 'subscription_id')
        }),
        (_('Информация о подписке'), {
            'fields': ('status', 'is_active', 'auto_renew', 'original_tariff'),
            'classes': ('wide',),
            'description': 'original_tariff заполняется автоматически для пробных тарифов (чтобы знать, с какого тарифа был переход)',
        }),
        (_('Период действия'), {
            'fields': ('started_at', 'expires_at', 'last_payment_date', 'next_payment_date'),
            'classes': ('wide',),
        }),
        (_('Попытки продления'), {
            'fields': ('renewal_attempts', 'max_renewal_attempts', 'last_renewal_attempt'),
            'classes': ('wide',),
            'description': 'Можно редактировать вручную при необходимости',
        }),
        (_('Уведомления'), {
            'fields': ('last_expiry_notification_sent',),
            'classes': ('wide',),
            'description': 'Дата последнего уведомления об истечении (сбрасывается при продлении)',
        }),
        (_('Данные Robokassa'), {
            'fields': ('robokassa_invoice_id',),
            'classes': ('wide',),
        }),
        (_('Даты создания'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        return ['subscription_id', 'created_at', 'updated_at', 'days_left_display']

    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'Пользователь'
    user_link.admin_order_field = 'user__email'

    def edit_link(self, obj):
        url = reverse('admin:users_usersubscription_change', args=[obj.id])
        return format_html('<a href="{}"><i class="fas fa-edit"></i> Редактировать</a>', url)
    edit_link.short_description = 'Действия'

    def tariff_info(self, obj):
        if obj.tariff:
            return format_html(
                '{}<br><small>{} стр. / {} ₽</small>',
                obj.tariff.display_name,
                obj.tariff.pages_count,
                obj.tariff.price
            )
        return '-'
    tariff_info.short_description = 'Тариф'

    def original_tariff_link(self, obj):
        if obj.original_tariff:
            url = reverse('admin:users_tariff_change', args=[obj.original_tariff.id])
            return format_html('<a href="{}">{}</a>', url, obj.original_tariff.display_name)
        return '-'
    original_tariff_link.short_description = 'Исходный тариф (пробный)'
    original_tariff_link.admin_order_field = 'original_tariff'

    def status_colored(self, obj):
        colors = {
            'active': 'green',
            'expired': 'red',
            'cancelled': 'orange',
            'pending': 'blue',
        }
        return mark_safe(
            '<span style="color: {}; font-weight: bold;">{}</span>'.format(
                colors.get(obj.status, 'gray'),
                obj.get_status_display()
            )
        )
    status_colored.short_description = 'Статус'
    status_colored.admin_order_field = 'status'

    def days_left(self, obj):
        days = obj.days_until_expiration()
        if obj.is_expired():
            return mark_safe('<span style="color: red;">Истекла</span>')

        if days <= 3 and obj.auto_renew and not obj.tariff.is_free:
            attempts_left = obj.max_renewal_attempts - obj.renewal_attempts
            if attempts_left > 0:
                return mark_safe(
                    '<span style="color: orange;">{} дн. (попыток: {})</span>'.format(days, attempts_left)
                )
            elif attempts_left == 0:
                return mark_safe(
                    '<span style="color: red;">{} дн. (лимит исчерпан)</span>'.format(days)
                )
        return mark_safe('<span style="color: green;">{} дн.</span>'.format(days))
    days_left.short_description = 'Осталось'
    days_left.admin_order_field = 'expires_at'

    def days_left_display(self, obj):
        if obj.expires_at:
            if obj.is_expired():
                return f'Истекла {obj.expires_at.strftime("%d.%m.%Y")}'
            days = obj.days_until_expiration()
            attempts_left = obj.max_renewal_attempts - obj.renewal_attempts
            info = f'{days} дней (до {obj.expires_at.strftime("%d.%m.%Y")})'
            if obj.auto_renew and not obj.tariff.is_free:
                info += f'\nПопыток: {obj.renewal_attempts}/{obj.max_renewal_attempts}'
                if obj.last_renewal_attempt:
                    info += f'\nПоследняя: {obj.last_renewal_attempt.strftime("%d.%m.%Y %H:%M")}'
            return info
        return '-'
    days_left_display.short_description = 'Детали окончания'

    def renewal_info(self, obj):
        if not obj.auto_renew or obj.tariff.is_free:
            return '-'
        attempts_left = obj.max_renewal_attempts - obj.renewal_attempts
        if obj.renewal_attempts == 0:
            return mark_safe('<span style="color: green;">Ожидание</span>')
        color = 'green' if attempts_left > 3 else 'orange' if attempts_left > 0 else 'red'
        return mark_safe(f'<span style="color: {color};">{obj.renewal_attempts}/{obj.max_renewal_attempts} попыток</span>')
    renewal_info.short_description = 'Попытки'
    renewal_info.admin_order_field = 'renewal_attempts'

    actions = ['mark_as_active', 'mark_as_expired', 'mark_as_cancelled',
               'enable_auto_renew', 'disable_auto_renew', 'reset_renewal_attempts']

    def mark_as_active(self, request, queryset):
        queryset.update(status='active', is_active=True)
        self.message_user(request, f'✅ {queryset.count()} подписок отмечены как активные')
    mark_as_active.short_description = 'Отметить как активные'

    def mark_as_expired(self, request, queryset):
        queryset.update(status='expired', is_active=False)
        self.message_user(request, f'✅ {queryset.count()} подписок отмечены как истекшие')
    mark_as_expired.short_description = 'Отметить как истекшие'

    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled', auto_renew=False)
        self.message_user(request, f'✅ {queryset.count()} подписок отменены')
    mark_as_cancelled.short_description = 'Отметить как отмененные'

    def enable_auto_renew(self, request, queryset):
        queryset.update(auto_renew=True)
        self.message_user(request, f'✅ Автопродление включено для {queryset.count()} подписок')
    enable_auto_renew.short_description = 'Включить автопродление'

    def disable_auto_renew(self, request, queryset):
        queryset.update(auto_renew=False)
        self.message_user(request, f'✅ Автопродление отключено для {queryset.count()} подписок')
    disable_auto_renew.short_description = 'Отключить автопродление'

    def reset_renewal_attempts(self, request, queryset):
        queryset.update(renewal_attempts=0, last_renewal_attempt=None)
        self.message_user(request, f'✅ Счетчики попыток сброшены для {queryset.count()} подписок')
    reset_renewal_attempts.short_description = 'Сбросить попытки продления'


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'tariff_info', 'amount_colored',
                    'pages_count', 'payment_type_display', 'status_colored',
                    'created_at', 'paid_at')
    list_filter = ('status', 'payment_type', 'created_at', 'paid_at', 'tariff')
    search_fields = ('user__username', 'user__email', 'invoice_id', 'payment_id')
    readonly_fields = ('created_at', 'updated_at', 'invoice_id', 'payment_type_display')
    list_select_related = ('user', 'tariff', 'subscription', 'parent_payment')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {'fields': ('user', 'tariff', 'subscription')}),
        (_('Данные платежа'), {'fields': ('invoice_id', 'payment_id', 'amount', 'pages_count', 'payment_type')}),
        (_('Связи'), {'fields': ('parent_payment', 'payment_type_display')}),
        (_('Статус'), {'fields': ('status', 'paid_at', 'payment_method', 'description')}),
        (_('Даты'), {'fields': ('created_at', 'updated_at')}),
    )

    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'Пользователь'
    user_link.admin_order_field = 'user__email'

    def tariff_info(self, obj):
        if obj.tariff:
            return format_html('{}<br><small>{} стр.</small>', obj.tariff.display_name, obj.tariff.pages_count)
        elif obj.payment_type == 'pages':
            return format_html('<span style="color: #9333ea;">Покупка звезд</span><br><small>{} стр.</small>', obj.pages_count)
        return '-'
    tariff_info.short_description = 'Тариф/Тип'

    def amount_colored(self, obj):
        if obj.amount > 0:
            return format_html('<span style="color: green; font-weight: bold;">{} ₽</span>', obj.amount)
        return format_html('<span style="color: gray;">0 ₽</span>')
    amount_colored.short_description = 'Сумма'

    def payment_type_display(self, obj):
        if obj.payment_type == 'pages':
            return format_html('<span style="color: #9333ea; font-weight: bold; background: #f3e8ff; padding: 3px 8px; border-radius: 20px;">📄 Покупка звезд</span>')
        elif obj.payment_type == 'subscription':
            if obj.parent_payment is None:
                return format_html('<span style="color: #2563eb; font-weight: bold; background: #dbeafe; padding: 3px 8px; border-radius: 20px;">🔷 Материнский (подписка)</span>')
            else:
                return format_html('<span style="color: #059669; font-weight: bold; background: #d1fae5; padding: 3px 8px; border-radius: 20px;">🔶 Дочерний (автопродление)</span>')
        else:
            return format_html('<span style="color: #6b7280; font-weight: bold; background: #f3f4f6; padding: 3px 8px; border-radius: 20px;">❓ Неизвестный</span>')
    payment_type_display.short_description = 'Тип платежа'

    def payment_type_display_form(self, obj):
        if obj.payment_type == 'pages':
            return format_html('<div style="background: #f3e8ff; padding: 10px; border-radius: 8px; border-left: 4px solid #9333ea;">📄 ПОКУПКА звезд<br>{} стр. за {} ₽</div>', obj.pages_count, obj.amount)
        elif obj.payment_type == 'subscription':
            if obj.parent_payment is None:
                return format_html('<div style="background: #dbeafe; padding: 10px; border-radius: 8px; border-left: 4px solid #2563eb;">🔷 МАТЕРИНСКИЙ ПЛАТЕЖ<br>Первый платеж по тарифу {}</div>', obj.tariff.display_name if obj.tariff else '-')
            else:
                parent_link = reverse('admin:users_paymenthistory_change', args=[obj.parent_payment.id])
                return format_html('<div style="background: #d1fae5; padding: 10px; border-radius: 8px; border-left: 4px solid #059669;">🔶 ДОЧЕРНИЙ ПЛАТЕЖ<br>Привязан к <a href="{}">#{}</a> (InvId: {})<br>Тариф: {}</div>', parent_link, obj.parent_payment.id, obj.parent_payment.invoice_id, obj.tariff.display_name if obj.tariff else '-')
        else:
            return format_html('<div style="background: #f3f4f6; padding: 10px; border-radius: 8px; border-left: 4px solid #6b7280;">❓ НЕИЗВЕСТНЫЙ ТИП</div>')
    payment_type_display_form.short_description = 'Тип платежа'

    def status_colored(self, obj):
        colors = {'pending': 'orange', 'success': 'green', 'failed': 'red', 'refunded': 'gray'}
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', colors.get(obj.status, 'gray'), obj.get_status_display())
    status_colored.short_description = 'Статус'

    actions = ['mark_as_paid', 'mark_as_failed', 'refund_payment']
    def mark_as_paid(self, request, queryset):
        queryset.update(status='success', paid_at=timezone.now())
        self.message_user(request, f'✅ {queryset.count()} платежей отмечены как успешные')
    mark_as_paid.short_description = 'Отметить как оплаченные'
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
        self.message_user(request, f'✅ {queryset.count()} платежей отмечены как неуспешные')
    mark_as_failed.short_description = 'Отметить как неуспешные'
    def refund_payment(self, request, queryset):
        queryset.update(status='refunded')
        self.message_user(request, f'✅ {queryset.count()} платежей отмечены как возвращенные')
    refund_payment.short_description = 'Отметить как возврат'


@admin.register(PageSaleSettings)
class PageSaleSettingsAdmin(admin.ModelAdmin):
    list_display = ('price_per_page', 'min_pages_for_purchase', 'max_pages_for_purchase', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    readonly_fields = ('updated_at',)
    fieldsets = (
        (None, {'fields': ('price_per_page', 'is_active')}),
        (_('Ограничения'), {'fields': ('min_pages_for_purchase', 'max_pages_for_purchase')}),
        (_('Даты'), {'fields': ('updated_at',)}),
    )
    def has_add_permission(self, request):
        return False if self.model.objects.exists() else super().has_add_permission(request)
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'email_verified', 'tariff_info',
                    'pages_display', 'rub_balance', 'can_convert_to_rub', 'shadow_banned', 'is_active',
                    'total_logins', 'date_joined')
    list_filter = ('email_verified', 'shadow_banned', 'is_active', 'is_staff', 'date_joined', 'tariff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('date_joined', 'last_login', 'created_at', 'updated_at', 'subscription_details')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Email verification'), {'fields': ('email_verified', 'email_verification_token', 'email_verification_code')}),
        (_('Тарифы и звезды'), {'fields': ('tariff', 'active_subscription', 'pages_count', 'subscription_details')}),
        (_('Баланс в рублях'), {'fields': ('rub_balance', 'can_convert_to_rub')}),
        (_('Security'), {'fields': ('shadow_banned',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj:
            readonly.append('email')
        return readonly
    def tariff_info(self, obj):
        if obj.tariff:
            if obj.tariff.is_free:
                return format_html('{}<br><small>{} стр. (бесплатно)</small>', obj.tariff.display_name, obj.tariff.pages_count)
            else:
                return format_html('{}<br><small>{} стр. / {} ₽</small>', obj.tariff.display_name, obj.tariff.pages_count, obj.tariff.price)
        return '-'
    tariff_info.short_description = 'Тариф'
    tariff_info.admin_order_field = 'tariff__display_name'
    def pages_display(self, obj):
        color = 'green' if obj.pages_count > 10 else 'orange' if obj.pages_count > 0 else 'red'
        return format_html('<span style="color: {}; font-weight: bold;">{} звезд</span>', color, obj.pages_count)
    pages_display.short_description = 'Звезды'
    def subscription_details(self, obj):
        if obj.active_subscription:
            sub = obj.active_subscription
            return format_html(
                '<div style="background: #f8f9fa; padding: 12px; border-radius: 8px;">'
                '<p><strong>ID подписки:</strong> {}</p>'
                '<p><strong>Тариф:</strong> {}</p>'
                '<p><strong>Статус:</strong> {}</p>'
                '<p><strong>Начало:</strong> {}</p>'
                '<p><strong>Окончание:</strong> {}</p>'
                '<p><strong>Автопродление:</strong> {}</p>'
                '<p><strong>Звезд по тарифу:</strong> {}</p>'
                '</div>',
                sub.subscription_id,
                sub.tariff.display_name if sub.tariff else '-',
                sub.get_status_display(),
                sub.started_at.strftime('%d.%m.%Y %H:%M') if sub.started_at else '-',
                sub.expires_at.strftime('%d.%m.%Y %H:%M') if sub.expires_at else '-',
                'Да' if sub.auto_renew else 'Нет',
                sub.tariff.pages_count if sub.tariff else 0
            )
        return 'Нет активной подписки'
    subscription_details.short_description = 'Детали подписки'
    def total_logins(self, obj):
        total = sum(log.login_count for log in obj.activity_logs.all())
        return format_html('<strong>{}</strong>', total)
    total_logins.short_description = 'Всего входов'
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('tariff', 'active_subscription').prefetch_related('activity_logs')
    actions = ['add_pages_to_users', 'change_tariff_for_users', 'export_users_stats',
               'return_to_free_tariff', 'activate_paid_tariff', 'set_pages_count']
    def add_pages_to_users(self, request, queryset):
        pages_count = request.POST.get('pages_count')
        if pages_count:
            try:
                pages_count = int(pages_count)
                for user in queryset:
                    user.add_pages(pages_count)
                self.message_user(request, f'✅ Добавлено {pages_count} звезд {queryset.count()} пользователям')
            except ValueError:
                self.message_user(request, '❌ Укажите корректное число', level='ERROR')
        else:
            self.message_user(request, '❌ Укажите количество звезд', level='ERROR')
    add_pages_to_users.short_description = 'Добавить звезды выбранным пользователям'
    def set_pages_count(self, request, queryset):
        pages_count = request.POST.get('pages_count')
        if pages_count:
            try:
                pages_count = int(pages_count)
                for user in queryset:
                    user.set_pages(pages_count)
                self.message_user(request, f'✅ Установлено {pages_count} звезд {queryset.count()} пользователям')
            except ValueError:
                self.message_user(request, '❌ Укажите корректное число', level='ERROR')
        else:
            self.message_user(request, '❌ Укажите количество звезд', level='ERROR')
    set_pages_count.short_description = 'Установить точное количество звезд'
    def change_tariff_for_users(self, request, queryset):
        tariff_id = request.POST.get('tariff_id')
        if tariff_id:
            try:
                tariff = Tariff.objects.get(id=tariff_id)
                for user in queryset:
                    user.tariff = tariff
                    user.pages_count = tariff.pages_count
                    user.save()
                self.message_user(request, f'✅ Тариф изменен на "{tariff.display_name}" для {queryset.count()} пользователей')
            except Tariff.DoesNotExist:
                self.message_user(request, '❌ Указанный тариф не существует', level='ERROR')
        else:
            self.message_user(request, '❌ Укажите ID тарифа', level='ERROR')
    change_tariff_for_users.short_description = 'Изменить тариф выбранным пользователям'
    def return_to_free_tariff(self, request, queryset):
        count = 0
        for user in queryset:
            if user.tariff and not user.tariff.is_free:
                user.return_to_free_tariff()
                count += 1
        self.message_user(request, f'✅ {count} пользователей возвращены на бесплатный тариф')
    return_to_free_tariff.short_description = 'Вернуть на бесплатный тариф'
    def activate_paid_tariff(self, request, queryset):
        tariff_id = request.POST.get('tariff_id')
        if tariff_id:
            try:
                tariff = Tariff.objects.get(id=tariff_id, is_free=False)
                for user in queryset:
                    user.activate_paid_tariff(tariff, {'invoice_id': 'admin_activation'})
                self.message_user(request, f'✅ Платный тариф "{tariff.display_name}" активирован для {queryset.count()} пользователей')
            except Tariff.DoesNotExist:
                self.message_user(request, '❌ Указанный платный тариф не существует', level='ERROR')
        else:
            self.message_user(request, '❌ Укажите ID платного тарифа', level='ERROR')
    activate_paid_tariff.short_description = 'Активировать платный тариф'
    def export_users_stats(self, request, queryset):
        import csv
        from django.http import HttpResponse
        from datetime import datetime
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="users_stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Username', 'Email', 'Тариф', 'Тип тарифа', 'Звезд по тарифу',
                         'Текущее количество звезд', 'Статус подписки', 'Окончание подписки',
                         'Дата регистрации', 'Последний вход', 'Email подтвержден', 'Теневой бан'])
        for user in queryset:
            subscription_status = '-'
            subscription_expires = '-'
            if user.active_subscription:
                subscription_status = user.active_subscription.get_status_display()
                subscription_expires = user.active_subscription.expires_at.strftime('%Y-%m-%d') if user.active_subscription.expires_at else '-'
            writer.writerow([
                user.username, user.email,
                user.tariff.display_name if user.tariff else 'Нет',
                'Бесплатный' if user.tariff and user.tariff.is_free else 'Платный' if user.tariff else '-',
                user.tariff.pages_count if user.tariff else 0,
                user.pages_count, subscription_status, subscription_expires,
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else '',
                'Да' if user.email_verified else 'Нет',
                'Да' if user.shadow_banned else 'Нет',
            ])
        return response
    export_users_stats.short_description = 'Экспортировать статистику (CSV)'


@admin.register(UserIPAddress)
class UserIPAddressAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'ip_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('created_at',)
    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user)
    user_link.short_description = 'Пользователь'
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'date', 'login_count', 'last_login_time')
    list_filter = ('date',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date'
    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user)
    user_link.short_description = 'Пользователь'
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_type_display', 'title', 'last_updated_display', 'created_at')
    list_filter = ('document_type', 'last_updated')
    search_fields = ('title', 'content')
    readonly_fields = ('created_at', 'last_updated', 'document_type_info')
    fieldsets = (
        (None, {'fields': ('document_type', 'title')}),
        ('Содержание', {'fields': ('content',)}),
        ('Даты', {'fields': ('created_at', 'last_updated', 'document_type_info')}),
    )
    def document_type_display(self, obj):
        colors = {'privacy': '#2563eb', 'terms': '#9333ea'}
        icons = {'privacy': '🔒', 'terms': '📜'}
        return format_html('<span style="color: {}; font-weight: bold;">{} {}</span>', colors.get(obj.document_type, '#000'), icons.get(obj.document_type, '📄'), obj.get_document_type_display())
    document_type_display.short_description = 'Тип документа'
    def last_updated_display(self, obj):
        return format_html('<span title="{}">{}</span>', obj.last_updated.strftime('%d.%m.%Y %H:%M'), obj.last_updated.strftime('%d.%m.%Y'))
    last_updated_display.short_description = 'Обновлено'
    def document_type_info(self, obj):
        if obj.document_type == 'privacy':
            return mark_safe('<div style="background: #dbeafe; padding: 10px; border-radius: 8px; border-left: 4px solid #2563eb;">🔒 ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ<br>Страница /privacy-policy/</div>')
        elif obj.document_type == 'terms':
            return mark_safe('<div style="background: #f3e8ff; padding: 10px; border-radius: 8px; border-left: 4px solid #9333ea;">📜 ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ<br>Страница /terms-of-service/</div>')
        return '-'
    document_type_info.short_description = 'Информация'
    def has_add_permission(self, request):
        return LegalDocument.objects.count() < 2
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['document_type', 'created_at', 'last_updated', 'document_type_info']
        return ['created_at', 'last_updated', 'document_type_info']


@admin.register(SiteCounter)
class SiteCounterAdmin(admin.ModelAdmin):
    list_display = ('counter_text',)
    def has_add_permission(self, request):
        return SiteCounter.objects.count() == 0


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'stars', 'usage_limit', 'used_count', 'is_active', 'expires_at', 'created_at')
    list_filter = ('is_active', 'expires_at')
    search_fields = ('code',)
    list_editable = ('stars', 'usage_limit', 'is_active')
    readonly_fields = ('used_count', 'created_at')
    fieldsets = (
        (None, {'fields': ('code', 'stars')}),
        ('Ограничения', {'fields': ('usage_limit', 'expires_at', 'is_active')}),
        ('Статистика', {'fields': ('used_count', 'created_at')}),
    )


@admin.register(UserSpending)
class UserSpendingAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'amount', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'

    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'Пользователь'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Основные настройки', {
            'fields': ('title', 'description', 'keywords', 'inn', 'vk_url', 'telegram_url', 'support_email'),
        }),
        ('SEO для блога', {
            'fields': ('blog_title', 'blog_description', 'blog_keywords'),
            'classes': ('wide',),
        }),
        ('SEO для каталога', {
            'fields': ('catalog_title', 'catalog_description', 'catalog_keywords'),
            'classes': ('wide',),
        }),
        ('Дата', {'fields': ('updated_at',)}),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ReferralEarning)
class ReferralEarningAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_rub', 'amount_stars', 'tariff', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email',)
    readonly_fields = ('created_at',)


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'card_number', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email',)
    actions = ['approve_withdrawals', 'reject_withdrawals']

    def approve_withdrawals(self, request, queryset):
        for req in queryset:
            if req.status == 'pending':
                req.status = 'completed'
                req.processed_at = timezone.now()
                req.save()
                # Баланс уже уменьшен при создании запроса, здесь просто отмечаем
        self.message_user(request, f'✅ {queryset.count()} запросов подтверждены.')
    approve_withdrawals.short_description = 'Подтвердить вывод'

    def reject_withdrawals(self, request, queryset):
        for req in queryset:
            if req.status == 'pending':
                req.status = 'cancelled'
                req.processed_at = timezone.now()
                req.save()
                # Возвращаем средства пользователю
                req.user.add_rub(req.amount)
        self.message_user(request, f'✅ {queryset.count()} запросов отклонены, средства возвращены.')
    reject_withdrawals.short_description = 'Отклонить вывод и вернуть средства'