import os
from aiogram import Bot
from aiogram.enums import ParseMode

from fastapi import FastAPI
import psycopg2
import stripe
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils import t

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST")
}

# Инициализация бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_BOT_TOKEN)

app = FastAPI()

# Асинхронная функция добавления пользователя
async def add_user_with_subscription(telegram_id, language):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        subscription_end = datetime.now() + timedelta(days=30)

        cur.execute("""
            INSERT INTO users (telegram_id, username, subscription_end, trial_used, language) 
            VALUES (%s, %s, %s, FALSE, %s)
            ON CONFLICT (telegram_id) DO UPDATE 
            SET subscription_end = EXCLUDED.subscription_end,
                language = EXCLUDED.language;
        """, (telegram_id, f"user_{telegram_id}", subscription_end, language))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка добавления пользователя: {e}")

# Функция отправки сообщений в Telegram
async def send_telegram_message(telegram_id, message, language='ru'):
    try:
        # Используем t() для перевода сообщения
        text = t(message, language)
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения в Telegram: {e}")
    finally:
        # Явное закрытие сессии, чтобы избежать предупреждения об "unclosed session"
        await bot.session.close()

# Фоновая задача — удаление пользователей с истекшей подпиской каждый час
async def cleanup_expired_users():
    while True:
        try:
            conn = psycopg2.connect(**DB_PARAMS)
            cur = conn.cursor()

            cur.execute("""
                DELETE FROM users 
                WHERE subscription_end < NOW();
            """)

            deleted_count = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()

            print(f"🗑️ Удалено пользователей с истекшей подпиской: {deleted_count}")
        except Exception as e:
            print(f"❌ Ошибка при удалении пользователей: {e}")

        await asyncio.sleep(3600)
