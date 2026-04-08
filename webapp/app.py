#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flask приложение для WebApp Telegram бота
"""

import os
import sys
import hmac
import hashlib
import json
from urllib.parse import parse_qs
from flask import Flask, render_template, request, jsonify, session, make_response
from functools import wraps
import time

# Добавляем родительскую директорию в путь для импорта модулей бота
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import get_user, is_admin, ensure_user, get_user_registration_date, get_user_last_active
    from database import get_ref_count, get_deposits_sum, get_user_garden_level, get_garden_level_info
    from database import get_user_trees, get_all_fruits, get_fruit_price, get_withdrawals_by_status
    from database import get_active_boosters_grouped, get_user_achievements
    from database import get_referrals, get_referral_info, get_ref_bonus, add_balance, set_user_balance
    from database import get_deposits, create_deposit, approve_deposit, reject_deposit_with_reason
    from database import get_deposit_by_id, get_withdrawal_by_id
    from database import get_maintenance_mode, set_maintenance_mode
    from database import get_withdrawals_by_status, create_withdraw, confirm_withdraw, reject_withdraw_with_reason
    from database import get_active_tasks, get_task_by_id, create_task, complete_task, get_all_tasks
    from database import get_user_tasks_stats, get_user_task_completions, get_task_completions_stats
    from database import update_task
    from database import get_user_trees, get_all_fruits, get_tree_price, get_fruit_price, get_all_fruit_prices
    from database import get_user_garden_level, get_garden_level_info, get_next_garden_level_price, set_user_garden_level
    from database import get_user_garden_commission, add_fruit, remove_fruit, water_tree, get_tree_watering_status
    from database import get_user_trees_with_watering, get_garden_history_summary, can_upgrade_garden_level
    from database import get_watering_settings
    from database import harvest_user_garden
    from database import get_user_activity_feed
    from database import get_economy_harvest_multiplier, get_effective_fruit_price, get_fruit_amount
    from database import set_tree_price, set_fruit_price, get_garden_history_by_date, get_tree_income, set_tree_income
    from database import get_or_create_local_user, get_next_local_user_id
    from database import use_promo_code, add_fruit, get_user_office, get_user_office_employees
    from database import get_gift_last_play, get_gift_cooldown_hours, format_duration
    from database import calculate_deposit_bonus
    from database import (
        get_gift_session_version,
        get_gift_attempts,
        get_gift_level_attempts,
        init_default_gift_attempts,
        get_gift_bombs_count,
        get_gift_attempt_reward,
        set_gift_last_play,
        set_gift_bombs_count,
        set_gift_cooldown_hours,
        set_gift_attempts,
        get_gift_reward_balance,
        set_gift_reward_balance,
        get_gift_reward_fruit,
        set_gift_reward_fruit,
        set_gift_attempt_reward,
        reset_all_gift_cooldowns,
        bump_gift_session_version,
    )
    from database import get_user_state, set_user_state, get_user_garden_level
    from database import _db
    from database import create_notification, get_user_notifications, get_unread_notifications_count
    from database import mark_notification_read, mark_all_notifications_read, delete_notification
    from database import (
        create_support_ticket,
        add_support_message,
        get_support_ticket,
        get_support_tickets_for_user,
        get_support_messages,
        list_support_tickets,
        update_support_ticket_status,
        mark_support_ticket_read,
        get_user_support_unread_count,
        get_admin_support_unread_summary,
    )
    from database import add_beta, remove_beta, get_beta_testers_stats, get_beta_testers
    from database import remove_inactive_beta_testers, cleanup_inactive_beta_testers
    from database import is_beta, get_user_by_username
    from database import get_min_deposit, set_min_deposit
    from database import (
        get_latest_news_for_user,
        mark_news_viewed,
        create_news,
        update_news,
        delete_news,
        get_news,
        list_news,
        get_news_stats,
        set_news_like,
        get_unread_news_count,
        get_branding_settings,
        update_branding_settings,
    )
    # Мінімальний вивід зберігається в окремому модулі, який працює без ORM
    from min_withdraw_utils import get_min_withdraw, set_min_withdraw
except ImportError as e:
    print(f"[ERROR] Failed to import database module: {e}")
    raise

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.environ.get('WEBAPP_SECRET_KEY', 'change-this-secret-key-in-production')

# Получаем токен бота для проверки подписи
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7612542064:AAHj6KKNYHuJP1Jjyf06IeeJTe1XMZcsVM8")

# Бета-доступ: токен для ограничения доступа
BETA_ACCESS_TOKEN = os.environ.get('BETA_ACCESS_TOKEN', None)
BETA_TESTERS = os.environ.get('BETA_TESTERS', '').split(',') if os.environ.get('BETA_TESTERS') else []

# Вспомогательные функции форматирования
def format_currency(amount):
    """Форматирует сумму валюты"""
    try:
        return f"{float(amount or 0):.2f}"
    except (ValueError, TypeError):
        return "0.00"


def _safe_create_notification(user_id: int, notif_type: str, title: str, message: str, extra: dict | None = None):
    """Створює уведомлення без падіння основного потоку."""
    if not user_id:
        return
    try:
        create_notification(user_id, notif_type, title, message, extra or {})
    except Exception as notify_error:
        print(f"[WARN] Failed to create notification ({notif_type}) for user {user_id}: {notify_error}")


def _derive_watering_display(status: dict | None) -> int:
    """Відповідає JS-функції deriveWaterVisual та повертає відсоток води для сумарної статистики."""
    if not status:
        return 100
    is_withered = bool(status.get('is_withered'))
    base_water = round(float(status.get('water_level', 100)) or 100)
    interval = max(60, int(status.get('watering_interval') or 900))
    wither_threshold = max(interval * 2, int(status.get('wither_threshold') or (interval * 8)))
    seconds_until_next = max(0, int(status.get('seconds_until_next_water') or 0))
    time_passed = max(0, int(status.get('time_passed') or 0))
    can_water = status.get('can_water_now', True) not in (False, 0, '0')

    display_level = base_water
    if is_withered:
        display_level = min(display_level, 25)
    elif not can_water and seconds_until_next > 0:
        ratio = 1 - min(1, seconds_until_next / interval)
        display_level = max(base_water, round(65 + ratio * 30))
    else:
        safe_threshold = max(1, wither_threshold)
        ratio = min(1, time_passed / safe_threshold)
        display_level = max(15, round(100 - ratio * 70))
    return int(min(100, max(0, display_level)))


def _build_watering_alerts(trees_with_watering: list[dict]) -> dict:
    """Формує агреговану статистику для UI (скільки дерев потребує уваги)."""
    summary = {
        'total_tree_slots': 0,
        'withered_trees': 0,
        'low_water_trees': 0,
        'details': []
    }
    for entry in trees_with_watering or []:
        count = int(entry.get('count') or 0)
        if count <= 0:
            continue
        status = entry.get('watering_status') or {}
        summary['total_tree_slots'] += count
        if status.get('is_withered'):
            summary['withered_trees'] += count
            summary['details'].append({
                'tree_type': entry.get('tree_type'),
                'count': count,
                'kind': 'withered'
            })
        else:
            display_level = _derive_watering_display(status)
            if display_level < 40:
                summary['low_water_trees'] += count
                summary['details'].append({
                    'tree_type': entry.get('tree_type'),
                    'count': count,
                    'kind': 'low_water'
                })
    return summary

def format_kiev_time(timestamp):
    """Форматирует timestamp в киевское время"""
    try:
        import datetime
        import calendar
        
        def _kyiv_offset_seconds_for_timestamp(ts: int) -> int:
            dt_utc = datetime.datetime.utcfromtimestamp(int(ts))
            year = dt_utc.year
            def last_sunday(year: int, month: int) -> int:
                last_day = calendar.monthrange(year, month)[1]
                wd = datetime.date(year, month, last_day).weekday()
                return last_day - ((wd + 1) % 7)
            dst_start_utc = datetime.datetime(year, 3, last_sunday(year, 3), 1, 0, 0)
            dst_end_utc = datetime.datetime(year, 10, last_sunday(year, 10), 1, 0, 0)
            if dst_start_utc <= dt_utc < dst_end_utc:
                return 3 * 3600
            return 2 * 3600
        
        offset = _kyiv_offset_seconds_for_timestamp(timestamp)
        dt = datetime.datetime.utcfromtimestamp(timestamp) + datetime.timedelta(seconds=offset)
        return dt.strftime('%d.%m.%Y %H:%M')
    except Exception:
        return str(timestamp)

def verify_telegram_webapp_data(init_data: str) -> dict:
    """
    Проверяет подпись initData от Telegram WebApp
    Возвращает словарь с данными пользователя или None если проверка не прошла
    """
    try:
        # Парсим initData
        parsed_data = parse_qs(init_data)
        
        # Извлекаем hash и остальные данные
        received_hash = parsed_data.get('hash', [None])[0]
        if not received_hash:
            return None
        
        # Удаляем hash из данных для проверки
        auth_data = []
        for key, value in parsed_data.items():
            if key != 'hash':
                auth_data.append(f"{key}={value[0]}")
        
        auth_data.sort()
        data_check_string = '\n'.join(auth_data)
        
        # Вычисляем секретный ключ
        secret_key = hmac.new(
            "WebAppData".encode('utf-8'),
            BOT_TOKEN.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Проверяем hash
        if calculated_hash != received_hash:
            print(f"[WARNING] Hash mismatch: calculated={calculated_hash}, received={received_hash}")
            return None
        
        # Парсим user данные
        user_data = parsed_data.get('user', [None])[0]
        if user_data:
            user_dict = json.loads(user_data)
            # photo_url может быть в initDataUnsafe, но не в подписанных данных
            # Поэтому мы его не получаем здесь, а будем получать на клиенте
            return user_dict
        
        return None
    except Exception as e:
        print(f"[ERROR] Error verifying Telegram WebApp data: {e}")
        return None

def check_beta_access():
    """Проверяет доступ по токену бета-тестирования"""
    if not BETA_ACCESS_TOKEN:
        return True  # Токен не установлен - доступ открыт
    
    # Проверяем токен из параметра URL или сессии
    token = request.args.get('token') or session.get('beta_token')
    
    if token and token == BETA_ACCESS_TOKEN:
        session['beta_token'] = token
        return True
    
    # Если токен неверный или отсутствует
    return False

def require_telegram_auth(f):
    """Декоратор для проверки авторизации через Telegram WebApp или создания локального пользователя"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_start_time = time.time()
        
        # Проверяем бета-доступ (если включен)
        if BETA_ACCESS_TOKEN and not check_beta_access():
            # Если это API запрос, возвращаем ошибку
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Beta access token required', 'beta_required': True}), 403
            # Если это страница, показываем форму ввода токена
            return render_template('beta_access.html', error='Неверный токен доступа')
        
        # Получаем initData из заголовка или параметра (Telegram WebApp)
        init_data = request.headers.get('X-Telegram-Init-Data') or request.args.get('_auth')
        
        # В режиме разработки пропускаем проверку подписи Telegram, но все равно проверяем наличие данных
        dev_mode = os.environ.get('WEBAPP_DEV_MODE') == '1'
        
        if init_data:
            # Есть Telegram данные - используем Telegram ID
            if dev_mode:
                # В режиме разработки пропускаем проверку подписи
                try:
                    parsed_data = parse_qs(init_data)
                    user_data_str = parsed_data.get('user', [None])[0]
                    if user_data_str:
                        user_data = json.loads(user_data_str)
                    else:
                        user_data = None
                except Exception:
                    user_data = None
            else:
                # В обычном режиме проверяем подпись
                user_data = verify_telegram_webapp_data(init_data)
                # Если photo_url не в подписанных данных, пробуем получить из initDataUnsafe
                if user_data and not user_data.get('photo_url'):
                    try:
                        # Пробуем получить из initDataUnsafe (если доступно на клиенте)
                        # Но на сервере мы не имеем доступа к initDataUnsafe, поэтому это делается на клиенте
                        pass
                    except:
                        pass
            
            if not user_data:
                # Если нет валидных Telegram данных, создаем локального пользователя
                # Проверяем cookie для постоянства сессии
                saved_session_id = request.cookies.get('local_session_id')
                if saved_session_id:
                    session['local_session_id'] = saved_session_id
                elif 'local_session_id' not in session:
                    import uuid
                    session['local_session_id'] = str(uuid.uuid4())
                
                try:
                    local_user_id = get_or_create_local_user(session['local_session_id'], 'Гість')
                    session['user_id'] = local_user_id
                    session['is_telegram_user'] = False
                    session['username'] = None
                    session['first_name'] = 'Гість'
                    session['last_name'] = ''
                except Exception as e:
                    print(f"[ERROR] Failed to create local user: {e}")
                    return jsonify({'error': 'Failed to create user session'}), 500
            else:
                # Валидные Telegram данные - используем Telegram ID
                telegram_user_id = user_data.get('id')
                session['user_id'] = telegram_user_id
                session['username'] = user_data.get('username')
                session['first_name'] = user_data.get('first_name')
                session['last_name'] = user_data.get('last_name')
                session['photo_url'] = user_data.get('photo_url')  # Сохраняем photo_url если есть
                session['is_telegram_user'] = True
                
                # Убеждаемся, что пользователь существует в БД
                try:
                    user_name = (user_data.get('first_name', '') + ' ' + user_data.get('last_name', '')).strip() or user_data.get('username', 'User')
                    ensure_user(telegram_user_id, user_name)
                except Exception:
                    pass
        else:
            # Нет Telegram данных - проверяем сохраненный user_id из cookie (для админов)
            saved_user_id = request.cookies.get('admin_user_id')
            if saved_user_id:
                try:
                    saved_user_id = int(saved_user_id)
                    # Проверяем, что пользователь является админом
                    if is_admin(saved_user_id):
                        session['user_id'] = saved_user_id
                        session['is_telegram_user'] = True
                        user_row = get_user(saved_user_id)
                        if user_row:
                            session['username'] = user_row[8]
                            session['first_name'] = user_row[1] or 'Admin'
                            session['last_name'] = ''
                            print(f"[DEBUG] Using saved admin user_id={saved_user_id}")
                        else:
                            ensure_user(saved_user_id, f'Admin {saved_user_id}')
                            session['username'] = None
                            session['first_name'] = f'Admin {saved_user_id}'
                            session['last_name'] = ''
                    else:
                        # Сохраненный ID не админ, создаем локального пользователя
                        saved_user_id = None
                except (ValueError, TypeError):
                    saved_user_id = None
            
            if not saved_user_id:
                # Нет сохраненного админского ID - создаем/используем локального пользователя
                # Проверяем cookie для постоянства сессии
                saved_session_id = request.cookies.get('local_session_id')
                if saved_session_id:
                    session['local_session_id'] = saved_session_id
                elif 'local_session_id' not in session:
                    import uuid
                    session['local_session_id'] = str(uuid.uuid4())
                
                try:
                    local_user_id = get_or_create_local_user(session['local_session_id'], 'Гість')
                    session['user_id'] = local_user_id
                    session['is_telegram_user'] = False
                    session['username'] = None
                    session['first_name'] = 'Гість'
                    session['last_name'] = ''
                except Exception as e:
                    print(f"[ERROR] Failed to create local user: {e}")
                    return jsonify({'error': 'Failed to create user session'}), 500
        
        # Проверяем режим технічних робіт для звичайних користувачів
        try:
            maintenance_enabled = get_maintenance_mode()
        except Exception as maintenance_error:
            print(f"[ERROR] Failed to read maintenance flag: {maintenance_error}")
            maintenance_enabled = False

        if maintenance_enabled:
            print("[MAINT] Maintenance mode active - VERSION 3.0")
            user_id = session.get('user_id')
            is_admin_user = bool(user_id and is_admin(user_id))
            is_beta_user = bool(user_id and is_beta(user_id))
            print(f"[MAINT] user_id={user_id}, is_admin={is_admin_user}, is_beta={is_beta_user}")
            if not (is_admin_user or is_beta_user):
                print("[MAINT] Rendering maintenance page with NEW inline HTML")
                maintenance_message = '🔧 На сайті тривають технічні роботи. Спробуйте пізніше.'
                if request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'maintenance',
                        'maintenance': True,
                        'message': maintenance_message,
                        'user_id': user_id
                    }), 503
                else:
                    # Используем render_template для гарантии использования правильного шаблона
                    beta_user_id_val = str(user_id or session.get('local_session_id', '-'))
                    version_id = int(time.time())  # Уникальный ID версии для принудительного обновления
                    
                    # Генерируем HTML с версионированием для принудительного обновления
                    maintenance_html = f'''<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="version" content="{version_id}">
    <title>Технічні роботи (v{version_id})</title>
    <link rel="stylesheet" href="/static/css/main.css?v={int(time.time())}">
    <script>
        // ВЕРСИЯ: {version_id} - Принудительное обновление при загрузке
        (function() {{
            var VERSION_ID = {version_id};
            var EXPECTED_BETA_TEXT = 'Хочеш протестувати першим';
            var CHECKED = false;
            
            // Функция принудительной очистки кеша и перезагрузки
            function forceReload() {{
                if (CHECKED) return; // Предотвращаем множественные перезагрузки
                CHECKED = true;
                console.log('[MAINT] Принудительная перезагрузка для версии', VERSION_ID);
                
                // Очищаем весь кеш
                if ('caches' in window) {{
                    caches.keys().then(function(names) {{
                        names.forEach(function(name) {{ caches.delete(name); }});
                    }});
                }}
                sessionStorage.clear();
                localStorage.clear();
                
                // Принудительная перезагрузка с уникальным параметром
                var url = location.href.split('?')[0];
                var separator = url.includes('?') ? '&' : '?';
                // Используем location.replace вместо location.href для предотвращения кеширования
                location.replace(url + separator + 'v=' + VERSION_ID + '&_t=' + Date.now() + '&_r=' + Math.random() + '&_force=1');
            }}
            
            // Проверка наличия всех необходимых элементов
            function validatePage() {{
                if (CHECKED) return true;
                
                var betaInvite = document.querySelector('.beta-invite');
                var betaCta = document.querySelector('.beta-cta');
                var hasBetaText = document.body && document.body.textContent && document.body.textContent.includes(EXPECTED_BETA_TEXT);
                var hasBetaUserID = document.querySelector('.beta-user-id');
                var versionAttr = betaInvite ? betaInvite.getAttribute('data-version') : null;
                
                // Проверяем версию из мета-тега
                var metaVersion = document.querySelector('meta[name="version"]');
                var metaVersionValue = metaVersion ? metaVersion.getAttribute('content') : null;
                
                // Если отсутствует ЛЮБОЙ из элементов ИЛИ версия не совпадает - это старая версия
                if (!betaInvite || !betaCta || !hasBetaText || !hasBetaUserID || versionAttr != VERSION_ID || metaVersionValue != VERSION_ID.toString()) {{
                    console.log('[MAINT] Обнаружена старая версия!', {{
                        betaInvite: !!betaInvite,
                        betaCta: !!betaCta,
                        hasBetaText: hasBetaText,
                        hasBetaUserID: !!hasBetaUserID,
                        versionAttr: versionAttr,
                        expectedVersion: VERSION_ID,
                        metaVersion: metaVersionValue
                    }});
                    forceReload();
                    return false;
                }}
                CHECKED = true;
                return true;
            }}
            
            // Немедленная проверка при загрузке (до загрузки DOM)
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', function() {{
                    setTimeout(function() {{
                        if (!validatePage()) return;
                        // Дополнительные проверки
                        setTimeout(validatePage, 50);
                        setTimeout(validatePage, 200);
                    }}, 10);
                }});
            }} else {{
                setTimeout(function() {{
                    if (!validatePage()) return;
                    setTimeout(validatePage, 50);
                    setTimeout(validatePage, 200);
                }}, 10);
            }}
            
            // Проверка при каждом изменении DOM (на случай динамической загрузки)
            if (document.body) {{
                var observer = new MutationObserver(function() {{
                    if (!CHECKED) {{
                        validatePage();
                    }}
                }});
                observer.observe(document.body, {{ childList: true, subtree: true }});
            }}
        }})();
    </script>
    <style>
        body {{ display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
        .beta-invite {{ margin-top: 24px; padding: 18px; border-radius: 16px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.08); }}
        .beta-invite h3 {{ margin-top: 0; margin-bottom: 8px; font-size: 18px; }}
        .beta-invite p {{ margin: 4px 0; color: rgba(255, 255, 255, 0.8); }}
        .beta-cta {{ display: inline-flex; align-items: center; justify-content: center; margin-top: 12px; padding: 10px 20px; border-radius: 999px; background: linear-gradient(120deg, #4facfe, #00f2fe); color: #0b1130; font-weight: 600; text-decoration: none; box-shadow: 0 10px 25px rgba(0, 242, 254, 0.2); transition: transform 0.2s ease, box-shadow 0.2s ease; }}
        .beta-cta:hover {{ transform: translateY(-2px); box-shadow: 0 14px 30px rgba(0, 242, 254, 0.25); }}
        .beta-note {{ font-size: 13px; color: rgba(255, 255, 255, 0.6) !important; }}
        .beta-user-id {{ margin-top: 14px; padding: 12px 16px; border-radius: 12px; background: rgba(7, 16, 42, 0.6); border: 1px dashed rgba(255, 255, 255, 0.2); }}
        .beta-user-id-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: rgba(255, 255, 255, 0.6); }}
        .beta-user-id-value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
    </style>
</head>
<body>
    <div class="maintenance-overlay active" style="position: static; background: transparent;">
        <div class="maintenance-card">
            <div class="maintenance-icon">🛠</div>
            <h2>Технічні роботи</h2>
            <p>Ми тимчасово обмежили доступ до кабінету, щоб встановити оновлення. Зазвичай це займає лише кілька хвилин.</p>
            <!-- VERSION {version_id} - BETA INVITE ALWAYS VISIBLE -->
            <div class="beta-invite" data-version="{version_id}">
                <h3>Хочеш протестувати першим?</h3>
                <p>Бета-тестери отримують ранній доступ навіть під час оновлень. Напиши нам у Telegram та отримай персональний пропуск.</p>
                <a class="beta-cta" href="https://t.me/palmaron" target="_blank" rel="noopener noreferrer">
                    <span>Написати @palmaron</span>
                </a>
                <div class="beta-user-id">
                    <div class="beta-user-id-label">Твій ID для бета-доступу:</div>
                    <div class="beta-user-id-value">{beta_user_id_val}</div>
                    <p class="beta-note">Скопіюй та надішли цей ID у повідомленні — ми включимо тебе до списку тестерів.</p>
                </div>
            </div>
            <p style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: rgba(255,255,255,0.6);">Дякуємо за розуміння 💙</p>
        </div>
    </div>
</body>
</html>'''
                    response = make_response(maintenance_html, 200)  # 200 вместо 503 чтобы браузер не кешировал
                    response.headers['Content-Type'] = 'text/html; charset=utf-8'
                    # Максимально агрессивные заголовки против кеширования
                    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private, proxy-revalidate, pre-check=0, post-check=0'
                    response.headers['Pragma'] = 'no-cache'
                    response.headers['Expires'] = '0'
                    response.headers['X-Maintenance-Version'] = f'6.0-beta-invite-v{version_id}'
                    response.headers['X-Content-Type-Options'] = 'nosniff'
                    response.headers['Last-Modified'] = 'Thu, 01 Jan 1970 00:00:00 GMT'
                    response.headers['ETag'] = ''
                    response.headers['Vary'] = '*'
                    # Добавляем версионирование в заголовки для дополнительной защиты
                    response.headers['X-Timestamp'] = str(version_id)
                    response.headers['X-Version-ID'] = str(version_id)
                    return response

        # Логируем время обработки (только для медленных запросов)
        elapsed = time.time() - request_start_time
        if elapsed > 1.0:
            print(f"[SLOW] {request.path} обработан за {elapsed:.2f}с")
        
        # Выполняем функцию и оборачиваем ответ для установки cookie
        result = f(*args, **kwargs)
        
        # Если это JSON ответ, оборачиваем его для установки cookie
        if isinstance(result, tuple) and len(result) == 2:
            response_obj, status = result
            if hasattr(response_obj, 'set_cookie'):
                response = response_obj
            else:
                response = make_response(response_obj, status)
        elif hasattr(result, 'set_cookie'):
            response = result
        elif isinstance(result, str):
            # Это может быть HTML шаблон
            response = make_response(result)
        else:
            response = make_response(result)
        
        # Сохраняем local_session_id в cookie для постоянства сессии
        local_session_id = session.get('local_session_id')
        if local_session_id:
            response.set_cookie('local_session_id', local_session_id, max_age=60*60*24*30)  # 30 дней
        
        # Сохраняем user_id в cookie если это админ
        user_id = session.get('user_id')
        if user_id and user_id > 0 and is_admin(user_id):
            response.set_cookie('admin_user_id', str(user_id), max_age=60*60*24*30)  # 30 дней
        
        return response if isinstance(result, tuple) and len(result) == 2 else response
    return decorated_function

