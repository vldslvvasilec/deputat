import os
from aiogram import types
import psycopg2
from dotenv import load_dotenv
from translations import translations

load_dotenv()

DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST")
}

def t(key: str, lang: str = 'ru') -> str:
    return translations.get(key, {}).get(lang, key)

def get_user_language(message: types.Message) -> str:
    lang_code = message.from_user.language_code
    if lang_code:
        if lang_code == 'uk':
            return 'ua'
        elif lang_code == 'cs':
            return 'cs'
        elif lang_code == 'ru':
            return 'ru'
        else:
            return 'en'
    else:
        return 'en'
    

def get_user_language_by_id(chat_id: int) -> str:
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    cur.execute("SELECT language FROM users WHERE telegram_id = %s", (chat_id,))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result and result[0]:
        lang_code = result[0]
        if lang_code.startswith('uk'):
            return 'ua'
        elif lang_code.startswith('cs'):
            return 'cs'
        elif lang_code.startswith('ru'):
            return 'ru'
        else:
            return 'en'
    else: 
        return 'en'
