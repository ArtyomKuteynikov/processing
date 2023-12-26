import csv

from django.contrib import admin
from django.db.models import Count, Sum, F
from customer.models import Notifications
from django.http import HttpResponse

from .models import Transaction, Order, Statistics
from interface.utils import send_tg


class TransactionAdmin(admin.ModelAdmin):
    list_display = ['created', 'sender', 'receiver', 'amount', 'link', 'category', 'status', 'counted', 'denomination']

    def denomination(self, obj):
        return obj.link.currency.denomination

    def save_model(self, request, obj, form, change):
        if obj.type == 0 and obj.status == 1:
            balance = obj.sender.balance_set.get(balance_link=obj.link)
            balance.amount = round(balance.amount + obj.amount)
            balance.save()
            notification=Notifications(
                customer=obj.sender,
                title=f"Баланс пополнен",
                body=f"Баланс аккаунта пополнен на {obj.amount/obj.link.currency.denomination}",
                link='/transactions',
                category='input'
            )
            notification.save()
            try:
                send_tg(obj.sender.telegram_id, notification.body)
            except:
                pass
        super().save_model(request, obj, form, change)


class OrderAdmin(admin.ModelAdmin):
    # change_list_template = 'admin/orders.html'
    list_display = ('id', 'created', 'sender', 'order_site', 'amount_counted', 'currency', 'status')

    def currency(self, obj):
        return obj.input_link.currency.ticker if obj.input_link else ''

    def amount_counted(self, obj):
        return obj.input_amount/obj.input_link.currency.denomination if obj.input_link else 0


class StatisticsAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_type', 'sender', 'site', 'customer_status', 'currency', 'amount_counted', 'type', 'status', 'created')
    list_filter = ('sender__account_type', 'site', 'sender__account_status', 'link__currency__name', 'type', 'status', 'created')

    actions = ["export_csv"]

    def export_csv(self, request, queryset):
        # Prepare CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="transactions_report.csv"'

        # Create CSV writer
        writer = csv.writer(response)
        writer.writerow(['ID', 'Customer Type', 'Customer', 'Site', 'Customer Status', 'Currency', 'Transaction Type', 'Transaction Status', 'Created'])

        for obj in queryset:
            writer.writerow([obj.id, obj.sender.account_type, obj.sender, obj.site, obj.sender.account_status,
                             obj.link.currency.name, obj.get_type_display(), obj.get_status_display(), obj.created])

        return response

    export_csv.short_description = ".CSV"

    def changelist_view(self, request, extra_context=None):
        # Your existing code for filtering and grouping goes here

        return super().changelist_view(request, extra_context=extra_context)

    def site(self, obj):
        return obj.link.currency.denomination

    def amount_counted(self, obj):
        return obj.amount/obj.link.currency.denomination

    def customer_type(self, obj):
        return obj.sender.account_type

    def customer_status(self, obj):
        return obj.sender.account_status

    def currency(self, obj):
        return obj.link.currency.name

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Order, OrderAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Statistics, StatisticsAdmin)
