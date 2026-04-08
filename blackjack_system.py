#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система блекджека для розіграшів
"""

import json
import random
import time
from database import _db, get_giveaway

# Колода карт (52 карти)
CARD_SUITS = ['♠️', '♥️', '♦️', '♣️']
CARD_VALUES = {
    'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 10, 'Q': 10, 'K': 10
}
CARD_NAMES = {
    'A': 'Туз', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', '10': '10',
    'J': 'Валет', 'Q': 'Дама', 'K': 'Король'
}

def create_deck():
    """Створює колоду з 52 карт"""
    deck = []
    for suit in CARD_SUITS:
        for value in CARD_VALUES.keys():
            deck.append({'suit': suit, 'value': value})
    random.shuffle(deck)
    return deck

def get_card_name(card):
    """Повертає назву карти для відображення"""
    return f"{CARD_NAMES[card['value']]}{card['suit']}"

def calculate_score(cards):
    """Розраховує рахунок руки з урахуванням тузів"""
    score = 0
    aces = 0
    
    for card in cards:
        value = CARD_VALUES[card['value']]
        if card['value'] == 'A':
            aces += 1
        score += value
    
    # Якщо є тузи і перебір - зменшуємо рахунок
    while score > 21 and aces > 0:
        score -= 10
        aces -= 1
    
    return score

def deal_card(deck):
    """Видає одну карту з колоди"""
    if not deck:
        return None, deck
    card = deck.pop()
    return card, deck

def get_player(giveaway_id, user_id):
    """Отримує інформацію про гравця"""
    with _db() as con:
        row = con.execute("""
            SELECT id, cards, score, status, last_action_at
            FROM blackjack_players
            WHERE giveaway_id = ? AND user_id = ?
        """, (giveaway_id, user_id)).fetchone()
        
        if not row:
            return None
        
        cards = json.loads(row[1]) if row[1] else []
        return {
            'id': row[0],
            'cards': cards,
            'score': row[2],
            'status': row[3],
            'last_action_at': row[4]
        }

def create_player(giveaway_id, user_id):
    """Створює нового гравця та видає дві карти"""
    deck = create_deck()
    
    # Видаємо дві карти
    card1, deck = deal_card(deck)
    card2, deck = deal_card(deck)
    
    cards = [card1, card2]
    score = calculate_score(cards)
    
    cards_json = json.dumps(cards)
    
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO blackjack_players
            (giveaway_id, user_id, cards, score, status, last_action_at)
            VALUES (?, ?, ?, ?, 'playing', ?)
        """, (giveaway_id, user_id, cards_json, score, int(time.time())))
        con.commit()
    
    return cards, score, deck

def hit_card(giveaway_id, user_id):
    """Видає гравцю ще одну карту"""
    player = get_player(giveaway_id, user_id)
    if not player:
        return None, None, None
    
    if player['status'] != 'playing':
        return None, None, None  # Гравець вже зупинився
    
    # Створюємо нову колоду (в реальності колода спільна, але для простоти створюємо нову)
    deck = create_deck()
    
    # Видаємо карту
    new_card, _ = deal_card(deck)
    
    # Додаємо карту до руки
    cards = player['cards'] + [new_card]
    score = calculate_score(cards)
    
    # Визначаємо статус
    status = 'playing'
    if score > 21:
        status = 'busted'  # Перебір
    elif score == 21:
        status = 'blackjack'  # Блекджек
    
    cards_json = json.dumps(cards)
    
    with _db() as con:
        con.execute("""
            UPDATE blackjack_players
            SET cards = ?, score = ?, status = ?, last_action_at = ?
            WHERE giveaway_id = ? AND user_id = ?
        """, (cards_json, score, status, int(time.time()), giveaway_id, user_id))
        con.commit()
    
    return new_card, score, status

def stand_player(giveaway_id, user_id):
    """Гравець зупиняється (пас)"""
    player = get_player(giveaway_id, user_id)
    if not player:
        return False
    
    if player['status'] != 'playing':
        return False  # Гравець вже зупинився
    
    with _db() as con:
        con.execute("""
            UPDATE blackjack_players
            SET status = 'stood', last_action_at = ?
            WHERE giveaway_id = ? AND user_id = ?
        """, (int(time.time()), giveaway_id, user_id))
        con.commit()
    
    return True

