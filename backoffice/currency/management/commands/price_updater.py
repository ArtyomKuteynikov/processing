import time

import requests
from django.core.management import BaseCommand
from currency.models import Courses
import json


class Bybit:
    URL = 'https://api2.bybit.com/fiat/otc/item/online'
    HEADERS = {
        'Accept': 'application/json',
        'Accept-Language': 'ru-RU',
        'Content-Type': 'application/json;charset=UTF-8',
        'Lang': 'ru-RU',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
    }

    RUB = {
        'amount': '100000',
        'authMaker': True,
        'canTrade': False,
        'currencyId': 'RUB',
        'page': '1',
        'payment': ['582', '585'],  # Sber
        'side': '1',  # 1 buy, 0 sell
        'size': '100',
        'tokenId': 'USDT',
        'userId': ''
    }

    UZS = {
        'amount': '1000000',
        'authMaker': False,
        'canTrade': False,
        'currencyId': 'UZS',
        'page': '1',
        'payment': ['282'],  # HUMO
        'side': '1',
        'size': '5',
        'tokenId': 'USDT',
        'userId': ''
    }

    KZT = {
        'userId': '',
        'tokenId': 'USDT',
        'currencyId': 'KZT',
        'payment': ['280'],  # Altyn Bank
        'side': '1',
        'size': '5',
        'page': '1',
        'amount': '',
        'authMaker': False,
        'canTrade': False
    }

    UAH = {
        'userId': '',
        'tokenId': 'USDT',
        'currencyId': 'UAH',
        'payment': ['43'],  # Monobank
        'side': '1',
        'size': '5',
        'page': '1',
        'amount': '',
        'authMaker': False,
        'canTrade': False
    }

    CURRENCY_PARAMS = {
        'UZS': UZS,
        'RUB': RUB,
        'KZT': KZT,
        'UAH': UAH
    }

    @staticmethod
    def call(currency, crypto, side):
        params = Bybit.CURRENCY_PARAMS[currency].copy()
        params['side'] = side
        params['tokenId'] = crypto
        response = requests.post(Bybit.URL, headers=Bybit.HEADERS, data=json.dumps(params))
        return response.json()['result']['items']


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
    crypto = symbol.upper().replace('RUB', '')
    asks = [float(i['price']) for i in Bybit.call('RUB', crypto, '0') if float(i['lastQuantity']) * float(i['price']) >= 100000]
    bids = [float(i['price']) for i in Bybit.call('RUB', crypto, '1') if float(i['lastQuantity']) * float(i['price']) >= 100000]
    price_ask = asks[2] if len(asks) >= 3 else asks[-1] if asks else 0
    price_bid = bids[2] if len(bids) >= 3 else bids[-1] if bids else 0

    return price_ask, price_bid


def binance(symbol):
    r = requests.get(f'https://api-aws.huobi.pro/market/depth?symbol={symbol.lower()}&type=step0')
    if not 'tick' in r.json():
        return 0, 0
    bids = [i for i in r.json()['tick']['bids'] if float(i[0]) * float(i[1]) >= 1000]
    asks = [i for i in r.json()['tick']['asks'] if float(i[0]) * float(i[1]) >= 1000]

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
