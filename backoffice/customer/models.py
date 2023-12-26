import datetime
import uuid

import pyotp
from django.db import models
from django.db.models import Sum, F
from django.urls import reverse
from django.contrib.auth.models import User

from currency.models import Currency, PaymentMethods, ExchangeDirection
from django.utils import timezone
from django.core.cache import cache

# from wallet.models import Balance

OPENING_STATUSES = [
    ('pending', 'PENDING'),
    ('completed', 'COMPLETED'),
    ('rejected', 'REJECTED'),
]

VERIFICATION_STATUSES = [
    ('request', 'Verification request'),
    ('pending', 'Verification pending'),
    ('verified', 'Verified'),
    ('rejected', 'Verification rejected'),
]

ACCOUNT_TYPES = [
    ('MERCHANT', 'Merchant'),
    ('TRADER', 'Trader'),
]

ACCOUNT_STATUSES = [
    ('active', 'Active'),
    ('blocked', 'Blocked'),
]

KYC_TYPES = [
    ('INIT', 'Initial'),
    ('BLOCKED', 'Blocked'),
]

CUSTOMER_STATUSES = [
    ('NEW', 'New'),
    ('ACTIVE', 'Active'),
    ('Inactive', 'INACTIVE'),
]

CODES_STATUSES = [
    (0, 'New'),
    (1, 'Used'),
    (2, 'Deactivated')
]

WEBSITES_STATUSES = [
    (0, 'New'),
    (1, 'Active'),
    (2, 'Rejected'),
    (3, 'Blocked')
]

PAYMENT_METHODS = [
    (0, 'On system page'),
    (1, 'JS popup')
]

WEBSITES_VERIFICATION = [
    (0, 'Verification pending'),
    (1, 'Verified'),
    (2, 'Not verified'),
    (3, 'Verification rejected')
]

REQUEST_STATUSES = [
    (0, 'New'),
    (1, 'Paused'),
    (2, 'Approved'),
    (3, 'Rejected')
]


def default_expiry():
    return timezone.now() + datetime.timedelta(days=Settings.objects.first().invite_expiration)


class Settings(models.Model):
    trader_deposit_limit = models.IntegerField(verbose_name="Депозит трейдер (лимит)")
    trader_limit = models.IntegerField(verbose_name="Кол-во заявок трейдера на вывод в сутки")
    min_limit = models.IntegerField(verbose_name="Лимит трейдера на минимальную сумму вывода")
    fix_commission = models.IntegerField(verbose_name="Фикс % трейдер")

    merchant_deposit = models.IntegerField(verbose_name="Депозит мерчант (лимит)")
    commission_in = models.IntegerField(verbose_name="Комиссия системы инвойс клиентам")
    commission_out = models.IntegerField(verbose_name="Комиссия системы вывод")
    withdrawals_limit = models.IntegerField(verbose_name="Кол-во заявок мерчанта на вывод в сутки")
    withdrawal_min = models.IntegerField(verbose_name="Лимит мерчанта на минимальную сумму вывода")
    new_merchants_limit = models.IntegerField(verbose_name="Лимиты для новых мерчантов")
    order_life = models.IntegerField(verbose_name="Срок действия ордера (для клиента)")

    max_registration_tries = models.IntegerField(verbose_name='Кол-во попыток ввода кода подтверждения')
    withdrawal_block = models.IntegerField(verbose_name='Блок на вывод средств после смены email/телефон')
    phone_restriction = models.IntegerField(verbose_name="Запрет на использование “освобожденного телефона/email")
    max_ip_requests = models.IntegerField(verbose_name="Кол-во запросов с одного ip")
    max_phone_retries = models.IntegerField(verbose_name="Кол-во регистраций с одного телефона")
    invite_expiration = models.IntegerField(verbose_name="Срок действия инвайт кода")

    website_verification = models.BooleanField(verbose_name="Обязательность верификации сайта мерчанта")
    dns_salt = models.CharField(verbose_name="Соль для кода верификации для TXT в DNS ")

    min_traders = models.IntegerField(verbose_name="Минимальное количество активных трейдеров")
    min_amounts = models.IntegerField(verbose_name="Минимальные остатки по лимитам активных трейдеров (в USDT)")
    max_limit = models.IntegerField(
        verbose_name="Максимальный процент отношения общей суммы заявок за последние 10 минут к остаткам по лимитам всех активных трейдеров (в %)")
    logout_in = models.IntegerField(verbose_name="Разлогинивать через")

    trader_inactive_push = models.IntegerField(verbose_name="Пуш уведомление о “засыпании” трейдера")
    inactive_email = models.IntegerField(verbose_name="Email уведомление о неактивности")

    def __str__(self):
        return 'Processing settings'


