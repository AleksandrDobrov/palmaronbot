#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система моніторингу чатів для автоматичного блокування користувачів
"""

import telebot
import time
from database import (
    get_required_chats, is_user_blocked, block_user_for_chat_leave,
    get_user_block_info, unblock_user, get_required_channels
)

# Словник для зберігання ID повідомлень про блокування (user_id -> message_id)
block_notification_messages = {}

def handle_my_chat_member_update(update):
    """Обробляє оновлення статусу бота в чаті"""
    try:
        # Імпортуємо bot з глобального контексту
        import bot as bot_module
        bot = bot_module.bot
        
        chat_id = update.my_chat_member.chat.id
        user_id = update.my_chat_member.from_user.id
        old_status = update.my_chat_member.old_chat_member.status
        new_status = update.my_chat_member.new_chat_member.status
        
        print(f"[DEBUG] my_chat_member_update: chat_id={chat_id}, user_id={user_id}, {old_status} -> {new_status}")
        
        # Перевіряємо чи це обов'язковий чат
        required_chats = get_required_chats()
        if str(chat_id) not in required_chats:
            print(f"[DEBUG] Чат {chat_id} не є обов'язковим")
            return
        
        # Якщо бот був видалений з чату
        if new_status in ['left', 'kicked']:
            print(f"[WARNING] Бот був видалений з обов'язкового чату {chat_id}")
            # Тут можна додати сповіщення адміністратору
            return
        
        # Якщо бот був доданий як адміністратор
        if new_status in ['administrator', 'creator']:
            print(f"[INFO] Бот отримав права адміністратора в чаті {chat_id}")
            return
            
    except Exception as e:
        print(f"[ERROR] Помилка обробки my_chat_member_update: {e}")

def handle_chat_member_update(update):
    """Обробляє оновлення учасників чату"""
    try:
        # Імпортуємо bot з глобального контексту
        import bot as bot_module
        bot = bot_module.bot
        
        chat_id = update.chat_member.chat.id
        user_id = update.chat_member.from_user.id
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        
        print(f"[DEBUG] chat_member_update: chat_id={chat_id}, user_id={user_id}, {old_status} -> {new_status}")
        
        # Перевіряємо чи це обов'язковий чат
        required_chats = get_required_chats()
        if str(chat_id) not in required_chats:
            print(f"[DEBUG] Чат {chat_id} не є обов'язковим")
            return
        
        # Якщо користувач вийшов з чату
        if new_status in ['left', 'kicked']:
            print(f"[INFO] Користувач {user_id} вийшов з обов'язкового чату {chat_id}")
            
            # Перевіряємо чи не заблокований вже користувач
            if is_user_blocked(user_id):
                print(f"[DEBUG] Користувач {user_id} вже заблокований")
                return
            
            # Отримуємо інформацію про чат
            try:
                chat_info = bot.get_chat(chat_id)
                chat_title = chat_info.title
            except:
                chat_title = f"Чат {chat_id}"
            
            # Блокуємо користувача
            block_user_for_chat_leave(user_id, str(chat_id), chat_title)
            print(f"[INFO] Користувач {user_id} заблокований за вихід з чату {chat_title}")
            
            # Відправляємо повідомлення про блокування (передаємо update для перевірки типу)
            send_block_notification_to_user(bot, user_id, chat_title, update)
            
        # Якщо користувач повернувся в чат
        elif old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
            print(f"[INFO] Користувач {user_id} повернувся в обов'язковий чат {chat_id}")
            
            # Перевіряємо чи заблокований користувач
            if is_user_blocked(user_id):
                # Розблоковуємо користувача
                unblock_user(user_id)
                print(f"[INFO] Користувач {user_id} розблокований за повернення в чат {chat_title}")
                
                # Відправляємо повідомлення про розблокування
                send_unblock_notification_to_user(bot, user_id, chat_title)
            
    except Exception as e:
        print(f"[ERROR] Помилка обробки chat_member_update: {e}")

def send_block_notification_to_user(bot, user_id, chat_title, message_or_call=None):
    """Відправляє користувачу повідомлення про блокування"""
    global block_notification_messages
    
    try:
        # Перевіряємо чи це повідомлення від каналу (пост) - не відправляємо в такому випадку
        if message_or_call:
            try:
                # Якщо це повідомлення з каналу (sender_chat існує), не відправляємо
                if hasattr(message_or_call, 'sender_chat') and message_or_call.sender_chat:
                    print(f"[DEBUG] Повідомлення від каналу, пропускаємо відправку блокування для {user_id}")
                    return
                # Якщо це call і повідомлення з каналу
                if hasattr(message_or_call, 'message') and hasattr(message_or_call.message, 'sender_chat') and message_or_call.message.sender_chat:
                    print(f"[DEBUG] Call від каналу, пропускаємо відправку блокування для {user_id}")
                    return
                # Якщо це update з chat_member
                if hasattr(message_or_call, 'chat_member') and hasattr(message_or_call.chat_member, 'chat') and hasattr(message_or_call.chat_member.chat, 'type') and message_or_call.chat_member.chat.type == 'channel':
                    print(f"[DEBUG] Update від каналу, пропускаємо відправку блокування для {user_id}")
                    return
            except Exception:
                pass
        
        # Отримуємо інформацію про користувача для згадування
        try:
            user_info = bot.get_chat_member(user_id, user_id)
            username = user_info.user.username if hasattr(user_info, 'user') and user_info.user.username else None
            first_name = user_info.user.first_name if hasattr(user_info, 'user') and user_info.user.first_name else f"ID{user_id}"
        except Exception:
            try:
                user_chat = bot.get_chat(user_id)
                username = user_chat.username if hasattr(user_chat, 'username') else None
                first_name = user_chat.first_name if hasattr(user_chat, 'first_name') else f"ID{user_id}"
            except Exception:
                username = None
                first_name = f"ID{user_id}"
        
        # Формуємо згадування
        if username:
            mention = f"@{username}"
        else:
            mention = f"<a href='tg://user?id={user_id}'>{first_name}</a>"
        
        # Отримуємо інформацію про блокування
        block_info = get_user_block_info(user_id)
        block_type = "чат" if block_info and block_info[2] == 'chat_leave' else "канал/чат"
        
        # Отримуємо список обов'язкових каналів
        required_channels = get_required_channels()
        main_channel = None
        if required_channels:
            try:
                # Беремо перший канал як основний
                main_channel = required_channels[0]
                if isinstance(main_channel, str) and not main_channel.startswith('@'):
                    main_channel = f"@{main_channel}"
            except Exception:
                pass
        
        block_text = (
            f"🚫 <b>ДОСТУП ЗАБЛОКОВАНО!</b>\n\n"
            f"👤 {mention}, ви вийшли з обов'язкового чату!\n\n"
            f"❌ <b>Причина:</b> Вихід з обов'язкового {block_type}\n"
            f"📅 <b>Дата блокування:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(int(block_info[6]) if block_info and block_info[6] else time.time()))}\n\n"
            f"💬 <b>Чати:</b>\n"
            f"❌ <b>{chat_title}</b> — ❌ Не приєднано\n\n"
            f"💡 <b>Що робити:</b>\n"
            f"• Приєднайтеся до обов'язкового чату: <b>{chat_title}</b>\n"
        )
        
        if main_channel:
            block_text += (
                f"• Напишіть в <b>коментаріях до посту</b> в каналі {main_channel}, щоб отримати допомогу\n"
            )
        
        block_text += (
            f"• Зверніться до адміністратора\n"
            f"• Очікуйте розблокування\n\n"
            f"🔄 <b>Після підписки натисніть кнопку нижче для перевірки:</b>"
        )
        
        # Додаємо кнопку перевірки підписки
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔄 Перевірити підписку", callback_data="verify_subscription"))
        
        # Відправляємо повідомлення
        sent_message = bot.send_message(user_id, block_text, reply_markup=kb, parse_mode="HTML")
        
        # Зберігаємо ID повідомлення для подальшого видалення
        if sent_message:
            block_notification_messages[user_id] = sent_message.message_id
        
        print(f"[INFO] Повідомлення про блокування відправлено користувачу {user_id}")
        
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про блокування: {e}")

def send_unblock_notification_to_user(bot, user_id, chat_title):
    """Відправляє користувачу повідомлення про розблокування та видаляє повідомлення про блокування"""
    global block_notification_messages
    
    try:
        # Видаляємо повідомлення про блокування, якщо воно існує
        if user_id in block_notification_messages:
            try:
                message_id = block_notification_messages[user_id]
                bot.delete_message(user_id, message_id)
                print(f"[INFO] Видалено повідомлення про блокування (ID: {message_id}) для користувача {user_id}")
                del block_notification_messages[user_id]
            except Exception as e:
                print(f"[WARNING] Не вдалося видалити повідомлення про блокування: {e}")
        
        # Отримуємо інформацію про блокування
        block_info = get_user_block_info(user_id)
        block_type = "чат" if block_info and block_info[2] == 'chat_leave' else "канал/чат"
        
        unblock_text = (
            "✅ <b>ДОСТУП ВІДНОВЛЕНО!</b>\n\n"
            f"🎉 <b>Причина:</b> Повернення в обов'язковий {block_type}: {chat_title}\n"
            f"📅 <b>Дата розблокування:</b> {time.strftime('%d.%m.%Y %H:%M')}\n\n"
            "🔓 <b>Що сталося:</b>\n"
            f"• Ви повернулися в обов'язковий {block_type}\n"
            "• Бот автоматично розблокував доступ\n"
            "• Всі функції знову доступні\n\n"
            "💎 <b>Вітаємо назад в Investing Palmaron Bot!</b>"
        )
        
        bot.send_message(user_id, unblock_text, parse_mode="HTML")
        print(f"[INFO] Повідомлення про розблокування відправлено користувачу {user_id}")
        
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про розблокування: {e}")

def setup_chat_monitoring(bot):
    """Налаштовує систему моніторингу чатів"""
    try:
        # Додаємо обробники
        bot.my_chat_member_handler = handle_my_chat_member_update
        bot.chat_member_handler = handle_chat_member_update
        
        print("[INFO] Система моніторингу чатів налаштована")
        
    except Exception as e:
        print(f"[ERROR] Помилка налаштування системи моніторингу: {e}")

def check_all_users_in_required_chats(bot):
    """Перевіряє всіх користувачів в обов'язкових чатах"""
    try:
        from database import get_all_users, get_required_chats
        
        required_chats = get_required_chats()
        if not required_chats:
            print("[DEBUG] Немає обов'язкових чатів для перевірки")
            return
        
        all_users = get_all_users()
        print(f"[INFO] Перевіряю {len(all_users)} користувачів в {len(required_chats)} чатах")
        
        for user_id in all_users:
            try:
                # Перевіряємо участь в кожному чаті
                for chat_id in required_chats:
                    try:
                        member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                        if member.status in ['left', 'kicked']:
                            # Користувач не в чаті - блокуємо
                            chat_info = bot.get_chat(chat_id)
                            chat_title = chat_info.title
                            
                            if not is_user_blocked(user_id):
                                block_user_for_chat_leave(user_id, str(chat_id), chat_title)
                                print(f"[INFO] Користувач {user_id} заблокований за відсутність в чаті {chat_title}")
                                
                                # Відправляємо повідомлення (без update, бо це перевірка)
                                send_block_notification_to_user(bot, user_id, chat_title, None)
                            break
                            
                    except Exception as e:
                        print(f"[ERROR] Помилка перевірки користувача {user_id} в чаті {chat_id}: {e}")
                        continue
                        
            except Exception as e:
                print(f"[ERROR] Помилка обробки користувача {user_id}: {e}")
                continue
        
        print("[INFO] Перевірка всіх користувачів завершена")
        
    except Exception as e:
        print(f"[ERROR] Помилка масової перевірки користувачів: {e}")

def schedule_chat_monitoring(bot, interval_hours=24):
    """Планує періодичну перевірку користувачів в чатах"""
    import threading
    import time
    
    def monitoring_loop():
        while True:
            try:
                print(f"[INFO] Запуск планової перевірки користувачів в чатах")
                check_all_users_in_required_chats(bot)
                print(f"[INFO] Планова перевірка завершена. Наступна через {interval_hours} годин")
            except Exception as e:
                print(f"[ERROR] Помилка планової перевірки: {e}")
            
            # Чекаємо до наступної перевірки
            time.sleep(interval_hours * 3600)
    
    # Запускаємо в окремому потоці
    monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitoring_thread.start()
    
    print(f"[INFO] Планова перевірка чатів запущена з інтервалом {interval_hours} годин")

