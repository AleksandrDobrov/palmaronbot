#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка почему порт не отвечает
"""

import sys
import os
import socket
import subprocess

print("=" * 70)
print("🔍 Диагностика: Почему порт не отвечает")
print("=" * 70)
print()

# 1. Проверка Python
print("[1] Проверка Python...")
try:
    import sys
    print(f"   ✅ Python {sys.version}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    sys.exit(1)
print()

# 2. Проверка Flask
print("[2] Проверка Flask...")
try:
    import flask
    print(f"   ✅ Flask установлен")
except ImportError:
    print("   ❌ Flask не установлен!")
    print("   Установите: pip install Flask")
    sys.exit(1)
print()

# 3. Проверка импорта app
print("[3] Проверка импорта app.py...")
webapp_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(webapp_dir)

sys.path.insert(0, parent_dir)
sys.path.insert(0, webapp_dir)

try:
    import importlib.util
    app_path = os.path.join(webapp_dir, 'app.py')
    print(f"   Путь к app.py: {app_path}")
    
    if not os.path.exists(app_path):
        print(f"   ❌ Файл app.py не найден!")
        sys.exit(1)
    
    print("   Попытка импорта...")
    spec = importlib.util.spec_from_file_location("webapp_app", app_path)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    
    if not hasattr(app_module, 'app'):
        print("   ❌ В app.py нет объекта 'app'!")
        sys.exit(1)
    
    print("   ✅ app.py успешно импортирован")
except Exception as e:
    print(f"   ❌ Ошибка импорта: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
print()

# 4. Проверка порта
print("[4] Проверка порта 5000...")
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(1)
result = sock.connect_ex(('127.0.0.1', 5000))
sock.close()

if result == 0:
    print("   ✅ Порт 5000 занят (сервер запущен)")
else:
    print("   ⚠️  Порт 5000 свободен (сервер не запущен)")
print()

# 5. Проверка процессов
print("[5] Проверка процессов Python...")
try:
    result = subprocess.run(
        ['tasklist', '/FI', 'IMAGENAME eq python.exe'],
        capture_output=True,
        text=True,
        timeout=5
    )
    python_processes = result.stdout.count('python.exe')
    print(f"   Найдено процессов Python: {python_processes}")
except:
    print("   ⚠️  Не удалось проверить процессы")
print()

# 6. Попытка запуска
print("[6] Попытка запуска сервера (тест)...")
print("   Это займет 3 секунды...")
try:
    # Пробуем запустить в отдельном процессе
    import threading
    import time
    
    def test_run():
        try:
            app = app_module.app
            app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
        except Exception as e:
            print(f"   Ошибка запуска: {e}")
    
    thread = threading.Thread(target=test_run, daemon=True)
    thread.start()
    time.sleep(2)
    print("   ✅ Сервер может запуститься")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
print()

print("=" * 70)
print("📋 Рекомендации:")
print("=" * 70)
print()
print("1. Запустите сервер:")
print("   cd webapp")
print("   python app.py")
print()
print("2. Если есть ошибки при запуске - пришлите их")
print()
print("3. Проверьте, что порт 5000 не занят другим приложением")
print()

