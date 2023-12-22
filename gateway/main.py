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
from telegram_bot.order import start, marked_as_payed, success, cancel, out_order
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from models import Customer, Order, Balance, Link, Currency, ExchangeDirection, TraderPaymentMethod, User, Network
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi_pagination import Page, add_pagination, paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from config.main import SECRET_AUTH
import jwt

disable_installed_extensions_check()

app = FastAPI(
    title="Processing",
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

COMMISSION = 2
TIME_LIMIT = 600


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


async def release_crypto(order_id: int, session: AsyncSession):
    order = await session.execute(select(Order).where(Order.id == order_id))
    order = order.fetchone()
    if order:
        amount = order[0].input_amount
        merchant_balance = await session.execute(select(Balance).where((Balance.account_id == order[0].sender_id) &
                                                                       (Balance.balance_link_id == order[
                                                                           0].input_link_id)))
        merchant_balance = merchant_balance.fetchone()
        if not merchant_balance:
            merchant_balance = Balance(
                account_id=order[0].sender_id,
                balance_link_id=order[0].input_link_id,
                amount=0
            )
            session.add(merchant_balance)
            await session.commit()
        trader_balance = await session.execute(select(Balance).where((Balance.account_id == order[0].trader_id) &
                                                                     (Balance.balance_link_id == order[
                                                                         0].input_link_id)))
        trader_balance = trader_balance.fetchone()
        if not trader_balance:
            trader_balance = Balance(
                account_id=order[0].sender_id,
                balance_link_id=order[0].input_link_id,
                amount=0
            )
            session.add(trader_balance)
            await session.commit()
            trader_balance = [trader_balance]
        if order[0].side == 'IN':
            trader_balance[0].amount = trader_balance[0].amount - amount - amount * (COMMISSION / 100)
            merchant_balance[0].amount = merchant_balance[0].amount + amount
        else:
            merchant_balance[0].amount = merchant_balance[0].amount - amount - amount * (COMMISSION / 100)
            trader_balance[0].amount = trader_balance[0].amount + amount
        await session.commit()


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
    await aio.sleep(TIME_LIMIT - 1)
    order = await session.execute(select(Order).where(Order.id == order_id))
    order = order.fetchone()
    if order:
        if order[0].status in [0, 1]:
            order[0].status = 5
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.first()
            await cancel(trader[0].telegram_id, order[0].uuid)
        elif order[0].status in [2]:
            order[0].status = 6
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.fetchone()
            if trader:
                trader[0].status = 'Inactive'
                await session.commit()
                await cancel(trader[0].telegram_id, order[0].uuid)


async def order_create(data: CreateOrder, user_id: int, session: AsyncSession):
    course = await redis_pool.get(f"market_price:USDT:RUB")
    result = await session.execute(select(Currency).where((Currency.ticker == data.output_link.split('_')[0])))
    currency = result.first()
    result = await session.execute(select(Network).where((Network.short_name == data.output_link.split('_')[1])))
    network = result.first()
    if not currency or not network:
        return
    output_link = session.execute(select(Link).where(Link.currency_id == currency[0].id) & (Link.network_id == network[0].id))
    if data.amount:
        amount = round(data.amount * currency[0].denomination)
        quantity = round((data.amount * course) * currency[0].denomination)
    elif data.quantity:
        amount = round((data.quantity / course) * currency[0].denomination)
        quantity = round(data.quantity * currency[0].denomination)
    else:
        return
    trader_id = None
    order_id = str(uuid.uuid4())
    if data.side == 'OUT':
        payment_methods = await session.execute(
            select(TraderPaymentMethod).where((TraderPaymentMethod.method_id == input_link[0].method_id)))
        payment_methods = payment_methods.all()
        traders = []
        for i in payment_methods:
            customer = await get_user_by_id(i[0].customer_id, session)
            if not customer:
                continue
            if customer.status == 'ACTIVE':
                traders.append((i[0].customer_id, i[0].id, customer))
        if not traders:
            return
        trader = random.choice(traders)
        if trader:
            trader_id = trader[0]
        trader = await get_user_by_id(trader_id, session)
        await out_order(order_id, amount, currency[0].ticker, trader.telegram_id, data.payment_detail, data.initials)
    new_order = Order(
        sender_id=user_id,
        input_link_id=input_link[0].id,
        output_link_id=output_link[0].id,
        order_site_id=data.website,
        input_amount=amount,
        output_amount=quantity,
        comment=data.comment,
        status=0 if data.side == 'IN' else 1,
        uuid=order_id,
        created=datetime.datetime.now(),
        side=data.side,
        payment_details=data.payment_detail,
        initials=data.initials,
        trader_id=trader_id
    )
    session.add(new_order)
    await session.commit()
    return new_order


async def order_get(order_id: int, user_id: int, session: AsyncSession):
    result = await session.execute(select(Order).where((Order.id == order_id)))
    user = result.first()
    if user:
        if user[0].sender_id == user_id or user[0].trader_id == user_id:
            return user[0]
    return None


async def order_status_get(order_id: str, session: AsyncSession):
    result = await session.execute(select(Order).where((Order.uuid == order_id)))
    user = result.first()
    if user:
        return user[0].status
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
    order = await order_create(data, user.user_ptr_id, session)
    if not order:
        raise HTTPException(status_code=404)
    aio.create_task(timeout_limit(session, order.id))
    if order:
        return JSONResponse(status_code=200, content={
            'link': f'{LINK}/order-start/{order.uuid}' if data.side == 'IN' else f'{LINK}/order/{order.uuid}',
            'order_id': order.id,
            'input_link_id': order.input_link_id,
            'output_link_id': order.output_link_id,
            'order_site_id': order.order_site_id,
            'input_amount': order.input_amount,
            'output_amount': order.output_amount,
            'status': order.status,
            'uuid': order.uuid
        })
    else:
        raise HTTPException(status_code=404)


@app.get('/order-start/{order_id}', tags=['Page'], include_in_schema=False)
async def order_start(request: Request, order_id: str, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    if order[0].status != 0:
        return RedirectResponse(f"/order/{order_id}")
    return templates.TemplateResponse("chose_method.html", {
        'request': request,
        'order_id': order_id,
    })


@app.get('/v1/order-put/{order_id}', tags=['Page'], include_in_schema=False)
async def chose_payment_method(order_id: str, method: int, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    if not order:
        raise HTTPException(status_code=404)
    if order[0].trader_id:
        raise HTTPException(status_code=404)
    payment_methods = await session.execute(
        select(TraderPaymentMethod).where((TraderPaymentMethod.method_id == method)))
    payment_methods = payment_methods.all()
    traders = []
    for i in payment_methods:
        balance = await balances_get(i[0].customer_id, session, link=order[0].output_link_id)
        if not balance:
            continue
        if balance[0][0].amount < order[0].output_amount:
            continue
        customer = await get_user_by_id(i[0].customer_id, session)
        if not customer:
            continue
        if customer.status == 'ACTIVE':
            traders.append((i[0].customer_id, i[0].id, customer))
    if traders:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        trader = random.choice(traders)
        result = await session.execute(select(Link).where((Link.id == order[0].output_link_id)))
        result = result.first()
        currency = await session.execute(select(Currency).where((Currency.id == result[0].currency_id)))
        currency = currency.first()
        await start(order_id, order[0].output_amount / currency[0].denomination, 'RUB', customer.telegram_id)
        order[0].trader_id = trader[0]
        order[0].method_id = trader[1]
        order[0].status = 1
        await session.commit()
    return RedirectResponse(f"/order/{order_id}")


@app.get('/v1/order-status/{order_id}', tags=['Order'])
async def order_status(order_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = result.first()
    if not order:
        raise HTTPException(status_code=404, detail="ORDER NOT FOUND")
    if TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())) <= 0:
        if order[0].status in [0, 1]:
            order[0].status = 5
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.first()
            await cancel(trader[0].telegram_id, order[0].uuid)
        elif order[0].status in [2]:
            order[0].status = 6
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
            trader = trader.fetchone()
            if trader:
                trader[0].status = 'Inactive'
                await session.commit()
                await cancel(trader[0].telegram_id, order[0].uuid)
    return JSONResponse(status_code=200, content={
        'status': order[0].status,
    })


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
        'input_link_id': order.input_link_id,
        'output_link_id': order.output_link_id,
        'order_site_id': order.order_site_id,
        'input_amount': order.input_amount,
        'output_amount': order.output_amount,
        'create_at': int(order.created.timestamp() * 1000),
        'updated_at': int(order.updated.timestamp() * 1000),
        'status': 0,
        'uuid': order.uuid
    })


