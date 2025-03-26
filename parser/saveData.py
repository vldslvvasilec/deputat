import asyncio
from datetime import datetime
import psycopg2
from dotenv import load_dotenv
import sys
import os
import importlib
from datetime import datetime, time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from notifications import notify_new_product, notify_product_out_of_stock
from stripe_webhook import cleanup_expired_users

# Загрузка переменных окружения из .env
load_dotenv()

# Подключение к БД
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
chat_id = os.getenv("ADMIN_ID")

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def save_products(data, category):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            for product in data:
                if len(product) != 7:
                    print(f"[Ошибка]: Некорректные данные товара: {product}")
                    continue

                name, body, price, product_limit, stock_status, deposit_boxes, deposit_bottles = product

                try:
                    price = float(price)
                except ValueError:
                    print(f"[Ошибка цены]: '{price}' в товаре '{name}'")
                    continue

                if product_limit.lower() == 'skladem':
                    product_limit = 999
                else:
                    try:
                        product_limit = int(product_limit)
                    except ValueError:
                        print(f"[Ошибка лимита]: '{product_limit}' в товаре '{name}'")
                        continue

                cursor.execute("""
                    INSERT INTO products 
                    (name, body, price, stock_status, product_limit, deposit_boxes, deposit_bottles, category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name, category) DO UPDATE SET
                        body = EXCLUDED.body,
                        price = EXCLUDED.price,
                        stock_status = EXCLUDED.stock_status,
                        product_limit = EXCLUDED.product_limit,
                        deposit_boxes = EXCLUDED.deposit_boxes,
                        deposit_bottles = EXCLUDED.deposit_bottles;
                """, (name, body, price, stock_status, product_limit, deposit_boxes, deposit_bottles, category))
            conn.commit()

async def check_for_new_products(new_data, category, previous_data):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            # Получаем имена товаров из предыдущих данных
            previous_names = [product[0] for product in previous_data]
            new_names = [product[0] for product in new_data]

            for product in new_data:
                if len(product) != 7:
                    print(f"[Ошибка]: Некорректные данные товара: {product}")
                    continue

                name, body, price, product_limit, stock_status, deposit_boxes, deposit_bottles = product

                if name not in previous_names:
                    await notify_new_product(name, price, body, product_limit, stock_status, category)
                    print(f"[Новый товар]: {name}, цена: {price}, категория: {category}")

                # Обновление/сохранение товара
                save_products([product], category)

            # Удаление исчезнувших товаров
            deleted_products = set(previous_names) - set(new_names)
            for deleted_product in deleted_products:
                await notify_product_out_of_stock(deleted_product, category)
                print(f"[Удалено]: {deleted_product}, категория: {category}")
                cursor.execute("DELETE FROM products WHERE name = %s AND category = %s", (deleted_product, category))

            conn.commit()

    return new_data

def get_all_products(category):
    with connect_db() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT name, body, price, stock_status, product_limit, deposit_boxes, deposit_bottles, category 
                FROM products
                WHERE category = %s
            """, (category,))
            products = cursor.fetchall()
            return products

# Главная асинхронная функция
async def main():
    previous_data_a = get_all_products('a')
    previous_data_b = get_all_products('b')
    previous_data_x = get_all_products('x')

    # Интервал работы: с 08:30 до 17:00, с понедельника по пятницу
    work_start = time(5, 30)
    work_end = time(17, 30)

    # Запускаем задачу очистки пользователей в фоне
    asyncio.create_task(cleanup_expired_users())

    while True:
        now = datetime.now()
        current_time = now.strftime('%Y-%m-%d %H:%M:%S')
        weekday = now.weekday()  # 0 = понедельник, 6 = воскресенье

        if 0 <= weekday <= 6 and work_start <= now.time() <= work_end:
            try:
                import parserWeb
                importlib.reload(parserWeb)
                fetched_data = parserWeb.fetch_data()
                #import testFetch
                #importlib.reload(testFetch)
                #fetched_data = testFetch.fetch_data()

                if len(fetched_data) >= 3:
                    previous_data_a = await check_for_new_products(fetched_data[0], 'a', previous_data_a)
                    previous_data_b = await check_for_new_products(fetched_data[1], 'b', previous_data_b)
                    previous_data_x = await check_for_new_products(fetched_data[2], 'x', previous_data_x)
                else:
                    print("[Ошибка]: недостаточно данных от парсера.")
            except Exception as e:
                print(f"[Ошибка цикла]: {e}")
        else:
            print(f"[Ожидание рабочего времени]: Сейчас {current_time} — не в расписании.")

        await asyncio.sleep(1)

# Запуск event loop
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Завершение]: Программа остановлена вручную.")
