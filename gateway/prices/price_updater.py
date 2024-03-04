import asyncio
import bs4
import requests
from fastapi import Depends
from redis import asyncio as aioredis
import ccxt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from config.database import async_session_maker
from models import ExchangeDirection, Link, Currency
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


EXCHANGES = ['binance', 'okx']
ASSETS = ['USD', 'EUR', 'RUB']


def grantex(fiat, crypto):
    asks = [float(i['price']) for i in Bybit.call(fiat, crypto, '1') if
            float(i['lastQuantity']) * float(i['price']) >= 100000]
    price_ask = asks[2] if len(asks) >= 3 else asks[-1] if asks else 0

    return price_ask


async def get_exchange_directions():
    async with async_session_maker() as session:
        session = session
    result = await session.execute(select(ExchangeDirection))
    pairs = []
    results = result.all()
    for i in results:
        result = await session.execute(select(Link).where((Link.id == i[0].input_id)))
        result = result.first()
        if result:
            asset = await session.execute(select(Currency).where((Currency.id == result[0].currency_id)))
            asset = asset.first()
            result = await session.execute(select(Link).where((Link.id == i[0].output_id)))
            result = result.first()
            if result:
                currency = await session.execute(select(Currency).where((Currency.id == result[0].currency_id)))
                currency = currency.first()
                if asset and currency:
                    pairs.append((asset[0].ticker, currency[0].ticker))
    await session.close()
    return pairs


async def current_price(asset, currency, redis_pool):
    try:
        price = grantex(asset, currency)
    except:
        try:
            price = grantex(currency, asset)
        except:
            price = 0
    await redis_pool.set(f"market_price:{asset}:{currency}", price, ex=600)


def values(exchange_name, asset, redis_pool, currency='USDT'):
    exchange = getattr(ccxt, exchange_name)()
    ticker = exchange.fetch_ticker(f'{asset}/{currency}')
    ohlcv = exchange.fetch_ohlcv(f'{asset}/{currency}', timeframe='1d', limit=1)
    ohlcv_h = exchange.fetch_ohlcv(f'{asset}/{currency}', timeframe='1h', limit=24)
    close_values = [tick[4] for tick in ohlcv_h]
    mid_value = sum(close_values) / len(close_values)
    redis_pool.set(f"ask:{exchange_name}:{asset}:{currency}", ticker['ask'], ex=600)
    redis_pool.set(f"bid:{exchange_name}:{asset}:{currency}", ticker['bid'], ex=600)
    redis_pool.set(f"high:{exchange_name}:{asset}:{currency}", ohlcv[0][2], ex=600)
    redis_pool.set(f"low:{exchange_name}:{asset}:{currency}", ohlcv[0][3], ex=600)
    redis_pool.set(f"mid:{exchange_name}:{asset}:{currency}", mid_value, ex=600)


def ticker_update(redis_pool):
    for exchange_name in EXCHANGES:
        for asset in ASSETS:
            values(exchange_name, asset, redis_pool)


async def market_update(redis_pool):
    while True:
        try:
            pairs = set(await get_exchange_directions())
            pairs = [pair for pair in pairs]
            for pair in pairs:
                await current_price(pair[0], pair[1], redis_pool)
            await asyncio.sleep(10)
        except Exception as e:
            print('Price updater error: ', e)
