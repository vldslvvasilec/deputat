import os
import stripe
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv
from stripe_webhook import add_user_with_subscription, send_telegram_message
from utils import t, get_user_language

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
import asyncio

import stripe

from parser.saveData import get_all_products

# ===== Загрузка переменных из .env =====
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST")
}
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# ===== Инициализация бота и диспетчера =====
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

stripe.api_key = STRIPE_SECRET_KEY

# ===== Клавиатура с кнопками внизу =====
def main_keyboard(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("subscribe_button", lang))],
            [KeyboardButton(text=t("full_list_button", lang))]
        ],
        resize_keyboard=True
    )

# ===== Проверка подписки =====
async def check_subscription(user_id):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("SELECT subscription_end FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            sub_end = result[0]
            if sub_end and sub_end > datetime.now():
                return True
    except Exception as e:
        print(f"Ошибка при проверке подписки: {e}")
    return False

async def get_subscription_end_date(user_id):
    """Возвращает дату окончания подписки для пользователя."""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        cur.execute("SELECT subscription_end FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if result:
            return result[0]  # Возвращаем дату окончания подписки
        else:
            return None
    except Exception as e:
        print(f"Ошибка при получении даты окончания подписки: {e}")
        return None

# ===== Генерация ссылки оплаты =====
async def create_payment_link(name, telegram_id, lang):
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'czk',
                    'product_data': {'name': name},
                    'unit_amount': 20000,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://t.me/DeputatPragueBot?start=success',
            cancel_url='https://t.me/DeputatPragueBot?start=cancel',
            metadata={
                'telegram_id': str(telegram_id),
                'language': lang
            }
        )
        return session.url
    except Exception as e:
        return None


# ===== Обработка команды /start =====
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    lang = get_user_language(message)
    # Проверка, есть ли параметр 'start' в сообщении
    if message.text.startswith("/start"):
        param = message.text.split()[1] if len(message.text.split()) > 1 else ""

        if param == "success":
            # Обработка успешной оплаты
            user_id = message.chat.id
            lang = get_user_language(message)
            subscription_end = datetime.now() + timedelta(days=30)
            formatted_dt = subscription_end.strftime('%Y-%m-%d %H:%M')
            await add_user_with_subscription(user_id, lang)
            await message.answer(t("payment_successful", lang).format(date=formatted_dt), reply_markup=main_keyboard(lang))

        else:
            await message.answer(t("start_prompt", lang), reply_markup=main_keyboard(lang))

# ===== Обработка нажатий на кнопки =====
@dp.message(lambda message: message.text == t("subscribe_button", get_user_language(message)))
async def handle_subscribe(message: types.Message):
    lang = get_user_language(message)
    user_id = message.chat.id
    if await check_subscription(user_id):
        end_date = await get_subscription_end_date(user_id)
        formatted_date = end_date.strftime('%Y-%m-%d %H:%M')
        await message.answer(t("active_subscription", lang).format(formatted_date=formatted_date))
    else:
        payment_url = await create_payment_link(t("bot_subscription", lang), user_id, lang)
        if payment_url:
            await message.answer(
                t("no_subscription_pay", lang).format(payment_url=payment_url),
                disable_web_page_preview=True,
                parse_mode='Markdown'
            )
        else:
            await message.answer(t("payment_error", lang))

@dp.message(lambda message: message.text == t("full_list_button", get_user_language(message)))
async def handle_get_list(message: types.Message):
    lang = get_user_language(message)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 A", callback_data="category_a"),
            InlineKeyboardButton(text="🟡 B-C", callback_data="category_b"),
            InlineKeyboardButton(text="🟢 X", callback_data="category_x")
        ]
    ])
    await message.answer(t("select_category", lang), reply_markup=keyboard)

# ===== Обработка команды /id =====
@dp.message(Command("id"))
async def get_id(message: types.Message):
    lang = get_user_language(message)
    user_id = message.chat.id
    await message.answer(t("your_id", lang).format(user_id=user_id))

# ===== Обработка команды /categories =====
@dp.message(Command("categories"))
async def show_categories(message: types.Message):
    lang = get_user_language()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="A 🔴", callback_data="category_a"),
            InlineKeyboardButton(text="B-C 🟡", callback_data="category_b"),
            InlineKeyboardButton(text="X 🟢", callback_data="category_x")
        ]
    ])
    await message.answer(t("choose_category", lang), reply_markup=keyboard)

# ===== Обработка нажатий на кнопки категорий =====
@dp.callback_query(lambda call: call.data.startswith("category_"))
async def handle_category_callback(callback_query: types.CallbackQuery):
    lang = get_user_language(callback_query)
    category_map = {
        "category_a": ("A 🔴", "a"),
        "category_b": ("B-C 🟡", "b"),
        "category_x": ("X 🟢", "x")
    }

    # Получаем читаемое имя категории и код категории для БД
    selected_readable, category_code = category_map.get(callback_query.data, ("Неизвестная категория", None))

    if category_code:
        # Получаем товары из базы
        products = get_all_products(category_code)

        if products:
            product_messages = []
            for product in products:
                name, body, price, product_limit, stock_status, deposit_boxes, deposit_bottles, category = product

                # Опционально формируем текст по наличию
                quantity_text = t("stock_available", lang) if stock_status == 999 else t("stock_quantity_all", lang).format(stock_status=stock_status) if product_limit else t("out_of_stock", lang)

                product_text = (
                    t("product_template", lang).format(name=name, body=body, price=price, quantity_text=quantity_text, product_limit=product_limit)
                )
                product_messages.append(product_text)

            # Объединяем все товары в одно сообщение
            full_message = t("category_label", lang).format(selected_readable=selected_readable) + "".join(product_messages)

            # Отвечаем пользователю
            await callback_query.answer()  # Убираем индикатор загрузки
            await callback_query.message.answer(full_message, parse_mode="Markdown")
        else:
            await callback_query.answer()
            await callback_query.message.answer(t("no_products", lang))
    else:
        await callback_query.answer()
        await callback_query.message.answer(t("unknown_category", lang))

# ===== Список исключений — сообщения с этими командами/текстами не удалять =====
EXCLUDED_MESSAGES = [
    "/start",
    "/pay",
    "/categories"
    "/id",
]

@dp.message()
async def delete_all_messages(message: types.Message):
    try:
        text = message.text.lower() if message.text else ""

        # Проверяем, содержит ли сообщение исключение
        if any(text.startswith(exc.lower()) for exc in EXCLUDED_MESSAGES):
           return

        await message.delete()

    except TelegramBadRequest as e:
        print(f"Ошибка при удалении сообщения: {e}")


# ===== Запуск бота =====
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
