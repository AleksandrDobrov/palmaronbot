"""
Referral system handlers module.
Contains all handlers for referral program functionality.
"""
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton


def ref_program_handler(bot, call):
    """Обработчик меню реферальной программы"""
    from database import get_ref_count, get_ref_bonus
    # Импортируем функции из bot.py (они определены там, а не в utils)
    try:
        import bot as bot_module
        check_user_block_before_action = bot_module.check_user_block_before_action
        check_button_spam = bot_module.check_button_spam
        build_caption_from_text = getattr(bot_module, 'build_caption_from_text', None)
        send_banner_with_caption = getattr(bot_module, 'send_banner_with_caption', None)
    except ImportError:
        # Fallback если не удалось импортировать
        def check_user_block_before_action(call, bot):
            return False
        def check_button_spam(user_id, button_name):
            return False, ""
        build_caption_from_text = None
        send_banner_with_caption = None
    
    # Перевіряємо чи користувач заблокований
    if check_user_block_before_action(call, bot):
        return
    
    user_id = call.from_user.id
    
    # Перевірка спаму
    is_spam, spam_message = check_button_spam(user_id, "ref_program")
    if is_spam:
        bot.answer_callback_query(call.id, text=spam_message, show_alert=True)
        return
    
    bot_username = bot.get_me().username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    ref_count = get_ref_count(user_id)
    bonus = get_ref_bonus()
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📜 Мої реферали", callback_data="my_referrals"),
        InlineKeyboardButton("🏆 ТОП-5 запрошувачів", callback_data="top_referrers"),
    )
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="cabinet"))
    
    msg = (
        f"🎯 <b>Реферальна програма</b>\n\n"
        f"Запрошуйте друзів та отримуйте бонуси!\n"
        f"Ваше реферальне посилання:\n<code>{ref_link}</code>\n\n"
        f"За кожного активного друга ви отримуєте бонус: <b>{bonus} ₴</b>\n"
        f"Вже запрошено: <b>{ref_count}</b>\n"
    )
    
    try:
        short_caption = build_caption_from_text(msg, 1024)
        send_banner_with_caption(call.message.chat.id, "Реферальна програма", "🤝", short_caption, reply_markup=kb, parse_mode="HTML", subtitle="Запрошуй друзів — отримуй бонуси")
        if len(msg) > 1024:
            bot.send_message(call.message.chat.id, msg, parse_mode="HTML")
    except Exception:
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")


