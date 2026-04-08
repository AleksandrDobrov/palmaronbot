# --- Керування бета-тестерами ---
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import bot
from database import add_beta, remove_beta, is_beta, get_user

@bot.callback_query_handler(func=lambda c: c.data == "admin_beta_testers")
def admin_beta_testers_menu(call):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("👾 Список бета-тестерів", callback_data="admin_beta_list"),
        InlineKeyboardButton("➕ Видати бета-тестера", callback_data="admin_beta_add"),
        InlineKeyboardButton("➖ Забрати бета-тестера", callback_data="admin_beta_remove"),
        InlineKeyboardButton("⬅️ Назад", callback_data="panel")
    )
    bot.edit_message_text("👾 <b>Керування бета-тестерами</b>\nОберіть дію:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "admin_beta_list")
def admin_beta_list_handler(call):
    from database import _db
    import datetime
    with _db() as con:
        rows = con.execute("SELECT user_id, added_by, added_at FROM beta_testers").fetchall()
    if not rows:
        bot.send_message(call.message.chat.id, "😴 Бета-тестерів ще немає!")
        return
    msg = "<b>👾 Список бета-тестерів</b>\n\n"
    for user_id, added_by, added_at in rows:
        user = get_user(user_id)
        user_name = user[1] if user else '—'
        added_str = datetime.datetime.fromtimestamp(added_at).strftime('%d.%m.%Y %H:%M') if added_at else '—'
        admin = get_user(added_by)
        admin_name = admin[1] if admin else added_by
        msg += (
            f"👾 <b>{user_name}</b> (<code>{user_id}</code>)\n"
            f"🗓 Додано: <b>{added_str}</b> | 👤 Адмін: <b>{admin_name}</b>\n"
            f"{'—'*20}\n"
        )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⬅️ Назад", callback_data="admin_beta_testers"))
    bot.send_message(call.message.chat.id, msg, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: c.data == "admin_beta_add")
def admin_beta_add_ask_id(call):
    msg = bot.send_message(call.message.chat.id, "Введіть <b>ID користувача</b> для видачі бета-тестера:", parse_mode="HTML")
    bot.register_next_step_handler(msg, admin_beta_add_save, call.from_user.id)

def admin_beta_add_save(message, admin_id):
    try:
        user_id = int(message.text.strip())
    except Exception:
        bot.send_message(message.chat.id, "Некоректний ID.")
        return
    add_beta(user_id, admin_id)
    import datetime
    now = datetime.datetime.now().strftime('%d.%m.%Y %H:%M')
    admin_name = get_user(admin_id)[1] if get_user(admin_id) else admin_id
    bot.send_message(message.chat.id, f"👾 Бета-тестер <code>{user_id}</code> доданий!", parse_mode="HTML")
    # Повідомлення користувачу
    try:
        bot.send_message(user_id, f"👾 <b>Вам видано статус бета-тестера!</b>\n\n"
            f"Видав: <b>{admin_name}</b> (<code>{admin_id}</code>)\n"
            f"Дата: <b>{now}</b>\n\n"
            f"Ви отримали доступ до всіх нових функцій першими! Дякуємо за участь у розвитку бота! 🚀",
            parse_mode="HTML")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "admin_beta_remove")
def admin_beta_remove_ask_id(call):
    msg = bot.send_message(call.message.chat.id, "Введіть <b>ID користувача</b> для видалення з бета-тестерів:", parse_mode="HTML")
    bot.register_next_step_handler(msg, admin_beta_remove_save)

def admin_beta_remove_save(message):
    try:
        user_id = int(message.text.strip())
    except Exception:
        bot.send_message(message.chat.id, "Некоректний ID.")
        return
    remove_beta(user_id)
    bot.send_message(message.chat.id, f"❌ Користувача <code>{user_id}</code> видалено з бета-тестерів!", parse_mode="HTML")
    try:
        bot.send_message(user_id, "❌ <b>Вас видалено зі списку бета-тестерів.</b>\n\nДоступ до нових функцій закрито.", parse_mode="HTML")
    except Exception:
        pass 