class WebsitesCategories(models.Model):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class Request(models.Model):
    phone = models.CharField(max_length=256)
    email = models.EmailField(blank=False, unique=True)
    site = models.CharField(max_length=256)
    category = models.ForeignKey(WebsitesCategories, on_delete=models.CASCADE, null=True, blank=True,
                                 verbose_name='Категория')
    status = models.IntegerField(choices=REQUEST_STATUSES)
    expiry = models.DateField(default=default_expiry)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "request"
        ordering = ('created', 'status')
        verbose_name = 'Request'
        verbose_name_plural = 'Requests'

    def __str__(self):
        return f'Заявка №{self.id}'


class Admin(User):
    account_type = models.CharField(max_length=256, choices=[('ADMIN', 'Admin')])


class MerchantsCategories(models.Model):
    name = models.CharField(max_length=128)
    fees_in = models.FloatField()
    fees_out = models.FloatField()


class Customer(User):
    is_staff = None
    is_superuser = None
    permissions = None
    groups = None
    account_type = models.CharField(max_length=256, choices=ACCOUNT_TYPES)
    account_status = models.CharField(max_length=256, choices=ACCOUNT_STATUSES)
    status = models.CharField(max_length=256, choices=CUSTOMER_STATUSES)
    category = models.ForeignKey(MerchantsCategories, on_delete=models.CASCADE, blank=True, null=True)
    # email = models.EmailField(blank=False, unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    telegram_id = models.CharField(max_length=128, blank=True, null=True)
    email_is_verified = models.BooleanField(default=False)
    phone_is_verified = models.BooleanField(default=False)
    # password = models.CharField(max_length=1024, blank=True, null=True)
    key = models.CharField(max_length=1024)
    lang_code = models.CharField(max_length=10)
    method_2fa = models.IntegerField(blank=True, null=True)
    value_2fa = models.CharField(max_length=1024, blank=True, null=True)
    time_zone = models.IntegerField()
    # last_login = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    interest_rate = models.FloatField(null=True, blank=True)
    personal_course = models.FloatField(null=True, blank=True, verbose_name="Individual course")

    def verification_status(self):
        return self.customerdocument_set.first().get_status_display() if self.customerdocument_set.first() else 'Not started'

    def total_balance(self):
        total_balance = self.balance_set.aggregate(
            total_balance=models.Sum(models.F('amount') / models.F('balance_link__currency__denomination'))
        ).get('total_balance', 0)
        return total_balance or 0

    def frozen_balance(self):
        total_balance = self.balance_set.aggregate(
            total_balance=models.Sum(models.F('frozen') / models.F('balance_link__currency__denomination'))
        ).get('total_balance', 0)
        return total_balance or 0

    def notifications(self):
        return self.notifications_set.filter(read=False).all()

    def unread_notifications(self):
        return len(self.notifications_set.filter(read=False).all())

    def uri_2fa(self):
        return pyotp.totp.TOTP(self.value_2fa).provisioning_uri(
            name=self.email,
            issuer_name='Processing')

    def can_withdraw(self):
        if cache.get(f'restriction:{self.email}'):
            return False
        if self.account_type == 'MERCHANT':
            return Settings.objects.first().withdrawals_limit > len(self.withdrawal_set.filter(created__range=[datetime.datetime.now()-datetime.timedelta(days=1), datetime.datetime.now()]).all())
        else:
            if self.verification_status() != 'Verified':
                return False
            return Settings.objects.first().trader_limit > len(self.withdrawal_set.filter(created__range=[datetime.datetime.now()-datetime.timedelta(days=1), datetime.datetime.now()]).all())

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "customer"
        ordering = ('email',)
        verbose_name = 'Customer'
        verbose_name_plural = 'Customer'

    def __str__(self):
        return self.email


