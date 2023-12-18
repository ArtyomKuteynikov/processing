from django.contrib import admin
from django.db.models import Count, Sum, F

from .models import Transaction, Order, Statistics


class TransactionAdmin(admin.ModelAdmin):
    list_display = ['created', 'sender', 'receiver', 'amount', 'link', 'category', 'status', 'counted', 'denomination']

    def denomination(self, obj):
        return obj.link.currency.denomination

    def save_model(self, request, obj, form, change):
        if obj.type == 0 and obj.status == 1:
            balance = obj.sender.balance_set.get(balance_link=obj.link)
            balance.amount = round(balance.amount + obj.amount)
            balance.save()
        super().save_model(request, obj, form, change)


class OrderAdmin(admin.ModelAdmin):
    # change_list_template = 'admin/orders.html'
    list_display = ('id', 'created', 'sender', 'order_site', 'input_amount', 'currency', 'status')

    def currency(self, obj):
        return obj.output_link.currency.ticker


class StatisticsAdmin(admin.ModelAdmin):
    list_display = ['created', 'receiver', 'amount', 'link', 'category', 'status', 'counted',]
    date_hierarchy = 'created'
    list_filter = ('amount', )

    def site(self, obj):
        return obj.link.currency.denomination

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )
        print(dir(request), request.path_info, request.read(), request.content_params, extra_context)
        try:
            qs = response.context_data['cl'].queryset
        except (AttributeError, KeyError):
            return response
        print(qs)

        metrics = {
            'total': Count('id'),
            'total_sales': Sum('amount'),
        }
        response.context_data['summary'] = list(
            qs.annotate(**metrics).order_by('-created')
        )

        return response


admin.site.register(Order, OrderAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Statistics, StatisticsAdmin)
