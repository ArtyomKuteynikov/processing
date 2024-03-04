import datetime
import random
import time
import uuid
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi.encoders import jsonable_encoder
from redis import asyncio as aioredis
from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio as aio
from prices.price_updater import market_update
from models.schemas import CreateOrder
from config.database import engine, get_async_session
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload, subqueryload, selectinload
from config.main import Settings, LINK
from telegram_bot.order import start, marked_as_payed, success, cancel, out_order, send_tg
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from models import Customer, Order, Balance, Link, Currency, ExchangeDirection, TraderPaymentMethod, User, Network, \
    Websites, Transaction, SettingsModel, Notification
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_pagination import Page, add_pagination, paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from config.main import SECRET_AUTH
import jwt

disable_installed_extensions_check()

app = FastAPI(
    title="Time4Pay",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE", "PATCH", "PUT"],
    allow_headers=["Content-Type", "Set-Cookie", "Access-Control-Allow-Headers", "Access-Control-Allow-Origin",
                   "Authorization"],
)

add_pagination(app)

templates = Jinja2Templates(directory="templates")


ORDER_STATUS = {
    0: 'New',
    1: 'Trader found',
    2: 'Marked as payed',
    3: 'Success',
    4: 'Declined',
    5: 'Timeout at user',
    6: 'Timeout at trader',
    7: 'Canceled by user',
    8: 'Partially or incorrect payment',
    9: 'Solved partially or incorrect payment by support',
    10: 'Complaint',
    11: 'Solved to sender',
    12: 'Solved to trader',
}


def clean_phone(phone):
    return phone.replace('(', '').replace(')', '').replace('-', '').replace('+', '').replace(' ', '')


@AuthJWT.load_config
def get_config():
    return Settings()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


async def get_user_by_id(id: int, session: AsyncSession):
    result = await session.execute(select(Customer).where((Customer.user_ptr_id == id)))
    user = result.first()
    if user:
        return user[0]
    return None


async def get_trading_pair(direction: ExchangeDirection, session: AsyncSession):
    result = await session.execute(
        select(ExchangeDirection, Link, Currency).join(Link, ExchangeDirection.input_id == Link.id).join(Currency,
                                                                                                         Link.currency_id == Currency.id).where(ExchangeDirection.id == direction.id))
    pair = result.fetchone()
    if pair:
        return await redis_pool.get(
                    f"market_price:{pair[0].input_currency.currency.ticker}:{pair[0].output_currency.currency.ticker}")
    return 1


async def get_exchange_directions(session: AsyncSession):
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
    return pairs


async def get_asset_by_link_id(id: int, session: AsyncSession):
    result = await session.execute(select(Link).where((Link.id == id)))
    user = result.first()
    if user:
        result = await session.execute(select(Currency).where(Currency.id == user[0].currency_id))
        user = result.first()
        if user:
            return user[0].ticker
    return None


async def get_asset_denomination(id: int, session: AsyncSession):
    result = await session.execute(select(Link).where((Link.id == id)))
    user = result.first()
    if user:
        result = await session.execute(select(Currency).where(Currency.id == user[0].currency_id))
        user = result.first()
        if user:
            return user[0].denomination
    return 1


async def get_user_by_key(key: str, session: AsyncSession):
    result = await session.execute(select(Customer).where((Customer.key == key)))
    user = result.first()
    if user:
        return user[0]
    return None


async def authenticate_user(username: str, password: str, session: AsyncSession):
    result = await session.execute(
        select(Customer).join(User).options(joinedload(Customer.user)).where(
            (User.email == username) | (Customer.phone == clean_phone(username))
        )
    )
    user = result.first()
    if user and user[0].verify_password(password):
        return user[0]
    return None