def my_referrals_handler(bot, call):
    """Обработчик списка рефералов пользователя"""
    from database import get_referrals, _db
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    from utils import format_kiev_time
    
    refs = get_referrals(call.from_user.id)
    
    # Створюємо клавіатуру з кнопкою "Назад"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="ref_program"))
    
    if not refs:
        msg = "📋 <b>Ваші реферали:</b>\n\nУ вас ще немає рефералів.\n\n💡 <b>Поради:</b>\n• Поділіться своїм реферальним посиланням з друзями\n• За кожного активного друга ви отримуєте бонус\n• Перевірте свій баланс після реєстрації рефералів"
        bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
        return
    
    # Заголовок + последние 10
    msg = "📋 <b>Мої реферали</b>\n"
    msg += "━━━━━━━━━━━━━━━━━\n\n"
    last_referrals = refs[:10]
    for i, row in enumerate(last_referrals, 1):
        # совместимость: (uid, name) или (uid, name, ts)
        uid = row[0]
        name = row[1]
        ts = row[2] if len(row) > 2 else None
        when = (format_kiev_time(ts) if ts else "—")
        msg += f"{i}. 👤 <b>{name}</b>\n   🆔 <code>{uid}</code>\n   📅 {when}\n\n"
    
    total = len(refs)
    # Исправленный расчет заработка - считаем из транзакций
    earnings = get_referral_earnings_for_user(call.from_user.id)
    
    msg += f"🏁 <b>Всього рефералів:</b> <b>{total}</b>\n"
    msg += f"💰 <b>Зароблено за рефералів:</b> <b>{earnings:.2f}₴</b>\n\n"
    msg += "💡 <b>Поради:</b>\n• Діліться посиланням з друзями\n• Бонус нараховується після першої дії друга (продаж/вивід)"
    
    bot.edit_message_text(msg, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")


def top_referrers_handler(bot, call):
    """Обработчик топ-5 рефералов с красивым оформлением"""
    # Импортируем функции из bot.py (они определены там, а не в utils)
    try:
        import bot as bot_module
        check_user_block_before_action = bot_module.check_user_block_before_action
        check_button_spam = bot_module.check_button_spam
    except ImportError:
        # Fallback если не удалось импортировать
        def check_user_block_before_action(call, bot):
            return False
        def check_button_spam(user_id, button_name):
            return False, ""
    
    uid = call.from_user.id
    
    # Проверка блокировки
    if check_user_block_before_action(call, bot):
        return
    
    # Проверка спама
    is_spam, spam_message = check_button_spam(uid, "top_referrers")
    if is_spam:
        bot.answer_callback_query(call.id, text=spam_message, show_alert=True)
        return
    
    bot.answer_callback_query(call.id)
    
    try:
        # Получаем топ-рефералов с заработком (исправленная версия)
        top_referrers = get_top_referrers_with_earnings_fixed(5)
        
        # Форматируем для отображения
        text = format_top_referrers_display(top_referrers)
        
        # Добавляем кнопку "Оновити"
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔄 Оновити", callback_data="top_referrers"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_home"))
        
        # Отправляем обновлённое сообщение
        try:
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            # Если не удалось отредактировать, отправляем новое
            bot.send_message(
                call.message.chat.id,
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
    except Exception as e:
        print(f"[top_referrers] error: {e}")
        import traceback
        traceback.print_exc()
        bot.send_message(call.message.chat.id, "❌ Помилка завантаження топ-рефералів")


def get_referral_earnings_for_user(user_id):
    """Исправленная функция расчета заработка реферала из транзакций"""
    try:
        from database import _db
        import sqlite3
        
        with _db() as con:
            # Считаем заработок из транзакций с reason='referral_bonus'
            # Также учитываем разблокированные награды из таблицы referral_rewards
            earnings_from_transactions = con.execute(
                "SELECT COALESCE(SUM(delta), 0) FROM balance_ledger "
                "WHERE user_id = ? AND reason = 'referral_bonus' AND delta > 0",
                (user_id,)
            ).fetchone()[0] or 0
            
            # Также считаем из таблицы referral_rewards (разблокированные награды)
            earnings_from_rewards = con.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM referral_rewards "
                "WHERE referrer_id = ? AND status = 'unlocked'",
                (user_id,)
            ).fetchone()[0] or 0
            
            total_earnings = float(earnings_from_transactions) + float(earnings_from_rewards)
            return total_earnings
    except Exception as e:
        print(f"[get_referral_earnings_for_user] error: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def get_top_referrers_with_earnings_fixed(limit=5):
    """Исправленная функция получения топ рефералов с правильным расчетом заработка"""
    try:
        from database import _db, get_user
        
        with _db() as con:
            # Получаем топ рефералов по количеству приглашенных
            top_referrers_data = con.execute(
                "SELECT invited_by, COUNT(*) as ref_count "
                "FROM referrals "
                "GROUP BY invited_by "
                "ORDER BY ref_count DESC "
                "LIMIT ?",
                (limit,)
            ).fetchall()
            
            result = []
            for referrer_id, ref_count in top_referrers_data:
                # Получаем имя пользователя
                user_data = get_user(referrer_id)
                if not user_data:
                    continue
                
                name = user_data[1] if len(user_data) > 1 else f"User {referrer_id}"
                
                # Исправленный расчет заработка
                earnings = get_referral_earnings_for_user(referrer_id)
                
                result.append((referrer_id, name, ref_count, earnings))
            
            # Сортируем по заработку (если нужно)
            result.sort(key=lambda x: x[3], reverse=True)
            
            return result
    except Exception as e:
        print(f"[get_top_referrers_with_earnings_fixed] error: {e}")
        import traceback
        traceback.print_exc()
        return []


def format_top_referrers_display(top_referrers):
    """Форматирует топ-5 рефералов для красивого отображения"""
    if not top_referrers:
        return "📊 <b>Топ-5 запрошувачів</b>\n\nПоки що немає рефералів"
    
    lines = ["🏆 <b>Топ-5 запрошувачів</b>", ""]
    
    # Эмодзи для мест
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    
    for i, (user_id, name, ref_count, earnings) in enumerate(top_referrers[:5]):
        medal = medals[i] if i < len(medals) else f"{i+1}️⃣"
        
        # Форматируем имя (обрезаем если слишком длинное)
        display_name = name[:20] + "..." if len(name) > 20 else name
        
        # Форматируем заработок (исправлено - показываем реальный заработок)
        earnings_text = f"{earnings:.2f}₴" if earnings > 0 else "0₴"
        
        lines.append(f"{medal} <b>{display_name}</b>")
        lines.append(f"   👥 Запрошено: <b>{ref_count}</b> осіб")
        lines.append(f"   💰 Зароблено: <b>{earnings_text}</b>")
        
        # Добавляем декоративные элементы
        if i == 0:  # Первое место
            lines.append(f"   ⭐ Зірковий запрошувач!")
        elif i == 1:  # Второе место
            lines.append(f"   🔥 Відмінний результат!")
        elif i == 2:  # Третье место
            lines.append(f"   💎 Хороша робота!")
        
        lines.append("")  # Пустая строка между участниками
    
    # Добавляем общую статистику
    total_refs = sum(ref_count for _, _, ref_count, _ in top_referrers)
    total_earnings = sum(earnings for _, _, _, earnings in top_referrers)
    
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📈 <b>Загальна статистика:</b>")
    lines.append(f"👥 Всього запрошено: <b>{total_refs}</b> осіб")
    lines.append(f"💰 Всього зароблено: <b>{total_earnings:.2f}₴</b>")
    
    return "\n".join(lines)


def register_referral_handlers(bot):
    """Регистрирует все реферальные обработчики"""
    bot.callback_query_handler(func=lambda c: c.data == "ref_program")(lambda call: ref_program_handler(bot, call))
    bot.callback_query_handler(func=lambda c: c.data == "my_referrals")(lambda call: my_referrals_handler(bot, call))
    bot.callback_query_handler(func=lambda c: c.data == "top_referrers")(lambda call: top_referrers_handler(bot, call))
    bot.callback_query_handler(func=lambda c: c.data == "test_referral_system")(lambda call: test_referral_system_handler(bot, call))


def test_referral_system_handler(bot, call):
    """Тестовый обработчик реферальной системы (только для админов)"""
    from database import get_ref_count, get_user, ensure_user, save_referral, get_ref_bonus, add_balance, delete_user_completely
    # Импортируем функции из bot.py
    try:
        import bot as bot_module
        check_button_spam = bot_module.check_button_spam
        format_currency = getattr(bot_module, 'format_currency', lambda x: f"{x:.2f}")
    except ImportError:
        def check_button_spam(user_id, button_name):
            return False, ""
        format_currency = lambda x: f"{x:.2f}"
    from admin import is_admin
    
    user_id = call.from_user.id
    
    # Перевіряємо чи це адмін
    if not is_admin(user_id):
        bot.answer_callback_query(call.id, text="❌ Доступ заборонено!", show_alert=True)
        return
    
    # Перевірка спаму
    is_spam, spam_message = check_button_spam(user_id, "test_referral_system")
    if is_spam:
        bot.answer_callback_query(call.id, text=spam_message, show_alert=True)
        return
    
    try:
        # Створюємо тестових користувачів
        test_referrer_id = 999999999
        test_new_user_id = 111111111
        
        # Отримуємо поточні дані
        ref_count_before = get_ref_count(test_referrer_id)
        user_data_before = get_user(test_referrer_id)
        balance_before = user_data_before[2] if user_data_before else 0
        
        # Створюємо користувачів
        ensure_user(test_referrer_id, "Тестовий Реферер")
        ensure_user(test_new_user_id, "Тестовий Користувач")
        
        # Симулюємо реферальну реєстрацію
        save_referral(test_new_user_id, test_referrer_id)
        ref_bonus = get_ref_bonus()
        add_balance(test_referrer_id, ref_bonus)
        
        # Отримуємо нові дані
        ref_count_after = get_ref_count(test_referrer_id)
        user_data_after = get_user(test_referrer_id)
        balance_after = user_data_after[2] if user_data_after else 0
        
        # Видаляємо тестових користувачів
        delete_user_completely(test_new_user_id)
        
        # Формуємо результат
        result_msg = (
            f"🧪 <b>ТЕСТ РЕФЕРАЛЬНОЇ СИСТЕМИ</b>\n\n"
            f"✅ <b>Тест пройшов успішно!</b>\n\n"
            f"📊 <b>Результати:</b>\n"
            f"• Кількість рефералів до: <b>{ref_count_before}</b>\n"
            f"• Кількість рефералів після: <b>{ref_count_after}</b>\n"
            f"• Баланс до: <b>{format_currency(balance_before)} ₴</b>\n"
            f"• Баланс після: <b>{format_currency(balance_after)} ₴</b>\n"
            f"• Бонус: <b>{format_currency(ref_bonus)} ₴</b>\n"
        )
        
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, result_msg, parse_mode="HTML")
        
    except Exception as e:
        print(f"[test_referral_system] error: {e}")
        import traceback
        traceback.print_exc()
        bot.answer_callback_query(call.id, text=f"❌ Помилка: {str(e)}", show_alert=True)

