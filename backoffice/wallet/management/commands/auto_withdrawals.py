import time
import requests
from django.core.management.base import BaseCommand
from order.models import Transaction
from currency.models import Links, Currency, Networks
from interface.utils import send_tg
from customer.models import Notifications, Customer, Settings
from wallet.models import Withdrawal, Balance
import hashlib


class Command(BaseCommand):
    help = 'Auto withdrawal transactions'

    def handle(self, *args, **kwargs):
        while True:
            try:
                for withdrawal in Withdrawal.objects.filter(status='APPROVED').all():
                    balance = Balance.objects.filter(account=withdrawal.customer, balance_link=withdrawal.currency).first()
                    denomination = withdrawal.currency.currency.denomination
                    balance_amount = balance.frozen / denomination
                    if balance_amount < withdrawal.amount / denomination:
                        withdrawal.status = 'CANCELED'
                        withdrawal.save()
                        transaction = Transaction(
                            sender=withdrawal.customer,
                            receiver=withdrawal.customer,
                            link=withdrawal.currency,
                            amount=withdrawal.amount,
                            finished=True,
                            type=1,
                            status=4
                        )
                        transaction.save()
                        notification = Notifications(
                            customer=withdrawal.customer,
                            title=f"Запросу №{withdrawal.id} на вывод средств отменен",
                            body=f"Запросу №{withdrawal.id} на вывод средств отменен",
                            link='/withdrawals',
                            category='withdrawal'
                        )
                        notification.save()
                        try:
                            send_tg(withdrawal.customer.telegram_id, notification.body)
                        except:
                            pass
                    balance.frozen = balance.frozen - withdrawal.amount
                    balance.save()
                    settings = Settings.objects.first()
                    result = withdrawal.customer.wallet.transfer(withdrawal.address, (withdrawal.amount / denomination) - 2)
                    commission = withdrawal.customer.wallet.transfer(settings.system_wallet_address, 2)
                    if result['receipt']['result'] != 'SUCCESS':
                        withdrawal.status = 'CANCELED'
                        withdrawal.save()
                        transaction = Transaction(
                            sender=withdrawal.customer,
                            receiver=withdrawal.customer,
                            link=withdrawal.currency,
                            amount=withdrawal.amount,
                            finished=True,
                            type=1,
                            status=4
                        )
                        transaction.save()
                        notification = Notifications(
                            customer=withdrawal.customer,
                            title=f"Запросу №{withdrawal.id} на вывод средств отменен",
                            body=f"Запросу №{withdrawal.id} на вывод средств отменен",
                            link='/withdrawals',
                            category='withdrawal'
                        )
                        notification.save()
                        try:
                            send_tg(withdrawal.customer.telegram_id, notification.body)
                        except:
                            pass
                    else:
                        balance.amount = withdrawal.customer.wallet.balance() * denomination - balance.frozen
                        balance.save()
                        transaction = Transaction(
                            sender=withdrawal.customer,
                            receiver=withdrawal.customer,
                            link=withdrawal.currency,
                            amount=withdrawal.amount,
                            finished=True,
                            type=1,
                            status=1
                        )
                        transaction.save()
                        transaction.category = f"Вывод средств #{transaction.id}"
                        transaction.save()
                        notification = Notifications(
                            customer=withdrawal.customer,
                            title=f"Средства по запросу №{withdrawal.id} выведены",
                            body=f"Средства по запросу №{withdrawal.id} выведены",
                            link='/withdrawals',
                            category='withdrawal'
                        )
                        notification.save()
                        try:
                            send_tg(withdrawal.customer.telegram_id, notification.body)
                        except:
                            pass
                        withdrawal.status = 'PAID'
                        withdrawal.save()
                time.sleep(300)
            except Exception as e:
                print(e)