async def timeout_limit(session: AsyncSession, order_id: int):
    TIME_LIMIT = (await session.execute(select(SettingsModel))).first()[0].order_life * 60
    await aio.sleep(TIME_LIMIT - 1)
    order = await session.execute(select(Order).where(Order.id == order_id))
    order = order.fetchone()
    if order:
        if order[0].status in [0, 2] and order[0].side == "OUT":
            balance = await session.execute(
                select(Balance).where((Balance.account_id == order[0].sender_id) & (Balance.balance_link_id == order[0].output_link_id)))
            balance = balance.fetchone()
            transactions = await session.execute(select(Transaction).where(Transaction.other_id_1 == order[0].id))
            transactions = transactions.fetchall()
            for transaction in transactions:
                balance[0].amount = balance[0].amount + transaction[0].amount
                balance[0].frozen = balance[0].frozen - transaction[0].amount
                transaction[0].status = 4
                transaction[0].finished = True
                await session.commit()
        elif order[0].status in [0, 1] and order[0].side == 'IN':
            balance = await session.execute(
                select(Balance).where(
                    (Balance.account_id == order[0].trader_id) & (Balance.balance_link_id == order[0].output_link_id)))
            balance = balance.fetchone()
            transactions = await session.execute(select(Transaction).where(Transaction.other_id_1 == order[0].id))
            transactions = transactions.fetchall()
            for transaction in transactions:
                balance[0].amount = balance[0].amount + transaction[0].amount
                balance[0].frozen = balance[0].frozen - transaction[0].amount
                transaction[0].status = 4
                transaction[0].finished = True
                await session.commit()
        if (order[0].status in [0, 1] and order[0].side == 'IN') or (order[0].status in [0, 2] and order[0].side == 'OUT'):
            order[0].status = 5
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.first()
            notification = Notification(
                customer_id=trader[0].user_ptr_id,
                title=f"Ордер №{order[0].id} таймаут",
                body=f"Ордер отменен по таймауту у клиента",
                link='/orders',
                category='order'
            )
            session.add(notification)
            await session.commit()
            send_tg(trader[0].telegram_id, f"Ордер №{order[0].id} отменен по таймауту у клиента")
        elif (order[0].status in [2] and order[0].side == 'IN') or (order[0].status in [1] and order[0].side == 'OUT'):
            order[0].status = 6
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.fetchone()
            if trader:
                trader[0].status = 'Inactive'
                await session.commit()
                notification = Notification(
                    customer_id=trader[0].user_ptr_id,
                    title=f"Ордер №{order[0].id} таймаут",
                    body=f"Ордер отменен по таймауту, ваш статус изменен на НЕАКТИВЕН",
                    link='/orders',
                    category='order'
                )
                session.add(notification)
                await session.commit()
                send_tg(trader[0].telegram_id, f"Ордер №{order[0].id} отменен по таймауту, ваш статус изменен на НЕАКТИВЕН")


async def order_create(data: CreateOrder, user_id: int, session: AsyncSession):
    course = await redis_pool.get(f"market_price:USDT:RUB")
    result = await session.execute(select(Currency).where((Currency.ticker == data.output_link.split('_')[0])))
    currency = result.first()
    result = await session.execute(select(Network).where((Network.short_name == data.output_link.split('_')[1])))
    network = result.first()
    if not currency or not network:
        return None, 406
    website = await session.execute(select(Websites).where((Websites.key == data.website_key) & (Websites.merchant_id == user_id)))
    website = website.first()
    if not website:
        return None, 401
    if (await session.execute(select(SettingsModel))).first()[0].website_verification:
        if website[0].verified != 1 or website[0].status != 1:
            return None, 403
    output_link = await session.execute(select(Link).where((Link.currency_id == currency[0].id) & (Link.network_id == network[0].id)))
    output_link = output_link.first()
    if data.amount:
        amount = round(data.amount * currency[0].denomination)
        quantity = round((data.amount * float(course)) * currency[0].denomination)
    elif data.quantity:
        amount = round((data.quantity / float(course)) * currency[0].denomination)
        quantity = round(data.quantity * currency[0].denomination)
    else:
        return None, 406
    result = await session.execute(
        select(Balance).where((Balance.account_id == user_id) & (Balance.balance_link_id == output_link[0].id)))
    balance = result.first()
    if not balance:
        return None, 402
    if balance[0].amount < amount and data.side == "OUT":
        return None, 402
    trader_id = None
    order_id = str(uuid.uuid4())
    new_order = Order(
        sender_id=user_id,
        output_link_id=output_link[0].id,
        order_site_id=website[0].id,
        input_amount=quantity,
        output_amount=amount,
        comment=data.comment,
        status=0,
        uuid=order_id,
        created=datetime.datetime.now(),
        updated=datetime.datetime.now(),
        side=data.side,
        trader_id=trader_id,
        external_id=data.external,
        client_id=data.client,
        client_contact=data.client_contact
    )
    session.add(new_order)
    order = new_order
    await session.commit()
    return new_order, 0


async def order_get(order_id: int, user_id: int, session: AsyncSession):
    result = await session.execute(select(Order).where((Order.id == order_id)))
    user = result.first()
    if user:
        if user[0].sender_id == user_id or user[0].trader_id == user_id:
            return user[0]
    return None


async def balances_get(user_id: int, session: AsyncSession, link: int | None = None):
    if link:
        result = await session.execute(
            select(Balance).where((Balance.account_id == user_id) & (Balance.balance_link_id == link)))
    else:
        result = await session.execute(select(Balance).where((Balance.account_id == user_id)))
    user = result.all()
    return user


redis_pool = None


@app.on_event("startup")
async def startup_event():
    global redis_pool
    redis = aioredis.from_url("redis://127.0.0.1:6379",
                              encoding="utf8", decode_responses=True)
    redis_pool = redis
    # aio.create_task(ticker_update(redis_pool))
    aio.create_task(market_update(redis_pool))
    FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")


