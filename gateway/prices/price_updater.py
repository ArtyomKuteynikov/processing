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

EXCHANGES = ['binance', 'okx']
ASSETS = ['USD', 'EUR', 'RUB']


def grantex(symbol):
    try:
        r = requests.get(f'https://garantex.org/api/v2/depth?market={symbol.lower()}')

        if not 'bids' in r.json():
            return 0, 0

        bids = [i for i in r.json()['bids'] if float(i['price']) * float(i['volume']) >= 200000]
        asks = [i for i in r.json()['asks'] if float(i['price']) * float(i['volume']) >= 200000]

        price_bid = float(bids[0]['price']) if bids else 0
        price_ask = float(asks[0]['price']) if asks else 0

        return round((price_bid + price_ask) / 2, 2)
    except:
        return 92


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
    exchange = getattr(ccxt, 'binance')()
    try:
        price = grantex(f'{asset}{currency}')
    except:
        price = grantex(f'{currency}{asset}')
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
            await asyncio.sleep(60)
        except Exception as e:
            print(e)
