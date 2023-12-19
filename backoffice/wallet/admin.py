from django.contrib import admin
from django.core.exceptions import PermissionDenied
from order.models import Transaction

from .models import Withdrawal, Balance
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission

try:
    Permission.objects.create(codename='wallet.can_change_approved_status', name='Can change Approved withdrawals',
                              content_type=ContentType.objects.get_for_model(Withdrawal))
    Permission.objects.create(codename='wallet.can_change_paid_status', name='Can pay withdrawals',
                              content_type=ContentType.objects.get_for_model(Withdrawal))
except:
    pass


@admin.register(Balance)
class WalletAdmin(admin.ModelAdmin):
    pass


class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ['customer', 'amount', 'currency', 'status', 'created', 'updated']
    readonly_fields = ['created', 'updated']

    def save_model(self, request, obj, form, change):
        if obj.status in ['APPROVED', 'REFUSED'] and not request.user.has_perm('can_change_approved_status'):
            raise PermissionDenied(f'You do not have permission to set status {obj.status}')
        if obj.status in ['PAID', 'CANCELED'] and not request.user.has_perm('can_change_paid_status'):
            raise PermissionDenied(f'You do not have permission to set status {obj.status}')
        if obj.status == 'PAID':
            balance = obj.customer.balance_set.get(balance_link=obj.currency)
            balance.amount = round(balance.amount - obj.amount)
            if balance.amount < 0:
                raise PermissionDenied(f'Inefficient balance')
            balance.save()
            transaction = Transaction(
                sender=obj.customer,
                receiver=obj.customer,
                link=obj.currency,
                amount=obj.amount,
                finished=True,
                type=1,
                status=1
            )
            transaction.save()
            transaction.category = f"Вывод средств #{transaction.id}"
            transaction.save()
        elif obj.status == 'CANCELED':
            transaction = Transaction(
                sender=obj.customer,
                receiver=obj.customer,
                link=obj.currency,
                amount=obj.amount,
                finished=True,
                type=1,
                status=4
            )
            transaction.save()
        super().save_model(request, obj, form, change)


admin.site.register(Withdrawal, WithdrawalAdmin)
