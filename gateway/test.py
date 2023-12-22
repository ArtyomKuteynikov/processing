import logging
from telegram import Bot

# Replace 'YOUR_BOT_TOKEN' with the actual token obtained from BotFather
bot = Bot(token='6773531340:AAGKvgim-y1bijEi4ybq0tsXVILB3VpG4TA')

def send_message(username, text):
    try:
        # Send a message to the specified Telegram username
        bot.send_message(chat_id=username, text=text)
        print(f"Message sent to {username}: {text}")
    except Exception as e:
        print(f"Error sending message: {e}")

# Replace 'TARGET_USERNAME' with the actual Telegram username
target_username = '@artem_kuteynikov'
message_text = 'Hello, this is a test message from your Python script!'

send_message(target_username, message_text)