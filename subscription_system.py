#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import get_required_channels, set_user_state, get_user_state, clear_user_state, mark_subscription_verified
from subscription_service import check_user_subscriptions, clear_cache_for_user
import time

def _send_welcome_after_verification(bot, target_chat_id, user_id: int, first_name: str, username: str | None = None):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    name = first_name or "Користувач"
    user_link = f"https://t.me/{username}" if username else f"tg://user?id={user_id}"
    text = (
        f"✨ <a href='{user_link}'><b>{name}</b></a>, ви потрапили до нас в чат! Вливайся до нашої атмосфери!\n\n"
        "🫂 Ми раді тебе бачити в нашому чаті. Ми тут граємо ігри та проводимо час у веселій атмосфері.\n\n"
        "<b>Важливе повідомлення для кожного користувача бота ❕</b>\n"
        "Якщо ви покинули чат — модератор може автоматично заблокувати доступ, і ви не зможете користуватись загальним ботом Palmaron.\n"
        "Ігноруючи це повідомлення, ви берете відповідальність на себе.\n\n"
        "Приємного користування ботом та приємного спілкування в чаті ❤️"
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("Власник боту ❤️", url="https://t.me/palmaron"),
        InlineKeyboardButton("Ознайомлення з ботом 🔺", url="https://telegra.ph/Investing-Bot---Palmaron---Oznajomlennya-02-24"),
    )
    kb.add(
        InlineKeyboardButton("Фінансовий відділ 👩‍💼", url="https://t.me/Finance_support_palmaronBot"),
        InlineKeyboardButton("Загальний бот ✨", url="https://t.me/palmaron_bot"),
    )
    kb.add(
        InlineKeyboardButton("Виплати 💌", url="https://t.me/withdraw_ugta"),
        InlineKeyboardButton("Офіційний канал 🌟", url="https://t.me/payment_ugta"),
    )

    try:
        bot.send_message(target_chat_id, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    except Exception as e:
        print(f"[ERROR] send_welcome_after_verification: {e}")

def alert_left_and_send_card(message_or_call, user_id, bot):
    """Надсилає коротке попередження, з яких каналів/чатів вийшов користувач,
    а потім — стандартну картку перевірки підписки."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    try:
        required_channels = get_required_channels()
        required_chats = __import__('database').get_required_chats()
        ch_usernames = [c if str(c).startswith('@') else f"@{c}" for c in (required_channels or [])]
        channel_results = check_user_subscriptions(bot, user_id, ch_usernames, logger=print) if ch_usernames else {}
        missing = []
        # Канали
        for ch in ch_usernames:
            r = channel_results.get(ch) or channel_results.get(ch.replace('@',''))
            if not r or r.get('status') != 'subscribed':
                try:
                    ch_info = bot.get_chat(ch)
                    title = ch_info.title or (ch_info.username and f"@{ch_info.username}") or ch
                    username = ch_info.username or ch.replace('@','')
                except Exception:
                    title = ch
                    username = ch.replace('@','')
                missing.append((title, f"https://t.me/{username}"))
        # Чати
        for chat_id in (required_chats or []):
            try:
                member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                ok = member.status not in ['left','kicked']
            except Exception:
                ok = False
            if not ok:
                url = None
                title = None
                try:
                    chat_info = bot.get_chat(chat_id)
                    title = chat_info.title or (chat_info.username and f"@{chat_info.username}") or f"Чат {chat_id}"
                    # Якщо є username - використовуємо його
                    if chat_info.username:
                        url = f"https://t.me/{chat_info.username}"
                    else:
                        # Спробуємо отримати invite link через API (якщо бот адмін)
                        try:
                            invite_link = bot.export_chat_invite_link(chat_id)
                            url = invite_link.invite_link if hasattr(invite_link, 'invite_link') else str(invite_link)
                        except Exception as e:
                            print(f"[DEBUG] Не вдалося отримати invite link для чату {chat_id}: {e}")
                            # Fallback: формуємо посилання по ID
                            url = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
                except Exception:
                    title = f"Чат {chat_id}"
                    url = f"https://t.me/c/{str(chat_id)[4:] if str(chat_id).startswith('-100') else chat_id}"
                
                if url and title:
                    missing.append((title, url))

        if missing:
            text = "⚠️ <b>Ви вийшли з обов'язкових каналів/чатів</b>\n\nПоверніться, щоб продовжити користування ботом:\n"
            kb = InlineKeyboardMarkup(row_width=1)
            for title, url in missing:
                text += f"• {title}\n"
                kb.add(InlineKeyboardButton(f"Повернутися до {title}", url=url))
            try:
                chat_id = getattr(message_or_call, 'chat', None)
                chat_id = chat_id.id if chat_id else message_or_call.message.chat.id if hasattr(message_or_call, 'message') else message_or_call.chat.id
                bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
            except Exception as e:
                print(f"[ERROR] send left-alert: {e}")
    except Exception as e:
        print(f"[ERROR] alert_left_and_send_card pre: {e}")
    # Показуємо стандартну картку
    try:
        send_subscription_required_message(message_or_call, user_id, bot)
    except Exception as e:
        print(f"[ERROR] alert_left_and_send_card card: {e}")
def check_user_subscription(user_id, bot, check_only=False):
    """
    Перевіряє, чи підписаний користувач на всі необхідні канали/чати.
    Якщо користувач не підписаний - автоматично блокує його.
    
    Args:
        user_id: ID користувача
        bot: Екземпляр бота
        check_only: Якщо True, тільки перевіряє підписку без додаткових дій
        
    Returns:
        bool: True, якщо користувач підписаний на всі необхідні канали/чати
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from database import get_required_channels, get_required_chats, is_admin, get_user_block_info, is_user_blocked, block_user_for_channel_leave, block_user_for_chat_leave
        
        # Перевіряємо чи користувач не заблокований
        if is_user_blocked(user_id):
            logger.info(f"Користувач {user_id} заблокований")
            return False
            
        # Адміни завжди проходять перевірку
        if is_admin(user_id):
            return True
            
        # Отримуємо необхідні канали та чати
        required_channels = get_required_channels() or []
        required_chats = get_required_chats() or []
        
        # Якщо немає необхідних каналів/чатів, вважаємо, що перевірка пройдена
        if not required_channels and not required_chats:
            return True
            
        # Перевіряємо підписку на канали
        for channel in required_channels:
            try:
                member = bot.get_chat_member(chat_id=channel, user_id=user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    if not check_only:
                        logger.info(f"Користувач {user_id} не підписаний на канал {channel} - блокуємо")
                        # Автоматично блокуємо користувача
                        try:
                            chat_info = bot.get_chat(channel)
                            channel_title = chat_info.title or f"Канал {channel}"
                        except:
                            channel_title = f"Канал {channel}"
                        block_user_for_channel_leave(user_id, str(channel), channel_title)
                        logger.info(f"Користувач {user_id} заблокований за відсутність в каналі {channel_title}")
                    return False
            except Exception as e:
                logger.error(f"Помилка перевірки підписки на канал {channel}: {e}")
                if not check_only:
                    return False
                    
        # Перевіряємо підписку на чати
        for chat_id in required_chats:
            try:
                member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status not in ['member', 'administrator', 'creator']:
                    if not check_only:
                        logger.info(f"Користувач {user_id} не підписаний на чат {chat_id} - блокуємо")
                        # Автоматично блокуємо користувача
                        try:
                            chat_info = bot.get_chat(chat_id)
                            chat_title = chat_info.title or f"Чат {chat_id}"
                        except:
                            chat_title = f"Чат {chat_id}"
                        block_user_for_chat_leave(user_id, str(chat_id), chat_title)
                        logger.info(f"Користувач {user_id} заблокований за відсутність в чаті {chat_title}")
                    return False
            except Exception as e:
                logger.error(f"Помилка перевірки підписки на чат {chat_id}: {e}")
                if not check_only:
                    return False
        
        return True
        
    except Exception as e:
        logger.error(f"Помилка у check_user_subscription: {e}", exc_info=True)
        return False
    """Перевіряє підписку користувача на всі необхідні канали та чати"""
    from database import get_required_chats
    
    required_channels = get_required_channels() or []
    required_chats = get_required_chats() or []
    # Нормалізуємо: з "каналів" прибираємо числові -100.. і переносимо їх у "чати"; у каналах залишаємо тільки @username
    ch_usernames = []
    ch_ids_to_move = []
    for ch in required_channels or []:
        s = str(ch).strip()
        if s.lstrip('-').isdigit():
            try:
                ch_ids_to_move.append(int(s))
            except Exception:
                ch_ids_to_move.append(s)
        else:
            ch_usernames.append(ch if str(ch).startswith('@') else f"@{ch}")
    if ch_ids_to_move:
        required_chats = list((required_chats or [])) + ch_ids_to_move
    required_channels = ch_usernames
    # Авто-нормалізація: якщо в "каналах" випадково є числовий ID (-100...), переносимо його в "чати"
    channel_usernames = []
    channel_numeric_as_chats = []
    for ch in required_channels or []:
        s = str(ch).strip()
        if s.lstrip('-').isdigit():
            try:
                channel_numeric_as_chats.append(int(s))
            except Exception:
                channel_numeric_as_chats.append(s)
        else:
            channel_usernames.append(ch if str(ch).startswith('@') else f"@{ch}")
    if channel_numeric_as_chats:
        required_chats = list((required_chats or [])) + channel_numeric_as_chats
    required_channels = channel_usernames
    
    if not required_channels and not required_chats:
        print(f"[DEBUG] Каналів і чатів для перевірки немає для {user_id}")
        return True
    
    print(f"[DEBUG] Перевіряю підписку для {user_id} на канали: {required_channels}, чати: {required_chats}")
    
    # Перевіряємо канали
    for channel in required_channels:
        # Нормалізуємо username каналу до формату з '@' для API Telegram
        channel_id = channel if str(channel).startswith('@') else f"@{channel}"
        try:
            # Перевіряємо статус користувача в каналі
            member = bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            print(f"[DEBUG] Статус користувача {user_id} в каналі {channel}: {member.status}")
            
            # Якщо користувач не підписаний або покинув канал
            if member.status in ['left', 'kicked']:
                print(f"[DEBUG] Користувач {user_id} не підписаний на канал {channel}")
                return False
                
        except telebot.apihelper.ApiTelegramException as e:
            print(f"[ERROR] Помилка перевірки підписки на канал {channel_id}: {e}")
            # Якщо канал недоступний або назва некоректна — вважаємо НЕ підписаним
            return False
        except Exception as e:
            print(f"[ERROR] Загальна помилка перевірки підписки на канал {channel_id}: {e}")
            return False
    
    # Перевіряємо чати
    for chat_id in required_chats:
        try:
            # Перевіряємо статус користувача в чаті
            member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            print(f"[DEBUG] Статус користувача {user_id} в чаті {chat_id}: {member.status}")
            
            # Якщо користувач не в чаті або покинув чат
            if member.status in ['left', 'kicked']:
                print(f"[DEBUG] Користувач {user_id} не в чаті {chat_id}")
                return False
                
        except telebot.apihelper.ApiTelegramException as e:
            print(f"[ERROR] Помилка перевірки участі в чаті {chat_id}: {e}")
            # Якщо чат не знайдено або бот не має доступу - пропускаємо
            if "chat not found" in str(e) or "bot was blocked" in str(e):
                print(f"[DEBUG] Чат {chat_id} недоступний, пропускаю")
                continue
            else:
                print(f"[ERROR] Невідома помилка для чату {chat_id}: {e}")
                return False
        except Exception as e:
            print(f"[ERROR] Загальна помилка перевірки участі в чаті: {e}")
            return False
    
    print(f"[DEBUG] Користувач {user_id} підписаний на всі канали та в усіх чатах")
    return True

def send_subscription_required_message(message_or_call, user_id, bot):
    """Відправляє повідомлення з вимогою підписки.
    Повертає True якщо повідомлення/інлайн-клавіатура успішно показані,
    і False якщо сталася помилка при відправці.
    """
    try:
        print(f"[DEBUG] === ПОЧАТОК send_subscription_required_message ===")
        print(f"[DEBUG] user_id: {user_id}")
        print(f"[DEBUG] message_or_call type: {type(message_or_call)}")
        print(f"[DEBUG] bot type: {type(bot)}")
        
        from database import get_required_chats, is_user_blocked, get_user_block_info, get_required_channels
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        import os
        
        print(f"[DEBUG] Імпорти успішні")
    except Exception as e:
        print(f"[ERROR] Помилка на початку send_subscription_required_message: {e}")
        import traceback
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return False
    
    # Перевіряємо чи користувач заблокований
    if is_user_blocked(user_id):
        block_info = get_user_block_info(user_id)
        if block_info:
            block_type = "канал" if block_info[2] == 'channel_leave' else "чат"
            
            # Отримуємо всі обов'язкові канали та чати
            required_channels = get_required_channels()
            required_chats = get_required_chats()
            
            # Перевіряємо підписку на всі канали та чати
            not_subscribed_channels = []
            not_subscribed_chats = []
            
            # Перевіряємо канали
            if required_channels:
                for channel in required_channels:
                    try:
                        member = bot.get_chat_member(channel, user_id)
                        if member.status in ['left', 'kicked']:
                            not_subscribed_channels.append(channel)
                    except Exception as e:
                        print(f"[ERROR] Помилка перевірки каналу {channel}: {e}")
                        # Якщо не можемо перевірити - додаємо до списку
                        not_subscribed_channels.append(channel)
            
            # Перевіряємо чати
            if required_chats:
                for chat_id in required_chats:
                    try:
                        member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                        if member.status in ['left', 'kicked']:
                            not_subscribed_chats.append(chat_id)
                    except Exception as e:
                        print(f"[ERROR] Помилка перевірки чату {chat_id}: {e}")
                        # Якщо не можемо перевірити - додаємо до списку
                        not_subscribed_chats.append(chat_id)
            
            # Формуємо текст зі списком непідписаних каналів/чатів
            # Отримуємо інформацію про користувача для згадування
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
            
            # Отримуємо основний канал
            main_channel = None
            if required_channels:
                try:
                    main_channel = required_channels[0]
                    if isinstance(main_channel, str) and not main_channel.startswith('@'):
                        main_channel = f"@{main_channel}"
                except Exception:
                    pass
            
            block_text = (
                f"🚫 <b>ДОСТУП ЗАБЛОКОВАНО!</b>\n\n"
                f"👤 {mention}, ви вийшли з обов'язкового чату!\n\n"
                f"❌ <b>Причина:</b> Вихід з обов'язкового {block_type}\n"
                f"📅 <b>Дата блокування:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(int(block_info[6])))}\n\n"
            )
            
            # Додаємо список непідписаних каналів
            if not_subscribed_channels:
                block_text += "📢 <b>Канали:</b>\n"
                for channel in not_subscribed_channels:
                    try:
                        normalized = channel if str(channel).startswith('@') else f"@{channel}"
                        ch_info = bot.get_chat(normalized)
                        ch_title = ch_info.title or (ch_info.username and f"@{ch_info.username}") or str(channel)
                        block_text += f"❌ <b>{ch_title}</b> — ❌ Не підписано\n"
                    except Exception:
                        block_text += f"❌ <b>{channel}</b> — ❌ Не підписано\n"
                block_text += "\n"
            
            # Додаємо список непідписаних чатів
            if not_subscribed_chats:
                block_text += "💬 <b>Чати:</b>\n"
                for chat_id in not_subscribed_chats:
                    try:
                        chat_info = bot.get_chat(chat_id)
                        chat_title = chat_info.title or (chat_info.username and f"@{chat_info.username}") or f"Чат {chat_id}"
                        # Спеціальний випадок для відомого чату
                        if str(chat_id) == "-1002218982939":
                            chat_title = "💬 Головний чат"
                        block_text += f"❌ <b>{chat_title}</b> — ❌ Не приєднано\n"
                    except Exception:
                        block_text += f"❌ <b>Чат {chat_id}</b> — ❌ Не приєднано\n"
                block_text += "\n"
            
            block_text += (
                f"💡 <b>Що робити:</b>\n"
                f"• Підпишіться на всі канали та приєднайтеся до чатів\n"
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
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔄 Перевірити підписку", callback_data="verify_subscription"))
            
            try:
                # Перевіряємо чи це повідомлення від каналу (пост) - не відправляємо в такому випадку
                is_channel_post = False
                if hasattr(message_or_call, 'sender_chat') and message_or_call.sender_chat:
                    is_channel_post = True
                elif hasattr(message_or_call, 'message') and hasattr(message_or_call.message, 'sender_chat') and message_or_call.message.sender_chat:
                    is_channel_post = True
                
                if is_channel_post:
                    print(f"[DEBUG] Повідомлення від каналу, пропускаємо відправку блокування для {user_id}")
                    return False
                
                if hasattr(message_or_call, 'chat'):
                    bot.send_message(message_or_call.chat.id, block_text, reply_markup=kb, parse_mode="HTML")
                else:
                    bot.edit_message_text(block_text, message_or_call.message.chat.id, message_or_call.message.message_id, reply_markup=kb, parse_mode="HTML")
                return True
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення про блокування: {e}")
                return False
    
    required_channels = get_required_channels()
    required_chats = get_required_chats()
    # Простий форс-показ блоку підписки навіть якщо списки порожні
    force_show = False
    try:
        import os
        force_show = (os.environ.get("FORCE_SHOW_SUB_PROMPT", "0") == "1")
    except Exception:
        force_show = False
    
    print(f"[DEBUG] send_subscription_required_message: канали = {required_channels}, чати = {required_chats}")
    print(f"[DEBUG] FORCE_SHOW_SUB_PROMPT = {force_show}")
    print(f"[DEBUG] Користувач {user_id} - перевіряємо підписку")
    
    if (not required_channels) and (not required_chats) and not force_show:
        # Якщо каналів і чатів немає - вважаємо верифікацію пройденою
        print(f"[DEBUG] Каналів і чатів немає, підписка вважається підтвердженою для {user_id}")
        try:
            mark_subscription_verified(user_id)
        except Exception:
            pass
        from bot import show_main_menu
        show_main_menu(message_or_call)
        return True
    
    # Встановлюємо стан користувача, зберігаючи реферальну інформацію
    from database import get_user_state
    import json
    current_state = get_user_state(user_id)
    
    # Якщо є реферальна інформація, зберігаємо її разом зі станом підписки
    if current_state and current_state != "waiting_subscription":
        try:
            # Перевіряємо, чи це JSON з реферальною інформацією
            state_data = json.loads(current_state)
            if "referrer_id" in state_data:
                # Зберігаємо реферальну інформацію разом зі станом підписки
                state_data["subscription_status"] = "waiting_subscription"
                set_user_state(user_id, json.dumps(state_data))
                print(f"[DEBUG] Збережено реферальну інформацію разом зі станом підписки: {state_data}")
            else:
                set_user_state(user_id, "waiting_subscription")
        except:
            # Якщо не JSON, просто встановлюємо стан підписки
            set_user_state(user_id, "waiting_subscription")
    else:
        set_user_state(user_id, "waiting_subscription")
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Додаємо кнопки для каналів (з красивою назвою)
    for channel in required_channels:
        try:
            normalized = channel if str(channel).startswith('@') else f"@{channel}"
            ch_info = bot.get_chat(normalized)
            ch_title = ch_info.title or (ch_info.username and f"@{ch_info.username}") or str(channel)
            ch_username = ch_info.username or str(channel).replace('@', '')
        except Exception:
            ch_title = str(channel)
            ch_username = str(channel).replace('@', '')
        kb.add(InlineKeyboardButton(f"📢 Підписатися на {ch_title}", url=f"https://t.me/{ch_username}"))
    
    # Додаємо кнопки для чатів
    for chat_id in required_chats:
        invite_url = None
        chat_title = None
        try:
            chat_info = bot.get_chat(chat_id)
            chat_title = chat_info.title or f"Чат {chat_id}"
            # Спеціальний випадок для відомого чату
            if str(chat_id) == "-1002218982939":
                chat_title = "💬 Головний чат"
            
            # Якщо є username - використовуємо його
            if chat_info.username:
                invite_url = f"https://t.me/{chat_info.username}"
            else:
                # Спробуємо отримати invite link через API (якщо бот адмін)
                try:
                    invite_link = bot.export_chat_invite_link(chat_id)
                    invite_url = invite_link.invite_link if hasattr(invite_link, 'invite_link') else str(invite_link)
                except Exception as e:
                    print(f"[DEBUG] Не вдалося отримати invite link для чату {chat_id}: {e}")
                    # Fallback: формуємо посилання по ID (може не працювати для приватних чатів)
                    chat_id_clean = str(chat_id)[4:] if str(chat_id).startswith('-100') else str(chat_id)
                    invite_url = f"https://t.me/c/{chat_id_clean}"
        except Exception as e:
            print(f"[ERROR] Не вдалося отримати інфо чату {chat_id}: {e}")
            # Спеціальний випадок для відомого чату
            if str(chat_id) == "-1002218982939":
                chat_title = "💬 Головний чат"
            else:
                chat_title = f"Чат {chat_id}"
            # Fallback: формуємо посилання по ID
            chat_id_clean = str(chat_id)[4:] if str(chat_id).startswith('-100') else str(chat_id)
            invite_url = f"https://t.me/c/{chat_id_clean}"
        
        if invite_url and chat_title:
            kb.add(InlineKeyboardButton(f"💬 Приєднатися до {chat_title}", url=invite_url))
    
    # Кнопка перевірки підписки (RU текст за вимогою)
    kb.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="verify_subscription"))
    
    sub_text = "📎 <b>Підписка на канали та чати</b>\n\n"
    
    if required_channels:
        sub_text += "📢 <b>Обов'язкові канали:</b>\n"
        for i, channel in enumerate(required_channels, 1):
            # Виводимо назву каналу (title або @username)
            try:
                normalized = channel if str(channel).startswith('@') else f"@{channel}"
                ch_info = bot.get_chat(normalized)
                ch_title = ch_info.title or (ch_info.username and f"@{ch_info.username}") or str(channel)
            except Exception:
                ch_title = str(channel)
            sub_text += f"{i}. <b>{ch_title}</b>\n"
        sub_text += "\n"
    
    if required_chats:
        sub_text += "💬 <b>Обов'язкові чати:</b>\n"
        for i, chat_id in enumerate(required_chats, 1):
            try:
                chat_info = bot.get_chat(chat_id)
                chat_title = chat_info.title or f"Чат {chat_id}"
                # Спеціальний випадок для відомого чату
                if str(chat_id) == "-1002218982939":
                    chat_title = "💬 Головний чат"
                sub_text += f"{i}. <b>{chat_title}</b>\n"
            except Exception as e:
                print(f"[ERROR] Не вдалося отримати назву чату {chat_id}: {e}")
                # Спеціальний випадок для відомого чату
                if str(chat_id) == "-1002218982939":
                    chat_title = "💬 Головний чат"
                else:
                    chat_title = f"Чат {chat_id}"
                sub_text += f"{i}. <b>{chat_title}</b>\n"
        sub_text += "\n"

    sub_text += "Натисніть кнопки вище для підписки/приєднання, потім '🔄 Перевірити підписку'"
    
    print(f"[DEBUG] Відправляю вимогу підписки для {user_id}")
    print(f"[DEBUG] Текст повідомлення: {sub_text}")
    print(f"[DEBUG] Кількість кнопок: {len(kb.keyboard) if kb.keyboard else 0}")
    
    try:
        if hasattr(message_or_call, 'chat'):
            # Це message
            print(f"[DEBUG] Відправляю message в чат {message_or_call.chat.id}")
            bot.send_message(message_or_call.chat.id, sub_text, reply_markup=kb, parse_mode="HTML")
            chat_id_for_reminder = message_or_call.chat.id
        else:
            # Це call
            print(f"[DEBUG] Редагую message в чат {message_or_call.message.chat.id}, message_id {message_or_call.message.message_id}")
            bot.edit_message_text(
                sub_text,
                message_or_call.message.chat.id,
                message_or_call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
            chat_id_for_reminder = message_or_call.message.chat.id
        # Плануємо нагадування через 10 хв, якщо досі не підписаний
        try:
            import threading
            def _schedule_sub_reminder(chat_id, user_id, delay_sec=600):
                if not hasattr(bot, 'sub_reminders'):
                    bot.sub_reminders = {}
                prev = bot.sub_reminders.get(user_id)
                try:
                    if prev:
                        prev.cancel()
                except Exception:
                    pass
                def _send():
                    try:
                        from database import get_required_channels, get_required_chats
                        req_ch = get_required_channels() or []
                        req_gr = get_required_chats() or []
                        from .subscription_service import check_user_subscriptions as chk
                    except Exception:
                        try:
                            from subscription_service import check_user_subscriptions as chk
                        except Exception:
                            chk = None
                    try:
                        still = False
                        if req_ch and chk:
                            rs = chk(bot, user_id, req_ch, logger=print)
                            for ch in req_ch:
                                r = rs.get(ch) or rs.get(str(ch))
                                if not r or r.get('status') != 'subscribed':
                                    still = True
                                    break
                        if req_gr and not still:
                            for gid in req_gr:
                                try:
                                    m = bot.get_chat_member(chat_id=gid, user_id=user_id)
                                    if m.status in ['left','kicked']:
                                        still = True
                                        break
                                except Exception:
                                    still = True
                                    break
                        if still:
                            bot.send_message(chat_id, "⏰ <b>Нагадування:</b> підпишіться та натисніть \"✅ Проверить подписку\".", parse_mode="HTML")
                    except Exception:
                        pass
                    finally:
                        try:
                            bot.sub_reminders.pop(user_id, None)
                        except Exception:
                            pass
                t = threading.Timer(delay_sec, _send)
                bot.sub_reminders[user_id] = t
                try:
                    t.daemon = True
                except Exception:
                    pass
                t.start()
            _schedule_sub_reminder(chat_id_for_reminder, user_id, 600)
        except Exception:
            pass
        print(f"[DEBUG] Повідомлення про підписку відправлено успішно для {user_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Помилка відправки повідомлення про підписку: {e}")
        print(f"[ERROR] Тип помилки: {type(e).__name__}")
        return False

def verify_subscription_handler(call, bot):
    """Обробник кнопки 'Перевірити підписку'"""
    from database import get_required_chats
    
    user_id = call.from_user.id
    print(f"[DEBUG] ===== VERIFY_SUBSCRIPTION_HANDLER START =====")
    print(f"[DEBUG] Користувач: {user_id}")
    print(f"[DEBUG] Call ID: {call.id}")
    print(f"[DEBUG] Message ID: {call.message.message_id}")
    
    # Перевіряємо підписку через сервіс
    print(f"[DEBUG] Отримуємо список каналів та чатів...")
    required_channels = get_required_channels()
    required_chats = get_required_chats()
    print(f"[DEBUG] Канали: {required_channels}, Чати: {required_chats}")
    # Авто-нормалізація: якщо в каналах є числові -100.. ID — переносимо їх у чати; у каналах лишаємо лише @username
    ch_usernames = []
    ch_ids_to_move = []
    for ch in required_channels or []:
        s = str(ch).strip()
        if s.lstrip('-').isdigit():
            try:
                ch_ids_to_move.append(int(s))
            except Exception:
                ch_ids_to_move.append(s)
        else:
            ch_usernames.append(ch if str(ch).startswith('@') else f"@{ch}")
    if ch_ids_to_move:
        required_chats = list((required_chats or [])) + ch_ids_to_move
    required_channels = ch_usernames
    # Очищаємо кеш результатів, щоб не тримати старий стан після підписки
    try:
        clear_cache_for_user(user_id, required_channels)
    except Exception:
        pass
    
    # Перевіряємо канали (лише username-канали)
    channel_results = check_user_subscriptions(bot, user_id, required_channels, logger=print) if required_channels else {}
    # Додатковий лог для прозорості
    try:
        for ch in required_channels:
            r = channel_results.get(str(ch)) or channel_results.get(ch)
            print(f"[DEBUG] channel_status {ch} -> {r}")
    except Exception:
        pass
    
    # Перевіряємо чати
    chat_results = {}
    if required_chats:
        for chat_id in required_chats:
            try:
                member = bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if member.status in ['left', 'kicked']:
                    chat_results[chat_id] = {'status': 'not_subscribed'}
                else:
                    chat_results[chat_id] = {'status': 'subscribed'}
            except Exception as e:
                print(f"[ERROR] Помилка перевірки чату {chat_id}: {e}")
                chat_results[chat_id] = {'status': 'unavailable'}

    # Формуємо текст зі статусами
    text = "📎 <b>Перевірка підписки на канали та чати</b>\n\n"
    all_ok = True
    kb = InlineKeyboardMarkup(row_width=1)
    
    # Перевіряємо канали
    if required_channels:
        text += "📢 <b>Канали:</b>\n"
        for ch in required_channels:
            # Гарна назва каналу (title або @username)
            try:
                normalized = ch if str(ch).startswith('@') else f"@{ch}"
                ch_info = bot.get_chat(normalized)
                ch_title = ch_info.title or (ch_info.username and f"@{ch_info.username}") or str(ch)
                ch_username = ch_info.username or str(ch).replace('@', '')
                # Оновлюємо кеш назв каналів
                from database import cache_chat_info
                cache_chat_info(ch_info.id, ch_title, ch_info.username)
            except Exception as _e:
                # Якщо не вдалося отримати інфо, використовуємо ID
                ch_title = str(ch)
                ch_username = str(ch).replace('@', '')

            r = channel_results.get(str(ch)) or channel_results.get(ch)
            if not r:
                status = 'unavailable'
            else:
                status = r.get('status')
            if status == 'subscribed':
                text += f"✅ <b>{ch_title}</b> — ✅ Підписано\n"
            elif status == 'not_subscribed':
                all_ok = False
                text += f"❌ <b>{ch_title}</b> — ❌ Не підписано\n"
                kb.add(InlineKeyboardButton(f"📢 Підписатися на {ch_title}", url=f"https://t.me/{ch_username}"))
            else:
                all_ok = False
                err = (r or {}).get('error')
                hint = " (перевірте, що бот адмін каналу)" if err and ("forbidden" in err.lower() or "chat not found" in err.lower()) else ""
                text += f"⚠️ <b>{ch_title}</b> — ⚠️ Тимчасово недоступно{hint}\n"
        text += "\n"
    
    # Перевіряємо чати
    if required_chats:
        text += "💬 <b>Чати:</b>\n"
        for chat_id in required_chats:
            r = chat_results.get(chat_id)
            if not r:
                status = 'unavailable'
            else:
                status = r.get('status')
            
            # Прагнемо отримати заголовок чату окремо від перевірки членства, щоб не показувати сирий ID
            try:
                chat_info = bot.get_chat(chat_id)
                chat_title = chat_info.title or (chat_info.username and f"@{chat_info.username}") or f"Чат {chat_id}"
                # Спеціальний випадок для відомого чату
                if str(chat_id) == "-1002218982939":
                    chat_title = "💬 Головний чат"
            except Exception as e:
                print(f"[ERROR] Не вдалося отримати назву чату {chat_id}: {e}")
                # Спеціальний випадок для відомого чату
                if str(chat_id) == "-1002218982939":
                    chat_title = "💬 Головний чат"
                else:
                    chat_title = f"Чат {chat_id}"
            
            if status == 'subscribed':
                text += f"✅ <b>{chat_title}</b> — ✅ Приєднано\n"
            elif status == 'not_subscribed':
                all_ok = False
                text += f"❌ <b>{chat_title}</b> — ❌ Не приєднано\n"
                # Спробуємо отримати invite link для приватних чатів
                invite_url = None
                try:
                    chat_info = bot.get_chat(chat_id)
                    # Якщо є username - використовуємо його
                    if chat_info.username:
                        invite_url = f"https://t.me/{chat_info.username}"
                    else:
                        # Спробуємо отримати invite link через API (якщо бот адмін)
                        try:
                            invite_link = bot.export_chat_invite_link(chat_id)
                            invite_url = invite_link.invite_link if hasattr(invite_link, 'invite_link') else str(invite_link)
                        except Exception as e:
                            print(f"[DEBUG] Не вдалося отримати invite link для чату {chat_id}: {e}")
                            # Fallback: формуємо посилання по ID (може не працювати для приватних чатів)
                            chat_id_clean = str(chat_id)[4:] if str(chat_id).startswith('-100') else str(chat_id)
                            invite_url = f"https://t.me/c/{chat_id_clean}"
                except Exception as e:
                    print(f"[ERROR] Помилка отримання інформації про чат {chat_id}: {e}")
                    # Fallback: формуємо посилання по ID
                    chat_id_clean = str(chat_id)[4:] if str(chat_id).startswith('-100') else str(chat_id)
                    invite_url = f"https://t.me/c/{chat_id_clean}"
                
                if invite_url:
                    kb.add(InlineKeyboardButton(f"💬 Приєднатися до {chat_title}", url=invite_url))
            else:
                all_ok = False
                text += f"⚠️ <b>{chat_title}</b> — ⚠️ Тимчасово недоступно (перевірте, що бот у чаті та має право бачити учасників)\n"

    # Додаємо кнопку перевірки
    # Кнопка перевірки підписки (RU текст за вимогою)
    kb.add(InlineKeyboardButton("✅ Проверить подписку", callback_data="verify_subscription"))

    # Оновлюємо повідомлення
    try:
        bot.answer_callback_query(call.id, "🔄 Перевіряю...")
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        msg = str(e).lower()
        # Ігноруємо стандартну помилку Telegram "message is not modified"
        if "message is not modified" in msg:
            try:
                # На випадок, якщо змінилась лише розмітка, пробуємо оновити тільки клавіатуру
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=kb)
            except Exception:
                pass
        else:
            print(f"[ERROR] Помилка оновлення повідомлення перевірки підписки: {e}")

    if all_ok:
        # Перевіряємо чи є інформація про реферала для відправки повідомлення ПЕРЕД очисткою стану
        print(f"[DEBUG] ===== ПЕРЕВІРКА РЕФЕРАЛЬНОЇ ІНФОРМАЦІЇ ПІСЛЯ ПІДПИСКИ =====")
        print(f"[DEBUG] Користувач: {user_id}")
        try:
            from database import get_user_state
            import json
            user_state = get_user_state(user_id)
            print(f"[DEBUG] Стан користувача після підписки: {user_state}")
            if user_state:
                try:
                    state_data = json.loads(user_state)
                    print(f"[DEBUG] Розпарсений стан: {state_data}")
                    print(f"[DEBUG] Є referrer_id: {'referrer_id' in state_data}")
                    print(f"[DEBUG] Є referrer_name: {'referrer_name' in state_data}")
                    print(f"[DEBUG] Є ref_bonus: {'ref_bonus' in state_data}")
                    if "referrer_id" in state_data and "referrer_name" in state_data and "ref_bonus" in state_data:
                        # Відправляємо реферальне повідомлення
                        referrer_id = state_data["referrer_id"]
                        referrer_name = state_data["referrer_name"]
                        ref_bonus = state_data["ref_bonus"]
                        
                        try:
                            from utils import format_currency
                        except:
                            def format_currency(amount):
                                return f"{amount:.2f}"
                        
                        success_text = (
                            "🎉 <b>РЕФЕРАЛЬНА РЕЄСТРАЦІЯ УСПІШНА!</b>\n\n"
                            f"👤 <b>Ваш реферер:</b> {referrer_name}\n"
                            f"💰 <b>Бонус рефереру:</b> {format_currency(ref_bonus)} ₴\n\n"
                            "🎁 <b>Що це означає:</b>\n"
                            "• Ви зареєструвалися за реферальним посиланням\n"
                            "• Ваш реферер отримав бонус за вашу реєстрацію\n"
                            "• Тепер ви можете запрошувати своїх друзів\n\n"
                            "🚀 <b>Готово!</b>\n"
                            "Вітаємо в Investing Palmaron Bot!"
                        )
                        
                        print(f"[DEBUG] ===== ВІДПРАВКА РЕФЕРАЛЬНОГО ПОВІДОМЛЕННЯ =====")
                        print(f"[DEBUG] Користувач: {user_id}")
                        print(f"[DEBUG] Реферер: {referrer_name} (ID: {referrer_id})")
                        print(f"[DEBUG] Бонус: {ref_bonus}")
                        print(f"[DEBUG] Текст повідомлення: {success_text[:100]}...")
                        try:
                            sent_msg = bot.send_message(call.message.chat.id, success_text, parse_mode="HTML")
                            print(f"[DEBUG] ✅ Реферальне повідомлення відправлено успішно! ID: {sent_msg.message_id}")
                        except Exception as e:
                            print(f"[ERROR] ❌ Помилка відправки реферального повідомлення: {e}")
                    else:
                        print(f"[DEBUG] Реферальна інформація неповна: {state_data}")
                except Exception as e:
                    print(f"[ERROR] Помилка обробки реферальної інформації: {e}")
            else:
                print(f"[DEBUG] Стан користувача порожній або не містить реферальної інформації")
        except Exception as e:
            print(f"[ERROR] Помилка перевірки реферальної інформації: {e}")
        
        was_blocked = False
        try:
            # Перевіримо, чи був користувач заблокований саме за вихід з каналів/чатів
            from database import is_user_blocked
            was_blocked = bool(is_user_blocked(user_id))
        except Exception:
            was_blocked = False
        try:
            mark_subscription_verified(user_id)
        except Exception:
            pass
        clear_user_state(user_id)
        
        # Розблоковуємо користувача якщо він був заблокований
        from database import is_user_blocked, unblock_user, get_user_block_info
        if is_user_blocked(user_id):
            # Отримуємо інформацію про чат для видалення повідомлення
            block_info = get_user_block_info(user_id)
            chat_title = block_info[5] if block_info and len(block_info) > 5 else "чат"
            
            unblock_user(user_id)
            print(f"[INFO] Користувач {user_id} автоматично розблокований після підтвердження підписки")
            
            # Видаляємо повідомлення про блокування
            try:
                from chat_monitoring_system import block_notification_messages
                if user_id in block_notification_messages:
                    try:
                        message_id = block_notification_messages[user_id]
                        bot.delete_message(user_id, message_id)
                        print(f"[INFO] Видалено повідомлення про блокування (ID: {message_id}) для користувача {user_id}")
                        del block_notification_messages[user_id]
                    except Exception as e:
                        print(f"[WARNING] Не вдалося видалити повідомлення про блокування: {e}")
            except Exception as e:
                print(f"[WARNING] Помилка при видаленні повідомлення про блокування: {e}")
            
            try:
                from bot import notify_admins_about_returning_user
                user_name = (call.from_user.first_name or "") + (f" {getattr(call.from_user, 'last_name')}" if getattr(call.from_user, 'last_name', None) else "")
                notify_admins_about_returning_user(user_id, user_name.strip() or f"User {user_id}")
            except Exception as e:
                print(f"[ERROR] Не вдалося повідомити адмінів про повернення користувача {user_id}: {e}")
        
        bot.answer_callback_query(call.id, "✅ Підписку підтверджено")
        bot.edit_message_text("✅ <b>Дякуємо! Підписку підтверджено. Продовжуємо 🚀</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML")
        # Скасувати таймер нагадування про підписку
        try:
            if hasattr(bot, 'sub_reminders'):
                t = bot.sub_reminders.pop(user_id, None)
                if t:
                    t.cancel()
        except Exception:
            pass

        # Після успішної перевірки підписки та підтвердженого телефону — інформуємо адмінів
        # Відправляємо тільки ОДНЕ сповіщення: або "новий користувач", або "повернувся"
        # Уведомлення про нового користувача відправляється ТІЛЬКИ після повної реєстрації:
        # 1. Підтвердження номера телефона
        # 2. Підписка на канали
        # Це запобігає дублюванню уведомлень
        if not was_blocked:
            # Тільки для нових користувачів (не були заблоковані)
            try:
                from database import get_user_phone
                phone = get_user_phone(user_id)
                if phone:
                    try:
                        from bot import notify_admins_about_new_user
                        # Ім'я користувача беремо з call.from_user
                        user_name = (call.from_user.first_name or "") + (f" {call.from_user.last_name}" if getattr(call.from_user, 'last_name', None) else "")
                        notify_admins_about_new_user(user_id, user_name.strip() or f"User {user_id}", phone)
                    except Exception as e:
                        print(f"[ERROR] notify_admins_after_subscription: {e}")
            except Exception as e:
                print(f"[ERROR] Помилка отримання телефону користувача: {e}")
                import traceback
                traceback.print_exc()

        from bot import show_main_menu
        show_main_menu(call)
        # Відправляємо вітальне повідомлення у ГРУПУ/ЧАТ з підписки (якщо вказано), інакше у DM
        try:
            # Фіксований ID чату для вітального повідомлення
            target_chat_id = -1002218982939  # ID вашого чату
            print(f"[DEBUG] Використовуємо фіксований чат для вітань: {target_chat_id}")

            # Додаткова перевірка доступу до чату
            try:
                chat = bot.get_chat(target_chat_id)
                print(f"[DEBUG] Чат для вітань: {chat.title} ({chat.id})")
            except Exception as e:
                print(f"[ERROR] Не вдалося отримати дані чату {target_chat_id}: {e}")
                # Якщо не вдалося отримати чат, використовуємо особистий чат
                target_chat_id = call.message.chat.id
                print(f"[WARN] Використовуємо особистий чат: {target_chat_id}")

            # Дані користувача для згадки
            username = getattr(call.from_user, 'username', None)
            first_name = getattr(call.from_user, 'first_name', None)
            
            # Надсилання вітання - тільки для нових користувачів
            if not was_blocked:
                # Тільки для нових користувачів (не були заблоковані)
                try:
                    print(f"[INFO] Sending welcome to target_chat_id={target_chat_id} for new user {user_id}")
                    _send_welcome_after_verification(bot, int(target_chat_id), user_id, first_name, username)
                except Exception as e:
                    print(f"[ERROR] welcome to group failed: {e}; fallback to DM")
                    _send_welcome_after_verification(bot, call.message.chat.id, user_id, first_name, username)
            else:
                # Тільки для повернувшихся користувачів
                try:
                    comeback_text = (
                        "🔄 <b>Повернення в спільноту!</b>\n\n"
                        f"👋 Повернувся до нас: <a href='https://t.me/{username}'><b>{first_name or 'Користувач'}</b></a>\n"
                        "Ми раді бачити тебе знову! ✨"
                    )
                    bot.send_message(int(target_chat_id), comeback_text, parse_mode="HTML", disable_web_page_preview=True)
                except Exception:
                    pass
        except Exception as e:
            print(f"[ERROR] send welcome after verification: {e}")
    else:
        bot.answer_callback_query(call.id, "❌ Потрібно підписатися на всі канали та чати")
    
    print(f"[DEBUG] ===== VERIFY_SUBSCRIPTION_HANDLER END =====")

def check_subscription_before_action(message_or_call, bot):
    """
    Перевіряє підписку користувача перед виконанням дії.
    АГРЕСИВНА ПЕРЕВІРКА: автоматично блокує користувачів при відсутності підписки.
    
    Args:
        message_or_call: Повідомлення або callback, що викликало перевірку
        bot: Екземпляр бота
        
    Returns:
        bool: True, якщо користувач підписаний на всі необхідні канали/чати
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Отримуємо ID користувача
        if hasattr(message_or_call, 'from_user'):
            user_id = message_or_call.from_user.id
        elif hasattr(message_or_call, 'message') and hasattr(message_or_call.message, 'from_user'):
            user_id = message_or_call.message.from_user.id
        else:
            logger.error("Не вдалося визначити user_id")
            return False
            
        logger.debug(f"АГРЕСИВНА перевірка підписки для користувача {user_id}")
        
        # Виконуємо перевірку підписки (з автоматичним блокуванням)
        is_subscribed = check_user_subscription(user_id, bot, check_only=False)
        
        if not is_subscribed:
            logger.warning(f"Користувач {user_id} НЕ ПІДПИСАНИЙ - показуємо окно підписки")
            # Відправляємо повідомлення про необхідність підписки
            send_subscription_required_message(message_or_call, user_id, bot)
            
        return is_subscribed
        
    except Exception as e:
        logger.error(f"Помилка у check_subscription_before_action: {e}", exc_info=True)
        return False
    """Перевіряє підписку перед дією. 
    Повертає True якщо користувач підписаний на всі необхідні канали/чати,
    False в іншому випадку.
    """
    from database import get_user_block_info, is_admin
    
    # Визначаємо user_id та chat_id
    if hasattr(message_or_call, 'from_user'):
        user_id = message_or_call.from_user.id
        chat_id = message_or_call.chat.id if hasattr(message_or_call, 'chat') else None
        message = message_or_call
    else:
        user_id = message_or_call.message.from_user.id
        chat_id = message_or_call.message.chat.id if hasattr(message_or_call.message, 'chat') else None
        message = message_or_call.message
    
    print(f"[SUBSCRIPTION] Перевірка підписки для {user_id}")
    
    # Адміни завжди проходять перевірку
    if is_admin(user_id):
        return True
    
    # Перевіряємо чи користувач не заблокований
    block_info = get_user_block_info(user_id)
    if block_info and block_info.get('is_blocked'):
        reason = block_info.get('reason', 'невідома причина')
        try:
            bot.send_message(chat_id, f"❌ Ви заблоковані в боті. Причина: {reason}")
        except Exception as e:
            print(f"[ERROR] Не вдалося надіслати повідомлення про блокування: {e}")
        return False
    
    # Перевіряємо підписку на всі необхідні канали/чати
    is_subscribed = check_user_subscription(user_id, bot)
    
    if not is_subscribed:
        print(f"[SUBSCRIPTION] Користувач {user_id} не підписаний на всі необхідні канали/чати")
        # Відправляємо повідомлення про необхідність підписки
        send_subscription_required_message(message_or_call, user_id, bot)
        
        # Приховуємо клавіатуру для повідомлень
        if hasattr(message, 'message_id') and hasattr(message, 'chat'):
            try:
                bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=None
                )
            except Exception as e:
                print(f"[WARNING] Не вдалося приховати клавіатуру: {e}")
        
        return False
    
    print(f"[SUBSCRIPTION] Користувач {user_id} підписаний на всі необхідні канали/чати")
    return True

def subscription_guard(func):
    """Декоратор для захисту функцій від неавторизованих користувачів.
    АГРЕСИВНО блокує будь-які дії, якщо користувач не підписаний на всі необхідні канали/чати.
    Автоматично блокує користувачів при відсутності підписки.
    
    Використання:
    @bot.message_handler(commands=['command'])
    @subscription_guard
    def command_handler(message, bot):
        # Обробка команди
        pass
    
    АБО для callback-ів:
    @bot.callback_query_handler(func=lambda call: call.data == 'some_callback')
    @subscription_guard
    def callback_handler(call, bot):
        # Обробка callback
        pass
    """
    def wrapper(message_or_call, *args, **kwargs):
        # Отримуємо bot з аргументів або з повідомлення
        bot = None
        if len(args) > 0 and hasattr(args[0], 'answer_callback_query'):
            bot = args[0]
        elif 'bot' in kwargs:
            bot = kwargs['bot']
        
        if not bot:
            print("[ERROR] subscription_guard: Не вдалося отримати об'єкт бота")
            return
            
        # Отримуємо user_id для логування
        user_id = None
        chat_id = None
        
        if hasattr(message_or_call, 'from_user'):
            user_id = message_or_call.from_user.id
            if hasattr(message_or_call, 'chat'):
                chat_id = message_or_call.chat.id
        elif hasattr(message_or_call, 'message') and hasattr(message_or_call.message, 'from_user'):
            user_id = message_or_call.message.from_user.id
            if hasattr(message_or_call.message, 'chat'):
                chat_id = message_or_call.message.chat.id
        
        if not user_id:
            print("[ERROR] subscription_guard: Не вдалося визначити user_id")
            return
            
        print(f"[SUBSCRIPTION] Перевірка доступу для {user_id}")
            
        # Перевіряємо підписку
        if not check_subscription_before_action(message_or_call, bot):
            print(f"[SUBSCRIPTION] Заблоковано доступ до функціоналу для {user_id}")
            
            # Для callback-ів відповідаємо, що дія не доступна
            if hasattr(message_or_call, 'data') and hasattr(message_or_call, 'id'):
                try:
                    bot.answer_callback_query(
                        callback_query_id=message_or_call.id,
                        text="❌ Потрібно бути підписаним на всі канали/чати",
                        show_alert=True
                    )
                except Exception as e:
                    print(f"[ERROR] Помилка при відповіді на callback: {e}")
            
            return  # Блокуємо виконання функції
            
        # Якщо все гаразд - виконуємо оригінальну функцію
        return func(message_or_call, *args, **kwargs)
    
    # Зберігаємо посилання на оригінальну функцію для тестування
    wrapper._original = func
    return wrapper

def check_and_handle_subscription_for_user(user_id, bot, message_or_call=None):
    """Перевіряє підписку користувача та обробляє результат"""
    from database import get_required_channels, get_required_chats, is_user_blocked, get_user_block_info
    import time
    
    print(f"[DEBUG] check_and_handle_subscription_for_user для {user_id}")
    
    # Перевіряємо чи заблокований користувач
    if is_user_blocked(user_id):
        block_info = get_user_block_info(user_id)
        if block_info:
            block_type = "канал" if block_info[2] == 'channel_leave' else "чат"
            block_text = (
                f"🚫 <b>ДОСТУП ЗАБЛОКОВАНО!</b>\n\n"
                f"❌ <b>Причина:</b> Вихід з обов'язкового {block_type}\n"
                f"📅 <b>Дата блокування:</b> {time.strftime('%d.%m.%Y %H:%M', time.localtime(int(block_info[6])))}\n\n"
                f"💡 <b>Що робити:</b>\n"
                f"• Поверніться в {block_type}: {block_info[5]}\n"
                f"• Зверніться до адміністратора\n"
                f"• Очікуйте розблокування"
            )
            if message_or_call:
                try:
                    if hasattr(message_or_call, 'chat'):
                        # Це message
                        bot.send_message(message_or_call.chat.id, block_text, parse_mode="HTML")
                    else:
                        # Це call
                        bot.send_message(message_or_call.message.chat.id, block_text, parse_mode="HTML")
                except Exception as e:
                    print(f"[ERROR] Помилка відправки повідомлення про блокування: {e}")
            return False
    
    # Перевіряємо підписку
    required_channels = get_required_channels()
    required_chats = get_required_chats()
    
    if not required_channels and not required_chats:
        print(f"[DEBUG] Каналів і чатів немає, підписка вважається підтвердженою для {user_id}")
        return True
    
    # Перевіряємо підписку на канали та чати
    is_subscribed = check_user_subscription(user_id, bot)
    
    if is_subscribed:
        print(f"[DEBUG] Користувач {user_id} підписаний на всі канали та чати")
        # Відправляємо повідомлення про успішну перевірку
        success_text = (
            "✅ <b>ПІДПИСКА ПІДТВЕРДЖЕНА!</b>\n\n"
            "🎉 <b>Вітаємо!</b> Ви підписані на всі обов'язкові канали та чати.\n"
            "🚀 <b>Тепер ви можете повноцінно користуватися ботом!</b>\n\n"
            "💎 <b>Доступні функції:</b>\n"
            "• Сад та вирощування фруктів\n"
            "• Депозити та виплати\n"
            "• Реферальна програма\n"
            "• Ігрові події\n"
            "• Багато іншого!\n\n"
            "🎯 <b>Гарного користування!</b>"
        )
        
        if message_or_call:
            try:
                if hasattr(message_or_call, 'chat'):
                    # Це message
                    bot.send_message(message_or_call.chat.id, success_text, parse_mode="HTML")
                else:
                    # Це call
                    bot.send_message(message_or_call.message.chat.id, success_text, parse_mode="HTML")
            except Exception as e:
                print(f"[ERROR] Помилка відправки повідомлення про успіх: {e}")
        
        return True
    else:
        print(f"[DEBUG] Користувач {user_id} не підписаний на всі канали та чати")
        # Відправляємо повідомлення про необхідність підписки
        if message_or_call:
            send_subscription_required_message(message_or_call, user_id, bot)
        return False

def update_referral_message_with_subscription_check(bot, message, user_id, success_text):
    """Оновлює реферальне повідомлення з перевіркою підписки"""
    try:
        sent_msg = bot.send_message(message.chat.id, success_text, parse_mode="HTML")
        # Показуємо блок перевірки підписки під повідомленням про успіх
        try:
            check_and_handle_subscription_for_user(user_id, bot, sent_msg)
        except Exception as e:
            print(f"[ERROR] Не вдалося показати блок підписки після реф. повідомлення: {e}")
        return sent_msg
    except Exception as e:
        print(f"[ERROR] Помилка відправки реферального повідомлення: {e}")
        return None

def send_referral_message_with_subscription_check(bot, chat_id, user_id, success_text):
    """Відправляє реферальне повідомлення з перевіркою підписки"""
    try:
        sent_msg = bot.send_message(chat_id, success_text, parse_mode="HTML")
        # Показуємо блок перевірки підписки під повідомленням про успіх
        try:
            check_and_handle_subscription_for_user(user_id, bot, sent_msg)
        except Exception as e:
            print(f"[ERROR] Не вдалося показати блок підписки після реф. повідомлення: {e}")
        return sent_msg
    except Exception as e:
        print(f"[ERROR] Помилка відправки реферального повідомлення: {e}")
        return None 