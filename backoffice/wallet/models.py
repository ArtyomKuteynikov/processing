from django.db import models
from customer.models import Customer
from currency.models import Links

# Create your models here.

WITHDRAWALS_STATUSES = [
    ('NEW', 'New'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
    ('PAID', 'Paid'),
    ('CANCELED', 'Canceled'),
]


class Balance(models.Model):
    account = models.ForeignKey(Customer, on_delete=models.CASCADE)
    balance_link = models.ForeignKey(Links, on_delete=models.CASCADE)
    amount = models.FloatField()
    frozen = models.FloatField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def get_balance(self):
        return self.amount / self.balance_link.currency.denomination

    def __str__(self):
        return f"{self.account.email}'s {self.balance_link} wallet"

    class Meta:
        db_table = "wallet_balance"
        ordering = ('created',)
        verbose_name = "Balance"
        verbose_name_plural = "Balances"


class Withdrawal(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.FloatField()
    currency = models.ForeignKey(Links, on_delete=models.CASCADE)
    address = models.CharField(max_length=1000)
    comment = models.CharField(max_length=1000, null=True, blank=True)
    status = models.CharField(choices=WITHDRAWALS_STATUSES)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wallet_withdrawal"
        ordering = ('created',)
        verbose_name = "Withdrawal"
        verbose_name_plural = "Withdrawals"
