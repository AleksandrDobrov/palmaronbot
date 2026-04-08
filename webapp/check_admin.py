#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для проверки статуса админа
Использование:
  python check_admin.py [USER_ID]
"""

import sys
import os

# Добавляем путь к database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import _db, is_admin
    import sqlite3
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что database.py находится в родительской папке")
    sys.exit(1)

def check_admin_status(user_id):
    """Проверяет статус админа для пользователя"""
    print("=" * 60)
    print(f"🔍 Проверка статуса админа для пользователя {user_id}")
    print("=" * 60)
    print()
    
    # Проверяем через функцию is_admin
    is_admin_result = is_admin(user_id)
    print(f"Функция is_admin({user_id}): {is_admin_result}")
    print()
    
    # Проверяем напрямую в БД
    with _db() as con:
        # Проверяем наличие таблицы admins
        try:
            con.execute("SELECT 1 FROM admins LIMIT 1")
            print("✅ Таблица admins существует")
        except sqlite3.OperationalError:
            print("❌ Таблица admins не существует!")
            return
        
        # Проверяем наличие колонки added_at
        cursor = con.execute("PRAGMA table_info(admins)")
        columns = [column[1] for column in cursor.fetchall()]
        has_added_at = 'added_at' in columns
        
        # Проверяем наличие пользователя в таблице admins
        if has_added_at:
            admin_row = con.execute("SELECT user_id, added_at FROM admins WHERE user_id = ?", (user_id,)).fetchone()
        else:
            admin_row = con.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,)).fetchone()
        
        if admin_row:
            print(f"✅ Пользователь {user_id} найден в таблице admins")
            if has_added_at and len(admin_row) > 1:
                print(f"   Добавлен: {admin_row[1]}")
        else:
            print(f"❌ Пользователь {user_id} НЕ найден в таблице admins")
        
        # Показываем всех админов
        print()
        print("📋 Все админы в системе:")
        if has_added_at:
            all_admins = con.execute("SELECT user_id, added_at FROM admins ORDER BY user_id").fetchall()
            if all_admins:
                for admin_id, added_at in all_admins:
                    marker = "👉" if admin_id == user_id else "  "
                    print(f"{marker} ID: {admin_id}, добавлен: {added_at}")
            else:
                print("   (нет админов)")
        else:
            all_admins = con.execute("SELECT user_id FROM admins ORDER BY user_id").fetchall()
            if all_admins:
                for (admin_id,) in all_admins:
                    marker = "👉" if admin_id == user_id else "  "
                    print(f"{marker} ID: {admin_id}")
            else:
                print("   (нет админов)")
        
        # Проверяем наличие пользователя в таблице users
        print()
        user_row = con.execute("SELECT user_id, user_name FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user_row:
            print(f"✅ Пользователь {user_id} найден в таблице users")
            print(f"   Имя: {user_row[1]}")
        else:
            print(f"⚠️  Пользователь {user_id} НЕ найден в таблице users")
    
    print()
    print("=" * 60)
    if is_admin_result:
        print("✅ ИТОГ: Пользователь является админом")
    else:
        print("❌ ИТОГ: Пользователь НЕ является админом")
    print("=" * 60)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            user_id = int(sys.argv[1])
        except ValueError:
            print("❌ Ошибка: ID должен быть числом!")
            print("Использование: python check_admin.py [USER_ID]")
            sys.exit(1)
    else:
        try:
            user_id_input = input("Введите ID пользователя для проверки: ").strip()
            if not user_id_input:
                print("❌ ID не может быть пустым!")
                sys.exit(1)
            user_id = int(user_id_input)
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Отменено")
            sys.exit(1)
    
    check_admin_status(user_id)

