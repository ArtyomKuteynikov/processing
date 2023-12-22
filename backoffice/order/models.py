import modeltranslation.thread_context
import uuid
from django.db import models
from customer.models import Customer, Websites, Cards
from currency.models import Links
from currency.models import Currency, PaymentMethods

ORDER_TYPE = [
    ('Pending', 'Pending'),
    ('Sending', 'Sending')
]

ORDER_STATUS = [
    (0, 'New'),
    (1, 'Trader found'),
    (2, 'Marked as payed'),
    (3, 'Success'),
    (4, 'Declined'),
    (5, 'Timeout at user'),
    (6, 'Timeout at trader'),
    (7, 'Canceled by user'),
    (8, 'Partially or incorrect payment'),
    (9, 'Solved partially or incorrect payment by support'),
    (10, 'Complaint'),
    (11, 'Solved to sender'),
    (12, 'Solved to trader'),
]

TRANSACTION_STATUSES = [
    (0, 'New'),
    (1, 'Success'),
    (2, 'Froze at sender'),
    (3, 'Froze ar receiver'),
    (4, 'Canceled'),
]

TRANSACTION_TYPES = [
    (0, 'Deposit'),
    (1, 'Withdrawal'),
    (2, 'Client order'),
    (3, 'Repay'),
    (4, 'Input order'),
    (5, 'Output order'),
    (6, 'Commission')
]

COUNTED = [
    ('-2', 'Not counted at sender'),
    ('-1', 'Not counted at receiver'),
    ('0', 'Not counted'),
    ('1', 'Counted'),
    ('2', 'In counting process')
]

ORDER_SIDES = [
    ('IN', 'In'),
    ('OUT', 'Out')
]


class Transaction(models.Model):
    sender = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='transaction_sender')
    receiver = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='receiver')
    site = models.ForeignKey(Websites, on_delete=models.CASCADE, null=True, blank=True)
    link = models.ForeignKey(Links, on_delete=models.CASCADE)
    amount = models.FloatField()
    finished = models.BooleanField()
    type = models.IntegerField(choices=TRANSACTION_TYPES)
    status = models.IntegerField(choices=TRANSACTION_STATUSES)
    counted = models.CharField(max_length=2, choices=COUNTED)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    other_id_1 = models.IntegerField(null=True, blank=True)
    other_id_2 = models.IntegerField(null=True, blank=True)
    category = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        db_table = "order_transaction"
        ordering = ('created',)
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"


class Statistics(Transaction):
    class Meta:
        proxy = True
        verbose_name = "Statistics"
        verbose_name_plural = "Statistics"


class Order(models.Model):
    sender = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='order_sender')
    trader = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='trader', null=True)
    input_link = models.ForeignKey(Links, on_delete=models.CASCADE, related_name='order_input', null=True)
    output_link = models.ForeignKey(Links, on_delete=models.CASCADE, related_name='order_output', null=True)
    order_site = models.ForeignKey(Websites, on_delete=models.CASCADE, null=True)
    input_amount = models.FloatField(null=True)
    output_amount = models.FloatField(null=True)
    status = models.IntegerField(choices=ORDER_STATUS)
    comment = models.CharField(max_length=1024, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    uuid = models.CharField(max_length=128)
    method = models.ForeignKey(Cards, on_delete=models.CASCADE, null=True, blank=True)
    side = models.CharField(max_length=4, choices=ORDER_SIDES)
    client_id = models.IntegerField()
    external_id = models.IntegerField()

    class Meta:
        db_table = "order_order"
        ordering = ('created',)
        verbose_name = "Order"
        verbose_name_plural = "Orders"
