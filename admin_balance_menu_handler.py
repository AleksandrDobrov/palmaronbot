from telebot import types
from bot import bot, is_admin

@bot.callback_query_handler(func=lambda c: c.data == "admin_balance_menu")
def admin_balance_menu(call):
    if not is_admin(call.from_user.id):
        return bot.answer_callback_query(call.id, "Нема доступу", show_alert=True)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("💵 Видати баланс", callback_data="admin_give_balance"),
        types.InlineKeyboardButton("💸 Забрати баланс", callback_data="admin_take_balance"),
        types.InlineKeyboardButton("⬅️ Назад", callback_data="panel")
    )
    bot.edit_message_text(
        "💰 <b>Керування балансами</b>\nОберіть дію:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )
    bot.answer_callback_query(call.id)
