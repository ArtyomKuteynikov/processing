import time
import requests
from django.core.management.base import BaseCommand
from order.models import Transaction
from currency.models import Links, Currency, Networks
from interface.utils import send_tg
from customer.models import Notifications, Customer
import hashlib
from processing import settings


def generate_token(hash_value, access_key, access_id):
    token_string = f"{hash_value}:{access_key}:{access_id}"
    token = hashlib.md5(token_string.encode()).hexdigest()
    return token


def check_transaction(transaction_id, address, locale='en_US', flow='fast', asset='TRX', direction='deposit'):
    endpoint = "https://extrnlapiendpoint.silencatech.com/"
    access_key = "ScvPzWdKEf-cbyTA2V-keZDpvpW-pDFBm0XpX-DgtVjuWqCZ-sZIkbs64-xNXGTyz-ouLbqmtUo"
    access_id = 'BBF7D-DC887-8AE89E3'
    token = generate_token(transaction_id, access_key, access_id)
    parameters = {
        'accessId': access_id,
        'locale': locale,
        'hash': transaction_id,
        'address': address,
        'direction': direction,
        'asset': asset,
        'flow': flow,
        'token': token
    }
    response = requests.post(endpoint, data=parameters, headers={"accept": "application/x-www-form-urlencoded"})
    if response.status_code != 200:
        return True
    if 'data' not in response.json():
        return True
    return float(response.json()['data']['riskscore']) < 0.5


def get_transactions(account_id, customer):
    url = f"https://nile.trongrid.io/v1/accounts/{account_id}/transactions/trc20" if settings.DEBUG else f"https://api.trongrid.io/v1/accounts/{account_id}/transactions/trc20"
    params = {'only_to': True, 'only_confirmed': True, 'limit': 20,}
    r = requests.get(url, params=params, headers={"accept": "application/json"})
    params['fingerprint'] = r.json().get('meta', {}).get('fingerprint')
    for tr in r.json().get('data', []):
        transaction_id = tr.get('transaction_id')
        symbol = tr.get('token_info', {}).get('symbol')
        v = tr.get('value', '')
        dec = -1 * int(tr.get('token_info', {}).get('decimals', '6'))
        f = float(v[:dec] + '.' + v[dec:])
        if Transaction.objects.filter(transaction_id=transaction_id).first():
            continue
        currency = Currency.objects.get(ticker=symbol)
        network = Networks.objects.get(short_name='TRC20')
        link = Links.objects.get(currency=currency, network=network)
        if not link:
            continue
        if True:  # check_transaction(transaction_id, account_id):
            transaction = Transaction(
                sender=customer,
                receiver=customer,
                link=link,
                amount=f * link.currency.denomination,
                finished=True,
                type=0,
                status=1,
                counted=1,
                transaction_id=transaction_id
            )
            transaction.save()
            transaction.category = f"Пополнение аккаунта #{transaction.id}"
            transaction.save()
            balance = transaction.sender.balance_set.get(balance_link=transaction.link)
            balance.amount = round(balance.amount + transaction.amount)
            balance.save()
        else:
            transaction = Transaction(
                sender=customer,
                receiver=customer,
                link=link,
                amount=f * link.currency.denomination,
                finished=True,
                type=0,
                status=4,
                counted=1,
                transaction_id=transaction_id
            )
            transaction.save()
            transaction.category = f"Пополнение аккаунта #{transaction.id}"
            transaction.save()
        notification = Notifications(
            customer=transaction.sender,
            title=f"Баланс пополнен",
            body=f"Баланс аккаунта пополнен на {transaction.amount / transaction.link.currency.denomination} {symbol}",
            link='/transactions',
            category='input'
        )
        notification.save()
        try:
            send_tg(transaction.sender.telegram_id, notification.body)
        except:
            pass


class Command(BaseCommand):
    help = 'Catch deposit transactions'

    def handle(self, *args, **kwargs):
        while True:
            for customer in Customer.objects.filter(account_type="TRADER").all():
                if customer.wallet:
                    get_transactions(customer.wallet.address, customer)
            time.sleep(300)

