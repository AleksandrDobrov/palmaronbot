"""
P2P (Peer-to-Peer) transfer handlers module.
Contains all handlers for P2P transfers functionality.
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def transfer_command_handler(bot, message):
    """Команда для початку переводу - УПРОЩЕННАЯ ВЕРСИЯ"""
    print(f"[P2P] transfer_command_handler called: user={message.from_user.id}")
    try:
        user_id = message.from_user.id
        from database import get_user_balances
        balances = get_user_balances(user_id)
        print(f"[P2P] transfer_command_handler: balances={balances}")
        
        text = (
            f"💸 <b>P2P-ПЕРЕКАЗИ</b>\n\n"
            f"📊 <b>Ваші баланси:</b>\n"
            f"   💰 Основний: <b>{balances['main_balance']:.2f}₴</b>\n"
            f"   📤 Доступно для переказів: <b>{balances['transferable_balance']:.2f}₴</b>\n"
            f"   🔒 Заблоковано: <b>{balances['locked_balance']:.2f}₴</b>\n\n"
        )
        
        kb = InlineKeyboardMarkup(row_width=1)
        
        if balances['main_balance'] > 0:
            kb.add(InlineKeyboardButton(" рейтістити в перекази", callback_data="p2p_move_to_transferable"))
        
        kb.add(InlineKeyboardButton("📤 Створити переказ", callback_data="p2p_create_transfer"))
        kb.add(InlineKeyboardButton("📋 Історія переказів", callback_data="p2p_history"))
        kb.add(InlineKeyboardButton("⏳ Очікують підтвердження", callback_data="p2p_pending"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_home"))
        
        print(f"[P2P] transfer_command_handler: sending message")
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="HTML")
        print(f"[P2P] transfer_command_handler: message sent successfully")
        
    except Exception as e:
        print(f"[P2P] transfer_command_handler: EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        try:
            bot.reply_to(message, f"❌ Помилка: {str(e)}")
        except:
            pass


def p2p_menu_handler(bot, call):
    """Меню P2P-переводів - улучшенная версия"""
    try:
        # Отвечаем на callback сразу
        bot.answer_callback_query(call.id)
        
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        # Получаем балансы
        from database import get_user_balances, get_p2p_settings
        balances = get_user_balances(user_id)
        settings = get_p2p_settings()
        
        # Формируем красивое сообщение
        text = (
            f"💸 <b>P2P-ПЕРЕКАЗИ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>ВАШІ БАЛАНСИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Основний баланс:</b> <code>{balances['main_balance']:.2f}₴</code>\n"
            f"📤 <b>Доступно для переказів:</b> <code>{balances['transferable_balance']:.2f}₴</code>\n"
            f"🔒 <b>Заблоковано:</b> <code>{balances['locked_balance']:.2f}₴</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>НАЛАШТУВАННЯ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 Мінімальна сума: <b>{settings['min_amount']:.2f}₴</b>\n"
            f"📌 Максимальна сума: <b>{settings['max_amount']:.2f}₴</b>\n"
            f"📌 Комісія: <b>{settings['fee_percent']}%</b>\n"
        )
        
        # Создаем клавиатуру
        kb = InlineKeyboardMarkup(row_width=1)
        
        if balances['main_balance'] > 0:
            kb.add(InlineKeyboardButton(" рейтістити в перекази", callback_data="p2p_move_to_transferable"))
            kb.add(InlineKeyboardButton("🚀 Швидкий переказ (/move)", callback_data="simple_move_info"))
        
        kb.add(InlineKeyboardButton("📤 Створити переказ", callback_data="p2p_create_transfer"))
        kb.add(InlineKeyboardButton("📋 Історія переказів", callback_data="p2p_history"))
        kb.add(InlineKeyboardButton("⏳ Очікують підтвердження", callback_data="p2p_pending"))
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_home"))
        
        # Пытаемся отредактировать сообщение, если не получается - отправляем новое
        try:
            bot.edit_message_text(
                text, 
                chat_id, 
                call.message.message_id, 
                reply_markup=kb, 
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
            bot.send_message(call.from_user.id, f"❌ Помилка відкриття меню P2P: {str(e)}", parse_mode="HTML")
        except:
            pass


def admin_p2p_transfers_handler(bot, call):
    """Адмін-панель переказів - МАКСИМАЛЬНО УПРОЩЕННАЯ ВЕРСИЯ"""
    print(f"[P2P] ===== admin_p2p_transfers_handler START ===== user={call.from_user.id}")
    
    # ШАГ 1: Отвечаем на callback
    try:
        print(f"[P2P] Step 1: answering callback_query")
        bot.answer_callback_query(call.id)
        print(f"[P2P] Step 1: callback_query answered")
    except Exception as e1:
        print(f"[P2P] Step 1 ERROR: {e1}")
    
    # ШАГ 2: Получаем chat_id
    try:
        chat_id = call.message.chat.id
        print(f"[P2P] Step 2: chat_id={chat_id}")
    except Exception as e2:
        print(f"[P2P] Step 2 ERROR: {e2}")
        try:
            bot.send_message(call.from_user.id, "❌ Помилка: не вдалося отримати chat_id")
        except:
            pass
        return
    
    # ШАГ 3: Проверяем админа
    try:
        print(f"[P2P] Step 3: checking admin")
        from database import is_admin
        if not is_admin(call.from_user.id):
            print(f"[P2P] Step 3: not admin, sending access denied")
            bot.send_message(chat_id, "⛔️ Немає доступу", parse_mode="HTML")
            return
        print(f"[P2P] Step 3: admin confirmed")
    except Exception as e3:
        print(f"[P2P] Step 3 ERROR: {e3}")
        bot.send_message(chat_id, f"❌ Помилка перевірки прав: {str(e3)}", parse_mode="HTML")
        return
    
    # ШАГ 4: Получаем транзакции
    try:
        print(f"[P2P] Step 4: getting pending transactions")
        from database import get_pending_p2p_transactions, get_user
        pending = get_pending_p2p_transactions(limit=20)
        print(f"[P2P] Step 4: got {len(pending) if pending else 0} transactions")
    except Exception as e4:
        print(f"[P2P] Step 4 ERROR: {e4}")
        import traceback
        traceback.print_exc()
        bot.send_message(chat_id, f"❌ Помилка отримання транзакцій: {str(e4)}", parse_mode="HTML")
        return
    
    # ШАГ 5: Если нет транзакций
    if not pending:
        print(f"[P2P] Step 5: no pending transactions, sending message")
        try:
            bot.send_message(chat_id, "✅ Немає очікуючих переказів", parse_mode="HTML")
            print(f"[P2P] Step 5: message sent")
        except Exception as e5:
            print(f"[P2P] Step 5 ERROR: {e5}")
        return
    
    # ШАГ 6: Формируем сообщение
    try:
        print(f"[P2P] Step 6: building message")
        text = "📋 <b>ЗАПИТИ НА ПЕРЕКАЗИ</b>\n\n"
        kb = InlineKeyboardMarkup(row_width=2)
        
        for t in pending[:10]:
            try:
                from_user = get_user(t['from_user_id'])
                to_user = get_user(t['to_user_id'])
                from_name = from_user[1] if from_user else f"ID {t['from_user_id']}"
                to_name = to_user[1] if to_user else f"ID {t['to_user_id']}"
                
                text += (
                    f"📊 <b>#{t['id']}</b>\n"
                    f"   👤 Від: <b>{from_name}</b> → <b>{to_name}</b>\n"
                    f"   💰 Сума: <b>{t['amount']:.2f}₴</b> (комісія: {t['fee']:.2f}₴)\n\n"
                )
                
                kb.add(
                    InlineKeyboardButton(f"✅ #{t['id']}", callback_data=f"p2p_approve:{t['id']}"),
                    InlineKeyboardButton(f"❌ #{t['id']}", callback_data=f"p2p_reject:{t['id']}")
                )
            except Exception as e6:
                print(f"[P2P] Step 6: error processing transaction {t.get('id', 'unknown')}: {e6}")
                continue
        
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="panel"))
        print(f"[P2P] Step 6: message built, text length={len(text)}")
    except Exception as e6:
        print(f"[P2P] Step 6 ERROR: {e6}")
        import traceback
        traceback.print_exc()
        bot.send_message(chat_id, f"❌ Помилка формування повідомлення: {str(e6)}", parse_mode="HTML")
        return
    
    # ШАГ 7: Отправляем сообщение
    try:
        print(f"[P2P] Step 7: SENDING MESSAGE to chat_id={chat_id}")
        result = bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
        print(f"[P2P] Step 7: MESSAGE SENT SUCCESSFULLY! result={result}")
    except Exception as e7:
        print(f"[P2P] Step 7 ERROR: {e7}")
        import traceback
        traceback.print_exc()
        try:
            # Пробуем отправить без клавиатуры
            bot.send_message(chat_id, text, parse_mode="HTML")
            print(f"[P2P] Step 7: sent without keyboard")
        except Exception as e7b:
            print(f"[P2P] Step 7: even without keyboard failed: {e7b}")
            try:
                bot.send_message(chat_id, "❌ Помилка відправки повідомлення", parse_mode="HTML")
            except:
                pass
    
    print(f"[P2P] ===== admin_p2p_transfers_handler END ===== user={call.from_user.id}")


def p2p_create_transfer_handler(bot, call):
    """Початок створення переводу - улучшенная версия"""
    try:
        bot.answer_callback_query(call.id)
        
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        from database import get_user_balances, get_p2p_settings, set_user_state
        balances = get_user_balances(user_id)
        settings = get_p2p_settings()
        
        # Проверяем достаточность средств
        if balances['transferable_balance'] < settings['min_amount']:
            text = (
                f"❌ <b>НЕДОСТАТНЬО КОШТІВ</b>\n\n"
                f"📊 Ваш баланс для переказів: <code>{balances['transferable_balance']:.2f}₴</code>\n"
                f"📌 Мінімальна сума: <code>{settings['min_amount']:.2f}₴</code>\n\n"
                f"💡 <i>Перемістіть кошти з основного балансу в перекази</i>"
            )
            try:
                bot.edit_message_text(
                    text,
                    chat_id,
                    call.message.message_id,
                    parse_mode="HTML"
                )
            except:
                bot.send_message(chat_id, text, parse_mode="HTML")
            bot.answer_callback_query(
                call.id,
                f"❌ Мінімум: {settings['min_amount']:.2f}₴",
                show_alert=True
            )
            return
        
        # Устанавливаем состояние и запрашиваем получателя
        set_user_state(user_id, "p2p_waiting_recipient")
        
        text = (
            f"👤 <b>ВИБІР ОТРИМУВАЧА</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Введіть <b>user_id</b> або <b>@username</b> отримувача:\n\n"
            f"💡 <i>ID можна отримати, переславши повідомлення користувача боту @userinfobot</i>\n\n"
            f"📊 <b>Доступно для переказу:</b> <code>{balances['transferable_balance']:.2f}₴</code>"
        )
        
        try:
            bot.edit_message_text(
                text,
                chat_id,
                call.message.message_id,
                parse_mode="HTML"
            )
        except:
            bot.send_message(chat_id, text, parse_mode="HTML")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
        except:
            pass


def p2p_recipient_input_handler(bot, message):
    """Обробка введення отримувача"""
    from database import get_user_state, set_user_state, get_user, get_user_id_by_username, get_user_balances, get_p2p_settings, calculate_p2p_fee
    
    # Перевірка стану
    state = get_user_state(message.from_user.id)
    if state != "p2p_waiting_recipient":
        return
    
    try:
        user_input = message.text.strip()
        if not user_input:
            bot.reply_to(message, "❌ Помилка: Введіть ID або @username користувача!")
            return
        
        target_user_id = None
        
        # Перевірка чи це @username
        if user_input.startswith("@"):
            username = user_input.replace("@", "").strip()
            if not username:
                bot.reply_to(message, "❌ Помилка: Введіть коректний @username")
                return
            try:
                target_user_id = get_user_id_by_username(user_input)
                if not target_user_id:
                    bot.reply_to(message, f"❌ Користувача {user_input} не знайдено в базі даних")
                    set_user_state(message.from_user.id, None)
                    return
            except Exception as e:
                bot.reply_to(message, f"❌ Помилка при пошуку користувача: {e}")
                set_user_state(message.from_user.id, None)
                return
        else:
            try:
                target_user_id = int(user_input)
            except ValueError:
                bot.reply_to(message, "❌ Помилка: ID має бути числом або @username!")
                return
        
        # Перевірка чи користувач існує
        to_user = get_user(target_user_id)
        if not to_user:
            bot.reply_to(message, f"❌ Користувача з ID {target_user_id} не знайдено")
            set_user_state(message.from_user.id, None)
            return
        
        # Перевірка чи не переказ самому собі
        if target_user_id == message.from_user.id:
            bot.reply_to(message, "❌ Не можна переводити собі!")
            set_user_state(message.from_user.id, None)
            return
        
        # Перевіряємо, чи є достатній баланс для мінімального переказу
        settings = get_p2p_settings()
        balances = get_user_balances(message.from_user.id)
        min_total_needed = settings['min_amount'] + calculate_p2p_fee(settings['min_amount'])
        
        if balances['transferable_balance'] < min_total_needed:
            bot.reply_to(message, f"❌ Недостатньо коштів для переказу. Мінімум потрібно {min_total_needed:.2f}₴ для комісії та суми переказу")
            set_user_state(message.from_user.id, None)
            return
        
        to_user_name = to_user[1] if to_user else f"Користувач {target_user_id}"
        
        # Зберігаємо ID отримувача в стані
        set_user_state(message.from_user.id, f"p2p_waiting_amount:{target_user_id}")
        
        settings = get_p2p_settings()
        balances = get_user_balances(message.from_user.id)
        
        text = (
            f"💰 <b>ВВЕДЕННЯ СУМИ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>ОТРИМУВАЧ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📝 Ім'я: <code>{to_user_name}</code>\n"
            f"🆔 ID: <code>{target_user_id}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>ВАШ БАЛАНС</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💵 Доступно для переказу: <code>{balances['transferable_balance']:.2f}₴</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ <b>ОБМЕЖЕННЯ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 Мінімум: <code>{settings['min_amount']:.2f}₴</code>\n"
            f"📌 Максимум: <code>{settings['max_amount']:.2f}₴</code>\n"
            f"💳 Комісія: <code>{settings['fee_percent']}%</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 <b>Введіть суму переказу:</b>"
        )
        bot.send_message(message.chat.id, text, parse_mode="HTML")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        bot.reply_to(message, f"❌ Помилка: {str(e)}")
        set_user_state(message.from_user.id, None)


def p2p_amount_input_handler(bot, message):
    """Обробка введення суми"""
    from database import get_user_state, set_user_state, get_user, create_p2p_transaction, get_p2p_settings, calculate_p2p_fee, create_notification
    
    try:
        state = get_user_state(message.from_user.id)
        to_user_id = int(state.split(":")[1])
        
        try:
            amount = float(message.text.replace(",", "."))
        except ValueError:
            bot.reply_to(message, "❌ Помилка: Введіть коректне число!")
            return
        
        # Додаткова валідація суми
        if amount <= 0:
            bot.reply_to(message, "❌ Помилка: Сума має бути більше 0!")
            return
        
        # Перевірка лімітів
        settings = get_p2p_settings()
        if amount < settings['min_amount']:
            bot.reply_to(message, f"❌ Помилка: Мінімальна сума переказу {settings['min_amount']:.2f}₴")
            return
        
        if amount > settings['max_amount']:
            bot.reply_to(message, f"❌ Помилка: Максимальна сума переказу {settings['max_amount']:.2f}₴")
            return
        
        # Перевірка балансу користувача
        from database import get_user_balances
        balances = get_user_balances(message.from_user.id)
        fee = calculate_p2p_fee(amount)
        total_needed = amount + fee
        
        if balances['transferable_balance'] < total_needed:
            bot.reply_to(message, f"❌ Помилка: Недостатньо коштів для переказу. Потрібно {total_needed:.2f}₴, доступно {balances['transferable_balance']:.2f}₴")
            set_user_state(message.from_user.id, None)
            return
        
        # Створюємо транзакцію
        try:
            transaction_id = create_p2p_transaction(message.from_user.id, to_user_id, amount)
            
            to_user = get_user(to_user_id)
            to_user_name = to_user[1] if to_user else f"Користувач {to_user_id}"
            
            # Відправляємо повідомлення відправнику
            success_text = (
                f"✅ <b>ПЕРЕКАЗ СТВОРЕНО!</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📋 <b>ДЕТАЛІ ПЕРЕКАЗУ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 <b>Отримувач:</b> <code>{to_user_name}</code>\n"
                f"💰 <b>Сума:</b> <code>{amount:.2f}₴</code>\n"
                f"💳 <b>Комісія:</b> <code>{fee:.2f}₴</code>\n"
                f"📊 <b>ID транзакції:</b> <code>#{transaction_id}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⏳ <b>Статус:</b> Очікує підтвердження адміністратора"
            )
            bot.reply_to(message, success_text, parse_mode="HTML")
            
            # Сповіщення отримувачу
            try:
                create_notification(
                    to_user_id,
                    'p2p_incoming',
                    '💸 Вхідний переказ',
                    f"Користувач переказав вам {amount:.2f}₴. Очікує підтвердження."
                )
                notification_text = (
                    f"💸 <b>ВХІДНИЙ ПЕРЕКАЗ</b>\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💰 Сума: <code>{amount:.2f}₴</code>\n"
                    f"📊 ID транзакції: <code>#{transaction_id}</code>\n\n"
                    f"⏳ Переказ очікує підтвердження адміністратора."
                )
                bot.send_message(to_user_id, notification_text, parse_mode="HTML")
            except Exception:
                pass
            
            # Сповіщення адмінам
            from database import get_admins
            admins = get_admins()
            for admin_id in admins:
                try:
                    create_notification(
                        admin_id,
                        'p2p_pending',
                        '📋 Новий переказ',
                        f"Новий P2P переказ #{transaction_id}: {amount:.2f}₴"
                    )
                except Exception:
                    pass
            
        except ValueError as e:
            bot.reply_to(message, f"❌ {str(e)}")
            return
        
        set_user_state(message.from_user.id, None)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        bot.reply_to(message, f"❌ Помилка: {str(e)}")
        set_user_state(message.from_user.id, None)


def p2p_history_handler(bot, call):
    """Історія переказів користувача - улучшенная версия"""
    try:
        bot.answer_callback_query(call.id)
        
        from database import get_user_p2p_transactions, get_user
        transactions = get_user_p2p_transactions(call.from_user.id, limit=20)
        
        if not transactions:
            text = (
                f"📋 <b>ІСТОРІЯ ПЕРЕКАЗІВ</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📝 <i>Історія переказів порожня</i>\n\n"
                f"💡 <i>Створіть свій перший переказ!</i>"
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="p2p_menu"))
            try:
                bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except:
                bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
            return
        
        text = (
            f"📋 <b>ІСТОРІЯ ПЕРЕКАЗІВ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        status_emoji = {
            'pending': '⏳ Очікує',
            'completed': '✅ Завершено',
            'rejected': '❌ Відхилено'
        }
        
        for i, t in enumerate(transactions[:10], 1):
            from_user = get_user(t['from_user_id'])
            to_user = get_user(t['to_user_id'])
            from_name = from_user[1] if from_user else f"ID {t['from_user_id']}"
            to_name = to_user[1] if to_user else f"ID {t['to_user_id']}"
            
            direction = "➡️ Відправлено" if t['is_sent'] else "⬅️ Отримано"
            status_text = status_emoji.get(t['status'], f"❓ {t['status']}")
            
            text += (
                f"<b>#{i}</b> {direction}\n"
                f"💰 Сума: <code>{t['amount']:.2f}₴</code>\n"
                f"📊 Статус: {status_text}\n"
                f"👤 {'Отримувач' if t['is_sent'] else 'Відправник'}: <code>{to_name if t['is_sent'] else from_name}</code>\n"
                f"💳 Комісія: <code>{t['fee']:.2f}₴</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
            )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="p2p_menu"))
        
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
        except:
            pass


def p2p_pending_handler(bot, call):
    """Список очікуючих переказів користувача - улучшенная версия"""
    try:
        bot.answer_callback_query(call.id)
        
        from database import get_user_p2p_transactions, get_user
        all_transactions = get_user_p2p_transactions(call.from_user.id, limit=100)
        pending = [t for t in all_transactions if t['status'] == 'pending']
        
        if not pending:
            text = (
                f"⏳ <b>ОЧІКУЮЧІ ПЕРЕКАЗИ</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"✅ <i>Немає очікуючих переказів</i>\n\n"
                f"💡 <i>Всі ваші перекази оброблені!</i>"
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="p2p_menu"))
            try:
                bot.edit_message_text(
                    text,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except:
                bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
            return
        
        text = (
            f"⏳ <b>ОЧІКУЮЧІ ПЕРЕКАЗИ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        for i, t in enumerate(pending[:10], 1):
            from_user = get_user(t['from_user_id'])
            to_user = get_user(t['to_user_id'])
            from_name = from_user[1] if from_user else f"ID {t['from_user_id']}"
            to_name = to_user[1] if to_user else f"ID {t['to_user_id']}"
            
            direction = "➡️ Відправлено" if t['is_sent'] else "⬅️ Отримано"
            
            text += (
                f"<b>#{i}</b> {direction}\n"
                f"💰 Сума: <code>{t['amount']:.2f}₴</code>\n"
                f"👤 {'Отримувач' if t['is_sent'] else 'Відправник'}: <code>{to_name if t['is_sent'] else from_name}</code>\n"
                f"📊 ID транзакції: <code>#{t['id']}</code>\n"
                f"💳 Комісія: <code>{t['fee']:.2f}₴</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
            )
        
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="p2p_menu"))
        
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
        except:
            pass


def p2p_move_to_transferable_handler(bot, call):
    """Переміщення коштів в transferable_balance - улучшенная версия"""
    try:
        bot.answer_callback_query(call.id)
        
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        
        from database import get_user_balances, set_user_state
        balances = get_user_balances(user_id)
        
        if balances['main_balance'] <= 0:
            text = (
                f"❌ <b>НЕДОСТАТНЬО КОШТІВ</b>\n\n"
                f"💰 Ваш основний баланс: <code>0.00₴</code>\n\n"
                f"💡 <i>Поповніть баланс для використання P2P-переказів</i>"
            )
            try:
                bot.edit_message_text(
                    text,
                    chat_id,
                    call.message.message_id,
                    parse_mode="HTML"
                )
            except:
                bot.send_message(chat_id, text, parse_mode="HTML")
            bot.answer_callback_query(call.id, "❌ Немає коштів у основному балансі", show_alert=True)
            return
        
        print(f"[DEBUG] Setting user state to p2p_waiting_move_amount for user {user_id}")
        set_user_state(user_id, "p2p_waiting_move_amount")
        
        text = (
            f" рейтістити <b>ПЕРЕМІЩЕННЯ КОШТІВ</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>ВАШІ БАЛАНСИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Основний баланс:</b> <code>{balances['main_balance']:.2f}₴</code>\n"
            f"📤 <b>Доступно для переказів:</b> <code>{balances['transferable_balance']:.2f}₴</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 <b>Введіть суму, яку хочете перемістити:</b>\n\n"
            f"💡 <i>Максимальна сума: {balances['main_balance']:.2f}₴</i>"
        )
        
        # Додаємо кнопку скасування
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Скасувати", callback_data="cancel_p2p_move"))
        
        try:
            bot.edit_message_text(
                text,
                chat_id,
                call.message.message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            bot.send_message(chat_id, text, parse_mode="HTML")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
        except:
            pass


def p2p_move_amount_handler(bot, message):
    """Обробка введення суми для переміщення - ПОЛНАЯ ВЕРСИЯ"""
    print(f"[CRITICAL DEBUG] p2p_move_amount_handler CALLED! user={message.from_user.id}, text='{message.text}', chat_id={message.chat.id}")
    
    from database import get_user_state, set_user_state, move_to_transferable, get_user_balances
    
    try:
        current_state = get_user_state(message.from_user.id)
        print(f"[CRITICAL DEBUG] Current user state: '{current_state}'")
        
        if current_state != "p2p_waiting_move_amount":
            print(f"[CRITICAL DEBUG] WRONG STATE! Expected 'p2p_waiting_move_amount', got '{current_state}'")
            return
        
        print(f"[DEBUG] Converting amount: '{message.text}'")
        amount = float(message.text.replace(",", "."))
        print(f"[DEBUG] Amount converted successfully: {amount}")
        
        if amount <= 0:
            print(f"[DEBUG] Amount <= 0, sending error message")
            bot.reply_to(message, "❌ Сума має бути більше 0")
            return
        
        # Получаем балансы
        balances = get_user_balances(message.from_user.id)
        print(f"[DEBUG] User balances: main={balances['main_balance']}, transferable={balances['transferable_balance']}")
        
        if amount > balances['main_balance']:
            print(f"[DEBUG] Amount exceeds main balance")
            bot.reply_to(message, f"❌ Недостатньо коштів. Максимально: {balances['main_balance']:.2f}₴")
            return
        
        print(f"[DEBUG] Calling move_to_transferable function")
        success, error = move_to_transferable(message.from_user.id, amount, reason='user_move_to_transferable')
        print(f"[DEBUG] move_to_transferable returned: success={success}, error={error}")
        
        if success:
            print(f"[DEBUG] Transfer successful, getting new balances")
            new_balances = get_user_balances(message.from_user.id)
            print(f"[DEBUG] New balances: main={new_balances['main_balance']}, transferable={new_balances['transferable_balance']}")
            
            success_text = (
                f"✅ <b>КОШТИ ПЕРЕМІЩЕНО!</b>\n\n"
                f" рейтістити <b>{amount:.2f}₴</b> переміщено з основного балансу для переказів.\n\n"
                f"💰 <b>Ваш основний баланс:</b> <code>{new_balances['main_balance']:.2f}₴</code>\n"
                f"📤 <b>Ваш P2P баланс:</b> <code>{new_balances['transferable_balance']:.2f}₴</code>\n\n"
                f"💡 Тепер ви можете створювати P2P-перекази!"
            )
            bot.reply_to(message, success_text, parse_mode="HTML")
            print(f"[DEBUG] Success message sent")
        else:
            print(f"[DEBUG] Transfer failed, sending error: {error}")
            bot.reply_to(message, f"❌ {error}")
        
        print(f"[DEBUG] Setting user state to None")
        set_user_state(message.from_user.id, None)
        print(f"[DEBUG] User state set to None successfully")
        
    except ValueError:
        print(f"[DEBUG] ValueError occurred: {message.text}")
        bot.reply_to(message, "❌ Помилка: Введіть коректне число!")
        set_user_state(message.from_user.id, None)
    except Exception as e:
        print(f"[DEBUG] General exception in p2p_move_amount_handler: {str(e)}")
        import traceback
        traceback.print_exc()
        bot.reply_to(message, f"❌ Помилка: {str(e)}")
        set_user_state(message.from_user.id, None)


def p2p_approve_handler(bot, call):
    """Підтвердження переказу"""
    from database import is_admin, approve_p2p_transaction, get_p2p_transaction, get_user, create_notification
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    try:
        transaction_id = int(call.data.split(":")[1])
        transaction = get_p2p_transaction(transaction_id)
        
        if not transaction:
            return bot.answer_callback_query(call.id, "❌ Транзакцію не знайдено", show_alert=True)
        
        if transaction['status'] != 'pending':
            return bot.answer_callback_query(call.id, f"❌ Транзакція вже оброблена ({transaction['status']})", show_alert=True)
        
        approve_p2p_transaction(transaction_id, processed_by=call.from_user.id)
        
        from_user = get_user(transaction['from_user_id'])
        to_user = get_user(transaction['to_user_id'])
        
        # Сповіщення відправнику
        try:
            bot.send_message(
                transaction['from_user_id'],
                f"✅ <b>ПЕРЕКАЗ ПІДТВЕРДЖЕНО</b>\n\n"
                f"Ваш переказ <b>{transaction['amount']:.2f}₴</b> отримувачу зараховано!",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        # Сповіщення отримувачу
        try:
            bot.send_message(
                transaction['to_user_id'],
                f"✅ <b>ПЕРЕКАЗ ЗАРАХОВАНО</b>\n\n"
                f"Ви отримали <b>{transaction['amount']:.2f}₴</b>!",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        bot.answer_callback_query(call.id, f"✅ Переказ #{transaction_id} підтверджено", show_alert=True)
        admin_p2p_transfers_handler(bot, call)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)


def p2p_reject_handler(bot, call):
    """Відхилення переказу"""
    from database import is_admin, get_p2p_transaction, set_user_state
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "⛔️ Немає доступу", show_alert=True)
    
    try:
        transaction_id = int(call.data.split(":")[1])
        transaction = get_p2p_transaction(transaction_id)
        
        if not transaction:
            return bot.answer_callback_query(call.id, "❌ Транзакцію не знайдено", show_alert=True)
        
        if transaction['status'] != 'pending':
            return bot.answer_callback_query(call.id, f"❌ Транзакція вже оброблена", show_alert=True)
        
        # Зберігаємо ID транзакції для введення причини
        set_user_state(call.from_user.id, f"p2p_waiting_reject_reason:{transaction_id}")
        
        bot.send_message(
            call.message.chat.id,
            f"❌ <b>ВІДХИЛЕННЯ ПЕРЕКАЗУ</b>\n\n"
            f"Введіть причину відхилення переказу #{transaction_id}:",
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)


def p2p_reject_reason_handler(bot, message):
    """Обробка причини відхилення"""
    from database import get_user_state, set_user_state, reject_p2p_transaction, get_p2p_transaction, get_user, is_admin
    
    if not is_admin(message.from_user.id):
        set_user_state(message.from_user.id, None)
        return
    
    try:
        state = get_user_state(message.from_user.id)
        transaction_id = int(state.split(":")[1])
        reason = message.text.strip()
        
        if not reason:
            bot.reply_to(message, "❌ Введіть причину відхилення!")
            return
        
        reject_p2p_transaction(transaction_id, reason, processed_by=message.from_user.id)
        
        transaction = get_p2p_transaction(transaction_id)
        
        # Сповіщення відправнику
        try:
            bot.send_message(
                transaction['from_user_id'],
                f"❌ <b>ПЕРЕКАЗ ВІДХИЛЕНО</b>\n\n"
                f"Ваш переказ <b>{transaction['amount']:.2f}₴</b> відхилено.\n\n"
                f"📝 <b>Причина:</b> {reason}\n\n"
                f"💰 Кошти повернуто на рахунок для переказів.",
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        bot.reply_to(
            message,
            f"✅ <b>Переказ відхилено</b>\n\n"
            f"Кошти повернуто відправнику.",
            parse_mode="HTML"
        )
        
        set_user_state(message.from_user.id, None)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        bot.reply_to(message, f"❌ Помилка: {str(e)}")
        set_user_state(message.from_user.id, None)


def register_p2p_handlers(bot):
    """Регистрирует все P2P обработчики"""
    print("=== FUNCTION register_p2p_handlers STARTED ===")
    print("=== P2P HANDLER REGISTRATION STARTING ===")
    print(f"Bot object: {type(bot)}")
    
    # Упрощенная регистрация - только то что нужно
    
    print("Registering /move command...")
    @bot.message_handler(commands=['move'])  
    def move_cmd(message):
        print("=== /move COMMAND CALLED ===")
        
        from database import get_user_balances
        balances = get_user_balances(message.from_user.id)
        
        if balances['main_balance'] <= 0:
            bot.reply_to(message, "❌ На основному балансі немає коштів для переміщення")
            return
        
        # ВИКОРИСТОВУЄМО register_next_step_handler - це ПРОСТО і НАДІЙНО!
        text = (
            f" рейтістити <b>ПЕРЕМІЩЕННЯ ГРОШЕЙ</b>\n\n"
            f"💰 Основний баланс: <code>{balances['main_balance']:.2f}₴</code>\n"
            f"📤 P2P баланс: <code>{balances['transferable_balance']:.2f}₴</code>\n\n"
            f"💬 <b>Введіть суму для переміщення:</b>\n"
            f"💡 Максимально: <code>{balances['main_balance']:.2f}₴</code>"
        )
        
        # Відправляємо повідомлення і реєструємо наступний крок
        sent_msg = bot.send_message(message.chat.id, text, parse_mode="HTML")
        
        # Реєструємо обробник для наступного повідомлення
        bot.register_next_step_handler(sent_msg, lambda m: process_simple_move_amount(bot, m))
        
        # Додаємо кнопку скасування (окремим повідомленням)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Скасувати", callback_data="cancel_simple_move"))
        bot.send_message(message.chat.id, "Натисніть /cancel для скасування", reply_markup=kb)
    
    # Обробник для скасування
    @bot.message_handler(commands=['cancel'])
    def cancel_cmd(message):
        bot.reply_to(message, "❌ Операцію скасовано")


def process_simple_move_amount(bot, message):
    """Обробляє введену суму для простого переміщення"""
    print(f"[SIMPLE MOVE] process_simple_move_amount called: user={message.from_user.id}, text='{message.text}'")
    
    try:
        amount = float(message.text.replace(",", "."))
    except (ValueError, AttributeError):
        bot.reply_to(message, "❌ Введіть коректне число!")
        return
    
    from database import get_user_balances, move_to_transferable
    balances = get_user_balances(message.from_user.id)
    
    if amount > balances['main_balance']:
        bot.reply_to(message, f"❌ Недостатньо коштів. Максимально: {balances['main_balance']:.2f}₴")
        return
    
    if amount <= 0:
        bot.reply_to(message, "❌ Сума має бути більше 0")
        return
    
    success, error = move_to_transferable(message.from_user.id, amount, reason='simple_move')
    
    if success:
        new_balances = get_user_balances(message.from_user.id)
        bot.reply_to(message, f"✅ Успішно! Переказано {amount:.2f}₴ на P2P баланс\n"
                    f"💰 Основний баланс: {new_balances['main_balance']:.2f}₴\n"
                    f"💳 P2P баланс: {new_balances['transferable_balance']:.2f}₴")
    else:
        bot.reply_to(message, f"❌ Помилка: {error}")
    
    # Глобальний обробник видалено - використовується final_global_handler в bot.py
    
    print("Registering callback handlers...")
    # Callback handlers
    @bot.callback_query_handler(func=lambda c: c.data == "p2p_menu")
    def p2p_menu_cb(call):
        print("=== P2P MENU CALLBACK CALLED ===")
        p2p_menu_handler(bot, call)
    
    @bot.callback_query_handler(func=lambda c: c.data == "p2p_move_to_transferable")
    def p2p_move_cb(call):
        print("=== P2P MOVE TO TRANSFERABLE CALLBACK CALLED ===")
        p2p_move_to_transferable_handler(bot, call)
        
    @bot.callback_query_handler(func=lambda c: c.data == "simple_move_info")
    def simple_move_cb(call):
        print("=== SIMPLE MOVE INFO CALLBACK CALLED ===")
        simple_move_info_handler(bot, call)
    
    @bot.callback_query_handler(func=lambda c: c.data == "cancel_p2p_move")
    def cancel_p2p_move_cb(call):
        print("=== CANCEL P2P MOVE CALLBACK CALLED ===")
        try:
            bot.answer_callback_query(call.id, "Операцію скасовано")
            from database import set_user_state
            set_user_state(call.from_user.id, None)
            
            # Повертаємо користувача до меню P2P
            p2p_menu_handler(bot, call)
        except Exception as e:
            print(f"[CANCEL] Error: {e}")
            bot.answer_callback_query(call.id, "Помилка скасування", show_alert=True)
    
    @bot.callback_query_handler(func=lambda c: c.data == "cancel_simple_move")
    def cancel_simple_move_cb(call):
        print("=== CANCEL SIMPLE MOVE CALLBACK CALLED ===")
        try:
            bot.answer_callback_query(call.id, "Операцію скасовано")
            from database import set_user_state
            set_user_state(call.from_user.id, None)
            
            # Повертаємо користувача до головного меню
            text = "🔄 <b>Операцію скасовано</b>\n\nОперацію переміщення коштів скасовано."
            bot.send_message(call.from_user.id, text, parse_mode="HTML")
        except Exception as e:
            print(f"[CANCEL SIMPLE] Error: {e}")
            bot.answer_callback_query(call.id, "Помилка скасування", show_alert=True)
    
    print("=== P2P HANDLER REGISTRATION COMPLETED ===")
    print("=== FUNCTION register_p2p_handlers FINISHED ===")


def simple_move_info_handler(bot, call):
    """Обробник кнопки швидкого переміщення"""
    try:
        bot.answer_callback_query(call.id)
        
        from database import get_user_balances, set_user_state
        balances = get_user_balances(call.from_user.id)
        
        if balances['main_balance'] <= 0:
            text = "❌ На основному балансі немає коштів для переміщення"
            bot.send_message(call.from_user.id, text, parse_mode="HTML")
            return
        
        # Встановлюємо стан для очікування суми
        set_user_state(call.from_user.id, "simple_move_waiting_amount")
        
        text = (
            f"🚀 <b>ШВИДКИЙ ПЕРЕКАЗ</b>\n\n"
            f"💰 Основний баланс: <code>{balances['main_balance']:.2f}₴</code>\n"
            f"📤 P2P баланс: <code>{balances['transferable_balance']:.2f}₴</code>\n\n"
            f"💬 <b>Введіть суму для переміщення:</b>\n"
            f"💡 Максимально: <code>{balances['main_balance']:.2f}₴</code>\n\n"
            f"💡 <i>Або використайте команду /move</i>"
        )
        
        # Додаємо кнопку скасування
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("❌ Скасувати", callback_data="cancel_simple_move"))
        
        bot.send_message(call.from_user.id, text, reply_markup=kb, parse_mode="HTML")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            bot.answer_callback_query(call.id, f"❌ Помилка: {str(e)}", show_alert=True)
        except:
            pass




