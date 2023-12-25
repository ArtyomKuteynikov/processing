from django.contrib import admin
from .models import Currency, Networks, PaymentMethods, Links, ExchangeDirection, Courses
# Register your models here.


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ['name', 'ticker', 'active']


class NetworksAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'standard', 'active']


class PaymentMethodsAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_name', 'active']


class LinksAdmin(admin.ModelAdmin):
    list_display = ['currency', 'network', 'method']


class ExchangesDirectionsAdmin(admin.ModelAdmin):
    list_display = ['output', 'input', 'active']


class CoursesAdmin(admin.ModelAdmin):
    list_display = ['pair', 'binance_in', 'binance_out', 'commex_in', 'commex_out', 'grantex_in', 'grantex_out']
    readonly_fields = ['binance_in', 'binance_out', 'commex_in', 'commex_out', 'grantex_in', 'grantex_out']


admin.site.register(Currency, CurrencyAdmin)
admin.site.register(Networks, NetworksAdmin)
admin.site.register(PaymentMethods, PaymentMethodsAdmin)
admin.site.register(Links, LinksAdmin)
admin.site.register(ExchangeDirection, ExchangesDirectionsAdmin)
admin.site.register(Courses, CoursesAdmin)
