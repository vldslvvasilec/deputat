import requests
from bs4 import BeautifulSoup
import re

# URL для запроса
url = 'https://www.deputatpivo.cz/pokladny/akce_nastroje.php'

# Параметры запроса
params = {
    'akce': 'getZasobyInfo',
    'skladid': 2,
    'id': 131,
    'kod': '8e3308c853e47411c761429193511819',
    'info': 'ok'
}

# Функция для выполнения парсинга
def fetch_data():
    response = requests.get(url, params=params)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        categories_a = soup.find_all('a', href='#collapse0')  # Категория A
        categories_b_c = soup.find_all('a', href='#collapse1')  # Категория B+C
        categories_x = soup.find_all('a', href='#collapse')  # Категория X

        category_a = []
        category_b_c = []
        category_x = []

        def clean_text(text, suffix=None):
            if suffix:
                text = text.replace(suffix, '').strip()
            return text.strip()

        def get_limit_from_name(name):
            match = re.search(r'(\d+)ks/den', name.lower())
            if match:
                return int(match.group(1))
            return 2  # Значение по умолчанию

        def extract_price(price_text):
            match = re.search(r'(\d+)', price_text)
            if match:
                return match.group(1)
            return 'N/A'

        def clean_name(name):
            # Убираем лимит и упоминание категории X из названия
            name = re.sub(r'(\d+ks/den|kategorie x)', '', name, flags=re.IGNORECASE).strip()
            name = re.sub(r'[-\s]+$', '', name)
            return name

        def extract_flags_from_column(flag_column):
            text = flag_column.text.lower()
            prepravka = 'přepravka' in text
            lahve = 'lahve' in text
            return prepravka, lahve

        # Универсальная функция для обработки категорий
        def process_category(category_links, storage_list, allow_x=False):
            for category in category_links:
                items = category.find_next('div', class_='panel-collapse').find_all('div', class_='row')
                for item in items:
                    columns = item.find_all('div', class_='col-xs-4')
                    if len(columns) < 1:
                        continue

                    name_raw = columns[0].text.strip()
                    if name_raw == "Položka":
                        continue

                    points_column = item.find_all('div', class_='col-xs-1')
                    points = points_column[0].text.strip() if len(points_column) >= 1 else 'N/A'

                    quantity_column = points_column[1] if len(points_column) > 1 else None
                    quantity = clean_text(quantity_column.text, ' ks') if quantity_column else 'N/A'

                    price_column = item.find_all('div', class_='col-xs-2')
                    price = extract_price(price_column[1].text if len(price_column) > 1 else 'N/A')

                    # Флаги из третьего col-xs-2
                    flag_column = price_column[2] if len(price_column) > 2 else None
                    prepravka_flag, lahve_flag = (False, False)
                    if flag_column:
                        prepravka_flag, lahve_flag = extract_flags_from_column(flag_column)

                    limit = get_limit_from_name(name_raw)
                    cleaned_name = clean_name(name_raw)

                    data_tuple = (cleaned_name, points, price, quantity, limit, prepravka_flag, lahve_flag)

                    if allow_x and "kategorie x" in name_raw.lower():
                        category_x.append(data_tuple)
                    else:
                        storage_list.append(data_tuple)

        # Обработка всех категорий
        process_category(categories_a, category_a)
        process_category(categories_b_c, category_b_c, allow_x=True)
        process_category(categories_x, category_x)

        return category_a, category_b_c, category_x

    else:
        print(f"Ошибка запроса: {response.status_code}")