@app.on_event("shutdown")
async def shutdown_event():
    global redis_pool
    await redis_pool.close()


@app.get('/v1/authtoken', tags=['Account'])
async def get_authtoken(username: str, password: str, session: AsyncSession = Depends(get_async_session)):
    if not username:
        raise HTTPException(status_code=401, detail="incorrect_username")
    if not password:
        raise HTTPException(status_code=401, detail="incorrect_password")
    user = await authenticate_user(username, password, session)
    if user is None:
        raise HTTPException(
            status_code=401, detail="Incorrect username or password")
    if not user.key:
        user.set_token()
        await session.commit()
    access_token = user.key
    return JSONResponse(status_code=200, content={'access_token': access_token,
                                                  'customer_id': user.user_ptr_id,
                                                  'account_type': user.account_type,
                                                  'status': user.status})


@app.delete('/v1/authtoken', tags=['Account'])
async def delete_authtoken(key: str, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(key, session)
    if user is None:
        raise HTTPException(status_code=401, detail="INCORRECT KEY")
    user.reset_token()
    await session.commit()
    return JSONResponse(status_code=200, content={'status': 'TOKEN_DELETED'})


@app.post('/v1/order', tags=['Order'])
async def create_order(data: CreateOrder, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(data.key, session)
    if user is None:
        raise HTTPException(status_code=401, detail="INCORRECT KEY")
    min_amount = (await session.execute(select(SettingsModel))).first()[0].min_order_amount
    course = await redis_pool.get(f"market_price:USDT:RUB")
    if data.amount:
        quantity = round((data.amount * float(course)))
    else:
        quantity = round(data.quantity)
    if quantity < min_amount:
        raise HTTPException(status_code=400, detail=f"MIN ORDER AMOUNT IS {min_amount} RUB")
    order, status_code = await order_create(data, user.user_ptr_id, session)
    if not order:
        raise HTTPException(status_code=status_code)
    aio.create_task(timeout_limit(session, order.id))
    if order:
        return JSONResponse(status_code=200, content={
            'link': f'{LINK}/order/start/{order.uuid}',
            'order_id': order.id,
            'output_link_id': await get_asset_by_link_id(order.output_link_id, session),
            'order_site_id': order.order_site_id,
            'input_amount': order.input_amount / 100,
            'output_amount': order.output_amount / await get_asset_denomination(order.output_link_id, session),
            'status': ORDER_STATUS[order.status],
            'uuid': order.uuid
        })
    else:
        raise HTTPException(status_code=404)


@app.get('/v1/order/{order_id}', tags=['Order'])
async def order(order_id: int, key: str, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(key, session)
    if user is None:
        raise HTTPException(status_code=403, detail="INCORRECT KEY")
    order = await order_get(order_id, user.user_ptr_id, session)
    if not order:
        raise HTTPException(status_code=404, detail="ORDER NOT FOUND")
    return JSONResponse(status_code=200, content={
        'order_id': order.id,
        'trader_id': order.trader_id,
        'input_link_id': await get_asset_by_link_id(order.input_link_id, session),
        'output_link_id': await get_asset_by_link_id(order.output_link_id, session),
        'order_site_id': order.order_site_id,
        'input_amount': order.input_amount / await get_asset_denomination(order.input_link_id, session),
        'output_amount': order.output_amount / await get_asset_denomination(order.output_link_id, session),
        'create_at': order.created.strftime("%d.%m.%Y %H:%M:%S"),
        'updated_at': order.updated.strftime("%d.%m.%Y %H:%M:%S"),
        'status': ORDER_STATUS[order.status],
        'side': order.side,
        'uuid': order.uuid,
        'client_id': order.client_id,
        'external_id': order.external_id,
        'client_contact': order.client_contact
    })


@app.get('/v1/courses', tags=['Market'])
async def course(currency: str | None = None, session: AsyncSession = Depends(get_async_session)):
    data = []
    pairs = set(await get_exchange_directions(session))
    pairs = [pair for pair in pairs if currency.upper() in pair] if currency else [pair for pair in pairs]
    for pair in pairs:
        data.append({
            'currency_in': pair[0],
            'currency_out': pair[1],
            'price': await redis_pool.get(f"market_price:{pair[0]}:{pair[1]}")
        })
    return JSONResponse(status_code=200, content={
        'courses': data
    })


@app.get('/v1/balance', tags=['Account'])
async def balance(key: str, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(key, session)
    if user is None:
        raise HTTPException(status_code=403, detail="INCORRECT KEY")
    balances = await balances_get(user.user_ptr_id, session)
    data = []
    for i in balances:
        data.append({
            'currency': await get_asset_by_link_id(i[0].balance_link_id, session),
            'amount': i[0].amount / await get_asset_denomination(i[0].balance_link_id, session)
        })
    return JSONResponse(status_code=200, content={
        'balance': data
    })
