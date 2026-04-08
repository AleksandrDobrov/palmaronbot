#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Покращена адмінка для управління каналами та чатами
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    get_required_channels, get_required_chats, add_required_channel, 
    remove_required_channel, add_required_chat, remove_required_chat,
    get_all_blocked_users, unblock_user
)

def show_enhanced_channel_management(call, bot):
    """Показує покращене меню управління каналами та чатами"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    required_channels = get_required_channels()
    required_chats = get_required_chats()
    blocked_users = get_all_blocked_users()
    
    # Формуємо текст
    text = "📢 <b>УПРАВЛІННЯ КАНАЛАМИ ТА ЧАТАМИ</b>\n\n"
    
    if required_channels:
        text += "📢 <b>Канали для підписки:</b>\n"
        for i, channel in enumerate(required_channels, 1):
            text += f"{i}. <b>{channel}</b>\n"
        text += "\n"
    else:
        text += "📢 <b>Канали для підписки:</b> <i>Не встановлені</i>\n\n"
    
    if required_chats:
        text += "👥 <b>Чати для участі:</b>\n"
        for i, chat_id in enumerate(required_chats, 1):
            try:
                chat_info = bot.get_chat(chat_id)
                chat_title = chat_info.title
                text += f"{i}. <b>{chat_title}</b> (<code>{chat_id}</code>)\n"
            except:
                text += f"{i}. <b>Чат {chat_id}</b>\n"
        text += "\n"
    else:
        text += "👥 <b>Чати для участі:</b> <i>Не встановлені</i>\n\n"
    
    if blocked_users:
        text += f"🚫 <b>Заблоковані користувачі:</b> <code>{len(blocked_users)}</code>\n\n"
    
    text += "💡 <b>Можливості:</b>\n"
    text += "• Додати/видалити канали\n"
    text += "• Додати/видалити чати\n"
    text += "• Переглянути заблокованих\n"
    text += "• Масові операції\n\n"
    text += "🔒 <b>Всі користувачі будуть перевірятися!</b>"
    
    # Формуємо клавіатуру
    kb = InlineKeyboardMarkup(row_width=2)
    
    # Кнопки для каналів
    kb.add(
        InlineKeyboardButton("📢 Додати канал", callback_data="add_channel_enhanced"),
        InlineKeyboardButton("➖ Видалити канал", callback_data="remove_channel_enhanced")
    )
    
    # Кнопки для чатів
    kb.add(
        InlineKeyboardButton("👥 Додати чат", callback_data="add_chat_enhanced"),
        InlineKeyboardButton("➖ Видалити чат", callback_data="remove_chat_enhanced")
    )
    
    # Кнопки для заблокованих
    if blocked_users:
        kb.add(
            InlineKeyboardButton("🚫 Заблоковані", callback_data="show_blocked_users"),
            InlineKeyboardButton("🔄 Масова перевірка", callback_data="mass_check_users")
        )
    
    # Кнопки управління
    kb.add(
        InlineKeyboardButton("❌ Вимкнути всі", callback_data="disable_all_subscriptions"),
        InlineKeyboardButton("⬅️ Назад", callback_data="panel")
    )
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )

def add_channel_enhanced_handler(call, bot):
    """Обробник додавання каналу"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📢 Додати публічний канал", callback_data="add_public_channel_enhanced"),
        InlineKeyboardButton("⬅️ Назад", callback_data="enhanced_channel_management")
    )
    
    bot.edit_message_text(
        "📢 <b>ДОДАВАННЯ КАНАЛУ</b>\n\n"
        "💡 <b>Типи каналів:</b>\n"
        "• <b>Публічний канал</b> - користувачі підписуються\n"
        "• <b>Приватний канал</b> - потрібен invite link\n\n"
        "🔒 <b>Важливо:</b>\n"
        "• Канал має бути публічним\n"
        "• Бот має мати доступ до перегляду учасників\n\n"
        "👆 Оберіть тип:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )

def add_public_channel_enhanced_handler(call, bot):
    """Обробник додавання публічного каналу"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    msg = bot.send_message(
        call.message.chat.id, 
        "📝 <b>Введіть username публічного каналу:</b>\n\n"
        "💡 <b>Формат:</b> <code>@mychannel</code>\n"
        "🔍 <b>Приклад:</b> <code>@investing_palmaron</code>\n\n"
        "⚠️ <b>Важливо:</b>\n"
        "• Канал має бути публічним\n"
        "• Бот має мати доступ\n"
        "• Перевірте правильність username\n\n"
        "Введіть username каналу:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_add_channel_enhanced, bot)

def process_add_channel_enhanced(message, bot):
    """Обробляє додавання каналу"""
    from bot import is_admin
    if not is_admin(message.from_user.id):
        return
    
    channel_username = message.text.strip()
    
    if not channel_username.startswith('@'):
        return bot.send_message(
            message.chat.id, 
            "❌ <b>Помилка!</b>\n\n"
            "Username каналу має починатися з <code>@</code>\n"
            "Наприклад: <code>@mychannel</code>",
            parse_mode="HTML"
        )
    
    try:
        # Перевіряємо чи існує канал
        chat_info = bot.get_chat(channel_username)
        
        # Додаємо канал
        add_required_channel(channel_username)
        
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Канал додано успішно!</b>\n\n"
            f"📢 <b>Канал:</b> <b>{chat_info.title}</b>\n"
            f"🔗 <b>Username:</b> <code>{channel_username}</code>\n"
            f"👥 <b>Учасників:</b> <code>{chat_info.members_count if hasattr(chat_info, 'members_count') else 'Невідомо'}</code>\n\n"
            f"🔒 Тепер користувачі мають підписатися на всі канали!\n"
            f"💡 Адміни проходять без перевірки.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ <b>Помилка додавання каналу!</b>\n\n"
            f"🚫 <b>Причина:</b> {str(e)}\n\n"
            f"💡 <b>Перевірте:</b>\n"
            f"• Правильність username\n"
            f"• Публічність каналу\n"
            f"• Доступ бота до каналу",
            parse_mode="HTML"
        )

def add_chat_enhanced_handler(call, bot):
    """Обробник додавання чату"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    msg = bot.send_message(
        call.message.chat.id, 
        "📝 <b>Введіть ID чату:</b>\n\n"
        "💡 <b>Як отримати ID:</b>\n"
        "1. Додайте бота в чат як адміністратора\n"
        "2. Надішліть повідомлення в чат\n"
        "3. Використайте команду /get_chat_id\n\n"
        "🔍 <b>Формат:</b> <code>-1001234567890</code>\n\n"
        "⚠️ <b>Важливо:</b>\n"
        "• Бот має бути адміністратором\n"
        "• Права на перегляд учасників\n"
        "• Приватні чати потребують invite link\n\n"
        "Введіть ID чату:",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_add_chat_enhanced, bot)

