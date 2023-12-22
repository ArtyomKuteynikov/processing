from redis import asyncio as aioredis

redis = aioredis.from_url("redis://skyline_redis", encoding="utf8", decode_responses=True)
redis_pool = redis


def MAX(*a):
    return max(a)


def ask(exchange_name, asset):
    return float(redis_pool.get(f"ask:{exchange_name}:{asset}:USDT"))


def bid(exchange_name, asset):
    return float(redis_pool.get(f"bid:{exchange_name}:{asset}:USDT"))


def high(exchange_name, asset):
    return float(redis_pool.get(f"high:{exchange_name}:{asset}:USDT"))


def low(exchange_name, asset):
    return float(redis_pool.get(f"low:{exchange_name}:{asset}:USDT"))


def mid(exchange_name, asset):
    return float(redis_pool.get(f"mid:{exchange_name}:{asset}:USDT"))


async def market(asset):
    try:
        return float(await redis_pool.get(f"market_price:binance:{asset}:USDT"))
    except:
        return 0.0


def count_price(expression):
    try:
        return {'success': True, 'result': eval(expression)}
    except Exception as e:
        return {'success': False, 'error': str(e)}
