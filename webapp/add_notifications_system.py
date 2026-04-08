#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавление системы уведомлений в базу данных
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import _db

def create_notifications_table():
    """Создает таблицу уведомлений"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT,
                is_read INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Индексы для быстрого поиска
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id 
            ON notifications(user_id)
        """)
        
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_is_read 
            ON notifications(is_read)
        """)
        
        con.commit()
        print("✅ Таблица уведомлений создана!")

if __name__ == '__main__':
    print("Создание таблицы уведомлений...")
    create_notifications_table()
    print("Готово!")

































