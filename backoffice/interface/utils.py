import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import asyncio

load_dotenv()

SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
SMTP_SSL = os.environ.get("SMTP_SSL")
SMTP_LOGIN = os.environ.get("SMTP_LOGIN")
SMTP_PASS = os.environ.get("SMTP_PASS")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")


def send_email(recipient_email, subject, message):
    msg = MIMEMultipart()
    msg['From'] = SMTP_LOGIN
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_LOGIN, SMTP_PASS)
        smtp.send_message(msg)


def send_tg(telegram_id, message):
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
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


def handle_uploaded_file(f):
    with open('myapp/static/upload/'+f.name, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

