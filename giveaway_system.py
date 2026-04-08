#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Вспомогательные функции для системы розыгрышей
"""

import json
import random
from database import (
    get_giveaway, update_giveaway_status, add_giveaway_participant,
    get_giveaway_participants, add_balance, add_garden_transaction
)

def format_prize_text(giveaway):
    """Форматирует текст приза для отображения"""
    prize_type = giveaway['prize_type']
    prize_value = giveaway['prize_value']
    prize_extra = giveaway.get('prize_extra')
    
    if prize_type == 'money':
        return f"💰 <b>{prize_value}₴</b>"
    elif prize_type == 'tree':
        from garden_models import get_tree_name_uk
        tree_name = get_tree_name_uk(prize_value)
        return f"🌳 <b>{tree_name}</b>"
    elif prize_type == 'booster':
        booster_name = prize_value
        if prize_extra:
            try:
                extra_data = json.loads(prize_extra)
                duration = extra_data.get('duration', 0)
                return f"⚡ <b>{booster_name}</b> ({duration} год.)"
            except:
                return f"⚡ <b>{booster_name}</b>"
        return f"⚡ <b>{booster_name}</b>"
    elif prize_type == 'achievement':
        return f"🏆 <b>Досягнення: {prize_value}</b>"
    elif prize_type == 'fruit':
        if prize_extra:
            try:
                extra_data = json.loads(prize_extra)
                amount = extra_data.get('amount', 1)
                return f"🍎 <b>{prize_value}</b> x{amount}"
            except:
                return f"🍎 <b>{prize_value}</b>"
        return f"🍎 <b>{prize_value}</b>"
    return f"🎁 <b>{prize_value}</b>"

def create_giveaway_post_text(giveaway):
    """Створює текст поста для розіграшу"""
    prize_text = format_prize_text(giveaway)
    
    # Форматуємо кількість реакцій
    reactions_count = giveaway['required_reactions']
    reactions_word = "реакцію" if reactions_count == 1 else ("реакції" if reactions_count < 5 else "реакцій")
    
    text = (
        f"🎁 <b>РОЗІГРАШ!</b> 🎁\n\n"
        f"📌 <b>{giveaway['title']}</b>\n"
        f"🎁 <b>Приз:</b> {prize_text}\n\n"
        f"📊 <b>Для запуску:</b> <code>{reactions_count}</code> {reactions_word}\n"
        f"👥 <b>Учасників:</b> Без обмежень\n"
        f"🤖 <b>Умова:</b> Для захисту призу потрібно бути в <a href='tg://resolve?domain=palmaron_bot'>@palmaron_bot</a>\n\n"
        f"💬 <b>Як брати участь:</b>\n"
        f"1️⃣ Поставте <b>реакцію</b> на цей пост\n"
        f"2️⃣ Коли збереться <code>{reactions_count}</code> {reactions_word}, розіграш <b>запуститься</b>\n"
        f"3️⃣ Відправте <b>емодзі</b> в коментарях\n"
        f"4️⃣ Хто перший виб'є <b>777</b> — <b>перемагає!</b> 🎰\n\n"
        f"✨ <i>Удачі всім учасникам!</i> ✨"
    )
    return text

def create_giveaway_started_post_text(giveaway):
    """Створює текст поста про початок розіграшу (коли зібрано достатньо реакцій)"""
    prize_text = format_prize_text(giveaway)
    
    text = (
        f"🎉 <b>РОЗІГРАШ ПОЧАВСЯ!</b> 🎉\n\n"
        f"📌 <b>{giveaway['title']}</b>\n"
        f"🎁 <b>Приз:</b> {prize_text}\n\n"
        f"✅ <b>Потрібна кількість реакцій зібрано!</b>\n\n"
        f"💬 <b>Тепер відправляйте емодзі в коментарях!</b>\n"
        f"🎲 Хто перший виб'є <b>777</b> - перемагає! 🎰\n\n"
        f"⏰ <b>Розіграш триває...</b>"
    )
    return text

def award_prize(giveaway, winner_id):
    """Начисляет приз победителю"""
    prize_type = giveaway['prize_type']
    prize_value = giveaway['prize_value']
    prize_extra = giveaway.get('prize_extra')
    
    try:
        if prize_type == 'money':
            amount = float(prize_value)
            add_balance(winner_id, amount, reason='giveaway_prize', 
                       details=f'Розыгрыш #{giveaway["id"]}: {giveaway["title"]}')
            return f"💰 {amount}₴"
        
        elif prize_type == 'tree':
            from database import get_user_trees, _db
            with _db() as con:
                current = con.execute(
                    "SELECT count FROM users_garden WHERE user_id = ? AND tree_type = ?",
                    (winner_id, prize_value)
                ).fetchone()
                new_count = (current[0] if current else 0) + 1
                con.execute("""
                    INSERT OR REPLACE INTO users_garden (user_id, tree_type, count)
                    VALUES (?, ?, ?)
                """, (winner_id, prize_value, new_count))
                con.commit()
            add_garden_transaction(winner_id, 'giveaway_tree', 1, 'tree', 
                                 int(__import__('time').time()), 
                                 f'Розыгрыш #{giveaway["id"]}')
            from garden_models import get_tree_name_uk
            tree_name = get_tree_name_uk(prize_value)
            return f"🌳 {tree_name}"
        
        elif prize_type == 'booster':
            import time
            duration_hours = 1
            if prize_extra:
                try:
                    extra_data = json.loads(prize_extra)
                    duration_hours = extra_data.get('duration', 1)
                except:
                    pass
            
            expires_at = int(time.time()) + (duration_hours * 3600)
            from database import _db
            with _db() as con:
                con.execute("""
                    INSERT OR REPLACE INTO boosters (user_id, booster_type, expires_at)
                    VALUES (?, ?, ?)
                """, (winner_id, prize_value, expires_at))
                con.commit()
            return f"⚡ {prize_value} ({duration_hours} год.)"
        
        elif prize_type == 'achievement':
            from database import add_achievement_if_needed
            add_achievement_if_needed(winner_id, prize_value, 1)
            return f"🏆 {prize_value}"
        
        elif prize_type == 'fruit':
            amount = 1
            if prize_extra:
                try:
                    extra_data = json.loads(prize_extra)
                    amount = extra_data.get('amount', 1)
                except:
                    pass
            
            from database import _db
            with _db() as con:
                current = con.execute(
                    "SELECT amount FROM fruits WHERE user_id = ? AND fruit_type = ?",
                    (winner_id, prize_value)
                ).fetchone()
                new_amount = (float(current[0]) if current else 0) + amount
                con.execute("""
                    INSERT OR REPLACE INTO fruits (user_id, fruit_type, amount)
                    VALUES (?, ?, ?)
                """, (winner_id, prize_value, new_amount))
                con.commit()
            add_garden_transaction(winner_id, 'giveaway_fruit', amount, 'fruit',
                                 int(__import__('time').time()),
                                 f'Розыгрыш #{giveaway["id"]}')
            return f"🍎 {prize_value} x{amount}"
        
        return "🎁 Приз"
    except Exception as e:
        print(f"[ERROR] Помилка нарахування призу: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_giveaway_777(giveaway_id, bot):
    """Обрабатывает розыгрыш по механике 777"""
    giveaway = get_giveaway(giveaway_id)
    if not giveaway or giveaway['status'] != 'active':
        return None
    
    channel_id = giveaway['channel_id']
    post_message_id = giveaway['post_message_id']
    
    if not channel_id or not post_message_id:
        return None
    
    try:
        # Получаем все комментарии под постом
        # В Telegram Bot API нет прямого метода для получения комментариев
        # Нужно использовать message_thread_id или получать через forward/reply
        # Для упрощения будем использовать участников из БД
        
        participants = get_giveaway_participants(giveaway_id)
        if not participants:
            return None
        
        # Генерируем случайные числа для участников, у которых их еще нет
        # И проверяем, есть ли уже победитель с 777
        winner = None
        participants_with_numbers = []
        
        for participant in participants:
            # Если у участника уже есть число, используем его
            if participant.get('random_number'):
                num = participant['random_number']
                participants_with_numbers.append({
                    'user_id': participant['user_id'],
                    'comment_id': participant.get('comment_id'),
                    'random_number': num
                })
                if num == 777 and not winner:
                    winner = {
                        'user_id': participant['user_id'],
                        'comment_id': participant.get('comment_id'),
                        'random_number': 777
                    }
            else:
                # Генерируем новое число
                random_num = random.randint(1, 777)
                # Обновляем random_number в БД
                add_giveaway_participant(giveaway_id, participant['user_id'], 
                                        participant.get('comment_id'), random_num)
                participants_with_numbers.append({
                    'user_id': participant['user_id'],
                    'comment_id': participant.get('comment_id'),
                    'random_number': random_num
                })
                if random_num == 777 and not winner:
                    winner = {
                        'user_id': participant['user_id'],
                        'comment_id': participant.get('comment_id'),
                        'random_number': 777
                    }
        
        # Если никто не выбил 777, выбираем ближайшего к 777
        if not winner and participants_with_numbers:
            closest = min(participants_with_numbers, 
                         key=lambda p: abs(p['random_number'] - 777))
            winner = closest
        
        return winner
    except Exception as e:
        print(f"[ERROR] Помилка обробки розыгрыша 777: {e}")
        import traceback
        traceback.print_exc()
        return None

