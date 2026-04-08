#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Мониторинг реакций и комментариев для системы розыгрышей
"""

import time
import threading
import json
import re
from database import (
    get_giveaway, update_giveaway_status, add_giveaway_participant,
    get_giveaway_participants, get_user_emoji_count
)
from giveaway_system import process_giveaway_777, award_prize

# Словарь для хранения активных мониторингов
_active_monitors = {}
_monitor_lock = threading.Lock()

# Значение Telegram dice для выпадения 777 в слот-машине
TELEGRAM_SLOT_JACKPOT_VALUE = 64

def has_emoji(text):
    """Проверяет, содержит ли текст эмодзи"""
    if not text:
        return False
    # Паттерн для эмодзи (Unicode ranges для эмодзи)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs (включая 🎰 U+1F3B0)
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))

def count_emojis(text):
    """Подсчитывает количество эмодзи в тексте
    
    Возвращает количество найденных эмодзи (каждое эмодзи считается отдельно).
    Например: "🎰🎰🎰" = 3 эмодзи
    """
    if not text:
        return 0
    
    # Расширенный паттерн для эмодзи (Unicode ranges)
    # Включает все основные диапазоны эмодзи
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs (включая 🎰 U+1F3B0)
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"   # dingbats
        "\U000024C2-\U0001F251"   # enclosed characters
        "\U0001F900-\U0001F9FF"   # supplemental symbols
        "\U0001FA00-\U0001FA6F"   # chess symbols
        "\U0001FA70-\U0001FAFF"   # symbols and pictographs extended-A
        "\U00002600-\U000026FF"   # miscellaneous symbols
        "\U00002700-\U000027BF"   # dingbats
        "]+",
        flags=re.UNICODE
    )
    
    # Находим все последовательности эмодзи в тексте
    emoji_matches = emoji_pattern.finditer(text)
    
    # Подсчитываем количество отдельных эмодзи
    # Для большинства эмодзи один символ = одно эмодзи
    # Но некоторые эмодзи (флаги, составные) могут состоять из нескольких символов
    count = 0
    for match in emoji_matches:
        emoji_text = match.group()
        # Для большинства эмодзи считаем каждый символ отдельно
        # Но если это флаг (2 символа) - считаем как 1 эмодзи
        if len(emoji_text) >= 2 and '\U0001F1E0' <= emoji_text[0] <= '\U0001F1FF':
            # Это флаг - считаем как одно эмодзи
            count += 1
        else:
            # Обычные эмодзи - считаем каждый символ отдельно
            count += len(emoji_text)
    
    return count

def start_giveaway_monitoring(giveaway_id, bot):
    """Запускает мониторинг розыгрыша"""
    with _monitor_lock:
        if giveaway_id in _active_monitors:
            print(f"[INFO] Мониторинг для розыгрыша #{giveaway_id} уже запущен")
            return
        
        giveaway = get_giveaway(giveaway_id)
        if not giveaway or giveaway['status'] != 'active':
            print(f"[WARNING] Розыгрыш #{giveaway_id} не активен, мониторинг не запущен")
            return
        
        # Создаем поток для мониторинга
        monitor_thread = threading.Thread(
            target=_monitor_giveaway,
            args=(giveaway_id, bot),
            daemon=True
        )
        monitor_thread.start()
        _active_monitors[giveaway_id] = {
            'thread': monitor_thread,
            'started_at': time.time()
        }
        print(f"[INFO] Мониторинг для розыгрыша #{giveaway_id} запущен")

def stop_giveaway_monitoring(giveaway_id):
    """Останавливает мониторинг розыгрыша"""
    with _monitor_lock:
        if giveaway_id in _active_monitors:
            del _active_monitors[giveaway_id]
            print(f"[INFO] Мониторинг для розыгрыша #{giveaway_id} остановлен")

def update_reactions_from_channel(giveaway_id, bot):
    """
    Пытается автоматически обновить счетчик реакций из канала.
    Возвращает новое количество реакций или None если не удалось.
    """
    try:
        giveaway = get_giveaway(giveaway_id)
        if not giveaway:
            return None
        
        channel_id = giveaway.get('channel_id')
        post_message_id = giveaway.get('post_message_id')
        
        if not channel_id or not post_message_id:
            return None
        
        # Способ 1: Попытка использовать forward_message для получения актуальной информации
        # Но это не работает для получения реакций напрямую
        
        # Способ 2: Использование getUpdates с фильтрацией (требует настройки)
        # Но это polling и не очень эффективно
        
        # Способ 3: Webhook (требует настройки сервера) - самый надежный способ
        
        # Способ 4: Попытка получить сообщение через методы API
        # В pyTelegramBotAPI нет прямого метода для получения реакций
        # Но можно попробовать использовать методы библиотеки
        
        try:
            # Пробуем получить информацию о сообщении
            # Это может не сработать для реакций, но попробуем
            try:
                # В новых версиях pyTelegramBotAPI может быть метод для получения сообщения
                # Но пока его нет, используем альтернативный подход
                
                # Попытка через forward в канал бота (если есть)
                # Но это не даст реакции
                
                # Лучшее решение - использовать webhook или ручное обновление
                # Пока возвращаем None, что означает что автоматическое обновление недоступно
                return None
                
            except AttributeError:
                # Метод не существует
                return None
                
        except Exception as e:
            print(f"[DEBUG] Не удалось получить реакции через API: {e}")
            return None
            
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке реакций: {e}")
        return None

def _check_reactions_count(giveaway_id, bot):
    """Пытается получить актуальное количество реакций из канала"""
    return update_reactions_from_channel(giveaway_id, bot)

def _monitor_giveaway(giveaway_id, bot):
    """Основной цикл мониторинга"""
    check_counter = 0  # Счетчик для периодической проверки
    while True:
        try:
            giveaway = get_giveaway(giveaway_id)
            if not giveaway:
                stop_giveaway_monitoring(giveaway_id)
                break
            
            # Если розыгрыш завершен или отменен, останавливаем мониторинг
            if giveaway['status'] not in ['active', 'pending']:
                stop_giveaway_monitoring(giveaway_id)
                break
            
            # Проверяем количество реакций
            if giveaway['status'] in ['active', 'pending']:
                # Перевіряємо, чи вже створений пост про початок
                started_post_id = giveaway.get('started_post_message_id')
                
                if not started_post_id:
                    # Пост про початок ще не створено - перевіряємо реакції
                    # Пробуем получить актуальное количество реакций через API
                    check_counter += 1
                    if check_counter >= 2:  # Каждые 2 проверки (1 минута) проверяем реакции
                        check_counter = 0
                        try:
                            channel_id = giveaway.get('channel_id')
                            post_message_id = giveaway.get('post_message_id')
                            
                            # Автоматическое обновление реакций через API недоступно
                            # Используем счетчик из БД, который обновляется через обработчик событий
                            # или вручную через админку
                        except Exception as e:
                            print(f"[WARNING] Ошибка при периодической проверке реакций: {e}")
                    
                    # Проверяем текущий счетчик реакций (обновляется через обработчик событий или вручную)
                    reactions_count = giveaway.get('reactions_count', 0)
                    required_reactions = giveaway.get('required_reactions', 0)
                    
                    print(f"[DEBUG] Мониторинг розыгрыша #{giveaway_id}: reactions_count={reactions_count}, required={required_reactions}, started_post_id={started_post_id}")
                    
                    # АВТОМАТИЧЕСКИЙ ЗАПУСК: если счетчик обновлен (вручную или через события) и достигнут лимит
                    if reactions_count >= required_reactions and required_reactions > 0 and not started_post_id:
                        # Запускаем розыгрыш 777 - створюємо пост про початок
                        print(f"[INFO] ✅✅✅ Розыгрыш #{giveaway_id}: достигнуто {reactions_count}/{required_reactions} реакций, ЗАПУСКАЕМ АВТОМАТИЧЕСКИ!")
                        try:
                            _process_giveaway_activation(giveaway_id, bot)
                            print(f"[INFO] ✅ Розыгрыш #{giveaway_id} успешно запущен автоматически")
                        except Exception as e:
                            print(f"[ERROR] ❌ Ошибка при автозапуске розыгрыша #{giveaway_id}: {e}")
                            import traceback
                            traceback.print_exc()
                        # Продолжаем мониторинг для отслеживания комментариев
                else:
                    # Пост про початок вже створено - продовжуємо моніторинг
                    # Для блекджека перевіряємо чи потрібно завершити гру
                    game_type = giveaway.get('game_type', '777')
                    if game_type == 'blackjack':
                        # Перевіряємо чи всі гравці зупинилися або минув час
                        from blackjack_system import get_all_players
                        import time
                        players = get_all_players(giveaway_id)
                        
                        if players:
                            # Перевіряємо чи всі гравці зупинилися
                            all_stopped = all(p['status'] in ['stood', 'busted', 'blackjack'] for p in players)
                            
                            # Перевіряємо чи минув час (10 хвилин після старту)
                            time_elapsed = int(time.time()) - (giveaway.get('started_at', 0) or giveaway.get('created_at', 0))
                            time_limit = 600  # 10 хвилин
                            
                            if all_stopped or time_elapsed >= time_limit:
                                # Завершуємо гру
                                from blackjack_system import finish_blackjack_game
                                finish_blackjack_game(giveaway_id, bot)
                                print(f"[INFO] Блекджек #{giveaway_id} завершено")
                                break  # Виходимо з циклу моніторингу
                    
                    # Коментарі обробляються через message handler в bot.py
                    pass
            
            # Ждем перед следующей проверкой
            time.sleep(30)  # Проверяем каждые 30 секунд
            
        except Exception as e:
            print(f"[ERROR] Ошибка в мониторинге розыгрыша #{giveaway_id}: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)  # При ошибке ждем дольше

def check_bot_access_to_discussion_group(channel_id, bot):
    """
    Проверяет, имеет ли бот доступ к группе обсуждения канала.
    Возвращает True если доступ есть, False если нет.
    
    ВАЖНО: Бот может работать как обычный участник (member), админка не обязательна!
    """
    try:
        # Пытаемся получить информацию о канале
        chat = bot.get_chat(channel_id)
        
        # Проверяем, есть ли у канала связанная группа обсуждения
        if hasattr(chat, 'linked_chat_id') and chat.linked_chat_id:
            discussion_group_id = chat.linked_chat_id
            try:
                # Пытаемся получить информацию о боте в группе обсуждения
                bot_member = bot.get_chat_member(discussion_group_id, bot.get_me().id)
                if bot_member.status in ['member', 'administrator', 'creator']:
                    status_text = "администратором" if bot_member.status in ['administrator', 'creator'] else "участником"
                    print(f"[INFO] Бот имеет доступ к группе обсуждения {discussion_group_id} (как {status_text})")
                    return True
                else:
                    print(f"[WARNING] Бот не является участником группы обсуждения {discussion_group_id}")
                    print(f"[WARNING] Добавьте бота в группу обсуждения как обычного участника (админка не обязательна)")
                    return False
            except Exception as e:
                print(f"[WARNING] Не удалось проверить доступ бота к группе обсуждения: {e}")
                print(f"[WARNING] Убедитесь, что бот добавлен в группу обсуждения канала {channel_id}")
                print(f"[WARNING] Админка НЕ обязательна - достаточно добавить бота как обычного участника")
                return False
        else:
            # У канала нет связанной группы обсуждения
            print(f"[WARNING] У канала {channel_id} нет связанной группы обсуждения")
            print(f"[WARNING] Для работы с комментариями необходимо создать и привязать группу обсуждения")
            return False
    except Exception as e:
        print(f"[WARNING] Не удалось проверить доступ к группе обсуждения: {e}")
        return False

def _process_giveaway_activation(giveaway_id, bot):
    """Обрабатывает активацию розыгрыша (когда собрано достаточно реакций)"""
    try:
        giveaway = get_giveaway(giveaway_id)
        if not giveaway or giveaway['status'] != 'active':
            return
        
        channel_id = giveaway['channel_id']
        post_message_id = giveaway['post_message_id']
        
        if not channel_id or not post_message_id:
            print(f"[ERROR] Розыгрыш #{giveaway_id}: нет channel_id или post_message_id")
            return
        
        # Перевіряємо, чи вже був створений пост про початок
        # Якщо є started_post_message_id - значить вже запущено
        if giveaway.get('started_post_message_id'):
            print(f"[INFO] Розыгрыш #{giveaway_id}: уже запущен, пост про початок вже створено")
            return
        
        # Проверяем доступ бота к группе обсуждения (для предупреждения)
        print(f"[INFO] Розыгрыш #{giveaway_id}: проверка доступа к группе обсуждения...")
        has_access = check_bot_access_to_discussion_group(channel_id, bot)
        if not has_access:
            print(f"[WARNING] ⚠️ ВАЖНО: Бот может не получать комментарии из группы обсуждения!")
            print(f"[WARNING] Убедитесь, что:")
            print(f"[WARNING] 1. У канала есть связанная группа обсуждения")
            print(f"[WARNING] 2. Бот добавлен в группу обсуждения (как обычный участник)")
            print(f"[WARNING] 3. Админка НЕ обязательна - бот работает и как участник!")
            print(f"[WARNING] Если у вас спам-блок, просто добавьте бота в группу - этого достаточно")
            print(f"[WARNING] См. GIVEAWAY_SETUP_INSTRUCTIONS.md для подробностей")
        
        # Створюємо новий пост про початок розіграшу
        game_type = giveaway.get('game_type', '777')
        if game_type == 'blackjack':
            from blackjack_system import create_blackjack_started_post_text
            started_post_text = create_blackjack_started_post_text(giveaway)
        else:
            from giveaway_system import create_giveaway_started_post_text
            started_post_text = create_giveaway_started_post_text(giveaway)
        
        try:
            started_post = bot.send_message(
                channel_id,
                started_post_text,
                parse_mode="HTML"
            )
            
            # Зберігаємо ID нового поста в БД
            update_giveaway_status(
                giveaway_id,
                'active',
                started_post_message_id=started_post.message_id
            )
            
            print(f"[INFO] Розыгрыш #{giveaway_id}: создан пост про початок (message_id: {started_post.message_id})")
            if not has_access:
                print(f"[WARNING] Комментарии под этим постом могут не обрабатываться из-за отсутствия доступа к группе обсуждения!")
            
        except Exception as e:
            print(f"[ERROR] Не удалось создать пост про початок: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Тепер відстежуємо коментарі під новим постом
        # Механіка 777 буде запущена автоматично коли хтось виб'є 777
        # або після закінчення часу (якщо додамо таймер)
            
    except Exception as e:
        print(f"[ERROR] Ошибка при активации розыгрыша #{giveaway_id}: {e}")
        import traceback
        traceback.print_exc()

def _complete_giveaway(giveaway_id, winner_ids, bot):
    """Завершает розыгрыш и начисляет приз. winner_ids может быть int (один победитель) или list (несколько победителей)"""
    import time
    try:
        # Нормализуем winner_ids в список
        if isinstance(winner_ids, int):
            winner_ids = [winner_ids]
        elif not isinstance(winner_ids, list):
            print(f"[ERROR] winner_ids должен быть int или list, получен {type(winner_ids)}")
            return
        
        print(f"[INFO] ===== ЗАВЕРШЕНИЕ РОЗЫГРЫША #{giveaway_id} =====")
        print(f"[INFO] Победители: {winner_ids}")
        
        from database import get_giveaway, update_giveaway_status, get_user
        from giveaway_system import award_prize, create_giveaway_post_text
        
        giveaway = get_giveaway(giveaway_id)
        if not giveaway:
            print(f"[ERROR] Розыгрыш #{giveaway_id} не найден")
            return
        
        # Проверяем, не завершен ли уже розыгрыш
        if giveaway['status'] == 'completed':
            print(f"[WARNING] Розыгрыш #{giveaway_id} уже завершен. Победитель: {giveaway.get('winner_id')}")
            return
        
        # Перевірка: менеджер не може бути переможцем свого розіграшу
        from database import is_giveaway_manager, is_admin
        creator_id = giveaway.get('created_by')
        
        # Фільтруємо менеджерів зі списку переможців (якщо вони не повні адміни)
        valid_winner_ids = []
        for winner_id in winner_ids:
            # Якщо переможець - це менеджер, який створив розіграш, і він не повний адмін - пропускаємо
            if creator_id and winner_id == creator_id:
                if is_giveaway_manager(winner_id) and not is_admin(winner_id):
                    print(f"[WARNING] Менеджер {winner_id} не може бути переможцем свого розіграшу! Пропускаємо.")
                    continue
            valid_winner_ids.append(winner_id)
        
        if not valid_winner_ids:
            print(f"[ERROR] Після фільтрації не залишилось валідних переможців!")
            # Відправляємо повідомлення про помилку
            try:
                channel_id = giveaway.get('channel_id')
                if channel_id:
                    bot.send_message(channel_id, 
                        f"⚠️ <b>ПОМИЛКА РОЗІГРАШУ</b>\n\n"
                        f"📌 <b>{giveaway['title']}</b>\n\n"
                        f"❌ Неможливо визначити переможця через конфлікт інтересів.\n"
                        f"Розіграш скасовано.",
                        parse_mode="HTML"
                    )
            except Exception:
                pass
            return
        
        # Начисляем призы всем победителям
        prize_infos = []
        winners_info = []
        
        for winner_id in valid_winner_ids:
            print(f"[INFO] Начисляем приз победителю {winner_id}...")
            try:
                prize_info = award_prize(giveaway, winner_id)
                if prize_info:
                    prize_infos.append(prize_info)
                    # Получаем информацию о победителе
                    user = get_user(winner_id)
                    if user and isinstance(user, tuple) and len(user) > 1:
                        winner_name = user[1] if user[1] else 'Неизвестно'
                        winner_username_db = user[8] if len(user) > 8 and user[8] else None
                    elif user and isinstance(user, dict):
                        winner_name = user.get('user_name', 'Неизвестно')
                        winner_username_db = user.get('username')
                    else:
                        winner_name = 'Неизвестно'
                        winner_username_db = None
                    
                    winners_info.append({
                        'id': winner_id,
                        'name': winner_name,
                        'username': winner_username_db,
                        'prize': prize_info
                    })
                    print(f"[INFO] Приз начислен победителю {winner_id}: {prize_info}")
                else:
                    print(f"[ERROR] Не удалось начислить приз для победителя {winner_id}")
            except Exception as e:
                print(f"[ERROR] Ошибка при начислении приза для победителя {winner_id}: {e}")
                import traceback
                traceback.print_exc()
        
        if not prize_infos:
            print(f"[ERROR] Не удалось начислить призы ни одному победителю")
            return
        
        # Обновляем статус (сохраняем первого победителя в winner_id для обратной совместимости)
        print(f"[INFO] Обновляем статус розыгрыша на 'completed'...")
        update_giveaway_status(
            giveaway_id,
            'completed',
            winner_id=winner_ids[0] if winner_ids else None,
            completed_at=int(time.time())
        )
        print(f"[INFO] Статус обновлен")
        
        # Отправляем сообщение в канал
        channel_id = giveaway.get('channel_id')
        if channel_id:
            try:
                # Формируем список победителей для отображения
                winners_text_list = []
                for winner_info in winners_info:
                    winner_id = winner_info['id']
                    winner_name = winner_info['name']
                    winner_username_db = winner_info['username']
                    
                    # Всегда используем диплинк вместо @username
                    winner_display_name = winner_name or (f"@{winner_username_db}" if winner_username_db else f"User {winner_id}")
                    winner_username_text = f"<a href='tg://user?id={winner_id}'>{winner_display_name}</a>"
                    
                    winners_text_list.append(f"👤 {winner_username_text}")
                
                # Форматируем приз для отображения (берем первый, так как все одинаковые)
                prize_info = prize_infos[0] if prize_infos else "Приз"
                prize_display = prize_info
                if prize_info.startswith("💰"):
                    import re
                    prize_amount_match = re.search(r'(\d+(?:\.\d+)?)₴', prize_info)
                    if prize_amount_match:
                        prize_amount = prize_amount_match.group(1)
                        prize_display = f"{prize_amount}₴ на баланс"
                    else:
                        prize_display = prize_info.replace("💰", "").strip() + " на баланс"
                
                if len(winners_info) == 1:
                    winner_text = (
                        f"🏆 <b>МАЄМО ПЕРЕМОЖЦЯ!</b> 🏆\n\n"
                        f"🎉 <b>У грі \"777\" переміг:</b>\n"
                        f"{winners_text_list[0]} 🔥\n\n"
                        f"🎁 <b>Приз:</b> {prize_display}\n\n"
                        f"✨ <b>Вітаємо переможця!</b> ✨"
                    )
                else:
                    winner_text = (
                        f"🏆 <b>МАЄМО ПЕРЕМОЖЦІВ!</b> 🏆\n\n"
                        f"🎉 <b>У грі \"777\" перемогли:</b>\n"
                        f"{chr(10).join(winners_text_list)} 🔥\n\n"
                        f"🎁 <b>Приз:</b> {prize_display}\n\n"
                        f"✨ <b>Вітаємо переможців!</b> ✨"
                    )
                print(f"[INFO] Отправляем сообщение о победителях в канал {channel_id}...")
                sent_msg = bot.send_message(channel_id, winner_text, parse_mode="HTML")
                print(f"[INFO] ✅ Сообщение о победителях отправлено в канал (message_id={sent_msg.message_id})")
            except Exception as e:
                print(f"[ERROR] Не удалось отправить сообщение в канал {channel_id}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[WARNING] channel_id не указан для розыгрыша #{giveaway_id}")
        
        # Отправляем личные сообщения всем победителям
        for winner_info in winners_info:
            winner_id = winner_info['id']
            prize_info = winner_info['prize']
            try:
                print(f"[INFO] Отправляем личное сообщение победителю {winner_id}...")
                bot.send_message(
                    winner_id,
                    f"🎉 <b>ВІТАЄМО!</b> 🎉\n\n"
                    f"Ви виграли в розіграші:\n"
                    f"📌 <b>{giveaway['title']}</b>\n\n"
                    f"🎁 <b>Ваш приз:</b> {prize_info}\n\n"
                    f"Приз вже нараховано на ваш рахунок!",
                    parse_mode="HTML"
                )
                print(f"[INFO] ✅ Личное сообщение отправлено победителю {winner_id}")
            except Exception as e:
                print(f"[ERROR] Не удалось отправить сообщение победителю {winner_id}: {e}")
                import traceback
                traceback.print_exc()
        
        # Останавливаем мониторинг
        stop_giveaway_monitoring(giveaway_id)
        
        winners_names = ", ".join([w['name'] for w in winners_info])
        print(f"[INFO] ✅ Розыгрыш #{giveaway_id} успешно завершен, победители: {winners_names}")
        print(f"[INFO] ===== КОНЕЦ ЗАВЕРШЕНИЯ РОЗЫГРЫША =====")
        
    except Exception as e:
        print(f"[ERROR] КРИТИЧЕСКАЯ ОШИБКА при завершении розыгрыша #{giveaway_id}: {e}")
        import traceback
        traceback.print_exc()

def handle_message_reaction(giveaway_id, user_id, reaction_type, bot, reaction_delta=1, absolute_count=None):
    """Обрабатывает реакцию на пост розыгрыша.

    :param reaction_delta: насколько увеличить (или уменьшить) счетчик реакций.
    :param absolute_count: если указано, устанавливает счетчик реакций в это значение.
    """
    try:
        giveaway = get_giveaway(giveaway_id)
        if not giveaway:
            return
        
        # Обновляем счетчик реакций
        current_count = giveaway.get('reactions_count', 0)
        if absolute_count is not None:
            new_count = max(0, int(absolute_count))
        else:
            delta = reaction_delta if reaction_delta is not None else 0
            new_count = max(0, current_count + int(delta))

        print(f"[INFO] Розыгрыш #{giveaway_id}: реакции {current_count} -> {new_count} (reaction_type={reaction_type}, user_id={user_id})")

        # Сохраняем счётчик, не меняя статус (pending/active остаётся как есть)
        update_giveaway_status(
            giveaway_id,
            giveaway['status'],
            reactions_count=new_count
        )
        updated_giveaway = get_giveaway(giveaway_id)
        
        # Обновляем пост в канале (опционально)
        channel_id = updated_giveaway['channel_id'] if updated_giveaway else giveaway['channel_id']
        post_message_id = updated_giveaway['post_message_id'] if updated_giveaway else giveaway['post_message_id']
        
        if channel_id and post_message_id:
            try:
                from giveaway_system import create_giveaway_post_text
                # Получаем обновленные данные розыгрыша
                if updated_giveaway:
                    # Создаем новый текст с актуальным счетчиком
                    reactions_count = updated_giveaway.get('reactions_count', new_count)
                    required_reactions = updated_giveaway['required_reactions']
                    
                    # Создаем текст поста заново
                    prize_text = ""
                    from giveaway_system import format_prize_text
                    prize_data = {
                        'prize_type': updated_giveaway['prize_type'],
                        'prize_value': updated_giveaway['prize_value'],
                        'prize_extra': updated_giveaway.get('prize_extra')
                    }
                    prize_text = format_prize_text(prize_data)
                    
                    updated_text = (
                        f"🎁 <b>РОЗЫГРЫШ!</b> 🎁\n\n"
                        f"📌 <b>{updated_giveaway['title']}</b>\n\n"
                        f"🎁 <b>Приз:</b> {prize_text}\n\n"
                        f"📊 <b>Для запуска нужно:</b> {required_reactions} реакций\n\n"
                        f"💬 <b>Как участвовать:</b>\n"
                        f"1. Поставьте реакцию на этот пост\n"
                        f"2. Когда соберется {required_reactions} реакций, розыгрыш запустится\n"
                        f"3. Отправьте эмодзи в комментариях\n"
                        f"4. Кто первый выбьет 777 - побеждает!"
                    )
                    
                    bot.edit_message_text(
                        updated_text,
                        chat_id=channel_id,
                        message_id=post_message_id,
                        parse_mode="HTML"
                    )
            except Exception as e:
                print(f"[WARNING] Не удалось обновить пост: {e}")
        
        # Проверяем, нужно ли запускать розыгрыш автоматически
        if updated_giveaway:
            reactions_count = updated_giveaway.get('reactions_count', new_count)
            required_reactions = updated_giveaway.get('required_reactions', 0)
            started_post_id = updated_giveaway.get('started_post_message_id')
            
            print(f"[DEBUG] Проверка автозапуска: reactions_count={reactions_count}, required_reactions={required_reactions}, started_post_id={started_post_id}")
            print(f"[DEBUG] Условия: required_reactions={bool(required_reactions)}, reactions_count >= required_reactions={reactions_count >= required_reactions if required_reactions else False}, not started_post_id={not started_post_id}")
            
            if required_reactions and reactions_count >= required_reactions and not started_post_id:
                print(f"[INFO] ✅ Розыгрыш #{giveaway_id}: достигнуто {reactions_count}/{required_reactions} реакций (auto trigger)")
                try:
                    _process_giveaway_activation(giveaway_id, bot)
                    print(f"[INFO] ✅ _process_giveaway_activation вызвана для розыгрыша #{giveaway_id}")
                except Exception as e:
                    print(f"[ERROR] Не удалось автоматически запустить розыгрыш #{giveaway_id}: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[DEBUG] Автозапуск не выполнен: required_reactions={required_reactions}, reactions_count={reactions_count}, started_post_id={started_post_id}")

    except Exception as e:
        print(f"[ERROR] Ошибка при обработке реакции: {e}")
        import traceback
        traceback.print_exc()

def handle_comment(giveaway_id, user_id, comment_id, comment_text, bot, dice=None):
    """Обрабатывает комментарий или бросок слот-машины под постом розыгрыша
    
    - Если передан результат слот-машины (dice с emoji 🎰), проверяем значение броска.
      Победитель определяется только при выпадении комбинации 777 (значение 64).
    - Для текстовых комментариев продолжает работать проверка эмодзи/строки '777'.
    """
    try:
        print(f"[DEBUG] handle_comment вызвана: giveaway_id={giveaway_id}, user_id={user_id}, comment_id={comment_id}, text='{comment_text}', dice_present={dice is not None}")
        
        giveaway = get_giveaway(giveaway_id)
        if not giveaway:
            print(f"[ERROR] Розыгрыш #{giveaway_id} не найден")
            return
        
        if giveaway['status'] != 'active':
            print(f"[INFO] Розыгрыш #{giveaway_id} не активен (статус: {giveaway['status']})")
            return
        
        # Перевіряємо, чи вже створений пост про початок розіграшу
        # Коментарі обробляються тільки після створення поста про початок
        if not giveaway.get('started_post_message_id'):
            print(f"[INFO] Розыгрыш #{giveaway_id}: комментарий проигнорирован, пост про початок ще не створено")
            return
        
        # Обработка броска слот-машины (dice emoji 🎰)
        slot_dice = dice if dice and getattr(dice, 'emoji', None) == '🎰' else None
        if slot_dice:
            slot_value = getattr(slot_dice, 'value', None)
            print(f"[DEBUG] Получен бросок слот-машины: value={slot_value} (user_id={user_id})")

            if slot_value is None:
                print(f"[WARNING] Невозможно определить значение slot dice для пользователя {user_id}")
                return

            # Сохраняем попытку в БД (random_number - фактическое значение броска)
            stored_value = 777 if slot_value == TELEGRAM_SLOT_JACKPOT_VALUE else slot_value
            add_giveaway_participant(
                giveaway_id,
                user_id,
                comment_id=comment_id,
                random_number=stored_value
            )

            if slot_value == TELEGRAM_SLOT_JACKPOT_VALUE:
                print(f"[INFO] 🎉🎉🎉 УЧАСТНИК {user_id} ВЫБИЛ 777 (dice value {slot_value})! Завершаем розыгрыш...")
                if giveaway['status'] == 'active' and not giveaway.get('winner_id'):
                    try:
                        _complete_giveaway(giveaway_id, user_id, bot)
                        print(f"[INFO] ✅ Розыгрыш #{giveaway_id} завершен для победителя {user_id}")
                    except Exception as e:
                        print(f"[ERROR] ❌ КРИТИЧЕСКАЯ ОШИБКА при завершении розыгрыша: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[INFO] Розыгрыш уже завершен или имеет победителя")
            else:
                print(f"[INFO] Участник {user_id} бросил слот ({slot_value}), но 777 не выпало")
            return

        # Проверка текстовых комментариев (эмодзи или строка "777")
        has_emoji_in_text = has_emoji(comment_text) if comment_text else False
        has_777_in_text = '777' in (comment_text or '')

        if not has_emoji_in_text and not has_777_in_text:
            print(f"[DEBUG] Комментарий от {user_id} не содержит эмодзи или '777', пропускаем. Текст: '{comment_text}'")
            return

        emoji_count_in_comment = count_emojis(comment_text)
        print(f"[DEBUG] Комментарий от {user_id} содержит {emoji_count_in_comment} эмодзи, наличие '777': {has_777_in_text}")

        if has_777_in_text:
            # Если пользователь явно написал 777 - считаем это победой
            add_giveaway_participant(
                giveaway_id,
                user_id,
                comment_id=comment_id,
                random_number=777
            )
            print(f"[INFO] 🎰 В комментарии найдено '777'! Проверяем завершение розыгрыша")
            if giveaway['status'] == 'active' and not giveaway.get('winner_id'):
                try:
                    _complete_giveaway(giveaway_id, user_id, bot)
                    print(f"[INFO] ✅ Розыгрыш #{giveaway_id} завершен для победителя {user_id}")
                except Exception as e:
                    print(f"[ERROR] ❌ КРИТИЧЕСКАЯ ОШИБКА при завершении розыгрыша: {e}")
                    import traceback
                    traceback.print_exc()
            return

        if emoji_count_in_comment == 0:
            print(f"[DEBUG] В комментарии от {user_id} не найдено эмодзи (возможно ошибка парсинга). Текст: '{comment_text}'")
            return

        # Добавляем эмодзи из текущего комментария к счетчику пользователя
        current_emoji_count = get_user_emoji_count(giveaway_id, user_id)
        add_giveaway_participant(
            giveaway_id,
            user_id,
            comment_id=comment_id,
            emoji_count=emoji_count_in_comment
        )

        new_emoji_count = get_user_emoji_count(giveaway_id, user_id)
        print(f"[INFO] ✅ Пользователь {user_id}: было {current_emoji_count}, добавлено {emoji_count_in_comment}, стало {new_emoji_count}")

        if new_emoji_count == 777:
            print(f"[INFO] 🎉🎉🎉 УЧАСТНИК {user_id} ДОСТИГ ТОЧНО 777 ЭМОДЗИ! Завершаем розыгрыш...")
            if giveaway['status'] == 'active' and not giveaway.get('winner_id'):
                try:
                    _complete_giveaway(giveaway_id, user_id, bot)
                    print(f"[INFO] ✅ _complete_giveaway успешно выполнена")
                except Exception as e:
                    print(f"[ERROR] ❌ КРИТИЧЕСКАЯ ОШИБКА при вызове _complete_giveaway: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[INFO] Розыгрыш уже завершен или имеет победителя")
        elif new_emoji_count > 777:
            print(f"[INFO] Пользователь {user_id} превысил 777 эмодзи ({new_emoji_count}), но это не победа (нужно точно 777)")
        else:
            print(f"[INFO] Пользователь {user_id} имеет {new_emoji_count} эмодзи, нужно 777 для победы")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при обработке комментария: {e}")
        import traceback
        traceback.print_exc()

def get_active_monitors():
    """Возвращает список активных мониторингов"""
    with _monitor_lock:
        return list(_active_monitors.keys())

