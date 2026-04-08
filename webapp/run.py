#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска WebApp
"""

import os
import sys

# Получаем путь к директории webapp
webapp_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(webapp_dir)

# Добавляем родительскую директорию в путь (для database и других модулей)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Добавляем текущую директорию в начало пути (для импорта app из webapp)
if webapp_dir not in sys.path:
    sys.path.insert(0, webapp_dir)

# Импортируем app из webapp/app.py
# Используем явный импорт из текущей директории
import importlib.util
app_path = os.path.join(webapp_dir, 'app.py')
spec = importlib.util.spec_from_file_location("webapp_app", app_path)
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
app = app_module.app

if __name__ == '__main__':
    import socket
    
    # Улучшенная функция получения локального IP для Windows
    def get_local_ip():
        """Получает локальный IP-адрес компьютера несколькими способами"""
        ips = []
        
        # Способ 1: Через подключение к внешнему адресу
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith('127.'):
                ips.append(ip)
        except:
            pass
        
        # Способ 2: Через hostname
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ip and not ip.startswith('127.') and ip not in ips:
                    # Предпочитаем локальные IP (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
                    try:
                        if ip.startswith('192.168.') or ip.startswith('10.'):
                            ips.insert(0, ip)  # Добавляем в начало
                        elif ip.startswith('172.'):
                            parts = ip.split('.')
                            if len(parts) > 1:
                                second_octet = int(parts[1])
                                if 16 <= second_octet <= 31:
                                    ips.insert(0, ip)
                                else:
                                    ips.append(ip)
                            else:
                                ips.append(ip)
                        else:
                            ips.append(ip)
                    except (ValueError, IndexError):
                        ips.append(ip)
        except:
            pass
        
        # Способ 3: Через сетевые интерфейсы (Windows)
        try:
            import subprocess
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'IPv4' in line or 'IP Address' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        ip = parts[-1].strip()
                        if ip and not ip.startswith('127.') and ip not in ips:
                            try:
                                if ip.startswith('192.168.') or ip.startswith('10.'):
                                    ips.insert(0, ip)
                                elif ip.startswith('172.'):
                                    ip_parts = ip.split('.')
                                    if len(ip_parts) > 1:
                                        second_octet = int(ip_parts[1])
                                        if 16 <= second_octet <= 31:
                                            ips.insert(0, ip)
                                        else:
                                            ips.append(ip)
                                    else:
                                        ips.append(ip)
                                else:
                                    ips.append(ip)
                            except (ValueError, IndexError):
                                ips.append(ip)
        except:
            pass
        
        # Возвращаем первый найденный локальный IP или первый доступный
        if ips:
            return ips[0]
        return "localhost"
    
    def get_all_local_ips():
        """Получает все локальные IP адреса"""
        ips = []
        try:
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ip and not ip.startswith('127.'):
                    if ip.startswith('192.168.') or ip.startswith('10.') or (ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31):
                        if ip not in ips:
                            ips.insert(0, ip)
                    else:
                        if ip not in ips:
                            ips.append(ip)
        except:
            pass
        return ips
    
    def check_firewall_rule(port):
        """Проверяет наличие правила файрвола для порта"""
        try:
            import subprocess
            result = subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
                capture_output=True, text=True, timeout=5
            )
            return str(port) in result.stdout
        except:
            return False
    
    # Получаем порт из переменной окружения или используем 5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Показываем информацию о запуске
    print()
    print("=" * 70)
    print("🚀 WebApp запущен!")
    print("=" * 70)
    print()
    
    local_ip = get_local_ip()
    all_ips = get_all_local_ips()
    token = os.environ.get('BETA_ACCESS_TOKEN', '')
    
    # Проверяем файрвол
    firewall_ok = check_firewall_rule(port)
    
    # Определяем основную ссылку для всех устройств
    if local_ip and local_ip != "localhost":
        main_url = f"http://{local_ip}:{port}"
        if token:
            main_url_with_token = f"{main_url}/?token={token}"
        else:
            main_url_with_token = main_url
    else:
        main_url = None
        main_url_with_token = None
    
    print("🌐 ЕДИНАЯ ССЫЛКА ДЛЯ ВСЕХ УСТРОЙСТВ:")
    print("   (работает на компьютере, телефоне и других устройствах в вашей Wi-Fi сети)")
    print()
    if main_url:
        if token:
            print(f"   {main_url_with_token}")
        else:
            print(f"   {main_url}")
        print()
        print("   📋 Скопируйте эту ссылку и отправьте другим пользователям!")
        print("   💻 Откройте на компьютере - работает")
        print("   📱 Откройте на телефоне - работает")
        print("   👥 Другие в вашей Wi-Fi сети тоже могут использовать эту ссылку")
    else:
        print("   ⚠️  Не удалось определить IP адрес")
        print("   Попробуйте один из этих адресов:")
        for ip in all_ips[:3]:
            if token:
                print(f"   http://{ip}:{port}/?token={token}")
            else:
                print(f"   http://{ip}:{port}")
    print()
    
    # Альтернативные ссылки (для справки)
    if len(all_ips) > 1 and main_url:
        print("📋 Альтернативные IP адреса (если основной не работает):")
        for ip in all_ips:
            if ip != local_ip:
                if token:
                    print(f"   http://{ip}:{port}/?token={token}")
                else:
                    print(f"   http://{ip}:{port}")
        print()
    
    # Также показываем localhost для удобства на локальной машине
    print("💻 Для быстрого доступа на этом компьютере:")
    if token:
        print(f"   http://localhost:{port}/?token={token}")
    else:
        print(f"   http://localhost:{port}")
    print()
    
    if token:
        print(f"🔐 Токен доступа: {token}")
        print()
    
    # Предупреждение о файрволе
    if not firewall_ok:
        print("⚠️  ВНИМАНИЕ: Правило файрвола для порта не найдено!")
        print("   Для доступа с телефона может потребоваться:")
        print("   1. Запустить setup_firewall.bat от имени администратора")
        print("   2. Или вручную добавить исключение в файрвол Windows")
        print()
    
    print("=" * 70)
    print(f"📊 Сервер: {host}:{port} | Debug: {debug}")
    print("=" * 70)
    print()
    print("Нажмите Ctrl+C для остановки...")
    print()
    
    app.run(host=host, port=port, debug=debug)

