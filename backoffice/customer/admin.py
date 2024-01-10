import datetime
import random
import string
from django.contrib.auth.admin import UserAdmin
from django.contrib import admin
from django.db.models import Count, Sum, F
from django.utils.html import format_html
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Customer, CustomerDocument, InviteCodes, Websites, Traders, Merchants, Request, TraderPaymentMethod, \
    User, Settings, Cards, CardsLimits, WebsitesCategories, MerchantsCategories, Wallet
from wallet.models import Balance
from order.models import Transaction
from currency.models import Currency, PaymentMethods
from interface.utils import send_email


@admin.register(MerchantsCategories)
class MerchantsCategoriesAdmin(admin.ModelAdmin):
    pass


@admin.register(Wallet)
class WalletsAdmin(admin.ModelAdmin):
    list_display = ['address', 'balance', 'trx_balance']
    readonly_fields = ['hex_address', 'address', 'private_key', 'public_key', 'balance', 'trx_balance']

    def balance(self, obj):
        return f'{obj.balance()} USDT'

    def trx_balance(self, obj):
        return f'{obj.trx_balance()} TRX'


class CustomerDocumentInline(admin.TabularInline):
    model = CustomerDocument
    max_num = 1


class CardsLimitsInline(admin.TabularInline):
    model = CardsLimits
    max_num = 1


class WebsitesInline(admin.TabularInline):
    model = Websites
    extra = 0


class BalanceInline(admin.TabularInline):
    model = Balance
    extra = 0
    max_num = 1000


class PaymentMethodsInline(admin.TabularInline):
    model = TraderPaymentMethod
    extra = 0


class TransactionsInline(admin.TabularInline):
    model = Transaction
    fk_name = 'receiver'
    extra = 0


class CardAdmin(admin.ModelAdmin):
    list_display = ['name', 'method', 'currency', 'customer']
    inlines = [CardsLimitsInline]


class CustomerAdmin(admin.ModelAdmin):
    readonly_fields = ['last_login', 'username', 'is_superuser', 'is_staff', 'groups', 'permissions']
    list_display = ['email', 'phone', 'email_is_verified', 'phone_is_verified', 'status']

    inlines = [CustomerDocumentInline, WebsitesInline]


class StaffAdmin(UserAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=True)


class InviteCodesAdmin(admin.ModelAdmin):
    list_display = ['email', 'code', 'status', 'account']

    readonly_fields = ['email', 'code', 'expiry', 'account']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WebsitesAdmin(admin.ModelAdmin):
    list_display = ['domain', 'status']


class BaseCustomerAdmin(admin.ModelAdmin):
    exclude = ['last_login', 'username', 'is_superuser', 'is_staff', 'groups', 'user_permissions', 'date_joined']
    readonly_fields = ['account_type', 'value_2fa', 'password', 'value_2fa', 'wallet', 'key', 'method_2fa']


