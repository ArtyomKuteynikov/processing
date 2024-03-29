import requests
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

from config.main import LINK

API_TOKEN = '6851506746:AAF5S-FdMwFrVvYUx16YvvQvESpcudka2Jk'
bot = Bot(token=API_TOKEN)


async def start(order_id, amount, currency, chat_id):
    message_text = (f"""Новая заявка на обмен

Order_id: {order_id}
Amount: {str(amount)} {currency}""")
    await bot.send_message(chat_id=chat_id, text=message_text,)


async def marked_as_payed(chat_id, key, order_id):
    message_text = (f"""Клиент ордера ```{order_id}```
изменил статус ордера на "Средства переведены", проверьте перевод и нажмите 'Подтвердить'""")
    buttons = [
        InlineKeyboardButton(text="Подтвердить", url=f"{LINK}/order/success/{order_id}?key={key}&chat_id={chat_id}"),
        InlineKeyboardButton(text="Не пришли деньги", url=f"{LINK}/incorrect-payment/{order_id}?key={key}&chat_id={chat_id}"),
    ]
    keyboard = (InlineKeyboardMarkup(row_width=2, inline_keyboard=[buttons]))
    await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=keyboard, parse_mode="MarkdownV2")


async def out_order(order_id, amount, currency, chat_id, card_number, initials):
    message_text = (f"""Новый ордер на вывод {order_id}:

Переведите {str(amount).replace('.', ',')} {currency}
На карту: {str(card_number).replace(' ', '')}
Получатель: {initials}
""".replace('.', ''))
    print(message_text)
    buttons = [
        InlineKeyboardButton(text="перевод выполнен", url=f"{LINK}/order/payed/{ order_id }"),
        InlineKeyboardButton(text="Отменить", url=f"{LINK}/order/cancel/{order_id}"),
    ]
    keyboard = (InlineKeyboardMarkup(row_width=2, inline_keyboard=[buttons]))
    await bot.send_message(chat_id=chat_id, text=message_text, reply_markup=keyboard)


async def success(chat_id: str):
    message_text = "✅Готово!"
    await bot.send_message(chat_id=chat_id, text=message_text)


async def cancel(chat_id: str, order_id: str):
    message_text = f"❌Транзакция ```{order_id}``` отменена"
    await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="MarkdownV2")


def send_tg(telegram_id, message):
    url = f'https://api.telegram.org/bot{API_TOKEN}/sendMessage'
    params = {
        'chat_id': telegram_id,
        'text': message,
    }
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        print(f"Сообщение успешно отправлено в Telegram для пользователя с ID {telegram_id}")
        return 0
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке сообщения в Telegram: {e}")
        return 0
