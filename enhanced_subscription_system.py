#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Покращена система перевірки підписки з підтримкою обов'язкових чатів
"""

import telebot
import random
import time
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_required_channels, get_required_chats, is_user_blocked, 
    block_user_for_chat_leave, get_user_block_info, set_user_state, 
    get_user_state, clear_user_state
)

def check_user_subscription_enhanced(user_id, bot):
    """Покращена перевірка підписки користувача на канали та чати"""
    
    # Спочатку перевіряємо чи не заблокований користувач
    if is_user_blocked(user_id):
        print(f"[DEBUG] Користувач {user_id} заблокований за вихід з чату")
        return False, "blocked"
    
    # Перевіряємо канали
    required_channels = get_required_channels()
    channels_status = check_channels_subscription(user_id, bot, required_channels)
    
    # Перевіряємо чати
    required_chats = get_required_chats()
    chats_status = check_chats_membership(user_id, bot, required_chats)
    
    # Якщо є і канали і чати - користувач має бути в усіх
    if required_channels and required_chats:
        return channels_status and chats_status, "both"
    elif required_channels:
        return channels_status, "channels"
    elif required_chats:
        return chats_status, "chats"
    else:
        return True, "none"

def check_channels_subscription(user_id, bot, channels):
    """Перевіряє підписку на канали"""
    if not channels:
        return True
    
    print(f"[DEBUG] Перевіряю підписку для {user_id} на канали: {channels}")
    
    for channel in channels:
        try:
            member = bot.get_chat_member(chat_id=channel, user_id=user_id)
            print(f"[DEBUG] Статус користувача {user_id} в каналі {channel}: {member.status}")
            
            if member.status in ['left', 'kicked']:
                print(f"[DEBUG] Користувач {user_id} не підписаний на канал {channel}")
                return False
                
        except telebot.apihelper.ApiTelegramException as e:
            print(f"[ERROR] Помилка перевірки підписки на канал {channel}: {e}")
            if "chat not found" in str(e) or "bot was blocked" in str(e):
                print(f"[DEBUG] Канал {channel} недоступний, пропускаю")
                continue
            else:
                return False
        except Exception as e:
            print(f"[ERROR] Загальна помилка перевірки підписки: {e}")
            return False
    
    print(f"[DEBUG] Користувач {user_id} підписаний на всі канали")
    return True

def check_chats_membership(user_id, bot, chats):
    """Перевіряє участь в чатах"""
    if not chats:
        return True
    
    print(f"[DEBUG] Перевіряю участь для {user_id} в чатах: {chats}")
    
    for chat_id in chats:
        try:
            member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            print(f"[DEBUG] Статус користувача {user_id} в чаті {chat_id}: {member.status}")
            
            if member.status in ['left', 'kicked']:
                print(f"[DEBUG] Користувач {user_id} не в чаті {chat_id}")
                return False
                
        except telebot.apihelper.ApiTelegramException as e:
            print(f"[ERROR] Помилка перевірки участь в чаті {chat_id}: {e}")
            if "chat not found" in str(e) or "bot was blocked" in str(e):
                print(f"[DEBUG] Чат {chat_id} недоступний, пропускаю")
                continue
            else:
                return False
        except Exception as e:
            print(f"[ERROR] Загальна помилка перевірки участь в чаті: {e}")
            return False
    
    print(f"[DEBUG] Користувач {user_id} учасник всіх чатів")
    return True

def send_subscription_required_message_enhanced(message_or_call, user_id, bot):
    """Відправляє покращене повідомлення з вимогою підписки"""
    
    # Перевіряємо чи не заблокований користувач
    if is_user_blocked(user_id):
        block_info = get_user_block_info(user_id)
        send_blocked_message(message_or_call, user_id, bot, block_info)
        return
    
    required_channels = get_required_channels()
    required_chats = get_required_chats()
    
    print(f"[DEBUG] send_subscription_required_message_enhanced: канали = {required_channels}, чати = {required_chats}")
    
    if not required_channels and not required_chats:
        # Якщо нічого не потрібно - показуємо головне меню
        print(f"[DEBUG] Нічого не потрібно, показую головне меню для {user_id}")
        from bot import show_main_menu
        show_main_menu(message_or_call)
        return
    
    # Встановлюємо стан користувача
    set_user_state(user_id, "waiting_subscription")
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Додаємо кнопки для каналів
    for channel in required_channels:
        channel_name = channel.replace('@', '')
        kb.add(InlineKeyboardButton(f"📢 Підписатися на {channel}", url=f"https://t.me/{channel_name}"))
    
    # Додаємо кнопки для чатів
    for chat_id in required_chats:
        try:
            chat_info = bot.get_chat(chat_id)
            chat_title = chat_info.title
            kb.add(InlineKeyboardButton(f"👥 Приєднатися до {chat_title}", url=f"https://t.me/+{chat_info.invite_link.split('/')[-1]}" if chat_info.invite_link else f"tg://openmessage?chat={chat_id}"))
        except:
            kb.add(InlineKeyboardButton(f"👥 Приєднатися до чату {chat_id}", callback_data=f"join_chat_{chat_id}"))
    
    kb.add(InlineKeyboardButton("✅ Перевірити підписку", callback_data="verify_subscription_enhanced"))
    
    # Формуємо текст повідомлення
    sub_text = "🔒 <b>ОБОВ'ЯЗКОВА ПІДПИСКА</b>\n\n"
    
    if required_channels:
        sub_text += "📢 <b>Канали для підписки:</b>\n"
        for i, channel in enumerate(required_channels, 1):
            sub_text += f"{i}. <b>{channel}</b>\n"
        sub_text += "\n"
    
    if required_chats:
        sub_text += "👥 <b>Чати для участі:</b>\n"
        for i, chat_id in enumerate(required_chats, 1):
            try:
                chat_info = bot.get_chat(chat_id)
                sub_text += f"{i}. <b>{chat_info.title}</b>\n"
            except:
                sub_text += f"{i}. <b>Чат {chat_id}</b>\n"
        sub_text += "\n"
    
    sub_text += (
        "💎 <i>Investing Palmaron Bot — тільки для підписників!</i>\n\n"
        "👆 Натисніть кнопки підписки/участі, потім 'Перевірити підписку'"
    )
    
    print(f"[DEBUG] Відправляю вимогу підписки для {user_id}")
    
    try:
        if hasattr(message_or_call, 'chat'):
            # Це message
            bot.send_message(message_or_call.chat.id, sub_text, reply_markup=kb, parse_mode="HTML")
        else:
            # Це call
            bot.edit_message_text(
                sub_text,
                message_or_call.message.chat.id,
                message_or_call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        print(f"[DEBUG] Повідомлення про підписку відправлено успішно для {user_id}")
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про підписку: {e}")

def send_blocked_message(message_or_call, user_id, bot, block_info):
    """Відправляє повідомлення про блокування"""
    
    if not block_info:
        return
    
    blocked_at = time.strftime("%d.%m.%Y %H:%M", time.localtime(int(block_info[6])))
    
    block_text = (
        "🚫 <b>ДОСТУП ЗАБЛОКОВАНО!</b>\n\n"
        f"❌ <b>Причина:</b> {block_info[2]}\n"
        f"📅 <b>Дата блокування:</b> {blocked_at}\n"
        f"💬 <b>Чат:</b> {block_info[5]}\n\n"
        "🔒 <b>Що сталося:</b>\n"
        "• Ви вийшли з обов'язкового чату\n"
        "• Бот автоматично заблокував доступ\n"
        "• Всі функції недоступні\n\n"
        "💡 <b>Що робити:</b>\n"
        "• Поверніться в чат: {block_info[5]}\n"
        "• Зверніться до адміністратора\n"
        "• Очікуйте розблокування\n\n"
        "📞 <i>Для розблокування зверніться до підтримки</i>"
    )
    
    try:
        if hasattr(message_or_call, 'chat'):
            bot.send_message(message_or_call.chat.id, block_text, parse_mode="HTML")
        else:
            bot.edit_message_text(
                block_text,
                message_or_call.message.chat.id,
                message_or_call.message.message_id,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про блокування: {e}")

def verify_subscription_enhanced_handler(call, bot):
    """Покращений обробник кнопки 'Перевірити підписку'"""
    user_id = call.from_user.id
    print(f"[DEBUG] verify_subscription_enhanced_handler для {user_id}")
    
    # Перевіряємо підписку
    is_subscribed, sub_type = check_user_subscription_enhanced(user_id, bot)
    
    if is_subscribed:
        # Підписка підтверджена
        bot.answer_callback_query(call.id, "✅ Підписка підтверджена!")
        
        # Очищаємо стан користувача
        clear_user_state(user_id)
        
        # Показуємо повідомлення про успіх
        success_text = "✅ <b>Підписка підтверджена!</b>\n\n"
        
        if sub_type == "both":
            success_text += "🎉 Ви підписані на всі канали та учасник всіх чатів!\n"
        elif sub_type == "channels":
            success_text += "🎉 Ви підписані на всі необхідні канали!\n"
        elif sub_type == "chats":
            success_text += "🎉 Ви учасник всіх необхідних чатів!\n"
        
        success_text += "\n💎 <b>Вітаємо в Investing Palmaron Bot!</b>"
        
        bot.edit_message_text(
            success_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )
        
        # Показуємо головне меню
        from bot import show_main_menu
        show_main_menu(call)
    else:
        # Підписка не підтверджена
        if sub_type == "blocked":
            bot.answer_callback_query(call.id, "🚫 Користувач заблокований!")
            return
        
        bot.answer_callback_query(call.id, "❌ Потрібна підписка на всі канали/чати!")
        
        # Показуємо повідомлення про необхідність підписки
        bot.edit_message_text(
            "❌ <b>Підписка не підтверджена!</b>\n\n"
            "📢 Ви повинні підписатися на всі необхідні канали та приєднатися до всіх чатів!\n\n"
            "🔄 Спробуйте ще раз або зверніться до підтримки",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML"
        )

def check_subscription_before_action_enhanced(message_or_call, bot):
    """Покращена перевірка підписки перед дією"""
    # Визначаємо user_id
    if hasattr(message_or_call, 'from_user'):
        user_id = message_or_call.from_user.id
    else:
        user_id = message_or_call.message.from_user.id
    
    print(f"[DEBUG] check_subscription_before_action_enhanced для {user_id}")
    
    # Перевіряємо стан користувача
    user_state = get_user_state(user_id)
    
    if user_state == "waiting_subscription":
        print(f"[DEBUG] Користувач {user_id} очікує підписку")
        return False
    
    # Перевіряємо підписку на канали та чати
    is_subscribed, sub_type = check_user_subscription_enhanced(user_id, bot)
    
    if not is_subscribed:
        print(f"[DEBUG] Користувач {user_id} не підписаний на канали/чати")
        # Відправляємо повідомлення про необхідність підписки
        send_subscription_required_message_enhanced(message_or_call, user_id, bot)
        return False
    
    print(f"[DEBUG] Користувач {user_id} може виконувати дії")
    return True

def subscription_guard_enhanced(func):
    """Покращений декоратор для захисту функцій"""
    def wrapper(message_or_call, *args, **kwargs):
        if not check_subscription_before_action_enhanced(message_or_call, bot):
            return  # Якщо підписка не підтверджена, функція вже показала повідомлення
        
        return func(message_or_call, *args, **kwargs)
    return wrapper

