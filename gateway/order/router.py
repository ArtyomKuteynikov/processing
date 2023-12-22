import datetime
import random
import time
import uuid
from fastapi.responses import RedirectResponse
from fastapi import FastAPI, Depends, HTTPException, status, Request, Header, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio as aio
from models.schemas import CreateOrder
from config.database import engine, get_async_session
from sqlalchemy import select, and_
from config.main import Settings, LINK
from telegram_bot.order import start, marked_as_payed, success, cancel
from models import Customer, Order, Balance, Link, Currency, ExchangeDirection, TraderPaymentMethod
from fastapi.responses import HTMLResponse, JSONResponse


router = APIRouter(
    prefix="/v1/chat",
    tags=["Chat"]
)


@app.post('/v1/order', tags=['Order'])
async def create_order(data: CreateOrder, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(data.key, session)
    if user is None:
        raise HTTPException(status_code=401, detail="INCORRECT KEY")
    order = await order_create(data, user.id, session)
    aio.create_task(timeout_limit(session, order.id))
    if order:
        return JSONResponse(status_code=200, content={
            'link': f'{LINK}/order-start/{order.uuid}',
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


@app.get('/order-start/{order_id}', tags=['Page'])
async def order_start(request: Request, order_id: str, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    if order[0].status != 0:
        return RedirectResponse(f"/order/{order_id}")
    return templates.TemplateResponse("chose_method.html", {
        'request': request,
        'order_id': order_id,
    })


@app.get('/v1/order-put/{order_id}', tags=['Page'])
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
        await start(order_id, order[0].output_amount/currency[0].denomination, 'RUB', customer.telegram_id)
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
            trader = await session.execute(select(Customer).where(Customer.id == order[0].trader_id))
            trader = trader.first()
            await cancel(trader[0].telegram_id, order[0].uuid)
        elif order[0].status in [2]:
            order[0].status = 6
            await session.commit()
            trader = await session.execute(select(Customer).where(Customer.id == order[0].trader_id))
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
    order = await order_get(order_id, user.id, session)
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
    balances = await balances_get(user.id, session)
    data = []
    for i in balances:
        data.append({
            'currency': await get_asset_by_link_id(i[0].balance_link_id, session),
            'amount': i[0].amount
        })
    return JSONResponse(status_code=200, content={
        'balance': data
    })


@app.get('/order/payed/{order_id}', tags=['Page'])
async def order_payed(order_id: str, session: AsyncSession = Depends(get_async_session)):
    order = await session.execute(select(Order).where((Order.uuid == order_id)))
    order = order.first()
    customer = await get_user_by_id(order[0].trader_id, session)
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 1:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 2
        await session.commit()
        await marked_as_payed(customer.telegram_id, customer.key, order[0].uuid)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/cancel/{order_id}', tags=['Page'])
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


@app.get('/order/incorrect-payment/{order_id}', tags=['Page'])
async def order_incorrect(order_id: str, key: str, chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(key, session)
    if user is None:
        raise HTTPException(status_code=403, detail="INCORRECT KEY")
    order = await session.execute(select(Order).where((Order.uuid == order_id) & (Order.trader_id == user.id)))
    order = order.first()
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 2:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 8
        await session.commit()
        await cancel(chat_id, order_id)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/success/{order_id}', tags=['Page'])
async def order_success(order_id: str, key: str, chat_id: str, session: AsyncSession = Depends(get_async_session)):
    user = await get_user_by_key(key, session)
    if user is None:
        raise HTTPException(status_code=403, detail="INCORRECT KEY")
    print(user.id)
    order = await session.execute(select(Order).where((Order.uuid == order_id) & (Order.trader_id == user.id)))
    order = order.first()
    if int(time.time()) < TIME_LIMIT + int(order[0].created.timestamp()) and order[0].status == 2:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.fetchone()
        order[0].status = 3
        await session.commit()
        await success(chat_id)
    return RedirectResponse(f"/order/{order_id}")


@app.get('/order/{order_id}', tags=['Page'])
async def client_order(request: Request, order_id: str, session: AsyncSession = Depends(get_async_session)):
    try:
        order = await session.execute(select(Order).where((Order.uuid == order_id)))
        order = order.first()
        if not order:
            raise HTTPException(status_code=404)
        if TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())) <= 0:
            if order[0].status in [0, 1]:
                order[0].status = 5
                await session.commit()
                trader = await session.execute(select(Customer).where(Customer.id == order[0].trader_id))
                trader = trader.first()
                await cancel(trader[0].telegram_id, order[0].uuid)
            elif order[0].status in [2]:
                order[0].status = 6
                await session.commit()
                trader = await session.execute(select(Customer).where(Customer.id == order[0].trader_id))
                trader = trader.fetchone()
                if trader:
                    trader[0].status = 'Inactive'
                    await session.commit()
                    await cancel(trader[0].telegram_id, order[0].uuid)
        if order[0].status == 0:
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
        print(int(time.time()) - int(order[0].created.timestamp()), order[0].created)
        return templates.TemplateResponse("order_card.html", {
            'request': request,
            'amount': order[0].output_amount/currency[0].denomination,
            'currency': currency[0].ticker,
            'time': TIME_LIMIT - (int(time.time()) - int(order[0].created.timestamp())),
            'order': order_id,
            'card': payment_method[0].payment_details,
            'trader': payment_method[0].initials,
            'status': order[0].status
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            'request': request,
            'error': str(e)
        })