def require_admin(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    @require_telegram_auth
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        is_telegram_user = session.get('is_telegram_user', True)
        
        # Проверяем админа для всех пользователей (и Telegram, и локальных)
        # Это позволяет использовать админку без Telegram
        if not user_id:
            return jsonify({'error': 'Admin access required. User not found.'}), 403
        
        if not is_admin(user_id):
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Главная страница WebApp"""
    # Проверяем бета-доступ
    if BETA_ACCESS_TOKEN and not check_beta_access():
        return render_template('beta_access.html')
    response = make_response(render_template('index.html'))
    # Устанавливаем cookie для сохранения user_id админа (если есть)
    user_id = session.get('user_id')
    if user_id and user_id > 0 and is_admin(user_id):
        response.set_cookie('admin_user_id', str(user_id), max_age=60*60*24*30)  # 30 дней
    
    # Сохраняем local_session_id в cookie для постоянства сессии
    local_session_id = session.get('local_session_id')
    if local_session_id:
        response.set_cookie('local_session_id', local_session_id, max_age=60*60*24*30)  # 30 дней
    
    return response

@app.route('/set-admin-cookie/<int:user_id>')
def set_admin_cookie(user_id):
    """Устанавливает cookie для админа (только если пользователь действительно админ)"""
    if not is_admin(user_id):
        return jsonify({'error': 'User is not admin'}), 403
    
    # Убеждаемся, что пользователь существует
    user_row = get_user(user_id)
    if not user_row:
        ensure_user(user_id, f'Admin {user_id}')
    
    # Устанавливаем сессию
    session['user_id'] = user_id
    session['is_telegram_user'] = True
    if user_row:
        session['username'] = user_row[8]
        session['first_name'] = user_row[1] or 'Admin'
    else:
        session['username'] = None
        session['first_name'] = f'Admin {user_id}'
    session['last_name'] = ''
    
    # Создаем ответ с cookie
    response = make_response(jsonify({'success': True, 'message': f'Admin cookie set for user {user_id}'}))
    response.set_cookie('admin_user_id', str(user_id), max_age=60*60*24*30)  # 30 дней
    
    # Перенаправляем на главную
    response.headers['Location'] = '/'
    response.status_code = 302
    return response

@app.route('/health')
def health():
    """Проверка здоровья сервера (быстрый ответ)"""
    return jsonify({
        'status': 'ok', 
        'message': 'Server is running',
        'timestamp': time.time()
    }), 200

@app.before_request
def log_request_info():
    """Логирует информацию о запросах для диагностики"""
    if request.path.startswith('/static/'):
        return  # Пропускаем статические файлы
    
    # Логируем только медленные или проблемные запросы
    pass

@app.route('/beta/access', methods=['GET', 'POST'])
def beta_access():
    """Страница ввода токена бета-доступа"""
    if request.method == 'POST':
        token = request.form.get('token', '').strip()
        if token == BETA_ACCESS_TOKEN:
            session['beta_token'] = token
            return render_template('index.html')
        else:
            return render_template('beta_access.html', error='Неверный токен доступа')
    return render_template('beta_access.html')

@app.route('/cabinet')
def cabinet():
    """Страница кабинета пользователя"""
    return render_template('cabinet.html')

@app.route('/forms/deposit')
@require_telegram_auth
def deposit_form_page():
    """Окно форми поповнення"""
    return render_template('form_deposit.html')

@app.route('/forms/withdraw')
@require_telegram_auth
def withdraw_form_page():
    """Окно форми виводу"""
    return render_template('form_withdraw.html')

@app.route('/tasks')
def tasks():
    """Страница заданий пользователя"""
    return render_template('tasks.html')

@app.route('/garden')
def garden():
    """Страница сада пользователя"""
    return render_template('garden.html')

@app.route('/promo')
def promo():
    """Страница активации промокода"""
    return render_template('promo.html')

@app.route('/gift')
def gift():
    """Страница подарунка"""
    return render_template('gift.html')

@app.route('/info')
def info():
    """Страница информации"""
    return render_template('info.html')

@app.route('/debug/maintenance')
def debug_maintenance():
    """Вспомогательный роут для превью страницы техработ"""
    try:
        beta_user_id = request.args.get('user_id') or session.get('user_id') or '-'
    except Exception:
        beta_user_id = '-'
    return render_template(
        'maintenance.html',
        beta_user_id=beta_user_id,
        beta_contact='@palmaron',
        is_admin=session.get('user_id') and is_admin(session.get('user_id'))
    )

@app.route('/url')
def show_url():
    """Страница для отображения сохраненной ссылки"""
    url = None
    token = None
    
    # Читаем сохраненную ссылку
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp_url.txt')
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webapp_token.txt')
    
    if os.path.exists(url_file):
        try:
            with open(url_file, 'r', encoding='utf-8') as f:
                url = f.read().strip()
        except Exception:
            pass
    
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                token = f.read().strip()
        except Exception:
            pass
    
    return render_template('url_info.html', url=url, token=token)

@app.route('/office')
def office():
    """Страница инвестиционного офиса"""
    return render_template('office.html')

@app.route('/notifications')
def notifications():
    """Страница уведомлений"""
    return render_template('notifications.html')

@app.route('/admin/tasks')
@require_admin
def admin_tasks():
    """Страница управления заданиями для админа"""
    return render_template('admin-tasks.html')

@app.route('/admin')
@require_admin
def admin():
    """Страница админ-панели"""
    return render_template('admin.html')

@app.route('/admin/garden')
@require_admin
def admin_garden():
    """Страница админ-панели управления садом"""
    return render_template('admin-garden.html')

@app.route('/api/user/info')
@require_telegram_auth
def api_user_info():
    """API: Информация о пользователе"""
    try:
        print(f"[DEBUG] api_user_info called, session keys: {list(session.keys())}")
        user_id = session.get('user_id')
        print(f"[DEBUG] api_user_info: user_id from session = {user_id}")
        if not user_id:
            print("[ERROR] api_user_info: user_id not found in session")
            return jsonify({'error': 'User not found'}), 404
        
        user_row = get_user(user_id)
        if not user_row:
            # Создаем пользователя если его нет
            user_name = session.get('first_name', '')
            if session.get('last_name'):
                user_name += f" {session.get('last_name')}"
            if not user_name:
                user_name = session.get('username') or f'User {user_id}'
            ensure_user(user_id, user_name or str(user_id))
            user_row = get_user(user_id)
        
        if not user_row:
            return jsonify({'error': 'Failed to get user data'}), 500
        
        user_id_db, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username = user_row
        
        # Если имя пустое, используем данные из сессии или Telegram
        if not user_name or user_name.strip() == '' or user_name == 'Користувач' or user_name == 'Гість':
            # Приоритет: first_name из сессии → username из сессии → username из БД → fallback
            user_name = session.get('first_name', '') or session.get('username', '') or username or f'User {user_id_db}'
        
        # Если все еще пустое, используем дефолтное имя
        if not user_name or user_name.strip() == '':
            user_name = 'Користувач'
        
        # Получаем дополнительную информацию для header
        try:
            ref_count = get_ref_count(user_id_db)
            deposits_sum = get_deposits_sum(user_id_db)
        except Exception:
            ref_count = 0
            deposits_sum = float(deposits or 0)
        
        # Определяем тип пользователя
        is_telegram_user = session.get('is_telegram_user', user_id_db > 0)
        
        # Отладочная информация
        print(f"[DEBUG] api_user_info: user_id={user_id_db}, is_telegram_user={is_telegram_user}")
        
        # Проверяем админа: строго проверяем, есть ли user_id в таблице admins
        # Работает для всех пользователей (и Telegram, и локальных)
        admin_check_result = is_admin(user_id_db)
        # Убеждаемся, что возвращается boolean значение
        if not isinstance(admin_check_result, bool):
            admin_check_result = bool(admin_check_result)
        print(f"[DEBUG] api_user_info: is_admin({user_id_db}) = {admin_check_result} (type: {type(admin_check_result)})")
        
        # Получаем имя бота для реферальной ссылки
        try:
            import os
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", BOT_TOKEN)
            if bot_token:
                # Пробуем получить username бота из БД или используем дефолтный
                bot_username = os.environ.get('BOT_USERNAME', 'your_bot')
                ref_link = f"https://t.me/{bot_username}?start={user_id_db}"
            else:
                ref_link = None
        except Exception:
            ref_link = None
        
        try:
            branding_settings = get_branding_settings()
        except Exception:
            branding_settings = {}
        try:
            unread_news = int(get_unread_news_count(user_id_db))
        except Exception:
            unread_news = 0
        
        # Отладочная информация
        print(f"[DEBUG] api_user_info response: user_id={user_id_db}, user_name={user_name}, balance={balance}")
        
        # Приоритет для отображения имени: username из Telegram → first_name → user_name → fallback
        display_name = None
        if is_telegram_user:
            display_name = session.get('username') or session.get('first_name') or user_name
        else:
            display_name = user_name or session.get('first_name')
        
        if not display_name or display_name.strip() == '' or display_name == 'Користувач' or display_name == 'Гість':
            display_name = session.get('username') or username or 'Користувач'
        
        # Убеждаемся, что user_id_db положительный (для Telegram пользователей)
        # Если user_id_db отрицательный, но это Telegram пользователь - это ошибка
        final_user_id = user_id_db
        if is_telegram_user:
            if user_id_db and user_id_db < 0:
                print(f"[WARN] Telegram user has negative ID: {user_id_db}, using session user_id: {user_id}")
                # Используем user_id из сессии, если он положительный
                if user_id and user_id > 0:
                    final_user_id = user_id
                else:
                    # Если и в сессии нет положительного ID, используем то что есть, но логируем
                    print(f"[ERROR] Telegram user has no positive ID! session user_id: {user_id}, db user_id: {user_id_db}")
            elif not user_id_db or user_id_db <= 0:
                # Если user_id_db пустой или отрицательный, пробуем из сессии
                if user_id and user_id > 0:
                    final_user_id = user_id
                    print(f"[WARN] Using session user_id for Telegram user: {user_id}")
        
        # Убеждаемся, что username передается правильно
        final_username = username or session.get('username') or None
        
        response_data = {
            'user_id': final_user_id if final_user_id and final_user_id > 0 else (user_id if user_id and user_id > 0 else user_id_db),
            'user_name': display_name,
            'username': final_username,
            'balance': float(balance or 0),
            'withdrawn': float(withdrawn or 0),
            'deposits': float(deposits_sum or deposits or 0),
            'deposits_sum': float(deposits_sum or deposits or 0),
            'ref_count': ref_count,
            'date_joined': date_joined,
            'last_active': last_active,
            'is_admin': admin_check_result,
            'is_telegram_user': is_telegram_user,
            'ref_link': ref_link if is_telegram_user else None,
            'telegram': {
                'first_name': session.get('first_name') or user_name,
                'last_name': session.get('last_name'),
                'username': session.get('username') or final_username,
                'id': final_user_id if (is_telegram_user and final_user_id and final_user_id > 0) else (user_id if is_telegram_user and user_id and user_id > 0 else None),
                'photo_url': session.get('photo_url')  # Добавляем photo_url если есть
            } if is_telegram_user else None,
            'branding': branding_settings,
            'news': {
                'unread_count': unread_news
            }
        }
        
        response = make_response(jsonify(response_data))
        
        # Сохраняем local_session_id в cookie для постоянства сессии
        local_session_id = session.get('local_session_id')
        if local_session_id:
            response.set_cookie('local_session_id', local_session_id, max_age=60*60*24*30)  # 30 дней
        
        return response
    except Exception as e:
        print(f"[ERROR] Error in api_user_info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/cabinet')
@require_telegram_auth
def api_user_cabinet():
    """API: Данные кабинета пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем базовую информацию
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        user_id_db, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username = user_row
        is_admin_flag = bool(is_admin(user_id))
        
        # Получаем дополнительную информацию
        ref_count = get_ref_count(user_id)
        deposits_sum = get_deposits_sum(user_id)
        reg_date = get_user_registration_date(user_id)
        last_active_ts = get_user_last_active(user_id)
        
        # Информация о саде
        try:
            garden_level = get_user_garden_level(user_id)
            level_info = get_garden_level_info(garden_level)
            level_name = level_info['name'] if level_info else '—'
            level_bonus = level_info['bonus_percent'] if level_info else 0
            level_commission = level_info['commission_percent'] if level_info else 15
        except Exception:
            garden_level, level_name, level_bonus, level_commission = 0, '—', 0, 15
        
        # Деревья
        trees = get_user_trees(user_id) or []
        tree_counts = {}
        for t in trees:
            tree_counts[t['type']] = tree_counts.get(t['type'], 0) + 1
        trees_total = sum(tree_counts.values())
        
        # Фрукты
        fruits = get_all_fruits(user_id) or {}
        total_fruits_value = 0.0
        fruits_list = []
        for ftype, amount in fruits.items():
            price = get_fruit_price(ftype) or 0
            value = (amount or 0) * price
            total_fruits_value += value
            fruits_list.append({
                'type': ftype,
                'amount': amount or 0,
                'price': price,
                'value': value
            })
        
        # Бустеры
        boosters = get_active_boosters_grouped(user_id)
        
        # Достижения
        achievements = get_user_achievements(user_id)
        
        # Ожидающие выводы
        try:
            pending_withdraws = len([r for r in get_withdrawals_by_status('pending') if r[1] == user_id])
        except Exception:
            pending_withdraws = 0
        
        # Ліміти по операціях
        try:
            min_deposit = float(get_min_deposit() or 0)
        except Exception:
            min_deposit = 0.0
        try:
            min_withdraw = float(get_min_withdraw() or 0)
        except Exception:
            min_withdraw = 0.0
        try:
            branding_settings = get_branding_settings()
        except Exception:
            branding_settings = {}
        try:
            unread_news = int(get_unread_news_count(user_id))
        except Exception:
            unread_news = 0
        try:
            activity_history = get_user_activity_feed(user_id, limit=30)
        except Exception:
            activity_history = []
        
        return jsonify({
            'user': {
                'id': user_id_db,
                'name': user_name,
                'username': username,
                'balance': float(balance or 0),
                'withdrawn': float(withdrawn or 0),
                'deposits': float(deposits or 0),
                'ref_count': ref_count,
                'deposits_sum': float(deposits_sum or 0),
                'date_joined': reg_date,
                'last_active': last_active_ts,
                'is_admin': is_admin_flag
            },
            'garden': {
                'level': garden_level,
                'level_name': level_name,
                'bonus_percent': level_bonus,
                'commission_percent': level_commission,
                'trees_total': trees_total,
                'tree_counts': tree_counts,
                'fruits': fruits_list,
                'fruits_total_value': total_fruits_value
            },
            'boosters': boosters,
            'achievements': [{'name': a[0], 'date': a[1]} for a in achievements] if achievements else [],
            'pending_withdraws': pending_withdraws,
            'limits': {
                'min_deposit': min_deposit,
                'min_withdraw': min_withdraw
            },
            'branding': branding_settings,
            'news': {
                'unread_count': unread_news
            },
            'history': activity_history
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_cabinet: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/history')
@require_telegram_auth
def api_user_history():
    """API: Історія фінансових операцій користувача"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        limit = request.args.get('limit', default=50, type=int) or 50
        limit = max(1, min(limit, 200))
        history = get_user_activity_feed(user_id, limit=limit)
        return jsonify({'history': history})
    except Exception as e:
        print(f"[ERROR] Error in api_user_history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/news')
@require_telegram_auth
def api_user_news():
    """API: Стрічка новин для користувача"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        limit = request.args.get('limit', default=3, type=int) or 3
        limit = max(1, min(limit, 10))
        news_items = get_latest_news_for_user(user_id, limit)
        for item in news_items:
            created_at = item.get('created_at')
            if created_at:
                try:
                    item['created_human'] = format_kiev_time(created_at)
                except Exception:
                    item['created_human'] = created_at
        return jsonify({'news': news_items})
    except Exception as e:
        print(f"[ERROR] Error in api_user_news: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/news/<int:news_id>/view', methods=['POST'])
@require_telegram_auth
def api_user_news_view(news_id: int):
    """API: Позначити новину як переглянуту / вподобану"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        data = request.get_json() or {}
        like_toggle = data.get('like')
        if like_toggle is not None:
            set_news_like(news_id, user_id, bool(like_toggle))
        else:
            mark_news_viewed(news_id, user_id, liked=bool(data.get('liked')))
        news_item = get_news(news_id)
        stats = get_news_stats(news_id)
        response = {
            'status': 'ok',
            'news': news_item,
            'stats': stats
        }
        return jsonify(response)
    except Exception as e:
        print(f"[ERROR] Error in api_user_news_view: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/panel')
@require_admin
def api_admin_panel():
    """API: Данные для админ-панели"""
    try:
        # Здесь можно добавить статистику для админов
        return jsonify({
            'status': 'ok',
            'message': 'Admin panel data',
            'stats': {
                # Можно добавить статистику из БД
            }
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_panel: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/news', methods=['GET'])
@require_admin
def api_admin_news_list():
    """Адмін: список новин"""
    try:
        include_drafts = request.args.get('include_drafts', '1') not in ('0', 'false', 'False')
        status_filter = request.args.get('status')
        limit = request.args.get('limit', default=50, type=int) or 50
        items = list_news(limit=limit, status=status_filter, include_drafts=include_drafts)
        return jsonify({'news': items})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_news_list: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/news', methods=['POST'])
@require_admin
def api_admin_news_create():
    """Адмін: створення новини"""
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        content = (data.get('content') or '').strip()
        if not title or not content:
            return jsonify({'error': 'Потрібні заголовок та текст'}), 400
        news_id = create_news(
            title=title,
            content=content,
            author_id=session.get('user_id'),
            cover_url=data.get('cover_url'),
            cta_label=data.get('cta_label'),
            cta_url=data.get('cta_url'),
            status=data.get('status', 'published'),
            pinned=bool(data.get('pinned'))
        )
        created_news = get_news(news_id)
        print(f"[News] Created news ID: {news_id}, status: {created_news.get('status') if created_news else 'N/A'}")
        return jsonify({'news_id': news_id, 'news': created_news})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_news_create: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/news/<int:news_id>', methods=['PUT', 'PATCH'])
@require_admin
def api_admin_news_update(news_id: int):
    """Адмін: оновлення новини"""
    try:
        data = request.get_json() or {}
        fields = {key: data.get(key) for key in ['title', 'content', 'cover_url', 'cta_label', 'cta_url', 'status', 'pinned']}
        if not any(value is not None for value in fields.values()):
            return jsonify({'error': 'Немає даних для оновлення'}), 400
        update_news(news_id, **fields)
        news_item = get_news(news_id)
        if not news_item:
            return jsonify({'error': 'Новину не знайдено'}), 404
        return jsonify({'news': news_item})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_news_update: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/news/<int:news_id>', methods=['DELETE'])
@require_admin
def api_admin_news_delete(news_id: int):
    """Адмін: видалення новини"""
    try:
        deleted = delete_news(news_id)
        if not deleted:
            return jsonify({'error': 'Новину не знайдено'}), 404
        return jsonify({'status': 'deleted', 'news_id': news_id})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_news_delete: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/news/<int:news_id>/stats')
@require_admin
def api_admin_news_stats(news_id: int):
    """Адмін: статистика новини"""
    try:
        news_item = get_news(news_id)
        if not news_item:
            return jsonify({'error': 'Новину не знайдено'}), 404
        stats = get_news_stats(news_id)
        stats['news'] = news_item
        return jsonify(stats)
    except Exception as e:
        print(f"[ERROR] Error in api_admin_news_stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/branding', methods=['GET', 'POST'])
@require_admin
def api_admin_branding():
    """Адмін: налаштування брендингу"""
    try:
        if request.method == 'GET':
            return jsonify(get_branding_settings())
        updates = request.get_json() or {}
        settings = update_branding_settings(updates)
        return jsonify(settings)
    except Exception as e:
        print(f"[ERROR] Error in api_admin_branding: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/gift/settings', methods=['GET', 'POST'])
@require_admin
def api_admin_gift_settings():
    """Адмін: налаштування подарунків"""
    try:
        if request.method == 'GET':
            levels = []
            for level in range(1, 6):
                attempts = get_gift_attempts(level)
                reward_balance = get_gift_reward_balance(level)
                fruit_type, fruit_amount = get_gift_reward_fruit(level)
                rewards = get_gift_level_attempts(level)
                levels.append({
                    'level': level,
                    'attempts': attempts,
                    'reward_balance': reward_balance,
                    'fruit_type': fruit_type,
                    'fruit_amount': fruit_amount,
                    'rewards': [
                        {
                            'attempt_number': row[0],
                            'reward_balance': row[1],
                            'fruit_type': row[2],
                            'fruit_amount': row[3]
                        }
                        for row in rewards
                    ]
                })
            return jsonify({
                'bombs_count': get_gift_bombs_count(),
                'cooldown_hours': get_gift_cooldown_hours(),
                'session_version': get_gift_session_version(),
                'levels': levels
            })

        data = request.get_json() or {}
        action = data.get('action', 'basic')

        if action == 'basic':
            bombs = data.get('bombs_count')
            cooldown = data.get('cooldown_hours')
            reset_sessions = bool(data.get('reset_sessions'))
            reset_cooldowns = bool(data.get('reset_cooldowns'))
            if bombs is not None:
                set_gift_bombs_count(int(bombs))
            if cooldown is not None:
                set_gift_cooldown_hours(int(cooldown))
            if reset_sessions:
                bump_gift_session_version()
            if reset_cooldowns:
                reset_all_gift_cooldowns()
            return jsonify({'status': 'ok'})

        if action == 'level':
            level = int(data.get('level', 1))
            if 'attempts' in data:
                set_gift_attempts(level, int(data['attempts']))
            if 'reward_balance' in data:
                set_gift_reward_balance(level, float(data['reward_balance']))
            if 'fruit_type' in data or 'fruit_amount' in data:
                fruit_type = data.get('fruit_type', 'apple')
                fruit_amount = float(data.get('fruit_amount', 0))
                set_gift_reward_fruit(level, fruit_type, fruit_amount)
            if data.get('regenerate_rewards'):
                attempts_count = get_gift_attempts(level)
                init_default_gift_attempts(level, attempts_count)
            return jsonify({'status': 'ok'})

        if action == 'attempt':
            level = int(data.get('level', 1))
            attempt_number = int(data.get('attempt_number', 1))
            reward_balance = float(data.get('reward_balance', 0))
            fruit_type = data.get('fruit_type', 'apple')
            fruit_amount = float(data.get('fruit_amount', 0))
            set_gift_attempt_reward(level, attempt_number, reward_balance, fruit_type, fruit_amount)
            return jsonify({'status': 'ok'})

        return jsonify({'error': 'Unknown action'}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_admin_gift_settings: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/action', methods=['POST'])
@require_telegram_auth
def api_user_action():
    """API: Выполнение действий пользователя"""
    try:
        data = request.get_json()
        action = data.get('action')
        
        # Здесь можно добавить обработку различных действий
        # Например: депозит, вывод, использование промокода и т.д.
        
        return jsonify({
            'status': 'ok',
            'message': f'Action {action} processed'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_action: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/referrals')
@require_telegram_auth
def api_user_referrals():
    """API: Реферальная программа пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем рефералов
        referrals = get_referrals(user_id) or []
        ref_count = get_ref_count(user_id)
        ref_bonus = get_ref_bonus()
        
        # Получаем имя бота для реферальной ссылки
        try:
            # Пробуем получить username бота из переменной окружения или используем дефолтный
            bot_username = os.environ.get('BOT_USERNAME')
            if not bot_username:
                # Пробуем получить из токена (если формат стандартный)
                try:
                    import requests
                    bot_info = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe", timeout=5).json()
                    if bot_info.get('ok'):
                        bot_username = bot_info['result'].get('username', 'your_bot')
                    else:
                        bot_username = 'your_bot'
                except Exception:
                    bot_username = 'your_bot'
            ref_link = f"https://t.me/{bot_username}?start={user_id}"
        except Exception:
            ref_link = None
        
        return jsonify({
            'ref_link': ref_link,
            'ref_count': ref_count,
            'ref_bonus': float(ref_bonus),
            'referrals': [{'user_id': r[0], 'user_name': r[1]} for r in referrals]
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_referrals: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/deposit', methods=['POST'])
@require_telegram_auth
def api_user_deposit():
    """API: Создание депозита"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json() or {}
        amount = float(data.get('amount', 0))
        comment = data.get('comment', '')
        
        if amount <= 0:
            return jsonify({'error': 'Некоректна сума поповнення'}), 400
        
        # Перевірка мінімального депозиту
        try:
            min_dep = float(get_min_deposit() or 0)
        except Exception:
            min_dep = 0.0
        if min_dep > 0 and amount < min_dep:
            return jsonify({'error': f'Мінімальна сума поповнення: {min_dep:.2f}₴'}), 400
        
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        user_name = user_row[1]
        
        # Создаем депозит
        dep_id = create_deposit(user_id, user_name, amount, comment)

        try:
            create_notification(
                user_id,
                'deposit',
                'Запит на поповнення створено',
                f"Ми зарахуємо {format_currency(amount)}₴ після перевірки оператора.",
                {
                    'deposit_id': dep_id,
                    'amount': float(amount),
                    'status': 'pending'
                }
            )
        except Exception as notify_error:
            print(f"[WARN] Failed to send deposit notification for user {user_id}: {notify_error}")
        
        return jsonify({
            'status': 'ok',
            'deposit_id': dep_id,
            'message': 'Deposit request created'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_deposit: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/withdraw', methods=['POST'])
@require_telegram_auth
def api_user_withdraw():
    """API: Создание вывода"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json() or {}
        amount = float(data.get('amount', 0))
        requisites = data.get('requisites', '')
        
        if amount <= 0:
            return jsonify({'error': 'Некоректна сума для виводу'}), 400
        
        # Перевірка мінімальної суми виводу
        try:
            min_wd = float(get_min_withdraw() or 0)
        except Exception:
            min_wd = 0.0
        if min_wd > 0 and amount < min_wd:
            return jsonify({'error': f'Мінімальна сума для виводу: {min_wd:.2f}₴'}), 400
        
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        balance = float(user_row[2] or 0)
        if amount > balance:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Создаем вывод (используем функцию из database.py)
        wd_id = create_withdraw(user_id, amount, 'manual', requisites)

        try:
            create_notification(
                user_id,
                'withdraw',
                'Запит на вивід створено',
                f"Ми опрацюємо {format_currency(amount)}₴ та повідомимо про результат.",
                {
                    'withdrawal_id': wd_id,
                    'amount': float(amount),
                    'status': 'pending'
                }
            )
        except Exception as notify_error:
            print(f"[WARN] Failed to send withdraw notification for user {user_id}: {notify_error}")
        
        return jsonify({
            'status': 'ok',
            'withdrawal_id': wd_id,
            'message': 'Withdrawal request created'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_withdraw: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/users')
@require_admin
def api_admin_users():
    """API: Список пользователей для админа"""
    try:
        with _db() as con:
            rows = con.execute("""
                SELECT user_id, user_name, balance, username, date_joined 
                FROM users 
                ORDER BY balance DESC 
                LIMIT 100
            """).fetchall()
        
        users = []
        for row in rows:
            users.append({
                'user_id': row[0],
                'user_name': row[1] or 'Unknown',
                'balance': float(row[2] or 0),
                'username': row[3],
                'date_joined': row[4]
            })
        
        return jsonify({'users': users})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_users: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/promo/activate', methods=['POST'])
@require_telegram_auth
def api_promo_activate():
    """API: Активация промокода"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        code = data.get('code', '').strip().upper()
        
        if not code:
            return jsonify({'error': 'Промокод не може бути порожнім'}), 400
        
        # Используем функцию из database.py
        ok, result = use_promo_code(code, user_id)
        
        if not ok:
            return jsonify({
                'status': 'error',
                'message': result
            }), 400
        
        reward, info = result
        
        # Обрабатываем награду в зависимости от типа
        reward_info = {
            'type': 'balance',
            'amount': float(reward),
            'message': f'Нараховано {reward:.2f} UAH'
        }
        
        if isinstance(info, dict):
            rtype = info.get('type')
            ritem = info.get('item')
            
            if rtype == 'fruit':
                add_fruit(user_id, ritem, int(reward))
                from garden_models import get_fruit_name_uk
                item_name = get_fruit_name_uk(ritem)
                reward_info = {
                    'type': 'fruit',
                    'item': ritem,
                    'item_name': item_name,
                    'amount': int(reward),
                    'message': f'Нараховано {int(reward)} {item_name}'
                }
            elif rtype == 'booster':
                from database import grant_booster
                from garden_models import BOOSTERS
                grant_booster(user_id, ritem, int(reward))
                booster_name = next((b['name'] for b in BOOSTERS if b['type'] == ritem), ritem)
                booster_emoji = next((b.get('emoji', '⚡') for b in BOOSTERS if b['type'] == ritem), '⚡')
                reward_info = {
                    'type': 'booster',
                    'item': ritem,
                    'item_name': booster_name,
                    'emoji': booster_emoji,
                    'amount': int(reward),
                    'message': f'{booster_emoji} Активовано бустер {booster_name} на {int(reward)//60} хв!'
                }
            elif rtype == 'tree':
                from database import grant_tree
                grant_tree(user_id, ritem, int(reward))
                reward_info = {
                    'type': 'tree',
                    'item': ritem,
                    'amount': int(reward),
                    'message': f'Видано {int(reward)} дерево(а) типу {ritem}!'
                }
            elif rtype == 'balance':
                add_balance(user_id, float(reward), reason=f'Промокод {code}')
                reward_info = {
                    'type': 'balance',
                    'amount': float(reward),
                    'message': f'Нараховано {reward:.2f} UAH'
                }
        
        return jsonify({
            'status': 'ok',
            'message': 'Промокод активовано',
            'reward': reward_info
        })
    except Exception as e:
        print(f"[ERROR] Error in api_promo_activate: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def _gift_load_session(user_id):
    """Загружает сессию подарунка из user_state"""
    import json
    raw = get_user_state(user_id)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data.get('gift_session')
    except Exception:
        return None

def _gift_save_session(user_id, sess):
    """Сохраняет сессию подарунка в user_state"""
    import json
    raw = get_user_state(user_id)
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}
    data['gift_session'] = sess
    set_user_state(user_id, json.dumps(data))

def _gift_reward_preview(level):
    """Формує короткий список винагород для UI."""
    preview = []
    try:
        rewards = get_gift_level_attempts(level)
        if not rewards:
            attempts = int(get_gift_attempts(level))
            init_default_gift_attempts(level, attempts)
            rewards = get_gift_level_attempts(level)
        for attempt_number, reward_balance, fruit_type, fruit_amount in rewards:
            preview.append({
                'attempt': int(attempt_number),
                'balance': round(float(reward_balance or 0.0), 2),
                'fruit_type': fruit_type or 'apple',
                'fruit_amount': round(float(fruit_amount or 0.0), 2)
            })
    except Exception as e:
        print(f"[WARN] Failed to build gift preview for level {level}: {e}")
    return preview

@app.route('/api/user/gift/status')
@require_telegram_auth
def api_gift_status():
    """API: Статус подарунка (можно ли открыть, кулдаун и т.д.)"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        import time
        last_play = get_gift_last_play(user_id)
        cooldown_hours = get_gift_cooldown_hours()
        current_ver = int(get_gift_session_version())
        
        can_play = True
        wait_time = None
        
        if last_play:
            elapsed = int(time.time()) - last_play
            cooldown_seconds = cooldown_hours * 3600
            if elapsed < cooldown_seconds:
                can_play = False
                wait_time = cooldown_seconds - elapsed
        
        # Проверяем активную сессию
        sess = _gift_load_session(user_id)
        if sess and not sess.get('finished') and int(sess.get('ver', current_ver)) == current_ver:
            # Есть активная сессия
            picked = sess.get('picked_safe', [False]*10)
            lvl = sess.get('level', 1)
            attempts_left = int(sess.get('attempts_allowed', 0)) - int(sess.get('attempts_used', 0))
            acc_bal = float(sess.get('acc_balance', 0.0))
            acc_fam = float(sess.get('acc_fruits', 0.0))
            
            return jsonify({
                'can_play': True,
                'has_active_session': True,
                'level': lvl,
                'attempts_left': attempts_left,
                'attempts_allowed': int(sess.get('attempts_allowed', 0)),
                'attempts_used': int(sess.get('attempts_used', 0)),
                'accumulated_balance': acc_bal,
                'accumulated_fruits': acc_fam,
                'picked_safe': picked,
                'bombs': sess.get('bombs', []),
                'finished': sess.get('finished', False),
                'last_attempt_reward': sess.get('last_attempt_reward'),
                'fruit_type': sess.get('fruit_type'),
                'reward_preview': _gift_reward_preview(lvl)
            })
        
        # Получаем уровень сада для определения количества попыток
        garden_level = get_user_garden_level(user_id) or 0
        # Для уровня 0: базово 0 попыток, но даем 2 попытки
        if garden_level == 0:
            attempts = 2
        else:
            attempts = int(get_gift_attempts(garden_level))
        
        return jsonify({
            'can_play': can_play,
            'has_active_session': False,
            'wait_time': wait_time,
            'wait_time_formatted': format_duration(wait_time) if wait_time else None,
            'cooldown_hours': cooldown_hours,
            'garden_level': garden_level,
            'attempts': attempts,
            'reward_preview': _gift_reward_preview(garden_level)
        })
    except Exception as e:
        print(f"[ERROR] Error in api_gift_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/gift/start', methods=['POST'])
@require_telegram_auth
def api_gift_start():
    """API: Начало новой сессии подарунка"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        import time
        import random
        
        # Проверяем кулдаун
        last_play = get_gift_last_play(user_id)
        cooldown_hours = get_gift_cooldown_hours()
        if last_play:
            elapsed = int(time.time()) - last_play
            cooldown_seconds = cooldown_hours * 3600
            if elapsed < cooldown_seconds:
                wait_time = cooldown_seconds - elapsed
                return jsonify({
                    'status': 'error',
                    'message': f'Зачекайте {format_duration(wait_time)} перед наступною спробою'
                }), 400
        
        # Проверяем активную сессию
        current_ver = int(get_gift_session_version())
        sess = _gift_load_session(user_id)
        if sess and not sess.get('finished') and int(sess.get('ver', current_ver)) == current_ver:
            return jsonify({
                'status': 'ok',
                'message': 'У вас вже є активна сесія',
                'session': sess
            })
        
        # Создаем новую сессию
        garden_level = get_user_garden_level(user_id) or 1
        attempts = int(get_gift_attempts(garden_level))
        
        # Инициализируем награды за попытки, если их еще нет
        attempts_data = get_gift_level_attempts(garden_level)
        if not attempts_data:
            init_default_gift_attempts(garden_level, attempts)
        
        # Генерируем бомбы
        bombs_count = max(0, int(get_gift_bombs_count()))
        bombs = random.sample(range(10), bombs_count)
        
        sess = {
            'level': garden_level,
            'attempts_allowed': attempts,
            'attempts_used': 0,
            'bombs': bombs,
            'picked_safe': [False]*10,
            'finished': False,
            'acc_balance': 0.0,
            'acc_fruits': 0.0,
            'ver': current_ver,
        }
        _gift_save_session(user_id, sess)
        
        return jsonify({
            'status': 'ok',
            'session': sess,
            'message': 'Нова сесія створена'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_gift_start: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/gift/pick', methods=['POST'])
@require_telegram_auth
def api_gift_pick():
    """API: Открытие коробочки в подарунке"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        box_index = int(data.get('box_index', -1))
        
        if box_index < 0 or box_index >= 10:
            return jsonify({'error': 'Невірний індекс коробочки'}), 400
        
        import time
        current_ver = int(get_gift_session_version())
        sess = _gift_load_session(user_id)
        
        if not sess or sess.get('finished'):
            return jsonify({
                'status': 'error',
                'message': 'Створіть нову спробу через меню Подарунок'
            }), 400
        
        if int(sess.get('ver', current_ver)) != current_ver:
            return jsonify({
                'status': 'error',
                'message': 'Сесію оновлено. Відкрийте Подарунок знову.'
            }), 400
        
        picked = sess.get('picked_safe', [False]*10)
        if picked[box_index]:
            return jsonify({
                'status': 'error',
                'message': 'Цю коробочку вже відкривали'
            }), 400
        
        lvl = int(sess.get('level', 1))
        bombs = set(sess.get('bombs', []))
        used = int(sess.get('attempts_used', 0)) + 1
        allowed = int(sess.get('attempts_allowed', 0))
        
        # Если это бомба — проигрыш
        if box_index in bombs:
            sess['finished'] = True
            sess['attempts_used'] = used
            picked[box_index] = False  # бомба не становится безопасной
            _gift_save_session(user_id, sess)
            set_gift_last_play(user_id, int(time.time()))
            
            return jsonify({
                'status': 'bomb',
                'message': '💥 БОМБА! Нажаль, весь незабраний виграш згорів.',
                'box_index': box_index,
                'is_bomb': True,
                'attempts_left': max(allowed - used, 0),
                'session': sess
            })
        
        # Получаем награду за попытку
        attempt_number = sum(1 for v in picked if v) + 1
        bal_add, ftype, fruit_add = get_gift_attempt_reward(lvl, attempt_number)
        
        # Если нет настроек для этой попытки - используем старую систему как fallback
        if bal_add == 0.0 and fruit_add == 0.0:
            from database import get_gift_reward_balance, get_gift_reward_fruit
            base_bal = float(get_gift_reward_balance(lvl))
            ftype_fallback, base_famt = get_gift_reward_fruit(lvl)
            bal_add = base_bal * (2 * attempt_number - 1)
            fruit_add = float(base_famt) * attempt_number
            ftype = ftype_fallback
        
        # Сохраняем награду за текущую попытку
        sess['acc_balance'] = float(sess.get('acc_balance', 0.0)) + float(bal_add)
        sess['acc_fruits'] = float(sess.get('acc_fruits', 0.0)) + float(fruit_add)
        sess['last_attempt_reward'] = attempt_number
        sess['fruit_type'] = ftype
        picked[box_index] = True
        sess['picked_safe'] = picked
        sess['attempts_used'] = used
        
        # Если достигли лимита попыток — авто-кашаут
        if used >= allowed:
            sess['finished'] = True
            _gift_save_session(user_id, sess)
            set_gift_last_play(user_id, int(time.time()))
            
            # Начисляем награду
            total_bal = float(sess.get('acc_balance', bal_add))
            total_fruits = float(sess.get('acc_fruits', fruit_add))
            if total_bal > 0:
                add_balance(user_id, total_bal, reason="gift_reward")
            if total_fruits > 0:
                add_fruit(user_id, ftype, total_fruits)
            
            return jsonify({
                'status': 'finished',
                'message': f'Всі спроби використано! Нараховано: {total_bal:.2f} UAH та {int(total_fruits)} фруктів',
                'box_index': box_index,
                'reward': {
                    'balance': total_bal,
                    'fruits': total_fruits,
                    'fruit_type': ftype
                },
                'attempts_left': 0,
                'session': sess
            })
        
        _gift_save_session(user_id, sess)
        
        return jsonify({
            'status': 'ok',
            'message': f'Влучно! Виграш за {attempt_number}-й момент: {bal_add:.2f} UAH та {int(fruit_add)} фруктів',
            'box_index': box_index,
            'reward': {
                'balance': bal_add,
                'fruits': fruit_add,
                'fruit_type': ftype
            },
            'attempts_left': max(allowed - used, 0),
            'session': sess
        })
    except Exception as e:
        print(f"[ERROR] Error in api_gift_pick: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/gift/collect', methods=['POST'])
@require_telegram_auth
def api_gift_collect():
    """API: Сбор накопленного выигрыша"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        import time
        sess = _gift_load_session(user_id)
        
        if not sess or sess.get('finished'):
            return jsonify({
                'status': 'error',
                'message': 'Немає активного виграшу для збору'
            }), 400
        
        acc_bal = float(sess.get('acc_balance', 0.0))
        acc_fam = float(sess.get('acc_fruits', 0.0))
        ftype = sess.get('fruit_type')
        
        if not ftype:
            from database import get_gift_reward_fruit
            ftype, _ = get_gift_reward_fruit(sess.get('level', 1))
        
        # Начисляем награду
        if acc_bal > 0:
            add_balance(user_id, acc_bal, reason="gift_reward")
        if acc_fam > 0:
            add_fruit(user_id, ftype, acc_fam)
        
        # Завершаем сессию
        sess['finished'] = True
        _gift_save_session(user_id, sess)
        set_gift_last_play(user_id, int(time.time()))
        
        return jsonify({
            'status': 'ok',
            'message': f'Виграш зараховано: {acc_bal:.2f} UAH та {int(acc_fam)} фруктів',
            'reward': {
                'balance': acc_bal,
                'fruits': acc_fam,
                'fruit_type': ftype
            }
        })
    except Exception as e:
        print(f"[ERROR] Error in api_gift_collect: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/office')
@require_telegram_auth
def api_user_office():
    """API: Информация об инвестиционном офисе пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        try:
            office = get_user_office(user_id)
            employees = get_user_office_employees(user_id)
            
            return jsonify({
                'office': office,
                'employees': employees
            })
        except Exception as e:
            # Если функция не найдена, возвращаем базовую информацию
            return jsonify({
                'office': None,
                'employees': [],
                'message': 'Функція інвестиційного офісу в розробці'
            })
    except Exception as e:
        print(f"[ERROR] Error in api_user_office: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/balance/change', methods=['POST'])
@require_admin
def api_admin_change_balance():
    """API: Изменение баланса пользователя (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        target_user_id = int(data.get('user_id'))
        amount = float(data.get('amount', 0))
        action = data.get('action', 'add')  # 'add', 'subtract', 'set'
        
        target_user = get_user(target_user_id)
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        if action == 'add':
            add_balance(target_user_id, amount, force_admin=True, reason=f'Admin {admin_id} added balance')
        elif action == 'subtract':
            add_balance(target_user_id, -amount, force_admin=True, reason=f'Admin {admin_id} subtracted balance')
        elif action == 'set':
            set_user_balance(target_user_id, amount)
        else:
            return jsonify({'error': 'Invalid action'}), 400
        
        # Получаем новый баланс
        updated_user = get_user(target_user_id)
        new_balance = float(updated_user[2] or 0)
        
        return jsonify({
            'status': 'ok',
            'new_balance': new_balance,
            'message': f'Balance {action}ed successfully'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_change_balance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/promo/create', methods=['POST'])
@require_admin
def api_admin_promo_create():
    """API: Создание промокода (админ)"""
    try:
        data = request.get_json()
        code = data.get('code', '').strip().upper()
        reward_type = data.get('reward_type', 'balance')  # balance, fruit, booster, tree
        reward_value = data.get('reward_value', 0)
        max_uses = data.get('max_uses', None)  # None = безлимит
        expiry = data.get('expiry', None)  # Unix timestamp или None
        item_type = data.get('item_type', None)  # Для fruit/booster/tree
        item_value = data.get('item_value', None)
        
        if not code:
            return jsonify({'error': 'Код промокода не може бути порожнім'}), 400
        
        if reward_value <= 0:
            return jsonify({'error': 'Значення винагороди повинно бути більше 0'}), 400
        
        # Конвертируем expiry в timestamp если передан как строка даты
        if expiry and isinstance(expiry, str):
            try:
                from datetime import datetime
                expiry_dt = datetime.strptime(expiry, '%Y-%m-%d %H:%M:%S')
                expiry = int(expiry_dt.timestamp())
            except:
                try:
                    expiry_dt = datetime.strptime(expiry, '%Y-%m-%d')
                    expiry = int(expiry_dt.timestamp())
                except:
                    return jsonify({'error': 'Невірний формат дати закінчення'}), 400
        
        # Создаем промокод
        from database import create_promo_code
        create_promo_code(code, reward_type, reward_value, max_uses, expiry, item_type, item_value)
        
        return jsonify({
            'status': 'ok',
            'message': 'Промокод успішно створено',
            'code': code
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_promo_create: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/promo/list')
@require_admin
def api_admin_promo_list():
    """API: Список промокодов (админ)"""
    try:
        from database import _db
        with _db() as con:
            cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
            counter_col = 'uses' if 'uses' in cols else ('current_uses' if 'current_uses' in cols else 'uses')
            rows = con.execute(f"""
                SELECT code, reward_type, reward_value, max_uses, {counter_col}, expiry, item_type, item_value, created_at
                FROM promo_codes
                ORDER BY created_at DESC
                LIMIT 100
            """).fetchall()
            
            promo_codes = []
            for row in rows:
                code, reward_type, reward_value, max_uses, uses, expiry, item_type, item_value, created_at = row
                promo_codes.append({
                    'code': code,
                    'reward_type': reward_type,
                    'reward_value': float(reward_value),
                    'max_uses': max_uses,
                    'uses': int(uses) if uses else 0,
                    'expiry': expiry,
                    'item_type': item_type,
                    'item_value': item_value,
                    'created_at': created_at,
                    'is_active': expiry is None or expiry > int(time.time()),
                    'is_available': max_uses is None or (int(uses) if uses else 0) < max_uses
                })
            
            return jsonify({
                'status': 'ok',
                'promo_codes': promo_codes
            })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_promo_list: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/user/<int:user_id>/profile', methods=['POST'])
@require_admin
def api_admin_user_profile(user_id):
    """API: Редактирование профиля пользователя (админ)"""
    try:
        data = request.get_json()
        user_name = data.get('user_name', '').strip()
        username = data.get('username', '').strip()
        
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'Користувач не знайдено'}), 404
        
        # Обновляем имя пользователя
        if user_name:
            from database import _db
            with _db() as con:
                con.execute("UPDATE users SET user_name = ? WHERE user_id = ?", (user_name, user_id))
                con.commit()
        
        # Обновляем username если передан
        if username is not None:
            from database import _db
            with _db() as con:
                con.execute("UPDATE users SET username = ? WHERE user_id = ?", (username or None, user_id))
                con.commit()
        
        return jsonify({
            'status': 'ok',
            'message': 'Профіль оновлено'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_user_profile: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/requisites', methods=['GET', 'POST'])
@require_admin
def api_admin_requisites():
    """API: Управление реквизитами (админ)"""
    try:
        if request.method == 'GET':
            # Получаем реквизиты из БД или настроек
            from database import _db
            requisites = {}
            with _db() as con:
                # Проверяем наличие таблицы settings
                try:
                    rows = con.execute("SELECT key, value FROM settings WHERE key LIKE 'requisites%'").fetchall()
                    for row in rows:
                        requisites[row[0]] = row[1]
                except:
                    pass
            
            return jsonify({
                'status': 'ok',
                'requisites': requisites
            })
        else:
            # Сохраняем реквизиты
            data = request.get_json()
            requisites_text = data.get('requisites', '').strip()
            
            from database import _db
            with _db() as con:
                # Создаем таблицу settings если нет
                try:
                    con.execute("""
                        CREATE TABLE IF NOT EXISTS settings (
                            key TEXT PRIMARY KEY,
                            value TEXT
                        )
                    """)
                except:
                    pass
                
                # Сохраняем реквизиты
                con.execute("""
                    INSERT OR REPLACE INTO settings (key, value) 
                    VALUES ('requisites', ?)
                """, (requisites_text,))
                con.commit()
            
            return jsonify({
                'status': 'ok',
                'message': 'Реквізити оновлено'
            })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_requisites: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/promo/<code>')
@require_admin
def api_admin_promo_info(code):
    """API: Информация о промокоде (админ)"""
    try:
        from database import _db
        with _db() as con:
            cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
            counter_col = 'uses' if 'uses' in cols else ('current_uses' if 'current_uses' in cols else 'uses')
            row = con.execute(f"""
                SELECT code, reward_type, reward_value, max_uses, {counter_col}, expiry, item_type, item_value, created_at
                FROM promo_codes
                WHERE code = ?
            """, (code.upper(),)).fetchone()
            
            if not row:
                return jsonify({'error': 'Промокод не знайдено'}), 404
            
            code_val, reward_type, reward_value, max_uses, uses, expiry, item_type, item_value, created_at = row
            
            return jsonify({
                'status': 'ok',
                'promo_code': {
                    'code': code_val,
                    'reward_type': reward_type,
                    'reward_value': float(reward_value),
                    'max_uses': max_uses,
                    'uses': int(uses) if uses else 0,
                    'expiry': expiry,
                    'item_type': item_type,
                    'item_value': item_value,
                    'created_at': created_at,
                    'is_active': expiry is None or expiry > int(time.time()),
                    'is_available': max_uses is None or (int(uses) if uses else 0) < max_uses
                }
            })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_promo_info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/deposits')
@require_admin
def api_admin_deposits():
    """API: Список депозитов для админа"""
    try:
        status = request.args.get('status', None)
        deposits_list = get_deposits(status) if status else get_deposits()
        
        deposits = []
        for dep in deposits_list:
            if isinstance(dep, (list, tuple)):
                deposits.append({
                    'id': dep[0],
                    'user_id': dep[1],
                    'user_name': dep[2] if len(dep) > 2 else None,
                    'amount': float(dep[3] if len(dep) > 3 and dep[3] is not None else 0),
                    'comment': dep[4] if len(dep) > 4 else None,
                    'proof': dep[5] if len(dep) > 5 else None,
                    'status': dep[6] if len(dep) > 6 else None,
                    'created_at': dep[7] if len(dep) > 7 else None
                })
            else:
                deposits.append({
                    'id': getattr(dep, 'id', None),
                    'user_id': getattr(dep, 'user_id', None),
                    'user_name': getattr(dep, 'user_name', None),
                    'amount': float(getattr(dep, 'amount', 0) or 0),
                    'comment': getattr(dep, 'comment', None),
                    'proof': getattr(dep, 'proof', None),
                    'status': getattr(dep, 'status', None),
                    'created_at': getattr(dep, 'created_at', None)
                })
        
        return jsonify({'deposits': deposits})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_deposits: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/withdrawals')
@require_admin
def api_admin_withdrawals():
    """API: Список выводов для админа"""
    try:
        status = request.args.get('status', None)
        withdrawals_list = get_withdrawals_by_status(status) if status else get_withdrawals_by_status()
        
        withdrawals = []
        for wd in withdrawals_list:
            if isinstance(wd, (list, tuple)):
                withdrawals.append({
                    'id': wd[0],
                    'user_id': wd[1],
                    'amount': float(wd[2] if wd[2] is not None else 0),
                    'comment': wd[3] if len(wd) > 3 else None,
                    'status': wd[4] if len(wd) > 4 else None,
                    'created_at': wd[5] if len(wd) > 5 else None,
                    'processed_at': wd[6] if len(wd) > 6 else None,
                    'requisites': wd[7] if len(wd) > 7 else None
                })
            else:
                withdrawals.append({
                    'id': getattr(wd, 'id', None),
                    'user_id': getattr(wd, 'user_id', None),
                    'amount': float(getattr(wd, 'amount', 0) or 0),
                    'comment': getattr(wd, 'comment', None),
                    'status': getattr(wd, 'status', None),
                    'created_at': getattr(wd, 'created_at', None),
                    'processed_at': getattr(wd, 'processed_at', None),
                    'requisites': getattr(wd, 'requisites', None)
                })
        
        return jsonify({'withdrawals': withdrawals})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_withdrawals: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/action', methods=['POST'])
@require_admin
def api_admin_action():
    """API: Выполнение админских действий"""
    try:
        data = request.get_json()
        action = data.get('action')
        params = data.get('params', {})
        
        def safe_notify(user_id_target, notif_type, title, message, extra=None):
            if not user_id_target:
                return
            try:
                create_notification(user_id_target, notif_type, title, message, extra)
            except Exception as notify_error:
                print(f"[WARN] Failed to send notification ({notif_type}) to {user_id_target}: {notify_error}")

        def parse_deposit_row(row):
            if not row:
                return None
            return {
                'id': row[0],
                'user_id': row[1],
                'user_name': row[2],
                'amount': float(row[3] or 0),
                'comment': row[4],
                'proof': row[5],
                'status': row[6],
                'created_at': row[7]
            }

        def parse_withdraw_row(row):
            if not row:
                return None
            return {
                'id': row[0],
                'user_id': row[1],
                'amount': float(row[2] or 0),
                'comment': row[3],
                'status': row[4],
                'created_at': row[5],
                'processed_at': row[6],
                'requisites': row[7]
            }
        
        if action == 'approve_deposit':
            dep_id = int(params.get('deposit_id'))
            dep_row = parse_deposit_row(get_deposit_by_id(dep_id))
            approve_deposit(dep_id)
            if dep_row:
                bonus_info = calculate_deposit_bonus(dep_row['amount'])
                credited = bonus_info.get('effective', dep_row['amount'])
                safe_notify(
                    dep_row['user_id'],
                    'deposit',
                    'Депозит зараховано',
                    f"Баланс поповнено на {format_currency(credited)}₴.",
                    {
                        'deposit_id': dep_id,
                        'base_amount': dep_row['amount'],
                        'credited_amount': credited,
                        'bonus_amount': bonus_info.get('total', 0)
                    }
                )
            return jsonify({'status': 'ok', 'message': 'Deposit approved'})
        
        elif action == 'reject_deposit':
            dep_id = int(params.get('deposit_id'))
            reason = params.get('reason', '')
            dep_row = parse_deposit_row(get_deposit_by_id(dep_id))
            reject_deposit_with_reason(dep_id, reason)
            if dep_row:
                safe_notify(
                    dep_row['user_id'],
                    'deposit',
                    'Депозит відхилено',
                    f"Заявку на поповнення відхилено. {reason or 'Зверніться в підтримку.'}",
                    {
                        'deposit_id': dep_id,
                        'reason': reason,
                        'base_amount': dep_row['amount']
                    }
                )
            return jsonify({'status': 'ok', 'message': 'Deposit rejected'})
        
        elif action == 'approve_withdrawal':
            wd_id = int(params.get('withdrawal_id'))
            withdrawal_row = parse_withdraw_row(get_withdrawal_by_id(wd_id))
            success = confirm_withdraw(wd_id)
            if not success:
                return jsonify({'error': 'Не вдалося підтвердити вивід. Перевірте баланс користувача.'}), 400
            if withdrawal_row:
                safe_notify(
                    withdrawal_row['user_id'],
                    'withdraw',
                    'Вивід підтверджено',
                    f"Виплату на {format_currency(withdrawal_row['amount'])}₴ відправлено на зазначені реквізити.",
                    {
                        'withdrawal_id': wd_id,
                        'amount': withdrawal_row['amount'],
                        'status': 'done'
                    }
                )
            return jsonify({'status': 'ok', 'message': 'Withdrawal approved'})
        
        elif action == 'reject_withdrawal':
            wd_id = int(params.get('withdrawal_id'))
            reason = params.get('reason', '')
            penalty_raw = params.get('penalty_amount')
            penalty_value = 0.0
            if penalty_raw not in (None, '', 0):
                try:
                    penalty_value = max(0.0, float(penalty_raw))
                except (TypeError, ValueError):
                    return jsonify({'error': 'Некоректна сума списання'}), 400
            withdrawal_row = parse_withdraw_row(get_withdrawal_by_id(wd_id))
            reject_withdraw_with_reason(wd_id, reason)
            if withdrawal_row and penalty_value > 0:
                add_balance(
                    withdrawal_row['user_id'],
                    -penalty_value,
                    force_admin=True,
                    reason=f'Penalty for withdrawal #{wd_id}'
                )
            if withdrawal_row:
                message = f"Заявку на вивід відхилено. {reason or 'Зверніться до підтримки для уточнення.'}"
                if penalty_value > 0:
                    message += f" Додатково списано {format_currency(penalty_value)}₴."
                safe_notify(
                    withdrawal_row['user_id'],
                    'withdraw',
                    'Вивід відхилено',
                    message,
                    {
                        'withdrawal_id': wd_id,
                        'amount': withdrawal_row['amount'],
                        'status': 'rejected',
                        'reason': reason,
                        'penalty_amount': penalty_value
                    }
                )
            return jsonify({'status': 'ok', 'message': 'Withdrawal rejected'})
        
        elif action == 'create_task':
            # Создание задания
            title = params.get('title')
            description = params.get('description', '')
            task_type = params.get('task_type')
            task_data = params.get('task_data', {})
            reward_amount = float(params.get('reward_amount', 0))
            reward_type = params.get('reward_type', 'balance')
            max_completions = params.get('max_completions')
            expires_at = params.get('expires_at')
            
            if not title or not task_type:
                return jsonify({'error': 'Title and task_type are required'}), 400
            
            admin_id = session.get('user_id')
            task_id = create_task(
                title=title,
                description=description or None,
                task_type=task_type,
                task_data=task_data,
                reward_amount=reward_amount,
                created_by=admin_id,
                reward_type=reward_type,
                max_completions=max_completions,
                expires_at=expires_at
            )
            
            return jsonify({
                'status': 'ok',
                'task_id': task_id,
                'message': 'Task created successfully'
            })
        
        elif action == 'update_task_status':
            # Изменение статуса задания
            task_id = int(params.get('task_id'))
            new_status = params.get('status')  # 'active', 'paused', 'completed'
            
            from database import update_task
            update_task(task_id, status=new_status)
            return jsonify({'status': 'ok', 'message': 'Task status updated'})
        
        elif action == 'get_min_settings':
            # Поточні ліміти для депозитів та виводів
            try:
                min_dep = float(get_min_deposit() or 0)
            except Exception:
                min_dep = 0.0
            try:
                min_wd = float(get_min_withdraw() or 0)
            except Exception:
                min_wd = 0.0
            return jsonify({
                'status': 'ok',
                'min_deposit': min_dep,
                'min_withdraw': min_wd
            })
        
        elif action == 'set_min_deposit':
            new_min = float(params.get('amount', 0))
            if new_min <= 0:
                return jsonify({'error': 'Мінімальний депозит має бути більше 0'}), 400
            set_min_deposit(new_min)
            return jsonify({'status': 'ok', 'min_deposit': new_min})
        
        elif action == 'set_min_withdraw':
            new_min = float(params.get('amount', 0))
            if new_min <= 0:
                return jsonify({'error': 'Мінімальний вивід має бути більше 0'}), 400
            set_min_withdraw(new_min)
            return jsonify({'status': 'ok', 'min_withdraw': new_min})
        
        elif action == 'balance_stats':
            # Загальна статистика по балансам сайту
            with _db() as con:
                total_row = con.execute("""
                    SELECT 
                        COUNT(*) as users_total,
                        SUM(balance) as total_balance,
                        SUM(deposits) as total_deposits,
                        SUM(withdrawn) as total_withdrawn
                    FROM users
                """).fetchone()
                users_total = total_row[0] or 0
                total_balance = float(total_row[1] or 0)
                total_deposits = float(total_row[2] or 0)
                total_withdrawn = float(total_row[3] or 0)
                
                # Топ-10 за балансом
                top_rows = con.execute("""
                    SELECT user_id, user_name, balance 
                    FROM users 
                    ORDER BY balance DESC 
                    LIMIT 10
                """).fetchall()
                top_users = [{
                    'user_id': r[0],
                    'user_name': r[1] or 'Користувач',
                    'balance': float(r[2] or 0)
                } for r in top_rows]
            
            return jsonify({
                'status': 'ok',
                'stats': {
                    'users_total': users_total,
                    'total_balance': total_balance,
                    'total_deposits': total_deposits,
                    'total_withdrawn': total_withdrawn
                },
                'top_users': top_users
            })
        
        else:
            return jsonify({'error': 'Unknown action'}), 400
        
    except Exception as e:
        print(f"[ERROR] Error in api_admin_action: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/maintenance/status')
@require_admin
def api_admin_maintenance_status():
    """Повертає поточний стан технічних робіт"""
    try:
        return jsonify({
            'status': 'ok',
            'enabled': get_maintenance_mode()
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_maintenance_status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/maintenance/toggle', methods=['POST'])
@require_admin
def api_admin_maintenance_toggle():
    """Вмикає або вимикає технічні роботи"""
    try:
        data = request.get_json() or {}
        requested = data.get('enabled')
        if requested is None:
            enabled = not get_maintenance_mode()
        else:
            enabled = bool(requested)
        set_maintenance_mode(enabled)
        return jsonify({'status': 'ok', 'enabled': enabled})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_maintenance_toggle: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/beta', methods=['GET'])
@require_admin
def api_admin_beta_list():
    """Повертає список бета-тестерів та статистику"""
    try:
        try:
            limit = int(request.args.get('limit', 200))
        except (TypeError, ValueError):
            limit = 200
        testers = get_beta_testers(limit)
        stats = get_beta_testers_stats()
        return jsonify({
            'status': 'ok',
            'testers': testers,
            'stats': stats
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_beta_list: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/beta/add', methods=['POST'])
@require_admin
def api_admin_beta_add():
    """Додає нового бета-тестера"""
    try:
        data = request.get_json() or {}
        raw_identifier = data.get('identifier') or data.get('user_id') or ''
        identifier = str(raw_identifier).strip()
        if not identifier:
            return jsonify({'error': 'Вкажіть ID або username користувача'}), 400

        resolved_user_id = None
        user_row = None

        def try_load_user(candidate_id: int):
            row = get_user(candidate_id)
            return candidate_id if row else None, row

        tried_ids = []

        try:
            numeric_id = int(identifier)
            # Перевіряємо ID як є
            tried_ids.append(numeric_id)
            if numeric_id != 0:
                # Також пробуємо дзеркальне значення (на випадок, якщо користувач ввів без мінуса)
                mirror = -abs(numeric_id)
                if mirror not in tried_ids:
                    tried_ids.append(mirror)
        except ValueError:
            numeric_id = None

        if numeric_id is not None:
            for candidate in tried_ids:
                resolved, row = try_load_user(candidate)
                if resolved:
                    resolved_user_id = resolved
                    user_row = row
                    break
        else:
            user_row = get_user_by_username(identifier)
            if user_row:
                resolved_user_id = int(user_row[0])

        if not resolved_user_id:
            return jsonify({'error': 'Користувача не знайдено'}), 404
        if not user_row:
            user_row = get_user(resolved_user_id)
        if not user_row:
            return jsonify({'error': 'Користувача не знайдено у базі'}), 404

        admin_id = session.get('user_id') or 0
        add_beta(resolved_user_id, admin_id)
        try:
            create_notification(
                resolved_user_id,
                'info',
                'Бета-доступ активовано',
                'Ви отримали доступ до бета-тестування. Сайт буде доступний навіть під час технічних робіт.',
                {'category': 'beta', 'granted_by': admin_id}
            )
        except Exception as notify_error:
            print(f"[WARN] Failed to notify beta tester {resolved_user_id}: {notify_error}")

        return jsonify({
            'status': 'ok',
            'user_id': resolved_user_id,
            'user_name': user_row[1]
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_beta_add: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/beta/remove', methods=['POST'])
@require_admin
def api_admin_beta_remove():
    """Видаляє бета-тестера"""
    try:
        data = request.get_json() or {}
        user_id = int(data.get('user_id', 0))
        if user_id <= 0:
            return jsonify({'error': 'Некоректний ID користувача'}), 400
        remove_beta(user_id)
        return jsonify({'status': 'ok', 'user_id': user_id})
    except ValueError:
        return jsonify({'error': 'Некоректний ID користувача'}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_admin_beta_remove: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/beta/cleanup', methods=['POST'])
@require_admin
def api_admin_beta_cleanup():
    """Видаляє неактивних бета-тестерів"""
    try:
        data = request.get_json() or {}
        hours = int(data.get('hours', 24))
        hours = max(1, min(168, hours))
        inactive_testers, removed_count = remove_inactive_beta_testers(hours)
        return jsonify({
            'status': 'ok',
            'removed': removed_count,
            'details': inactive_testers
        })
    except ValueError:
        return jsonify({'error': 'Некоректне значення годин'}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_admin_beta_cleanup: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/beta/notify', methods=['POST'])
@require_admin
def api_admin_beta_notify():
    """Надсилає повідомлення всім бета-тестерам"""
    try:
        data = request.get_json() or {}
        title = (data.get('title') or '').strip()
        message = (data.get('message') or '').strip()
        if not title or not message:
            return jsonify({'error': 'Заголовок та повідомлення обовʼязкові'}), 400
        testers = get_beta_testers(limit=1000)
        sent = 0
        for tester in testers:
            user_id = tester.get('user_id')
            if not user_id:
                continue
            create_notification(
                user_id,
                'info',
                title,
                message,
                {'category': 'beta'}
            )
            sent += 1
        return jsonify({'status': 'ok', 'sent': sent})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_beta_notify: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/tasks')
@require_telegram_auth
def api_user_tasks():
    """API: Получение заданий пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем активные задания
        available_tasks = get_active_tasks(user_id)
        
        # Получаем статистику
        stats = get_user_tasks_stats(user_id)
        
        # Получаем последние выполнения
        recent_completions = get_user_task_completions(user_id, limit=10)
        
        return jsonify({
            'available_tasks': available_tasks,
            'stats': stats,
            'recent_completions': recent_completions
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_tasks: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/tasks/<int:task_id>/check', methods=['POST'])
@require_telegram_auth
def api_user_task_check(task_id):
    """API: Проверка выполнения задания"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем задание
        task = get_task_by_id(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        if task['status'] != 'active':
            return jsonify({'error': 'Task is not active'}), 400
        
        # Проверяем выполнение в зависимости от типа задания
        # Здесь должна быть логика проверки выполнения задания
        # Пока просто возвращаем информацию о задании
        
        return jsonify({
            'task': task,
            'can_complete': False,  # Нужно реализовать проверку
            'message': 'Task check not implemented yet'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_task_check: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/tasks')
@require_admin
def api_admin_tasks():
    """API: Получение всех заданий для админа"""
    try:
        status = request.args.get('status', None)
        tasks = get_all_tasks(status)
        
        return jsonify({'tasks': tasks})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_tasks: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/tasks/<int:task_id>')
@require_admin
def api_admin_task_detail(task_id):
    """API: Детали задания для админа"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return jsonify({'error': 'Task not found'}), 404
        
        # Получаем статистику выполнений
        completions_stats = get_task_completions_stats(task_id)
        
        return jsonify({
            'task': task,
            'completions_stats': completions_stats
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_task_detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden')
@require_telegram_auth
def api_user_garden():
    """API: Данные сада пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем деревья
        trees = get_user_trees(user_id) or []
        trees_with_watering = get_user_trees_with_watering(user_id) or []
        watering_alerts = _build_watering_alerts(trees_with_watering)
        
        # Получаем фрукты
        fruits = get_all_fruits(user_id) or {}
        fruit_prices = get_all_fruit_prices() or {}
        watering_settings = get_watering_settings()
        
        # Уровень сада
        garden_level = get_user_garden_level(user_id)
        level_info = get_garden_level_info(garden_level)
        can_upgrade = can_upgrade_garden_level(user_id)
        next_level_price = get_next_garden_level_price(user_id) if can_upgrade else None
        next_level_info = None
        if can_upgrade:
            next_level_info = get_garden_level_info(garden_level + 1)
        
        # Комиссия
        commission = get_user_garden_commission(user_id)
        
        # Подсчет деревьев по типам
        tree_counts = {}
        for tree_data in trees_with_watering:
            tree_type = tree_data['tree_type']
            tree_counts[tree_type] = tree_data['count']
        
        # Подсчет общей доходности
        import time
        try:
            from garden_models import TREE_TYPES, get_effective_tree_income
        except ImportError:
            # Fallback если garden_models недоступен
            TREE_TYPES = []
            def get_effective_tree_income(tree_type, econ_mult):
                return 1.0
        
        econ_mult = get_economy_harvest_multiplier()
        total_hourly_income = 0
        next_harvest_time = None
        
        for tree_data in trees_with_watering:
            tree_type = tree_data['tree_type']
            count = tree_data['count']
            ttype = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
            if ttype:
                income_per_hour = get_effective_tree_income(tree_type, econ_mult)
                bonus = level_info['bonus_percent'] if level_info else 0
                income_with_bonus = income_per_hour * (1 + bonus / 100)
                total_hourly_income += income_with_bonus * count
        
        # Формируем список фруктов с ценами
        fruits_list = []
        total_fruits_value = 0.0
        for fruit_type, amount in fruits.items():
            price = fruit_prices.get(fruit_type, 0) or get_fruit_price(fruit_type) or 0
            value = float(amount or 0) * float(price)
            total_fruits_value += value
            fruits_list.append({
                'type': fruit_type,
                'amount': float(amount or 0),
                'price': float(price),
                'value': value
            })

        now_ts = int(time.time())
        min_growth_seconds = 900
        ready_trees = 0
        next_ready_in = None
        last_harvest_at = None
        for tree in trees:
            last_ts = int(tree.get('last_harvest') or 0)
            if last_ts:
                last_harvest_at = max(last_harvest_at or 0, last_ts)
            else:
                last_ts = now_ts - min_growth_seconds
            ready_at = last_ts + min_growth_seconds
            delta = ready_at - now_ts
            if delta <= 0:
                ready_trees += 1
            else:
                if next_ready_in is None or delta < next_ready_in:
                    next_ready_in = delta
        harvest_state = {
            'can_harvest_now': ready_trees > 0,
            'ready_tree_count': ready_trees,
            'next_ready_in': max(0, next_ready_in) if next_ready_in is not None else 0,
            'next_ready_at': now_ts + max(0, next_ready_in) if next_ready_in is not None else None,
            'min_growth_seconds': min_growth_seconds,
            'last_harvest_at': last_harvest_at
        }
        
        # Получаем баланс пользователя
        user_data = get_user(user_id)
        user_balance = float(user_data.get('balance', 0)) if user_data else 0.0
        
        return jsonify({
            'garden_level': garden_level,
            'level_info': level_info,
            'next_level_info': next_level_info,
            'can_upgrade': can_upgrade,
            'next_level_price': float(next_level_price) if next_level_price else None,
            'commission': commission,
            'balance': user_balance,  # Добавляем баланс
            'trees': trees,
            'tree_counts': tree_counts,
            'trees_with_watering': trees_with_watering,
            'fruits': fruits_list,
            'fruits_total_value': total_fruits_value,
            'total_hourly_income': total_hourly_income,
            'fruit_prices': {k: float(v) for k, v in fruit_prices.items()},
            'harvest_state': harvest_state,
            'watering_settings': watering_settings,
            'watering_alerts': watering_alerts
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_garden: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/buy_tree', methods=['POST'])
@require_telegram_auth
def api_user_buy_tree():
    """API: Покупка дерева"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        tree_type = data.get('tree_type')
        
        if not tree_type:
            return jsonify({'error': 'Tree type required'}), 400
        
        try:
            from garden_models import TREE_TYPES
        except ImportError:
            TREE_TYPES = []
        
        ttype = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
        if not ttype:
            return jsonify({'error': 'Invalid tree type'}), 400
        
        # Проверяем уровень сада
        garden_level = get_user_garden_level(user_id)
        level_info = get_garden_level_info(garden_level)
        if tree_type not in level_info.get('available_trees', []):
            return jsonify({'error': 'Tree not available for your level'}), 400
        
        # Проверяем баланс
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        balance = float(user_row[2] or 0)
        price = get_tree_price(tree_type) or ttype['price_uah']
        
        if balance < price:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Покупаем дерево
        import time
        from database import add_balance, add_garden_transaction
        
        add_balance(user_id, -price, reason="buy_tree", details=f"{ttype['name']} ({tree_type})")
        current_time = int(time.time())
        
        with _db() as con:
            con.execute(
                "INSERT INTO trees (user_id, type, level, planted_at, last_harvest) VALUES (?, ?, ?, ?, ?)",
                (user_id, tree_type, 1, current_time, current_time)
            )
            # Начальный уровень воды 80%
            try:
                con.execute(
                    "INSERT OR REPLACE INTO tree_watering (user_id, tree_type, water_level, last_watered) VALUES (?, ?, ?, ?)",
                    (user_id, tree_type, 80, current_time)
                )
            except Exception:
                pass
            con.commit()
        
        # Записываем транзакцию
        add_garden_transaction(
            user_id,
            "buy_tree",
            float(price),
            "UAH",
            current_time,
            f"Покупка {ttype['name']}"
        )

        _safe_create_notification(
            user_id,
            'garden_buy_tree',
            'Нове дерево придбано',
            f"Ви придбали {ttype['name']} за {format_currency(price)}₴.",
            {
                'tree_type': tree_type,
                'price': float(price)
            }
        )

        return jsonify({
            'status': 'ok',
            'message': f'Tree {ttype["name"]} purchased successfully',
            'new_balance': float(get_user(user_id)[2])
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_buy_tree: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/harvest', methods=['POST'])
@require_telegram_auth
def api_user_harvest():
    """API: Сбор урожая"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        garden_level = get_user_garden_level(user_id)
        if garden_level == 0:
            return jsonify({
                'success': False,
                'message': 'Щоб збирати врожай, підніміть сад до 1 рівня.'
            })
        
        harvest_result = harvest_user_garden(user_id)
        if harvest_result.get('success'):
            harvested = harvest_result.get('harvested') or []
            summary = ', '.join(
                f"{item.get('emoji', '🍎')} {item.get('fruit_name', '')} × {format_currency(item.get('amount', 0))}"
                for item in harvested
            )
            _safe_create_notification(
                user_id,
                'garden_harvest',
                'Врожай зібрано',
                summary or 'Ви зібрали врожай із ваших дерев.',
                {
                    'items': harvested,
                    'total_amount': harvest_result.get('total_amount')
                }
            )
        return jsonify(harvest_result)
    except Exception as e:
        print(f"[ERROR] Error in api_user_harvest: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/sell_fruits', methods=['POST'])
@require_telegram_auth
def api_user_sell_fruits():
    """API: Продажа фруктов"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        fruit_type = data.get('fruit_type')
        amount = float(data.get('amount', 0))
        
        if not fruit_type or amount <= 0:
            return jsonify({'error': 'Invalid parameters'}), 400
        
        # Проверяем наличие фруктов
        fruit_amount = get_fruit_amount(user_id, fruit_type)
        if fruit_amount < amount:
            return jsonify({'error': 'Insufficient fruits'}), 400
        
        # Получаем цену и комиссию
        price_per_unit = get_effective_fruit_price(fruit_type)
        commission = get_user_garden_commission(user_id)
        
        # Рассчитываем доход
        total_revenue = price_per_unit * amount
        commission_amount = total_revenue * (commission / 100)
        net_revenue = total_revenue - commission_amount
        
        # Удаляем фрукты и добавляем баланс
        remove_fruit(user_id, fruit_type, amount)
        add_balance(user_id, net_revenue, reason="sell_fruit", details=f"{fruit_type} x{amount}")
        
        # Записываем транзакцию
        import time
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "sell_fruit",
            float(amount),
            "FRUIT",
            int(time.time()),
            f"Продаж {fruit_type}"
        )

        _safe_create_notification(
            user_id,
            'garden_sell',
            'Фрукти продано',
            f"Ви продали {format_currency(amount)} шт {fruit_type} на {format_currency(net_revenue)}₴.",
            {
                'fruit_type': fruit_type,
                'amount': float(amount),
                'revenue': float(net_revenue),
                'commission': float(commission_amount)
            }
        )

        return jsonify({
            'status': 'ok',
            'sold_amount': amount,
            'revenue': float(net_revenue),
            'commission': float(commission_amount),
            'new_balance': float(get_user(user_id)[2])
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_sell_fruits: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/upgrade_level', methods=['POST'])
@require_telegram_auth
def api_user_upgrade_garden_level():
    """API: Повышение уровня сада"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        current_level = get_user_garden_level(user_id)
        upgrade_price = get_next_garden_level_price(user_id)
        new_level = current_level + 1
        
        if not upgrade_price:
            return jsonify({'error': 'Max level reached'}), 400
        
        # Проверяем баланс
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        balance = float(user_row[2] or 0)
        if balance < upgrade_price:
            return jsonify({'error': 'Insufficient balance'}), 400
        
        # Повышаем уровень
        from database import add_balance, add_garden_transaction
        import time
        
        add_balance(user_id, -upgrade_price, reason="garden_level_up", details=f"Level {new_level}")
        set_user_garden_level(user_id, new_level)
        
        # Записываем транзакцию
        add_garden_transaction(
            user_id,
            "level_up",
            float(upgrade_price),
            "UAH",
            int(time.time()),
            f"Підвищення рівня до {new_level}"
        )
        
        new_level_info = get_garden_level_info(new_level)

        _safe_create_notification(
            user_id,
            'garden_level',
            'Рівень саду підвищено',
            f"Новий рівень: {new_level_info.get('name', f'Рівень {new_level}')}.",
            {
                'new_level': new_level,
                'bonus_percent': new_level_info.get('bonus_percent'),
                'commission_percent': new_level_info.get('commission_percent')
            }
        )
        
        return jsonify({
            'status': 'ok',
            'new_level': new_level,
            'level_info': new_level_info,
            'new_balance': float(get_user(user_id)[2])
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_upgrade_garden_level: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/water_tree', methods=['POST'])
@require_telegram_auth
def api_user_water_tree():
    """API: Полив дерева"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        tree_type = data.get('tree_type')
        
        if not tree_type:
            return jsonify({'error': 'Tree type required'}), 400
        
        # Поливаем дерево
        success, message = water_tree(user_id, tree_type)
        if not success:
            return jsonify({
                'success': False,
                'message': message or 'Помилка поливу'
            }), 400
        
        # Получаем обновленный статус
        watering_status = get_tree_watering_status(user_id, tree_type)

        _safe_create_notification(
            user_id,
            'garden_water',
            'Полив завершено',
            message or 'Дерево полито.',
            {
                'tree_type': tree_type,
                'cooldown': watering_status.get('seconds_until_next_water')
            }
        )
        
        return jsonify({
            'success': True,
            'message': message or 'Дерево полито',
            'watering_status': watering_status
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_water_tree: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/garden/tree_prices')
@require_telegram_auth
def api_user_tree_prices():
    """API: Цены на деревья"""
    try:
        try:
            from garden_models import TREE_TYPES
        except ImportError:
            TREE_TYPES = []
        
        from database import get_user_garden_level, get_garden_level_info
        
        user_id = session.get('user_id')
        garden_level = get_user_garden_level(user_id)
        level_info = get_garden_level_info(garden_level)
        available_trees = level_info.get('available_trees', [])
        
        trees_list = []
        for ttype in TREE_TYPES:
            price = get_tree_price(ttype['type']) or ttype['price_uah']
            is_available = ttype['type'] in available_trees
            
            trees_list.append({
                'type': ttype['type'],
                'name': ttype['name'],
                'emoji': ttype['fruit_emoji'],
                'price': float(price),
                'available': is_available,
                'base_income': ttype.get('base_income', 1)
            })
        
        return jsonify({'trees': trees_list})
    except Exception as e:
        print(f"[ERROR] Error in api_user_tree_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== АДМИН-ПАНЕЛЬ УПРАВЛЕНИЯ САДОМ ==========

@app.route('/api/admin/garden/user/<int:user_id>')
@require_admin
def api_admin_garden_user(user_id):
    """API: Информация о саде пользователя для админа"""
    try:
        # Получаем информацию о пользователе
        user_row = get_user(user_id)
        if not user_row:
            return jsonify({'error': 'User not found'}), 404
        
        # Получаем данные сада
        garden_level = get_user_garden_level(user_id)
        level_info = get_garden_level_info(garden_level)
        
        # Деревья
        trees = get_user_trees(user_id) or []
        trees_with_watering = get_user_trees_with_watering(user_id) or []
        
        # Фрукты
        fruits = get_all_fruits(user_id) or {}
        fruit_prices = get_all_fruit_prices() or {}
        
        # Подсчет деревьев по типам
        tree_counts = {}
        for tree_data in trees_with_watering:
            tree_type = tree_data['tree_type']
            tree_counts[tree_type] = tree_data['count']
        
        # Формируем список фруктов
        fruits_list = []
        total_fruits_value = 0.0
        for fruit_type, amount in fruits.items():
            price = fruit_prices.get(fruit_type, 0) or get_fruit_price(fruit_type) or 0
            value = float(amount or 0) * float(price)
            total_fruits_value += value
            fruits_list.append({
                'type': fruit_type,
                'amount': float(amount or 0),
                'price': float(price),
                'value': value
            })
        
        return jsonify({
            'user_id': user_id,
            'user_name': user_row[1],
            'garden_level': garden_level,
            'level_info': level_info,
            'trees': trees,
            'tree_counts': tree_counts,
            'trees_with_watering': trees_with_watering,
            'fruits': fruits_list,
            'fruits_total_value': total_fruits_value
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_garden_user: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/user/<int:user_id>/set_level', methods=['POST'])
@require_admin
def api_admin_set_garden_level(user_id):
    """API: Установка уровня сада пользователя (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        new_level = int(data.get('level', 0))
        reason = data.get('reason', f'Admin {admin_id} set level')
        
        if new_level < 0:
            return jsonify({'error': 'Invalid level'}), 400
        
        set_user_garden_level(user_id, new_level)
        
        # Записываем транзакцию
        import time
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "admin_set_level",
            float(new_level),
            "LEVEL",
            int(time.time()),
            f"Адмін {admin_id}: {reason}"
        )
        
        new_level_info = get_garden_level_info(new_level)
        
        return jsonify({
            'status': 'ok',
            'new_level': new_level,
            'level_info': new_level_info,
            'message': f'Garden level set to {new_level}'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_set_garden_level: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/user/<int:user_id>/add_tree', methods=['POST'])
@require_admin
def api_admin_add_tree(user_id):
    """API: Добавление дерева пользователю (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        tree_type = data.get('tree_type')
        count = int(data.get('count', 1))
        
        if not tree_type:
            return jsonify({'error': 'Tree type required'}), 400
        
        if count <= 0:
            return jsonify({'error': 'Count must be positive'}), 400
        
        try:
            from garden_models import TREE_TYPES
            ttype = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
            if not ttype:
                return jsonify({'error': 'Invalid tree type'}), 400
        except ImportError:
            return jsonify({'error': 'Garden models not available'}), 500
        
        # Добавляем деревья
        import time
        current_time = int(time.time())
        
        with _db() as con:
            for _ in range(count):
                con.execute(
                    "INSERT INTO trees (user_id, type, level, planted_at, last_harvest) VALUES (?, ?, ?, ?, ?)",
                    (user_id, tree_type, 1, current_time, current_time)
                )
                # Начальный уровень воды 80%
                try:
                    con.execute(
                        "INSERT OR REPLACE INTO tree_watering (user_id, tree_type, water_level, last_watered) VALUES (?, ?, ?, ?)",
                        (user_id, tree_type, 80, current_time)
                    )
                except Exception:
                    pass
            con.commit()
        
        # Записываем транзакцию
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "admin_add_tree",
            float(count),
            "TREES",
            current_time,
            f"Адмін {admin_id}: додано {count} {ttype['name']}"
        )
        
        return jsonify({
            'status': 'ok',
            'tree_type': tree_type,
            'count': count,
            'message': f'Added {count} {ttype["name"]} tree(s)'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_add_tree: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/user/<int:user_id>/remove_tree', methods=['POST'])
@require_admin
def api_admin_remove_tree(user_id):
    """API: Удаление дерева у пользователя (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        tree_type = data.get('tree_type')
        count = int(data.get('count', 1))
        
        if not tree_type:
            return jsonify({'error': 'Tree type required'}), 400
        
        if count <= 0:
            return jsonify({'error': 'Count must be positive'}), 400
        
        try:
            from garden_models import TREE_TYPES, get_tree_name_uk
            ttype = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
            if not ttype:
                return jsonify({'error': 'Invalid tree type'}), 400
            tree_name = get_tree_name_uk(tree_type)
        except ImportError:
            return jsonify({'error': 'Garden models not available'}), 500
        
        # Проверяем количество доступных деревьев
        with _db() as con:
            available = con.execute(
                "SELECT COUNT(*) FROM trees WHERE user_id=? AND type=?",
                (user_id, tree_type)
            ).fetchone()[0]
        
        if available < count:
            return jsonify({'error': f'Only {available} trees available'}), 400
        
        # Удаляем деревья
        import time
        current_time = int(time.time())
        
        with _db() as con:
            con.execute(
                "DELETE FROM trees WHERE id IN (SELECT id FROM trees WHERE user_id=? AND type=? LIMIT ?)",
                (user_id, tree_type, count)
            )
            con.commit()
        
        # Записываем транзакцию
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "admin_remove_tree",
            float(count),
            "TREES",
            current_time,
            f"Адмін {admin_id}: видалено {count} {tree_name}"
        )
        
        return jsonify({
            'status': 'ok',
            'tree_type': tree_type,
            'count': count,
            'message': f'Removed {count} {tree_name} tree(s)'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_remove_tree: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/user/<int:user_id>/add_fruit', methods=['POST'])
@require_admin
def api_admin_add_fruit(user_id):
    """API: Добавление фруктов пользователю (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        fruit_type = data.get('fruit_type')
        amount = float(data.get('amount', 0))
        
        if not fruit_type:
            return jsonify({'error': 'Fruit type required'}), 400
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
        
        # Добавляем фрукты
        add_fruit(user_id, fruit_type, amount)
        
        # Записываем транзакцию
        import time
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "admin_add_fruit",
            float(amount),
            "FRUIT",
            int(time.time()),
            f"Адмін {admin_id}: додано {amount} {fruit_type}"
        )
        
        return jsonify({
            'status': 'ok',
            'fruit_type': fruit_type,
            'amount': amount,
            'message': f'Added {amount} {fruit_type}'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_add_fruit: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/user/<int:user_id>/remove_fruit', methods=['POST'])
@require_admin
def api_admin_remove_fruit(user_id):
    """API: Удаление фруктов у пользователя (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        fruit_type = data.get('fruit_type')
        amount = float(data.get('amount', 0))
        
        if not fruit_type:
            return jsonify({'error': 'Fruit type required'}), 400
        
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
        
        # Проверяем количество доступных фруктов
        available = get_fruit_amount(user_id, fruit_type)
        if available < amount:
            return jsonify({'error': f'Only {available} fruits available'}), 400
        
        # Удаляем фрукты
        remove_fruit(user_id, fruit_type, amount)
        
        # Записываем транзакцию
        import time
        from database import add_garden_transaction
        add_garden_transaction(
            user_id,
            "admin_remove_fruit",
            float(amount),
            "FRUIT",
            int(time.time()),
            f"Адмін {admin_id}: видалено {amount} {fruit_type}"
        )
        
        return jsonify({
            'status': 'ok',
            'fruit_type': fruit_type,
            'amount': amount,
            'message': f'Removed {amount} {fruit_type}'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_remove_fruit: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/prices/tree', methods=['GET', 'POST'])
@require_admin
def api_admin_tree_prices():
    """API: Управление ценами деревьев (админ)"""
    try:
        try:
            from garden_models import TREE_TYPES, GARDEN_LEVELS
        except ImportError:
            TREE_TYPES = []
            GARDEN_LEVELS = []
        
        if request.method == 'GET':
            # Готуємо карту рівнів, де доступне дерево
            tree_levels = {}
            for level in GARDEN_LEVELS:
                for ttype in level.get('available_trees', []):
                    tree_levels.setdefault(ttype, []).append(level['level'])
            
            prices = []
            for ttype in TREE_TYPES:
                tree_type = ttype['type']
                price = get_tree_price(tree_type) or ttype['price_uah']
                configured_income = get_tree_income(tree_type)
                base_income = float(ttype.get('base_income', 1))
                effective_income = float(configured_income) if configured_income else base_income
                
                prices.append({
                    'type': tree_type,
                    'name': ttype['name'],
                    'emoji': ttype['fruit_emoji'],
                    'price': float(price),
                    'base_price': float(ttype['price_uah']),
                    'base_income': base_income,
                    'configured_income': float(configured_income) if configured_income else None,
                    'effective_income': effective_income,
                    'available_levels': tree_levels.get(tree_type, [])
                })
            
            return jsonify({'prices': prices})
        
        # POST - оновлення налаштувань конкретного дерева
        data = request.get_json() or {}
        tree_type = data.get('tree_type')
        if not tree_type:
            return jsonify({'error': 'Tree type required'}), 400
        
        updated = {}
        if 'price' in data and data.get('price') not in (None, ''):
            price_val = float(data.get('price'))
            if price_val < 0:
                return jsonify({'error': 'Price must be non-negative'}), 400
            set_tree_price(tree_type, price_val)
            updated['price'] = price_val
        
        if 'income' in data and data.get('income') not in (None, ''):
            income_val = float(data.get('income'))
            if income_val < 0:
                return jsonify({'error': 'Income must be non-negative'}), 400
            set_tree_income(tree_type, income_val)
            updated['income'] = income_val
        
        if not updated:
            return jsonify({'error': 'Nothing to update'}), 400
        
        # Возвращаем актуальные значения
        tree_def = next((t for t in TREE_TYPES if t['type'] == tree_type), {})
        configured_income = get_tree_income(tree_type)
        base_income = float(tree_def.get('base_income', 1))
        response_data = {
            'type': tree_type,
            'price': float(get_tree_price(tree_type)),
            'base_price': float(tree_def.get('price_uah', 0)),
            'base_income': base_income,
            'configured_income': float(configured_income) if configured_income else None,
            'effective_income': float(configured_income) if configured_income else base_income
        }
        
        return jsonify({
            'status': 'ok',
            'tree': response_data,
            'updated': updated
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_tree_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/prices/fruit', methods=['GET', 'POST'])
@require_admin
def api_admin_fruit_prices():
    """API: Управление ценами фруктов (админ)"""
    try:
        if request.method == 'GET':
            # Получаем цены
            try:
                from garden_models import FRUITS
            except ImportError:
                FRUITS = []
            
            fruit_prices_db = get_all_fruit_prices() or {}
            prices = []
            for fruit in FRUITS:
                price = fruit_prices_db.get(fruit['type'], 0) or get_fruit_price(fruit['type']) or 0
                prices.append({
                    'type': fruit['type'],
                    'name': fruit['name'],
                    'emoji': fruit['emoji'],
                    'price': float(price)
                })
            
            return jsonify({'prices': prices})
        
        else:  # POST - установка цены
            data = request.get_json()
            fruit_type = data.get('fruit_type')
            price = float(data.get('price', 0))
            
            if not fruit_type:
                return jsonify({'error': 'Fruit type required'}), 400
            
            if price < 0:
                return jsonify({'error': 'Price must be non-negative'}), 400
            
            set_fruit_price(fruit_type, price)
            
            return jsonify({
                'status': 'ok',
                'fruit_type': fruit_type,
                'price': price,
                'message': f'Fruit price updated'
            })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_fruit_prices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/garden/history/<int:user_id>')
@require_admin
def api_admin_garden_history(user_id):
    """API: История сада пользователя (админ)"""
    try:
        period = request.args.get('period', 'all')  # 'today', 'week', 'month', 'all'
        
        if period == 'all':
            from database import get_garden_history
            history = get_garden_history(user_id, limit=100)
        else:
            history = get_garden_history_by_date(user_id, period)
        
        return jsonify({
            'user_id': user_id,
            'period': period,
            'history': history
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_garden_history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== СИСТЕМА УВЕДОМЛЕНИЙ ==========

@app.route('/api/user/notifications')
@require_telegram_auth
def api_user_notifications():
    """API: Получение уведомлений пользователя"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        limit = int(request.args.get('limit', 50))
        
        notifications = get_user_notifications(user_id, limit=limit, unread_only=unread_only)
        unread_count = get_unread_notifications_count(user_id)
        
        return jsonify({
            'notifications': notifications,
            'unread_count': unread_count
        })
    except Exception as e:
        print(f"[ERROR] Error in api_user_notifications: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/notifications/unread/count')
@require_telegram_auth
def api_user_notifications_unread_count():
    """API: Количество непрочитанных уведомлений"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        count = get_unread_notifications_count(user_id)
        return jsonify({'unread_count': count})
    except Exception as e:
        print(f"[ERROR] Error in api_user_notifications_unread_count: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/notifications/<int:notification_id>/read', methods=['POST'])
@require_telegram_auth
def api_mark_notification_read(notification_id):
    """API: Отметить уведомление как прочитанное"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        mark_notification_read(notification_id, user_id)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[ERROR] Error in api_mark_notification_read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/notifications/read-all', methods=['POST'])
@require_telegram_auth
def api_mark_all_notifications_read():
    """API: Отметить все уведомления как прочитанные"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        mark_all_notifications_read(user_id)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[ERROR] Error in api_mark_all_notifications_read: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/notifications/<int:notification_id>', methods=['DELETE'])
@require_telegram_auth
def api_delete_notification(notification_id):
    """API: Удалить уведомление"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        
        delete_notification(notification_id, user_id)
        return jsonify({'status': 'ok'})
    except Exception as e:
        print(f"[ERROR] Error in api_delete_notification: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/notifications/create', methods=['POST'])
@require_admin
def api_admin_create_notification():
    """API: Создать уведомление (админ)"""
    try:
        admin_id = session.get('user_id')
        data = request.get_json()
        
        target_user_id = int(data.get('user_id'))
        notification_type = data.get('type', 'info')
        title = data.get('title', 'Уведомление')
        message = data.get('message', '')
        notification_data = data.get('data')
        
        notification_id = create_notification(
            target_user_id,
            notification_type,
            title,
            message,
            notification_data
        )
        
        return jsonify({
            'status': 'ok',
            'notification_id': notification_id,
            'message': 'Notification created'
        })
    except Exception as e:
        print(f"[ERROR] Error in api_admin_create_notification: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== СИСТЕМА ПІДТРИМКИ ==========

def _parse_status_filter_param(raw):
    if not raw or raw.lower() == 'all':
        return None
    if isinstance(raw, str) and ',' in raw:
        return [part.strip() for part in raw.split(',') if part.strip()]
    return raw.strip() if isinstance(raw, str) else raw

@app.route('/api/user/support/tickets', methods=['GET', 'POST'])
@require_telegram_auth
def api_user_support_tickets():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        if request.method == 'POST':
            data = request.get_json() or {}
            message = (data.get('message') or '').strip()
            subject = (data.get('subject') or '').strip()
            category = data.get('category')
            if not message:
                return jsonify({'error': 'Повідомлення не може бути порожнім'}), 400
            ticket, first_message = create_support_ticket(
                user_id,
                message,
                subject=subject or None,
                source='webapp',
                category=category
            )
            return jsonify({'ticket': ticket, 'messages': [first_message]}), 201
        status_param = _parse_status_filter_param(request.args.get('status'))
        category_filter = request.args.get('category')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        tickets = get_support_tickets_for_user(
            user_id,
            status=status_param,
            category=category_filter,
            limit=max(1, min(limit, 100)),
            offset=max(0, offset)
        )
        return jsonify({'tickets': tickets})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_user_support_tickets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/user/support/tickets/<int:ticket_id>')
@require_telegram_auth
def api_user_support_ticket_detail(ticket_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        ticket = get_support_ticket(ticket_id)
        if not ticket or ticket.get('user_id') != user_id:
            return jsonify({'error': 'Ticket not found'}), 404
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        messages = get_support_messages(
            ticket_id,
            limit=max(1, min(limit, 200)),
            offset=max(0, offset),
            include_internal=False
        )
        mark_support_ticket_read(ticket_id, 'user', user_id=user_id)
        if ticket is not None:
            ticket['user_unread_count'] = 0
        return jsonify({'ticket': ticket, 'messages': messages})
    except Exception as e:
        print(f"[ERROR] Error in api_user_support_ticket_detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/user/support/tickets/<int:ticket_id>/reply', methods=['POST'])
@require_telegram_auth
def api_user_support_ticket_reply(ticket_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        ticket = get_support_ticket(ticket_id)
        if not ticket or ticket.get('user_id') != user_id:
            return jsonify({'error': 'Ticket not found'}), 404
        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'Повідомлення не може бути порожнім'}), 400
        msg, updated_ticket = add_support_message(
            ticket_id,
            user_id,
            'user',
            message,
            is_internal=False,
            status='pending'
        )
        return jsonify({'ticket': updated_ticket, 'message': msg})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_user_support_ticket_reply: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/user/support/tickets/<int:ticket_id>/close', methods=['POST'])
@require_telegram_auth
def api_user_support_ticket_close(ticket_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        ticket = get_support_ticket(ticket_id)
        if not ticket or ticket.get('user_id') != user_id:
            return jsonify({'error': 'Ticket not found'}), 404
        if (ticket.get('status') or '').lower() == 'closed':
            return jsonify({'ticket': ticket})
        data = request.get_json() or {}
        reason = data.get('reason')
        updated_ticket = update_support_ticket_status(
            ticket_id,
            'closed',
            admin_id=None,
            reason=reason
        )
        return jsonify({'ticket': updated_ticket})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_user_support_ticket_close: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/user/support/unread-count')
@require_telegram_auth
def api_user_support_unread_count():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not found'}), 404
        count = get_user_support_unread_count(user_id)
        return jsonify({'count': count})
    except Exception as e:
        print(f"[ERROR] Error in api_user_support_unread_count: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/admin/support/unread-count')
@require_admin
def api_admin_support_unread_count():
    try:
        admin_id = session.get('user_id')
        summary = get_admin_support_unread_summary(admin_id)
        return jsonify(summary)
    except Exception as e:
        print(f"[ERROR] Error in api_admin_support_unread_count: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500


@app.route('/api/admin/support/tickets')
@require_admin
def api_admin_support_tickets():
    try:
        admin_id = session.get('user_id')
        status_param = _parse_status_filter_param(request.args.get('status'))
        assigned_param = request.args.get('assigned')
        if assigned_param == 'me':
            assigned_param = int(admin_id)
        elif assigned_param and assigned_param.isdigit():
            assigned_param = int(assigned_param)
        search = request.args.get('search')
        category_filter = request.args.get('category')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        user_filter = request.args.get('user_id')
        user_filter = int(user_filter) if user_filter and user_filter.isdigit() else None
        result = list_support_tickets(
            status=status_param,
            assigned=assigned_param,
            search=search,
            limit=max(1, min(limit, 200)),
            offset=max(0, offset),
            user_id=user_filter,
            category=category_filter
        )
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] Error in api_admin_support_tickets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/admin/support/tickets/<int:ticket_id>')
@require_admin
def api_admin_support_ticket_detail(ticket_id):
    try:
        ticket = get_support_ticket(ticket_id)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        limit = int(request.args.get('limit', 200))
        offset = int(request.args.get('offset', 0))
        include_internal = request.args.get('include_internal', 'true').lower() != 'false'
        messages = get_support_messages(
            ticket_id,
            limit=max(1, min(limit, 500)),
            offset=max(0, offset),
            include_internal=include_internal
        )
        mark_support_ticket_read(ticket_id, 'admin')
        if ticket is not None:
            ticket['admin_unread_count'] = 0
        return jsonify({'ticket': ticket, 'messages': messages})
    except Exception as e:
        print(f"[ERROR] Error in api_admin_support_ticket_detail: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/admin/support/tickets/<int:ticket_id>/reply', methods=['POST'])
@require_admin
def api_admin_support_ticket_reply(ticket_id):
    try:
        admin_id = session.get('user_id')
        ticket = get_support_ticket(ticket_id)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        data = request.get_json() or {}
        message = (data.get('message') or '').strip()
        status_param = data.get('status') or 'answered'
        if not message:
            return jsonify({'error': 'Повідомлення не може бути порожнім'}), 400
        msg, updated_ticket = add_support_message(
            ticket_id,
            admin_id,
            'admin',
            message,
            is_internal=bool(data.get('internal')),
            status=status_param,
            assigned_admin_id=admin_id
        )
        notify = data.get('notify_user', True)
        if notify and ticket.get('user_id'):
            create_notification(
                ticket['user_id'],
                'support_reply',
                'Відповідь підтримки',
                'Ми відповіли на ваше звернення',
                {'ticket_id': ticket_id, 'preview': message[:200]}
            )
        return jsonify({'ticket': updated_ticket, 'message': msg})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_admin_support_ticket_reply: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/admin/support/tickets/<int:ticket_id>/status', methods=['POST'])
@require_admin
def api_admin_support_ticket_status(ticket_id):
    try:
        admin_id = session.get('user_id')
        ticket = get_support_ticket(ticket_id)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        data = request.get_json() or {}
        status_param = data.get('status')
        reason = data.get('reason')
        balance_delta_raw = data.get('balance_delta')
        balance_delta_value = None
        if balance_delta_raw not in (None, '', '0', 0, 0.0):
            try:
                balance_delta_value = float(balance_delta_raw)
            except (ValueError, TypeError):
                return jsonify({'error': 'Невірна сума списання/нарахування'}), 400
        notify_user = data.get('notify_user', True)
        meta_updates = data.get('meta')
        updated_ticket = update_support_ticket_status(
            ticket_id,
            status_param,
            admin_id=admin_id,
            reason=reason,
            balance_delta=balance_delta_value,
            meta_updates=meta_updates
        )
        if updated_ticket is None:
            return jsonify({'error': 'Ticket not found'}), 404
        if balance_delta_value:
            add_balance(
                ticket['user_id'],
                balance_delta_value,
                force_admin=True,
                reason=f'Support ticket #{ticket_id}'
            )
        if notify_user and ticket.get('user_id'):
            status_label = status_param or updated_ticket.get('status')
            title = 'Статус звернення оновлено'
            message = f"Ваше звернення №{ticket_id} тепер має статус «{status_label}»."
            if reason:
                message += f" Причина: {reason}"
            create_notification(
                ticket['user_id'],
                'support_status',
                title,
                message,
                {'ticket_id': ticket_id, 'status': status_label}
            )
        return jsonify({'ticket': updated_ticket})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print(f"[ERROR] Error in api_admin_support_ticket_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Server error'}), 500

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
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore')
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
                    try:
                        if ip.startswith('192.168.') or ip.startswith('10.'):
                            if ip not in ips:
                                ips.insert(0, ip)
                        elif ip.startswith('172.'):
                            parts = ip.split('.')
                            if len(parts) > 1:
                                second_octet = int(parts[1])
                                if 16 <= second_octet <= 31:
                                    if ip not in ips:
                                        ips.insert(0, ip)
                                else:
                                    if ip not in ips:
                                        ips.append(ip)
                            else:
                                if ip not in ips:
                                    ips.append(ip)
                        else:
                            if ip not in ips:
                                ips.append(ip)
                    except (ValueError, IndexError):
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
                capture_output=True, text=True, timeout=5, encoding='utf-8', errors='ignore'
            )
            return str(port) in result.stdout
        except:
            return False
    
    # Получаем порт из переменной окружения или используем 5000
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
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
    print(f"📊 Сервер слушает на: {host}:{port}")
    print("=" * 70)
    print()
    print("Нажмите Ctrl+C для остановки...")
    print()
    
    # Запускаем Flask
    # Важно: host='0.0.0.0' позволяет подключаться с других устройств
    try:
        app.run(host=host, port=port, debug=False, threaded=True)
    except OSError as e:
        if "Address already in use" in str(e) or "address is already in use" in str(e).lower():
            print()
            print("=" * 70)
            print("❌ ОШИБКА: Порт 5000 уже занят!")
            print("=" * 70)
            print()
            print("Решения:")
            print("1. Остановите другой процесс на порту 5000")
            print("2. Или используйте другой порт:")
            print("   set PORT=8080")
            print("   python app.py")
            print()
        else:
            raise

