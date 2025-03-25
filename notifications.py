import os
import psycopg2
from datetime import datetime
from aiogram.enums import ParseMode

from utils import get_user_language, get_user_language_by_id, t

# Параметры подключения к БД
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST")
}

# Проверка подписки по дате окончания
def check_subscription_by_date(subscription_end):
    return subscription_end and subscription_end > datetime.now()

# Получаем список пользователей с активной подпиской
def get_active_subscribers():
    active_users = []
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, subscription_end FROM users")
        rows = cur.fetchall()
        cur.close()
        conn.close()

        for telegram_id, subscription_end in rows:
            if check_subscription_by_date(subscription_end):
                active_users.append(telegram_id)
    except Exception as e:
        print(f"Ошибка при получении подписчиков: {e}")

    return active_users

# Удаление пользователя из базы по chat_id
def remove_user_from_db(chat_id):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE telegram_id = %s", (chat_id,))
        conn.commit()
        cur.close()
        conn.close()
        print(f"[INFO] Пользователь {chat_id} удалён из базы.")
    except Exception as e:
        print(f"[Ошибка удаления пользователя {chat_id}]: {e}")

# Словарь категорий
categories = {
    "x": "X🟢",
    "b": "B-C🟡",
    "a": "A🔴"
}

# ===== Уведомление о новом товаре =====
async def notify_new_product(name, price, body, quantity, product_limit, category):
    from bot import bot
    subscribers = get_active_subscribers()
    category_display = categories.get(category.lower(), "❓Неизвестная категория")
    for chat_id in subscribers:
        lang = get_user_language_by_id(chat_id)

        try:
            quantity_int = int(quantity)
            quantity_text = t("stock_quantity", lang).format(quantity=quantity_int)
        except (ValueError, TypeError):
            quantity_text = t("stock_available", lang)

        message_text = (
            t("new_product", lang).format(
            category_display=category_display, 
            name=name, 
            body=body, 
            price=price, 
            quantity_text=quantity_text, 
            product_limit=product_limit)
        )
        try:
            await bot.send_message(chat_id, message_text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            print(f"Ошибка отправки уведомления {chat_id}: {e}")
            if "chat not found" in str(e).lower():
                remove_user_from_db(chat_id)

# ===== Уведомление об окончании товара =====
async def notify_product_out_of_stock(name, category):
    from bot import bot

    category_display = categories.get(category.lower(), "❓Неизвестная категория")

    subscribers = get_active_subscribers()
    for chat_id in subscribers:
        try:
            lang = get_user_language_by_id(chat_id)

            message_text = t("product_out", lang).format(
                category_display=category_display, name=name
            )
            await bot.send_message(chat_id, message_text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            print(f"Ошибка отправки уведомления {chat_id}: {e}")
            if "chat not found" in str(e).lower():
                remove_user_from_db(chat_id)
