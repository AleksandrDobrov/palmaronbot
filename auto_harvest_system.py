#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система автоматичного збору фруктів
"""

import time
import threading
from database import get_active_boosters_grouped, get_user_trees, add_fruit, add_garden_transaction, _db, get_user_garden_level, get_garden_level_info, get_tree_watering_status
from garden_models import TREE_TYPES, FRUITS, get_dynamic_income
from booster_system import apply_harvest_boosters, apply_speed_growth_boosters

class AutoHarvestSystem:
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.running = False
        self.thread = None
        
    def start(self):
        """Запускає систему автоматичного збору"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._auto_harvest_loop, daemon=True)
        self.thread.start()
        print("[AUTO_HARVEST] Auto harvest system started")
        
    def stop(self):
        """Зупиняє систему автоматичного збору"""
        self.running = False
        if self.thread:
            self.thread.join()
        print("[AUTO_HARVEST] Auto harvest system stopped")
        
    def _auto_harvest_loop(self):
        """Основний цикл автоматичного збору"""
        while self.running:
            try:
                self._process_auto_harvest()
                self._process_harvest_reminders()
                # Перевіряємо кожну годину
                time.sleep(3600)
            except Exception as e:
                print(f"[AUTO_HARVEST] Error in auto harvest loop: {e}")
                time.sleep(60)  # Чекаємо хвилину перед повторною спробою
                
    def _process_auto_harvest(self):
        """Обробляє автоматичний збір для всіх користувачів з autoharvest бустером"""
        try:
            import time
            current_time = time.strftime("%H:%M:%S")
            print(f"[AUTO_HARVEST] [{current_time}] Starting auto harvest...")
            
            # Отримуємо користувачів з активним autoharvest бустером
            autoharvest_users = self._get_autoharvest_users()
            print(f"[AUTO_HARVEST] [{current_time}] Found {len(autoharvest_users)} users with auto harvest")
            
            processed_count = 0
            for user_id in autoharvest_users:
                try:
                    result = self._harvest_user_fruits(user_id)
                    if result:
                        processed_count += 1
                except Exception as e:
                    print(f"[AUTO_HARVEST] Harvest error for user {user_id}: {e}")
            
            print(f"[AUTO_HARVEST] [{current_time}] Processed {processed_count} users")
                    
        except Exception as e:
            print(f"[AUTO_HARVEST] Auto harvest processing error: {e}")
            
    def _get_autoharvest_users(self):
        """Повертає список користувачів з активним autoharvest бустером"""
        try:
            with _db() as con:
                now = int(time.time())
                rows = con.execute("""
                    SELECT DISTINCT user_id 
                    FROM boosters 
                    WHERE type = 'autoharvest' AND expires_at > ?
                """, (now,)).fetchall()
                
                return [row[0] for row in rows]
        except Exception as e:
            print(f"[AUTO_HARVEST] Error getting autoharvest users: {e}")
            return []
            
    def _harvest_user_fruits(self, user_id):
        """Збирає фрукти для конкретного користувача"""
        try:
            # Блокуємо автозбір для користувачів без купленого рівня (рівень 0)
            garden_level = get_user_garden_level(user_id)
            if garden_level == 0:
                return False

            # Отримуємо дерева користувача
            trees = get_user_trees(user_id)
            if not trees:
                return
                
            # Отримуємо бонуси від рівня саду
            level_info = get_garden_level_info(garden_level)
            bonus = level_info['bonus_percent'] if level_info else 0
            
            now = int(time.time())
            total_harvest = {f['type']: 0 for f in FRUITS}
            total_base_fruits = {f['type']: 0 for f in FRUITS}
            all_applied_boosters = set()  # Збираємо всі застосовані бустери
            harvested_something = False
            
            for tree in trees:
                ttype = next((t for t in TREE_TYPES if t['type'] == tree['type']), None)
                if not ttype:
                    continue
                    
                last_harvest = tree['last_harvest'] or tree['planted_at'] or now
                hours = (now - last_harvest) // 3600
                
                # Застосовуємо бустери прискореного росту
                original_hours = hours
                hours = apply_speed_growth_boosters(user_id, hours)
                if hours != original_hours:
                    all_applied_boosters.add("🌪️ Прискорений ріст (x2 швидкість)")
                
                # Перевіряємо рівень води
                watering_status = get_tree_watering_status(user_id, tree['type'])
                water_level = watering_status.get('water_level', 100)
                is_withered = watering_status.get('is_withered', False)
                
                # Якщо дерево засохло або рівень води дуже низький, воно не росте
                watering_blocked = is_withered or water_level < 20
                
                if hours >= 1 and not watering_blocked:
                    # Базовий дохід з бонусом від рівня саду
                    from database import get_economy_harvest_multiplier
                    from garden_models import get_effective_tree_income
                    econ_mult = get_economy_harvest_multiplier()
                    income_per_hour = get_effective_tree_income(ttype['type'], econ_mult)
                    base_fruits = hours * income_per_hour
                    bonus_fruits = base_fruits * (bonus / 100) if bonus > 0 else 0
                    fruits_gained = base_fruits + bonus_fruits
                    
                    # Зберігаємо базову кількість для порівняння
                    total_base_fruits[ttype['fruit']] += fruits_gained
                    
                    # Застосовуємо бустери врожаю (lucky_harvest тільки для першого дерева)
                    is_first_tree = tree == trees[0]  # Перше дерево в списку
                    final_fruits, applied_boosters = apply_harvest_boosters(user_id, fruits_gained, tree['type'], apply_lucky_once=is_first_tree)
                    
                    # Додаємо застосовані бустери до загального списку
                    for booster in applied_boosters:
                        all_applied_boosters.add(booster)
                    
                    # Додаємо фрукти
                    add_fruit(user_id, ttype['fruit'], final_fruits)
                    total_harvest[ttype['fruit']] += final_fruits
                    
                    # Оновлюємо час останнього збору
                    with _db() as con:
                        con.execute("UPDATE trees SET last_harvest=? WHERE id=?", (now, tree['id']))
                        con.commit()
                    
                    # Записуємо транзакцію
                    add_garden_transaction(
                        user_id, 
                        "auto_harvest", 
                        final_fruits, 
                        ttype['fruit'], 
                        now, 
                        comment=f"Автозбір з {ttype['name']}"
                    )
                    
                    harvested_something = True
                    
            # Відправляємо повідомлення користувачу, якщо щось зібрали
            if harvested_something:
                self._send_auto_harvest_notification(user_id, total_harvest, total_base_fruits, all_applied_boosters)
                return True
            else:
                return False
                
        except Exception as e:
            print(f"[AUTO_HARVEST] Harvest error for user {user_id}: {e}")
            return False
            
    def _send_auto_harvest_notification(self, user_id, total_harvest, total_base_fruits, all_applied_boosters):
        """Відправляє повідомлення про автоматичний збір з інформацією про бустери"""
        try:
            # Формуємо список зібраних фруктів
            fruit_lines = []
            total_collected = 0
            total_base = 0
            
            for f in FRUITS:
                amount = total_harvest[f['type']]
                base_amount = total_base_fruits[f['type']]
                if amount > 0:
                    total_collected += amount
                    total_base += base_amount
                    
                    # Показуємо різницю між базовою кількістю та фінальною
                    if amount > base_amount:
                        fruit_lines.append(f"├ {f['emoji']} <b>{f['name']}</b> × <b>{amount:.1f}</b> шт <i>(+{amount - base_amount:.1f} від бустерів)</i>")
                    else:
                        fruit_lines.append(f"├ {f['emoji']} <b>{f['name']}</b> × <b>{amount:.1f}</b> шт")
            
            if not fruit_lines:
                return
                
            msg = (
                f"🤖 <b>АВТОМАТИЧНИЙ ЗБІР ЗАВЕРШЕНО!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🍎 <b>ЗІБРАНІ ФРУКТИ:</b>\n"
                + "\n".join(fruit_lines) + 
                f"\n└ 📊 <b>Загалом зібрано:</b> <b>{total_collected:.1f}</b> шт\n"
            )
            
            # Додаємо інформацію про застосовані бустери
            if all_applied_boosters:
                msg += f"\n⚡ <b>ЗАСТОСОВАНІ БУСТЕРИ:</b>\n"
                for booster in sorted(all_applied_boosters):
                    msg += f"├ {booster}\n"
                msg += f"└ 🎯 <b>Бонус від бустерів:</b> <b>+{total_collected - total_base:.1f}</b> фруктів\n"
            
            msg += f"\n💡 <i>Ваш автозбір працює! Фрукти збираються автоматично кожну годину.</i>"
            
            self.bot.send_message(user_id, msg, parse_mode="HTML")
            
        except Exception as e:
            print(f"[AUTO_HARVEST] Error sending message to user {user_id}: {e}")

    # ===== Нагадувач про збір (remind_harvest) =====
    def _get_reminder_users(self):
        try:
            with _db() as con:
                now = int(time.time())
                rows = con.execute(
                    """
                    SELECT DISTINCT user_id
                    FROM boosters
                    WHERE type = 'remind_harvest' AND (expires_at IS NULL OR expires_at > ?)
                    """,
                    (now,)
                ).fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            print(f"[REMIND] Error getting remind_harvest users: {e}")
            return []

    def _is_user_ready_for_harvest(self, user_id: int) -> bool:
        try:
            from database import get_user_trees, get_tree_watering_status, get_user_garden_level
            trees = get_user_trees(user_id)
            if not trees:
                return False
            if get_user_garden_level(user_id) == 0:
                return False
            now = int(time.time())
            for tree in trees:
                last = tree['last_harvest'] or tree['planted_at'] or now
                hours = (now - last) // 3600
                ws = get_tree_watering_status(user_id, tree['type'])
                wl = ws.get('water_level', 100)
                iw = ws.get('is_withered', False)
                if hours >= 1 and not (iw or wl < 20):
                    return True
            return False
        except Exception as e:
            print(f"[REMIND] _is_user_ready_for_harvest error for {user_id}: {e}")
            return False

    def _process_harvest_reminders(self):
        try:
            users = self._get_reminder_users()
            if not users:
                return
            sent = 0
            for uid in users:
                try:
                    if self._is_user_ready_for_harvest(uid):
                        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                        kb = InlineKeyboardMarkup(row_width=1)
                        kb.add(InlineKeyboardButton("🍎 Зібрати фрукти", callback_data="harvest_fruits"))
                        self.bot.send_message(
                            uid,
                            "🔔 <b>Готово до збору!</b> Ваш сад дозрів і дерева політі. Час збирати врожай!",
                            reply_markup=kb,
                            parse_mode="HTML"
                        )
                        sent += 1
                except Exception as e:
                    print(f"[REMIND] Reminder error for {uid}: {e}")
            if sent:

                print(f"[REMIND] Sent reminders: {sent}")
        except Exception as e:
            print(f"[REMIND] General reminder error: {e}")

# Глобальний екземпляр системи
auto_harvest_system = None

def init_auto_harvest_system(bot_instance):
    """Ініціалізує систему автоматичного збору"""
    global auto_harvest_system
    auto_harvest_system = AutoHarvestSystem(bot_instance)
    auto_harvest_system.start()
    return auto_harvest_system

def stop_auto_harvest_system():
    """Зупиняє систему автоматичного збору"""
    global auto_harvest_system
    if auto_harvest_system:
        auto_harvest_system.stop() 