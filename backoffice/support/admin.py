from django.contrib import admin
from django.db import transaction
from django.db.models import Sum, Count, Q
from customer.models import Notifications
from .models import Ticket, TicketMessage, FAQ


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    min_num = 0


class FAQAdmin(admin.ModelAdmin):
    list_display = ['title']


class TicketAdmin(admin.ModelAdmin):
    list_display = ['id', 'client', 'priority', 'unread_messages']
    inlines = [TicketMessageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            unread_messages=Count('ticketmessage', filter=(Q(ticketmessage__read=False) & Q(ticketmessage__author=0)))
        )

    def save_model(self, request, obj, form, change):
        notification = Notifications(
            customer=obj.client,
            title=f"Новые сообщения по тикету №{obj.id}",
            body=f"Новые сообщения по тикету №{obj.id}",
            link=f'/ticket/{obj.id}',
            category='support'
        )
        notification.save()
        super().save_model(request, obj, form, change)
        obj.ticketmessage_set.filter(ticket=obj).update(read=True)

    def unread_messages(self, obj):
        return obj.unread_messages


admin.site.register(Ticket, TicketAdmin)
admin.site.register(FAQ, FAQAdmin)