class CustomerDocument(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    status = models.CharField(max_length=100, choices=VERIFICATION_STATUSES, default='request')
    passport_number = models.CharField(max_length=100, verbose_name='Номер паспорта')
    authority = models.CharField(max_length=100, verbose_name="Кем выдан")
    date_of_issue = models.DateField(verbose_name="Дата выдачи")
    date_of_birth = models.DateField(verbose_name="Дата рождения")
    passport_scan_1 = models.FileField(upload_to='documents', blank=True, verbose_name="Фото первой страницы паспорта")
    passport_scan_2 = models.FileField(upload_to='documents', blank=True, verbose_name="Фото страницы с пропиской")
    passport_video = models.FileField(upload_to='videos', blank=True, verbose_name="Видео")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_documents"
        ordering = ('created',)
        verbose_name = "Customer document"
        verbose_name_plural = "Customer documents"


class InviteCodes(models.Model):
    email = models.CharField(max_length=100)
    code = models.CharField(max_length=15)
    status = models.IntegerField(choices=CODES_STATUSES)
    account = models.ForeignKey(Request, on_delete=models.CASCADE)
    expiry = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_invite_codes"
        ordering = ('created',)
        verbose_name = "Invite code"
        verbose_name_plural = "Invite codes"

    def __str__(self):
        return f'Invite code {self.code}'


class Traders(Customer):
    class Meta:
        proxy = True
        verbose_name = "Trader"
        verbose_name_plural = "Traders"


class Merchants(Customer):
    class Meta:
        proxy = True
        verbose_name = "Merchant"
        verbose_name_plural = "Merchants"


class Websites(models.Model):
    merchant = models.ForeignKey(Customer, on_delete=models.CASCADE)
    domain = models.CharField(max_length=128, verbose_name='Домен')
    description = models.CharField(max_length=1024, verbose_name='Описание')
    category = models.ForeignKey(WebsitesCategories, on_delete=models.CASCADE, null=True, blank=True,
                                 verbose_name='Категория')
    status = models.IntegerField(choices=WEBSITES_STATUSES, default=0)
    payment_method = models.IntegerField(choices=PAYMENT_METHODS, default=0, verbose_name='Метод платежей')
    verified = models.IntegerField(choices=WEBSITES_VERIFICATION, default=0)
    verification_code = models.CharField(max_length=64, auto_created=uuid.uuid4, default=uuid.uuid4)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, verbose_name='Валюта инвойса')
    key = models.CharField(max_length=128, auto_created=uuid.uuid4, default=uuid.uuid4)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "customer_websites"
        ordering = ('created',)
        verbose_name = "Website"
        verbose_name_plural = "Websites"

    def __str__(self):
        return self.domain


class TraderPaymentMethod(models.Model):
    method = models.ForeignKey(PaymentMethods, on_delete=models.CASCADE)
    customer = models.ForeignKey(Traders, on_delete=models.CASCADE)
    payment_details = models.CharField(max_length=256)
    initials = models.CharField(max_length=256)

    class Meta:
        db_table = "customer_traderpaymentmethod"
        verbose_name = "Trader payment method"
        verbose_name_plural = "Trader payment methods"


class Cards(models.Model):
    name = models.CharField(max_length=256, verbose_name='Никнейм карты')
    method = models.ForeignKey(PaymentMethods, on_delete=models.CASCADE, verbose_name='Банк')
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, verbose_name='Валюта')
    customer = models.ForeignKey(Traders, on_delete=models.CASCADE)
    payment_details = models.CharField(max_length=19, verbose_name='Номер карты')
    initials = models.CharField(max_length=256, verbose_name='Инициалы владельца карты')
    status = models.BooleanField(verbose_name='Карта активна')
    last_used = models.DateTimeField(default=datetime.datetime(1970, 1, 1, 0, 0))

    def limits(self):
        return self.cardslimits

    class Meta:
        db_table = "customer_cards"
        verbose_name = "Card"
        verbose_name_plural = "Cards"


class CardsLimits(models.Model):
    card = models.OneToOneField(Cards, on_delete=models.CASCADE)
    input_min_limit = models.IntegerField()
    input_operation_limit = models.IntegerField()
    input_day_limit = models.IntegerField()
    input_month_limit = models.IntegerField()
    output_min_limit = models.IntegerField()
    output_operation_limit = models.IntegerField()
    output_dat_limit = models.IntegerField()
    output_month_limit = models.IntegerField()

    class Meta:
        db_table = "customer_cardslimits"
        verbose_name = "Card limits"
        verbose_name_plural = "Cards limits"


class TraderExchangeDirections(models.Model):
    trader = models.ForeignKey(Traders, on_delete=models.CASCADE)
    direction = models.ForeignKey(ExchangeDirection, on_delete=models.CASCADE)
    input = models.BooleanField()
    output = models.BooleanField()


class Notifications(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    title = models.CharField(max_length=128)
    body = models.CharField(max_length=1024)
    link = models.CharField(max_length=128)
    category = models.CharField(max_length=32)
    read = models.BooleanField(default=False)

    class Meta:
        db_table = "customer_notifications"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