def get_all_players(giveaway_id):
    """Отримує всіх гравців розіграшу"""
    with _db() as con:
        rows = con.execute("""
            SELECT user_id, cards, score, status
            FROM blackjack_players
            WHERE giveaway_id = ?
            ORDER BY score DESC, last_action_at ASC
        """, (giveaway_id,)).fetchall()
        
        players = []
        for row in rows:
            cards = json.loads(row[1]) if row[1] else []
            players.append({
                'user_id': row[0],
                'cards': cards,
                'score': row[2],
                'status': row[3]
            })
        
        return players

def determine_winner(giveaway_id):
    """Визначає переможця блекджека"""
    players = get_all_players(giveaway_id)
    
    if not players:
        return None
    
    # Фільтруємо гравців без перебору
    valid_players = [p for p in players if p['status'] != 'busted']
    
    if not valid_players:
        return None  # Всі з перебором
    
    # Знаходимо найвищий рахунок
    max_score = max(p['score'] for p in valid_players)
    winners = [p for p in valid_players if p['score'] == max_score]
    
    # Якщо кілька гравців з однаковим рахунком - повертаємо першого (або можна зробити поділ призу)
    return winners[0] if winners else None

def finish_blackjack_game(giveaway_id, bot):
    """Завершує гру блекджека та визначає переможця"""
    from database import update_giveaway_status, get_giveaway
    from giveaway_system import award_prize
    import time
    
    giveaway = get_giveaway(giveaway_id)
    if not giveaway:
        return
    
    winner = determine_winner(giveaway_id)
    
    if winner:
        # Нараховуємо приз переможцю
        prize_text = award_prize(giveaway, winner['user_id'])
        
        # Оновлюємо статус розіграшу
        update_giveaway_status(
            giveaway_id,
            'completed',
            winner_id=winner['user_id'],
            completed_at=int(time.time())
        )
        
        # Відправляємо повідомлення про переможця
        try:
            channel_id = giveaway.get('channel_id')
            if channel_id:
                from blackjack_system import format_cards_text
                cards_text = format_cards_text(winner['cards'])
                
                winner_info = bot.get_chat_member(channel_id, winner['user_id'])
                winner_name = winner_info.user.first_name if winner_info.user else "Гравець"
                
                finish_text = (
                    f"🎉 <b>БЛЕКДЖЕК ЗАВЕРШЕНО!</b> 🎉\n\n"
                    f"📌 <b>{giveaway['title']}</b>\n\n"
                    f"🏆 <b>ПЕРЕМОЖЕЦЬ:</b> {winner_name}\n"
                    f"📊 <b>Рахунок:</b> <b>{winner['score']}</b> очок\n"
                    f"🃏 <b>Карти:</b> {cards_text}\n\n"
                    f"🎁 <b>Приз:</b> {prize_text}\n\n"
                    f"✨ <i>Вітаємо переможця!</i> ✨"
                )
                
                bot.send_message(channel_id, finish_text, parse_mode="HTML")
        except Exception as e:
            print(f"[BLACKJACK] Помилка відправки повідомлення про переможця: {e}")
    else:
        # Немає переможця (всі з перебором)
        update_giveaway_status(
            giveaway_id,
            'completed',
            completed_at=int(time.time())
        )
        
        try:
            channel_id = giveaway.get('channel_id')
            if channel_id:
                finish_text = (
                    f"🃏 <b>БЛЕКДЖЕК ЗАВЕРШЕНО</b> 🃏\n\n"
                    f"📌 <b>{giveaway['title']}</b>\n\n"
                    f"❌ <b>Переможця немає</b> — всі гравці з перебором.\n\n"
                    f"💡 Спробуйте в наступному раунді!"
                )
                bot.send_message(channel_id, finish_text, parse_mode="HTML")
        except Exception as e:
            print(f"[BLACKJACK] Помилка відправки повідомлення: {e}")

def format_cards_text(cards):
    """Формує текст для відображення карт"""
    if not cards:
        return "Немає карт"
    return " | ".join([get_card_name(card) for card in cards])

