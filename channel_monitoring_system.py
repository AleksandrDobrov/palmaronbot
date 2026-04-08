#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система моніторингу каналів для автоматичного блокування користувачів
"""

import telebot
import time
from database import (
    get_required_channels, is_user_blocked, block_user_for_channel_leave,
    get_user_block_info, unblock_user, get_referral_info, get_ref_bonus,
    safe_clawback_balance, _db, get_user
)

def handle_channel_member_update(update):
    """Обробляє оновлення учасників каналу"""
    try:
        # Імпортуємо bot з глобального контексту
        import bot as bot_module
        bot = bot_module.bot
        
        chat_id = update.chat_member.chat.id
        user_id = update.chat_member.from_user.id
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        
        print(f"[DEBUG] channel_member_update: chat_id={chat_id}, user_id={user_id}, {old_status} -> {new_status}")
        
        # Отримуємо інформацію про канал для назв/username
        try:
            chat_info = bot.get_chat(chat_id)
            chat_title = getattr(chat_info, 'title', None) or (chat_info.username and f"@{chat_info.username}") or f"Канал {chat_id}"
            chat_username = chat_info.username
        except Exception:
            chat_info = None
            chat_title = f"Канал {chat_id}"
            chat_username = None

        # Перевіряємо чи це обов'язковий канал або чат
        from database import get_required_chats
        required_channels = get_required_channels()
        required_chats = get_required_chats()
        
        req_channels_set = set([str(x).strip() for x in (required_channels or [])])
        req_chats_set = set([str(x).strip() for x in (required_chats or [])])
        
        is_required = False
        # Перевіряємо канали
        if str(chat_id) in req_channels_set or f"-100{str(chat_id)[4:]}" in req_channels_set:
            is_required = True
        if chat_username and (f"@{chat_username}" in req_channels_set or chat_username in req_channels_set):
            is_required = True
        # Перевіряємо чати
        if str(chat_id) in req_chats_set:
            is_required = True
            
        if not is_required:
            print(f"[DEBUG] Канал/чат {chat_id} не є обов'язковим")
            return
        
        # Якщо користувач вийшов з каналу/чату
        if new_status in ['left', 'kicked']:
            print(f"[INFO] Користувач {user_id} вийшов з обов'язкового каналу/чату {chat_id}")
            
            # Перевіряємо чи не заблокований вже користувач
            if is_user_blocked(user_id):
                print(f"[DEBUG] Користувач {user_id} вже заблокований")
                return
            
            # Визначаємо чи це канал чи чат для правильного блокування
            if str(chat_id) in req_chats_set:
                # Це чат - використовуємо функцію блокування за чат
                from database import block_user_for_chat_leave
                block_user_for_chat_leave(user_id, str(chat_id), chat_title)
                print(f"[INFO] Користувач {user_id} заблокований за вихід з чату {chat_title}")
            else:
                # Це канал - використовуємо функцію блокування за канал
                block_user_for_channel_leave(user_id, str(chat_id), chat_title)
                print(f"[INFO] Користувач {user_id} заблокований за вихід з каналу {chat_title}")
            
            # Відправляємо повідомлення про блокування
            send_channel_block_notification_to_user(bot, user_id, chat_title)
            
            # Відбираємо реферальний бонус у реферера (якщо був нарахований)
            try:
                revoke_referral_bonus_on_unsubscribe(user_id, bot)
            except Exception as e:
                print(f"[ERROR] Помилка відбирання реферального бонусу: {e}")
            
        # Якщо користувач повернувся в канал
        elif old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
            print(f"[INFO] Користувач {user_id} повернувся в обов'язковий канал {chat_id}")
            
            # Перевіряємо чи заблокований користувач
            if is_user_blocked(user_id):
                # Розблоковуємо користувача
                unblock_user(user_id)
                print(f"[INFO] Користувач {user_id} розблокований за повернення в канал {chat_title}")
                
                # Відправляємо повідомлення про розблокування
                send_channel_unblock_notification_to_user(bot, user_id, chat_title)
                
                # Повертаємо реферальний бонус рефереру (якщо був відібраний)
                try:
                    restore_referral_bonus_on_resubscribe(user_id, bot)
                except Exception as e:
                    print(f"[ERROR] Помилка повернення реферального бонусу: {e}")
            
    except Exception as e:
        print(f"[ERROR] Помилка обробки channel_member_update: {e}")

def send_channel_block_notification_to_user(bot, user_id, channel_title):
    """Відправляє користувачу повідомлення про блокування за вихід з каналу"""
    try:
        block_text = (
            "🚫 <b>ДОСТУП ЗАБЛОКОВАНО!</b>\n\n"
            f"❌ <b>Причина:</b> Вихід з обов'язкового каналу: {channel_title}\n"
            f"📅 <b>Дата блокування:</b> {time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "🔒 <b>Що сталося:</b>\n"
            "• Ви вийшли з обов'язкового каналу\n"
            "• Бот автоматично заблокував доступ\n"
            "• Всі функції недоступні\n\n"
            "💡 <b>Що робити:</b>\n"
            f"• Поверніться в канал: {channel_title}\n"
            "• Зверніться до адміністратора\n"
            "• Очікуйте розблокування\n\n"
            "📞 <i>Для розблокування зверніться до підтримки</i>"
        )
        
        bot.send_message(user_id, block_text, parse_mode="HTML")
        print(f"[INFO] Повідомлення про блокування за канал відправлено користувачу {user_id}")
        
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про блокування за канал: {e}")

def send_channel_unblock_notification_to_user(bot, user_id, channel_title):
    """Відправляє користувачу повідомлення про розблокування за повернення в канал"""
    try:
        unblock_text = (
            "✅ <b>ДОСТУП ВІДНОВЛЕНО!</b>\n\n"
            f"🎉 <b>Причина:</b> Повернення в обов'язковий канал: {channel_title}\n"
            f"📅 <b>Дата розблокування:</b> {time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "🔓 <b>Що сталося:</b>\n"
            "• Ви повернулися в обов'язковий канал\n"
            "• Бот автоматично розблокував доступ\n"
            "• Всі функції знову доступні\n\n"
            "💎 <b>Вітаємо назад в Investing Palmaron Bot!</b>"
        )
        
        bot.send_message(user_id, unblock_text, parse_mode="HTML")
        print(f"[INFO] Повідомлення про розблокування за канал відправлено користувачу {user_id}")
        
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про розблокування за канал: {e}")

def check_all_users_in_required_channels(bot):
    """Перевіряє всіх користувачів в обов'язкових каналах"""
    try:
        from database import get_all_users, get_required_channels
        
        required_channels = get_required_channels()
        if not required_channels:
            print("[DEBUG] Немає обов'язкових каналів для перевірки")
            return
        
        all_users = get_all_users()
        print(f"[INFO] Перевіряю {len(all_users)} користувачів в {len(required_channels)} каналах")
        
        for user_id in all_users:
            try:
                # Перевіряємо участь в кожному каналі
                for channel in required_channels:
                    try:
                        member = bot.get_chat_member(chat_id=channel, user_id=user_id)
                        if member.status in ['left', 'kicked']:
                            # Користувач не в каналі - блокуємо
                            try:
                                chat_info = bot.get_chat(channel)
                                channel_title = chat_info.title
                            except:
                                channel_title = f"Канал {channel}"
                            
                            if not is_user_blocked(user_id):
                                block_user_for_channel_leave(user_id, str(channel), channel_title)
                                print(f"[INFO] Користувач {user_id} заблокований за відсутність в каналі {channel_title}")
                                
                                # Відправляємо повідомлення
                                send_channel_block_notification_to_user(bot, user_id, channel_title)
                            break
                            
                    except Exception as e:
                        print(f"[ERROR] Помилка перевірки користувача {user_id} в каналі {channel}: {e}")
                        continue
                        
            except Exception as e:
                print(f"[ERROR] Помилка обробки користувача {user_id}: {e}")
                continue
        
        print("[INFO] Перевірка всіх користувачів в каналах завершена")
        
    except Exception as e:
        print(f"[ERROR] Помилка масової перевірки користувачів в каналах: {e}")

