import sqlite3, pathlib
import json
import threading

DB_FILE = pathlib.Path(__file__).with_name("tg.db")

# Глобальна змінна для блокування
_init_lock = threading.Lock()

# Функція для перевірки адміністратора
def is_admin(user_id):
    """Перевіряє, чи є користувач адміністратором"""
    from database import _db
    with _db() as con:
        row = con.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)).fetchone()
        return bool(row)

def round_float(value, decimals=2):
    """
    Правильно округлює число з плаваючою комою до вказаної кількості знаків після коми.
    Вирішує проблему з числами типу 8.299999999999999 -> 8.30
    """
    if value is None:
        return 0.0
    
    # Конвертуємо в float якщо це не число
    try:
        value = float(value)
    except (ValueError, TypeError):
        return 0.0
    
    # Використовуємо round() для правильного округлення
    return round(value, decimals)

def format_currency(amount, decimals=2):
    """
    Форматує грошову суму з правильним округленням
    """
    rounded_amount = round_float(amount, decimals)
    return f"{rounded_amount:.{decimals}f}"

def get_user_name(user_id):
    """Отримує ім'я користувача"""
    try:
        from database import get_user
        user = get_user(user_id)
        if user and len(user) > 1:
            return user[1]  # user_name знаходиться в індексі 1
        else:
            return f"Користувач {user_id}"
    except:
        return f"Користувач {user_id}" 