@app.get('/v1/courses', tags=['Market'])
async def course(currency: str | None = None, session: AsyncSession = Depends(get_async_session)):
    data = []
    pairs = await get_exchange_directions(session)
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
            'amount': i[0].amount
        })
    return JSONResponse(status_code=200, content={
        'balance': data
    })


@app.get('/order/payed/{order_id}', tags=['Page'], include_in_schema=False)
async def order_payed(order_id: str, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    customer = await get_user_by_id(order[0].trader_id, session)
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 1:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 2
        await session.commit()
        if order[0].side == 'IN':
            await marked_as_payed(customer.telegram_id, customer.key, order[0].uuid)
    if order[0].side == 'IN':
        return RedirectResponse(f"/order/{order_id}")
    else:
        return RedirectResponse(f"https://t.me/processing_notifier_bot")


@app.get('/order/cancel/{order_id}', tags=['Page'], include_in_schema=False)
async def order_payed(order_id: str, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    customer = await get_user_by_id(order[0].trader_id, session)
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 1:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 7
        await session.commit()
        await cancel(customer.telegram_id, order_id)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/incorrect-payment/{order_id}', tags=['Page'], include_in_schema=False)
async def order_incorrect(order_id: str, key: str, chat_id: str | None = None, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    if order[0].side == 'IN':
        user = await get_user_by_key(key, session)
        if user is None:
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
        order = await session.execute(select(Order).where((Order.uuid == order_id) & (Order.trader_id == user.user_ptr_id)))
        order = order.first()
        if not order:
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
    else:
        decoded = jwt.decode(key, SECRET_AUTH, algorithms="HS256")
        if str(decoded['order']) != str(order_id):
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 2:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 8
        await session.commit()
        if order[0].side == 'IN':
            await cancel(chat_id, order_id)
        else:
            trader = await get_user_by_id(order[0].trader_id, session)
            await cancel(trader.telegram_id, order_id)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/success/{order_id}', tags=['Page'], include_in_schema=False)
async def order_success(order_id: str, key: str, chat_id: str | None = None,
                        session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    if order[0].side == 'IN':
        user = await get_user_by_key(key, session)
        if user is None:
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
        order = await session.execute(select(Order).where((Order.uuid == order_id) & (Order.trader_id == user.user_ptr_id)))
        order = order.first()
        if not order:
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
    else:
        decoded = jwt.decode(key, SECRET_AUTH, algorithms="HS256")
        print(decoded)
        if str(decoded['order']) != str(order_id):
            raise HTTPException(status_code=403, detail="INCORRECT KEY")
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 2:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        await release_crypto(order[0].id, session)
        order[0].status = 3
        await session.commit()
        if order[0].side == 'IN':
            await success(chat_id)
        else:
            trader = await get_user_by_id(order[0].trader_id, session)
            await success(trader.telegram_id)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/{order_id}', tags=['Page'], include_in_schema=False)
async def client_order(request: Request, order_id: str, session: AsyncSession = Depends(get_async_session)):
    try:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.first()
        if not order:
            raise HTTPException(status_code=404)
        if TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())) <= 0:
            if order[0].status in [2]:
                order[0].status = 5
                await session.commit()
                trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
                trader = trader.first()
                await cancel(trader[0].telegram_id, order[0].uuid)
            elif order[0].status in [0, 1]:
                order[0].status = 6
                await session.commit()
                trader = await session.execute(select(Customer).where(Customer.user_ptr_id == order[0].trader_id))
                trader = trader.fetchone()
                if trader:
                    trader[0].status = 'Inactive'
                    await session.commit()
                    await cancel(trader[0].telegram_id, order[0].uuid)
        if order[0].status == 0 and order[0].side == 'IN':
            return RedirectResponse(f"/order-start/{order_id}")
        if order[0].status in [3, 11]:
            return templates.TemplateResponse("sucсess.html", {
                'request': request,
            })
        if order[0].status in [4, 5, 6, 7, 8, 9, 10, 12]:
            return templates.TemplateResponse("canceled.html", {
                'request': request,
            })
        payment_method = await session.execute(
            select(TraderPaymentMethod).where(TraderPaymentMethod.id == order[0].method_id))
        payment_method = payment_method.first()
        result = await session.execute(select(Link).where((Link.id == order[0].output_link_id)))
        result = result.first()
        currency = await session.execute(select(Currency).where((Currency.id == result[0].currency_id)))
        currency = currency.first()
        if order[0].side == 'IN':
            return templates.TemplateResponse("order_card.html", {
                'request': request,
                'amount': order[0].output_amount / currency[0].denomination,
                'currency': currency[0].ticker,
                'time': TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())),
                'order': order_id,
                'card': payment_method[0].payment_details,
                'trader': payment_method[0].initials,
                'status': order[0].status
            })
        else:
            if order[0].status in [0, 1]:
                return templates.TemplateResponse("order_wait.html", {
                    'request': request,
                    'order': order_id,
                    'amount': order[0].output_amount / currency[0].denomination,
                    'currency': currency[0].ticker,
                    'time': TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())),
                    'status': order[0].status
                })
            elif order[0].status in [2]:
                return templates.TemplateResponse("order_realise_crypto.html", {
                    'request': request,
                    'order': order_id,
                    'amount': order[0].output_amount / currency[0].denomination,
                    'currency': currency[0].ticker,
                    'time': TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())),
                    'key': jwt.encode({'order': order_id}, SECRET_AUTH, algorithm="HS256").decode("utf-8"),
                    'status': order[0].status
                })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            'request': request,
            'error': str(e)
        })
