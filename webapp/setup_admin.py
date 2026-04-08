#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для установки админа (любой ID)
Использование:
  python setup_admin.py [USER_ID]
  или просто python setup_admin.py (скрипт спросит ID)
"""

import sys
import os

# Добавляем путь к database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import _db, ensure_user
    import sqlite3
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что database.py находится в родительской папке")
    sys.exit(1)

def set_admin(user_id):
    """Устанавливает пользователя как админа"""
    with _db() as con:
        # Проверяем, существует ли таблица admins
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    added_at INTEGER DEFAULT (strftime('%s', 'now'))
                )
            """)
            con.commit()
        except Exception as e:
            print(f"Ошибка создания таблицы admins: {e}")
        
        # Проверяем, существует ли пользователь
        user = con.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user:
            print(f"Создаю пользователя {user_id}...")
            ensure_user(user_id, "Admin")
        
        # Добавляем в админы
        try:
            con.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
            con.commit()
            print(f"✅ Пользователь {user_id} теперь админ!")
        except Exception as e:
            print(f"Ошибка добавления админа: {e}")
            # Пробуем через UPDATE
            try:
                con.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
                con.commit()
                print(f"✅ Пользователь {user_id} теперь админ (через UPDATE)!")
            except:
                pass

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 Установка админа")
    print("=" * 60)
    print()
    
    # Можно указать ID через аргумент командной строки
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print("❌ Ошибка: ID должен быть числом!")
            print("Использование: python setup_admin.py [USER_ID]")
            sys.exit(1)
    else:
        # По умолчанию спрашиваем
        try:
            user_id_input = input("Введите ID пользователя для установки админа (или Enter для ID=1): ").strip()
            if user_id_input:
                user_id = int(user_id_input)
            else:
                user_id = 1
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Отменено")
            sys.exit(1)
    
    print(f"Устанавливаю пользователя {user_id} как админа...")
    set_admin(user_id)
    
    print()
    print("=" * 60)
    print("✅ Готово!")
    print("=" * 60)
    print()
    print(f"Пользователь {user_id} теперь имеет права админа.")
    print("Войдите в WebApp и перейдите в раздел /admin")
    print()

