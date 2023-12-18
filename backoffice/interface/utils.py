import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telegram import Bot
import asyncio

load_dotenv()

SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT"))
SMTP_SSL = os.environ.get("SMTP_SSL")
SMTP_LOGIN = os.environ.get("SMTP_LOGIN")
SMTP_PASS = os.environ.get("SMTP_PASS")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

bot = Bot(token=TELEGRAM_TOKEN)


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


def send_tg(recipient, message):
    msg = asyncio.run(bot.send_message(chat_id=recipient, text=message))
    return msg.chat_id