def setup_channel_monitoring(bot):
    """Налаштовує систему моніторингу каналів"""
    try:
        # Додаємо обробник для каналів
        bot.chat_member_handler = handle_channel_member_update
        
        print("[INFO] Система моніторингу каналів налаштована")
        
    except Exception as e:
        print(f"[ERROR] Помилка налаштування системи моніторингу каналів: {e}")

def schedule_channel_monitoring(bot, interval_hours=24):
    """Планує періодичну перевірку користувачів в каналах"""
    import threading
    import time
    
    def monitoring_loop():
        while True:
            try:
                print(f"[INFO] Запуск планової перевірки користувачів в каналах")
                check_all_users_in_required_channels(bot)
                print(f"[INFO] Планова перевірка каналів завершена. Наступна через {interval_hours} годин")
            except Exception as e:
                print(f"[ERROR] Помилка планової перевірки каналів: {e}")
            
            # Чекаємо до наступної перевірки
            time.sleep(interval_hours * 3600)
    
    # Запускаємо в окремому потоці
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()

def revoke_referral_bonus_on_unsubscribe(referred_user_id: int, bot):
    """Відбирає реферальний бонус у реферера, якщо реферал відписався від каналу"""
    try:
        # Отримуємо інформацію про реферера
        referral_info = get_referral_info(referred_user_id)
        if not referral_info:
            print(f"[REFERRAL] Користувач {referred_user_id} не має реферера")
            return
        
        referrer_id = referral_info[0]  # invited_by
        referrer_name = referral_info[1] or f"Користувач {referrer_id}"
        referred_user = get_user(referred_user_id)
        referred_name = referred_user[1] if (referred_user and len(referred_user) > 1) else f"Користувач {referred_user_id}"
        
        # Отримуємо розмір бонусу
        ref_bonus = get_ref_bonus()
        
        # Шукаємо нарахований бонус в ledger (за останні 30 днів)
        import time
        thirty_days_ago = int(time.time()) - (30 * 24 * 3600)
        
        with _db() as con:
            # Шукаємо транзакцію реферального бонусу
            bonus_row = con.execute("""
                SELECT id, amount, timestamp 
                FROM ledger 
                WHERE user_id = ? 
                AND reason = 'referral_bonus' 
                AND details LIKE ?
                AND timestamp >= ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (referrer_id, f'%{referred_user_id}%', thirty_days_ago)).fetchone()
        
        if not bonus_row:
            print(f"[REFERRAL] Бонус для реферера {referrer_id} не знайдено в ledger")
            return
        
        bonus_id, bonus_amount, bonus_timestamp = bonus_row
        
        # Відбираємо бонус
        clawed_back = safe_clawback_balance(referrer_id, float(bonus_amount))
        
        # Створюємо запис в ledger про відбір бонусу
        if clawed_back > 0:
            try:
                import time
                from database import _db
                with _db() as con:
                    con.execute("""
                        INSERT INTO ledger (user_id, amount, reason, details, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                    """, (referrer_id, -float(clawed_back), 'referral_bonus', 
                          f'Відбір реферального бонусу за користувача {referred_user_id} ({referred_name}) - відписка від каналу',
                          int(time.time())))
                    con.commit()
            except Exception as e:
                print(f"[ERROR] Помилка створення запису про відбір бонусу: {e}")
        
        if clawed_back > 0:
            print(f"[REFERRAL] Відібрано {clawed_back}₴ у реферера {referrer_id} за відписку реферала {referred_user_id}")
            
            # Відправляємо повідомлення рефереру
            try:
                from utils import format_currency
            except Exception:
                def format_currency(amount):
                    return f"{amount:.2f}"
            
            try:
                bot.send_message(
                    referrer_id,
                    "⚠️ <b>РЕФЕРАЛЬНИЙ БОНУС ВІДІБРАНО</b>\n\n"
                    f"👤 <b>Реферал:</b> {referred_name}\n"
                    f"❌ <b>Причина:</b> Відписка від обов'язкового каналу\n\n"
                    f"💰 <b>Відібрано:</b> {format_currency(clawed_back)} ₴\n\n"
                    f"💡 Бонус буде повернуто, якщо реферал повернеться до каналу.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення рефереру: {e}")
            
            # Відправляємо повідомлення рефералу
            try:
                bot.send_message(
                    referred_user_id,
                    "⚠️ <b>УВАГА!</b>\n\n"
                    f"Ви відписалися від обов'язкового каналу.\n\n"
                    f"💰 Реферальний бонус вашого реферера ({referrer_name}) було відібрано.\n\n"
                    f"💡 Поверніться до каналу, щоб бонус було повернуто.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення рефералу: {e}")
        else:
            print(f"[REFERRAL] Не вдалося відібрати бонус у реферера {referrer_id} (недостатньо балансу або бонус вже виведено)")
            
    except Exception as e:
        print(f"[ERROR] Помилка відбирання реферального бонусу: {e}")
        import traceback
        traceback.print_exc()

def restore_referral_bonus_on_resubscribe(referred_user_id: int, bot):
    """Повертає реферальний бонус рефереру, якщо реферал повернувся до каналу"""
    try:
        # Отримуємо інформацію про реферера
        referral_info = get_referral_info(referred_user_id)
        if not referral_info:
            print(f"[REFERRAL] Користувач {referred_user_id} не має реферера")
            return
        
        referrer_id = referral_info[0]  # invited_by
        referrer_name = referral_info[1] or f"Користувач {referrer_id}"
        referred_user = get_user(referred_user_id)
        referred_name = referred_user[1] if (referred_user and len(referred_user) > 1) else f"Користувач {referred_user_id}"
        
        # Отримуємо розмір бонусу
        ref_bonus = get_ref_bonus()
        
        # Перевіряємо чи був відібраний бонус (шукаємо в ledger за останні 30 днів)
        import time
        thirty_days_ago = int(time.time()) - (30 * 24 * 3600)
        
        with _db() as con:
            # Шукаємо транзакцію реферального бонусу, яка була відібрана (від'ємна сума)
            clawback_row = con.execute("""
                SELECT id, ABS(amount), timestamp 
                FROM ledger 
                WHERE user_id = ? 
                AND reason = 'referral_bonus' 
                AND details LIKE ?
                AND amount < 0
                AND timestamp >= ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (referrer_id, f'%{referred_user_id}%', thirty_days_ago)).fetchone()
        
        if not clawback_row:
            print(f"[REFERRAL] Відібраний бонус для реферера {referrer_id} не знайдено")
            return
        
        clawback_id, clawback_amount, clawback_timestamp = clawback_row
        
        # Перевіряємо чи підписка дійсно є
        try:
            from subscription_system import check_user_subscription
            has_subscription = check_user_subscription(referred_user_id, bot, check_only=True)
        except Exception as e:
            print(f"[REFERRAL] Помилка перевірки підписки: {e}")
            has_subscription = False
        
        if not has_subscription:
            print(f"[REFERRAL] Підписка відсутня, бонус не повертається")
            return
        
        # Повертаємо бонус
        try:
            from database import add_balance
            add_balance(referrer_id, float(clawback_amount), reason='referral_bonus_restored', 
                       details=f'Повернення реферального бонусу за користувача {referred_user_id} ({referred_name}) - повернення до каналу')
            print(f"[REFERRAL] Повернено {clawback_amount}₴ рефереру {referrer_id} за повернення реферала {referred_user_id}")
            
            # Відправляємо повідомлення рефереру
            try:
                from utils import format_currency
            except Exception:
                def format_currency(amount):
                    return f"{amount:.2f}"
            
            try:
                bot.send_message(
                    referrer_id,
                    "✅ <b>РЕФЕРАЛЬНИЙ БОНУС ПОВЕРНЕНО</b>\n\n"
                    f"👤 <b>Реферал:</b> {referred_name}\n"
                    f"✅ <b>Причина:</b> Повернення до обов'язкового каналу\n\n"
                    f"💰 <b>Повернено:</b> {format_currency(clawback_amount)} ₴",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення рефереру: {e}")
            
            # Відправляємо повідомлення рефералу
            try:
                bot.send_message(
                    referred_user_id,
                    "✅ <b>ДЯКУЄМО ЗА ПОВЕРНЕННЯ!</b>\n\n"
                    f"Ви повернулися до обов'язкового каналу.\n\n"
                    f"💰 Реферальний бонус вашого реферера ({referrer_name}) повернуто.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення рефералу: {e}")
                
        except Exception as e:
            print(f"[REFERRAL] Помилка повернення бонусу: {e}")
            
    except Exception as e:
        print(f"[ERROR] Помилка повернення реферального бонусу: {e}")
        import traceback
        traceback.print_exc()
