#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка работы сервера WebApp
"""

import requests
import time
import sys

def check_server(url="http://localhost:5000", timeout=5):
    """Проверяет доступность сервера"""
    print(f"[INFO] Проверка сервера: {url}")
    print()
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed = time.time() - start_time
        
        print(f"✅ Сервер отвечает!")
        print(f"   Статус: {response.status_code}")
        print(f"   Время ответа: {elapsed:.2f} секунд")
        print(f"   Размер ответа: {len(response.content)} байт")
        
        if elapsed > 3:
            print(f"⚠️  Медленный ответ ({elapsed:.2f}с)!")
            print("   Возможные причины:")
            print("   - Первая загрузка (инициализация модулей)")
            print("   - Медленное подключение к БД")
            print("   - Импорт тяжелых модулей")
        
        return True
    except requests.exceptions.Timeout:
        print(f"❌ Таймаут! Сервер не отвечает за {timeout} секунд")
        print()
        print("Возможные причины:")
        print("1. Сервер не запущен")
        print("2. Сервер завис при загрузке")
        print("3. Проблемы с сетью")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться!")
        print()
        print("Возможные причины:")
        print("1. Сервер не запущен")
        print("2. Неправильный адрес")
        print("3. Файрвол блокирует подключение")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == '__main__':
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    check_server(url)