def create_blackjack_post_text(giveaway):
    """Створює текст поста для блекджека"""
    from giveaway_system import format_prize_text
    prize_text = format_prize_text(giveaway)
    
    reactions_count = giveaway['required_reactions']
    reactions_word = "реакцію" if reactions_count == 1 else ("реакції" if reactions_count < 5 else "реакцій")
    
    text = (
        f"🃏 <b>БЛЕКДЖЕК 21</b> 🃏\n\n"
        f"📌 <b>{giveaway['title']}</b>\n"
        f"🎁 <b>Приз:</b> {prize_text}\n\n"
        f"📊 <b>Для запуску:</b> <code>{reactions_count}</code> {reactions_word}\n"
        f"👥 <b>Учасників:</b> Без обмежень\n"
        f"🤖 <b>Умова:</b> Для захисту призу потрібно бути в <a href='tg://resolve?domain=palmaron_bot'>@palmaron_bot</a>\n\n"
        f"💬 <b>Як брати участь:</b>\n"
        f"1️⃣ Поставте <b>реакцію</b> на цей пост\n"
        f"2️⃣ Коли збереться <code>{reactions_count}</code> {reactions_word}, гра <b>запуститься</b>\n"
        f"3️⃣ В обсужденнях коментуйте <b>\"карта\"</b> щоб взяти карту\n"
        f"4️⃣ Коментуйте <b>\"пас\"</b> щоб зупинитися\n"
        f"5️⃣ Найближче до <b>21</b> без перебору — <b>перемагає!</b> 🎯\n\n"
        f"✨ <i>Удачі всім учасникам!</i> ✨"
    )
    return text

def create_blackjack_started_post_text(giveaway):
    """Створює текст поста про початок блекджека"""
    from giveaway_system import format_prize_text
    prize_text = format_prize_text(giveaway)
    
    text = (
        f"🎉 <b>БЛЕКДЖЕК ПОЧАВСЯ!</b> 🎉\n\n"
        f"📌 <b>{giveaway['title']}</b>\n"
        f"🎁 <b>Приз:</b> {prize_text}\n\n"
        f"✅ <b>Потрібна кількість реакцій зібрано!</b>\n\n"
        f"💬 <b>Тепер грайте в обсужденнях!</b>\n"
        f"🃏 Коментуйте <b>\"карта\"</b> щоб взяти карту\n"
        f"🛑 Коментуйте <b>\"пас\"</b> щоб зупинитися\n"
        f"🎯 Найближче до <b>21</b> без перебору — перемагає!\n\n"
        f"⏰ <b>Гра триває...</b>"
    )
    return text

def create_blackjack_status_text(giveaway):
    """Створює текст з поточним станом гри"""
    players = get_all_players(giveaway['id'])
    
    from giveaway_system import format_prize_text
    prize_text = format_prize_text(giveaway)
    
    text = f"🃏 <b>БЛЕКДЖЕК 21</b> 🃏\n\n"
    text += f"📌 <b>{giveaway['title']}</b>\n"
    text += f"🎁 <b>Приз:</b> {prize_text}\n\n"
    
    if players:
        text += f"👥 <b>Гравці ({len(players)}):</b>\n"
        for i, player in enumerate(players[:10], 1):  # Показуємо тільки перших 10
            status_emoji = "🟢" if player['status'] == 'playing' else ("🔴" if player['status'] == 'busted' else "🟡")
            status_text = "Грає" if player['status'] == 'playing' else ("Перебір" if player['status'] == 'busted' else "Зупинився")
            cards_text = format_cards_text(player['cards'])
            text += f"{i}. {status_emoji} <b>{player['score']}</b> очок — {status_text}\n"
            text += f"   🃏 {cards_text}\n"
        
        if len(players) > 10:
            text += f"\n... та ще {len(players) - 10} гравців\n"
    else:
        text += "👥 <b>Гравців:</b> Поки немає\n"
        text += "💬 Коментуйте <b>\"карта\"</b> щоб почати гру!\n"
    
    text += f"\n⏰ <b>Гра триває...</b>"
    
    return text

