#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервисы для создания туннелей без установки дополнительных программ
Использует только Python библиотеки и онлайн сервисы
"""

import requests
import json
import time
import threading
import subprocess
import sys
import os

class TunnelService:
    """Базовый класс для туннельных сервисов"""
    
    def __init__(self, port=5000):
        self.port = port
        self.url = None
        self.process = None
    
    def start(self):
        """Запускает туннель"""
        raise NotImplementedError
    
    def stop(self):
        """Останавливает туннель"""
        raise NotImplementedError
    
    def get_url(self):
        """Возвращает публичный URL"""
        return self.url


class LocalTunnelService(TunnelService):
    """Использует localtunnel через npx (если установлен Node.js)"""
    
    def start(self):
        """Запускает localtunnel через npx"""
        try:
            # Проверяем наличие npx
            result = subprocess.run(['npx', '--version'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode != 0:
                return False, "Node.js/npx не установлен"
            
            # Запускаем localtunnel
            self.process = subprocess.Popen(
                ['npx', '--yes', 'localtunnel', '--port', str(self.port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Ждем получения URL
            for _ in range(30):  # Максимум 30 секунд
                line = self.process.stdout.readline()
                if 'url' in line.lower() or 'https://' in line.lower():
                    # Извлекаем URL из строки
                    import re
                    urls = re.findall(r'https://[^\s]+', line)
                    if urls:
                        self.url = urls[0]
                        return True, self.url
                time.sleep(1)
            
            return False, "Не удалось получить URL"
            
        except FileNotFoundError:
            return False, "Node.js/npx не найден. Установите Node.js с https://nodejs.org"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()


class ServeoService(TunnelService):
    """Использует serveo.net (не требует установки)"""
    
    def start(self):
        """Запускает SSH туннель через serveo.net"""
        try:
            # Используем SSH для создания туннеля
            # serveo.net предоставляет бесплатный SSH туннель
            cmd = [
                'ssh',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-R', f'80:localhost:{self.port}',
                'serveo.net'
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Читаем вывод для получения URL
            for _ in range(30):
                line = self.process.stdout.readline()
                if line:
                    if 'Forwarding' in line or 'https://' in line:
                        import re
                        urls = re.findall(r'https://[^\s]+', line)
                        if urls:
                            self.url = urls[0]
                            return True, self.url
                time.sleep(1)
            
            return False, "Не удалось получить URL от serveo.net"
            
        except FileNotFoundError:
            return False, "SSH не найден. На Windows установите OpenSSH или используйте другой метод"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()


class CloudflaredService(TunnelService):
    """Использует cloudflared (скачивается автоматически)"""
    
    def start(self):
        """Запускает cloudflared туннель"""
        try:
            # Проверяем наличие cloudflared
            cloudflared_path = self._get_cloudflared()
            if not cloudflared_path:
                return False, "Не удалось получить cloudflared"
            
            # Запускаем cloudflared
            self.process = subprocess.Popen(
                [cloudflared_path, 'tunnel', '--url', f'http://localhost:{self.port}'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Читаем вывод
            for _ in range(30):
                line = self.process.stdout.readline()
                if line and 'https://' in line:
                    import re
                    urls = re.findall(r'https://[^\s]+\.trycloudflare\.com', line)
                    if urls:
                        self.url = urls[0]
                        return True, self.url
                time.sleep(1)
            
            return False, "Не удалось получить URL"
            
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def _get_cloudflared(self):
        """Получает cloudflared (скачивает если нужно)"""
        import platform
        import urllib.request
        import zipfile
        import shutil
        
        system = platform.system().lower()
        arch = platform.machine().lower()
        
        # Определяем путь для cloudflared
        if system == 'windows':
            exe_name = 'cloudflared.exe'
            url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
        elif system == 'linux':
            exe_name = 'cloudflared'
            url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64'
        elif system == 'darwin':
            exe_name = 'cloudflared'
            url = 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64'
        else:
            return None
        
        cloudflared_path = os.path.join(os.path.dirname(__file__), exe_name)
        
        # Если уже есть, используем его
        if os.path.exists(cloudflared_path):
            return cloudflared_path
        
        # Скачиваем
        try:
            print(f"[INFO] Скачивание cloudflared...")
            urllib.request.urlretrieve(url, cloudflared_path)
            if system != 'windows':
                os.chmod(cloudflared_path, 0o755)
            return cloudflared_path
        except Exception as e:
            print(f"[ERROR] Не удалось скачать cloudflared: {e}")
            return None
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()


def get_available_service(port=5000):
    """Возвращает доступный туннельный сервис"""
    services = [
        CloudflaredService(port),  # Самый надежный, скачивается автоматически
        LocalTunnelService(port),  # Если установлен Node.js
        ServeoService(port),       # Если установлен SSH
    ]
    
    for service in services:
        print(f"[INFO] Пробуем {service.__class__.__name__}...")
        success, result = service.start()
        if success:
            return service, result
        else:
            print(f"[INFO] {result}")
            service.stop()
    
    return None, "Не удалось найти доступный сервис"


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    print("=" * 60)
    print("🌐 Поиск доступного туннельного сервиса...")
    print("=" * 60)
    print()
    
    service, result = get_available_service(port)
    
    if service:
        print("=" * 60)
        print("✅ Туннель создан!")
        print(f"📱 Публичный URL: {result}")
        print("=" * 60)
        print()
        print("Нажмите Ctrl+C для остановки...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[INFO] Остановка туннеля...")
            service.stop()
            print("[INFO] Туннель остановлен")
    else:
        print("=" * 60)
        print("❌ Ошибка:", result)
        print("=" * 60)
        print()
        print("Альтернативы:")
        print("1. Установите Node.js и используйте localtunnel")
        print("2. Используйте ngrok (см. BETA_QUICKSTART.md)")
        print("3. Используйте локальный IP (см. QUICKSTART.md)")