def process_add_chat_enhanced(message, bot):
    """Обробляє додавання чату"""
    from bot import is_admin
    if not is_admin(message.from_user.id):
        return
    
    chat_id = message.text.strip()
    
    try:
        chat_id = int(chat_id)
        
        # Перевіряємо чи існує чат
        chat_info = bot.get_chat(chat_id)
        
        # Перевіряємо права бота
        bot_member = bot.get_chat_member(chat_id, bot.get_me().id)
        if bot_member.status not in ['administrator', 'creator']:
            return bot.send_message(
                message.chat.id,
                "❌ <b>Помилка!</b>\n\n"
                "🚫 Бот має бути адміністратором чату!\n\n"
                "💡 <b>Що робити:</b>\n"
                "• Додайте бота як адміністратора\n"
                "• Надайте права на перегляд учасників\n"
                "• Спробуйте ще раз",
                parse_mode="HTML"
            )
        
        # Додаємо чат
        add_required_chat(str(chat_id))
        
        bot.send_message(
            message.chat.id, 
            f"✅ <b>Чат додано успішно!</b>\n\n"
            f"👥 <b>Чат:</b> <b>{chat_info.title}</b>\n"
            f"🆔 <b>ID:</b> <code>{chat_id}</code>\n"
            f"👥 <b>Тип:</b> <b>{'Приватний' if chat_info.type in ['group', 'supergroup'] else 'Публічний'}</b>\n\n"
            f"🔒 Тепер користувачі мають бути учасниками всіх чатів!\n"
            f"💡 Адміни проходять без перевірки.",
            parse_mode="HTML"
        )
        
    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌ <b>Помилка!</b>\n\n"
            "🚫 ID чату має бути числом!\n"
            "Наприклад: <code>-1001234567890</code>",
            parse_mode="HTML"
        )
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ <b>Помилка додавання чату!</b>\n\n"
            f"🚫 <b>Причина:</b> {str(e)}\n\n"
            f"💡 <b>Перевірте:</b>\n"
            f"• Правильність ID\n"
            f"• Існування чату\n"
            f"• Права бота в чаті",
            parse_mode="HTML"
        )