class TraderAdmin(BaseCustomerAdmin):
    list_display = ('id', 'phone', 'email', 'balance', 'interest_rate', 'status', 'verified')
    readonly_fields = ['category', 'account_type', 'value_2fa', 'password', 'value_2fa', 'wallet', 'key'] #, 'method_2fa'
    inlines = [BalanceInline, CustomerDocumentInline, PaymentMethodsInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(account_type='TRADER').annotate(
            total_balance=Sum('balance__amount'),
            verified=F('customerdocument__status')
        )

    def save_model(self, request, obj, form, change):
        obj.account_type = 'TRADER'
        super().save_model(request, obj, form, change)

    def balance(self, obj):
        return obj.total_balance

    def currency(self, obj):
        return obj.currency

    def verified(self, obj):
        return obj.verified


class MerchantAdmin(BaseCustomerAdmin):
    list_display = ('id', 'created', 'site', 'phone', 'email', 'balance', 'status')
    inlines = [WebsitesInline, BalanceInline, TransactionsInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(account_type='MERCHANT').annotate(
            websites_count=Count('websites'),
            total_balance=Sum('balance__amount'),
        )

    def save_model(self, request, obj, form, change):
        obj.account_type = 'MERCHANT'
        obj.username = obj.email
        super().save_model(request, obj, form, change)

    def site(self, obj):
        return obj.websites_count

    def balance(self, obj):
        return obj.total_balance


class InviteCodesInline(admin.TabularInline):
    model = InviteCodes
    max_num = 1


class RequestAdmin(admin.ModelAdmin):
    list_display = ('created', 'phone', 'email', 'account_type', 'site', 'category', 'status', 'invite_code')
    inlines = [InviteCodesInline]

    def invite_code(self, obj):
        try:
            invite = InviteCodes.objects.get(account=obj)
            color = "red" if invite.expiry.timestamp() <= datetime.datetime.now().timestamp() else "green"
            return format_html(
                f'<a class="related-widget-wrapper-link change-related" id="change_id_account" data-href-template="/admin/customer/request/__fk__/change/?_to_field=id&amp;_popup=1" data-popup="yes" request""=""  href="/admin/customer/invitecodes/{invite.id}/change/?_to_field=id&amp;_popup=1" style="color: {color}">{invite.code}</a>'
            )
        except InviteCodes.DoesNotExist:
            return None

    invite_code.short_description = 'Invite Code'

    actions = ['add_invite_code']

    def add_invite_code(self, request, queryset):
        for request_obj in queryset:
            if not InviteCodes.objects.filter(account=request_obj).exists():
                code = generate_new_code()
                text = f"""Здравствуйте! 
Ваша заявка на регистрацию мерчанта одобрена. Пройти регистрацию Вы можете по ссылке: ... 
Инвайт код: {code}. 
Обращаем внимание, что срок действия кода ограничен."
                """
                send_email(request_obj.email, "Заявка на регистрацию одобрена", text)
                expiry = datetime.datetime.now() + datetime.timedelta(days=Settings.objects.first().invite_expiration)
                new_invite_code = InviteCodes(account=request_obj, code=code, status=0, email=request_obj.email, expiry=expiry)
                new_invite_code.save()

    add_invite_code.short_description = 'Add Invite Code'


def generate_new_code():
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(12))
    return random_string


class CurrencyInlines(admin.TabularInline):
    model = Currency


class PaymentMethodInline(admin.TabularInline):
    model = PaymentMethods


class SettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Trader settings', {
            'fields': ('trader_deposit_limit', 'trader_limit', 'min_limit', 'fix_commission'),
        }),
        ('Merchant settings', {
            'fields': ('merchant_deposit', 'commission_in', 'commission_out', 'withdrawals_limit', 'withdrawal_min',
                       'new_merchants_limit', 'order_life', 'min_order_amount'),
        }),
        ('Registration settings', {
            'fields': ('max_registration_tries', 'withdrawal_block', 'phone_restriction', 'max_ip_requests',
                       'max_phone_retries', 'invite_expiration'),
        }),
        ('Verification settings ', {
            'fields': ('website_verification', 'dns_salt'),
        }),
        ('Core settings', {
            'fields': ('min_traders', 'min_amounts', 'max_limit', 'logout_in'),
        }),
        ('Notifications', {
            'fields': ('trader_inactive_push', 'inactive_email'),
        }),
        ('System wallet', {
            'fields': ('system_wallet_address', 'system_wallet_private_key', 'trx_balance', 'usdt_balance'),
        }),
    )

    # inlines = [CurrencyInlines, PaymentMethodInline]

    readonly_fields = ['trx_balance', 'usdt_balance']

    def trx_balance(self, obj):
        return f'{obj.trx_balance()} TRX'

    def usdt_balance(self, obj):
        return f'{obj.usdt_balance()} USDT'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class WebsiteCategoriesAdmin(admin.ModelAdmin):
    pass


@receiver(post_save, sender=CustomerDocument)
def customer_document_status_change(sender, instance, **kwargs):
    if instance.status == 'verified':
        text = f"""Здравствуйте! 
Ваша заявка на верификацию личности одобрена. 
Теперь вы можете внести депозит и начать работу на платформе"""
        send_email(instance.customer.email, "Верификация успешно пройдена", text)


admin.site.register(Request, RequestAdmin)
admin.site.register(Traders, TraderAdmin)
admin.site.register(Merchants, MerchantAdmin)
admin.site.register(Websites, WebsitesAdmin)
admin.site.register(InviteCodes, InviteCodesAdmin)
admin.site.unregister(User)
admin.site.register(User, StaffAdmin)
admin.site.register(Cards, CardAdmin)
admin.site.register(Settings, SettingsAdmin)
admin.site.register(WebsitesCategories, WebsiteCategoriesAdmin)
