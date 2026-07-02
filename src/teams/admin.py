from django.contrib import admin
from django.utils import timezone
from .models import Organization, OrganizationMember, OrganizationInvite, Invoice


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'inn', 'owner', 'balance_rub', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'inn', 'owner__email']
    raw_id_fields = ['owner']


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ['organization', 'user', 'role', 'created_at']
    list_filter = ['role']
    raw_id_fields = ['organization', 'user']


@admin.register(OrganizationInvite)
class OrganizationInviteAdmin(admin.ModelAdmin):
    list_display = ['organization', 'email', 'is_accepted', 'expires_at', 'created_at']
    list_filter = ['is_accepted']
    search_fields = ['email', 'organization__name']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['number', 'organization', 'amount_rub', 'status', 'created_at', 'paid_at']
    list_filter = ['status', 'created_at']
    search_fields = ['number', 'organization__name']
    actions = ['mark_paid']

    @admin.action(description='Отметить оплаченными и зачислить баланс')
    def mark_paid(self, request, queryset):
        from django.db.models import F
        from .models import Organization

        count = 0
        for invoice in queryset.filter(status=Invoice.Status.PENDING).select_related('organization'):
            # Атомарный гейт по статусу: повторный клик/параллельный админ
            # не зачислит баланс дважды.
            claimed = Invoice.objects.filter(
                pk=invoice.pk, status=Invoice.Status.PENDING,
            ).update(status=Invoice.Status.PAID, paid_at=timezone.now())
            if not claimed:
                continue
            # F(): параллельное списание орг-баланса ботом не потеряется.
            Organization.objects.filter(pk=invoice.organization_id).update(
                balance_rub=F('balance_rub') + invoice.amount_rub
            )
            count += 1
        self.message_user(request, f'Оплачено и зачислено: {count} счетов')