def show_blocked_users_handler(call, bot):
    """Показує список заблокованих користувачів"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    blocked_users = get_all_blocked_users()
    
    if not blocked_users:
        bot.answer_callback_query(call.id, "✅ Заблокованих користувачів немає!", show_alert=True)
        return
    
    text = "🚫 <b>ЗАБЛОКОВАНІ КОРИСТУВАЧІ</b>\n\n"
    
    for i, (user_id, reason, chat_title, blocked_at) in enumerate(blocked_users[:10], 1):
        blocked_time = time.strftime("%d.%m.%Y %H:%M", time.localtime(blocked_at))
        text += f"{i}. <b>ID:</b> <code>{user_id}</code>\n"
        text += f"   <b>Причина:</b> {reason}\n"
        text += f"   <b>Чат:</b> {chat_title}\n"
        text += f"   <b>Дата:</b> {blocked_time}\n\n"
    
    if len(blocked_users) > 10:
        text += f"... та ще <code>{len(blocked_users) - 10}</code> користувачів\n\n"
    
    text += "💡 <b>Дії:</b>\n"
    text += "• Розблокувати окремого користувача\n"
    text += "• Масове розблокування\n"
    text += "• Перевірити всіх користувачів"
    
    # Формуємо клавіатуру
    kb = InlineKeyboardMarkup(row_width=2)
    
    if len(blocked_users) <= 10:
        # Кнопки для кожного заблокованого користувача
        for user_id, _, _, _ in blocked_users:
            kb.add(InlineKeyboardButton(f"🔓 Розблокувати {user_id}", callback_data=f"unblock_user_{user_id}"))
    
    kb.add(
        InlineKeyboardButton("🔄 Масова перевірка", callback_data="mass_check_users"),
        InlineKeyboardButton("🔓 Розблокувати всіх", callback_data="unblock_all_users")
    )
    
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="enhanced_channel_management"))
    
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )

def unblock_user_handler(call, bot):
    """Обробник розблокування користувача"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    user_id = int(call.data.split("_")[2])
    
    try:
        unblock_user(user_id)
        bot.answer_callback_query(call.id, f"✅ Користувач {user_id} розблокований!", show_alert=True)
        
        # Оновлюємо список
        show_blocked_users_handler(call, bot)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Помилка розблокування: {e}", show_alert=True)

def mass_check_users_handler(call, bot):
    """Обробник масової перевірки користувачів"""
    from bot import is_admin
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    bot.answer_callback_query(call.id, "🔄 Запуск масової перевірки...", show_alert=True)
    
    # Запускаємо перевірку в окремому потоці
    import threading
    from chat_monitoring_system import check_all_users_in_required_chats
    
    def check_thread():
        try:
            check_all_users_in_required_chats(bot)
            bot.send_message(call.message.chat.id, "✅ Масова перевірка завершена!")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Помилка масової перевірки: {e}")
    
    thread = threading.Thread(target=check_thread)
    thread.start()
    
    # Показуємо повідомлення про запуск
    bot.edit_message_text(
        "🔄 <b>МАСОВА ПЕРЕВІРКА ЗАПУЩЕНА</b>\n\n"
        "⏳ Перевіряю всіх користувачів в обов'язкових чатах...\n\n"
        "💡 <b>Це може зайняти деякий час</b>\n"
        "📱 Ви отримаєте повідомлення про завершення",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML"
    )

