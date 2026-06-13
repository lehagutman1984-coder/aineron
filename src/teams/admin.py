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
        count = 0
        for invoice in queryset.filter(status=Invoice.Status.PENDING).select_related('organization'):
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = timezone.now()
            invoice.save(update_fields=['status', 'paid_at'])
            invoice.organization.balance_rub += invoice.amount_rub
            invoice.organization.save(update_fields=['balance_rub'])
            count += 1
        self.message_user(request, f'Оплачено и зачислено: {count} счетов')
