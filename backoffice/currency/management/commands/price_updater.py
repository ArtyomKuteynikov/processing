import time

import requests
from django.core.management import BaseCommand
from currency.models import Courses


def grantex(symbol):
    r = requests.get(f'https://garantex.org/api/v2/depth?market={symbol.lower()}')

    if not 'bids' in r.json():
        return 0, 0

    bids = [i for i in r.json()['bids'] if float(i['price']) * float(i['volume']) >= 200000]
    asks = [i for i in r.json()['asks'] if float(i['price']) * float(i['volume']) >= 200000]

    price_bid = bids[0]['price'] if bids else 0
    price_ask = asks[0]['price'] if asks else 0

    return price_bid, price_ask


def commex(symbol):
    r = requests.get(f'https://api.commex.com/api/v1/depth?limit=1000&symbol={symbol}')

    if not 'bids' in r.json():
        return 0, 0

    bids = [i for i in r.json()['bids'] if float(i[0]) * float(i[1]) >= 200000]
    asks = [i for i in r.json()['asks'] if float(i[0]) * float(i[1]) >= 200000]

    price_bid = bids[0][0] if bids else 0
    price_ask = asks[0][0] if asks else 0

    return price_bid, price_ask


def binance(symbol):
    r = requests.get(f'https://api.binance.com/api/v3/depth?limit=1000&symbol={symbol}')
    if not 'bids' in r.json():
        return 0, 0
    bids = [i for i in r.json()['bids'] if float(i[0]) * float(i[1]) >= 200000]
    asks = [i for i in r.json()['asks'] if float(i[0]) * float(i[1]) >= 200000]

    price_bid = bids[0][0] if bids else 0
    price_ask = asks[0][0] if asks else 0

    return price_bid, price_ask


class Command(BaseCommand):
    help = 'Update assets and currencies prices'

    def handle(self, *args, **kwargs):
        while True:
            try:
                courses = Courses.objects.all()
                for pair in courses:
                    pair.binance_in, pair.binance_out = binance(pair.pair)
                    pair.commex_in, pair.commex_out = commex(pair.pair)
                    pair.grantex_in, pair.grantex_out = grantex(pair.pair)
                    pair.save()
                time.sleep(60)
            except Exception as e:
                print(e)
