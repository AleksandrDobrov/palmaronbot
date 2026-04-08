#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система бустерів для саду
"""

import time
import random
from database import get_active_boosters_grouped, get_booster_price
from garden_models import BOOSTERS

def apply_harvest_boosters(user_id: int, base_fruits: float, tree_type: str, apply_lucky_once: bool = True) -> tuple[float, list]:
    """
    Застосовує активні бустери до збору фруктів
    
    Args:
        user_id: ID користувача
        base_fruits: Базова кількість фруктів
        tree_type: Тип дерева
        apply_lucky_once: Чи застосовувати lucky_harvest тільки один раз
        
    Returns:
        tuple: (кількість фруктів після бустерів, список активних бустерів)
    """
    active_boosters = get_active_boosters_grouped(user_id)
    final_fruits = base_fruits
    applied_boosters = []
    
    for booster_type, expires_at in active_boosters:
        booster_info = next((b for b in BOOSTERS if b['type'] == booster_type), None)
        if not booster_info:
            continue
            
        # Застосовуємо різні типи бустерів
        if booster_type == "double_harvest":
            final_fruits *= 2
            applied_boosters.append(f"⚡ Подвійний врожай (x2)")
            
        elif booster_type == "triple_harvest":
            final_fruits *= 3
            applied_boosters.append(f"🚀 Потрійний врожай (x3)")
            
        elif booster_type == "lucky_harvest" and apply_lucky_once:
            # 30% шанс отримати бонусні фрукти (тільки один раз за збір)
            if random.random() < 0.3:
                bonus = random.randint(1, 3)
                final_fruits += bonus
                applied_boosters.append(f"🍀 Щасливий збір (+{bonus} фруктів)")
    
    return final_fruits, applied_boosters

def apply_speed_growth_boosters(user_id: int, hours: int) -> int:
    """
    Застосовує бустери прискореного росту
    
    Args:
        user_id: ID користувача
        hours: Базова кількість годин
        
    Returns:
        int: Кількість годин після застосування бустерів
    """
    active_boosters = get_active_boosters_grouped(user_id)
    
    for booster_type, expires_at in active_boosters:
        if booster_type == "speed_growth":
            # Фрукти ростуть в 2 рази швидше
            hours *= 2
            break
    
    return hours

def apply_discount_boosters(user_id: int, base_price: float) -> float:
    """
    Застосовує бустери знижки на дерева
    
    Args:
        user_id: ID користувача
        base_price: Базова ціна дерева
        
    Returns:
        float: Ціна після застосування знижки
    """
    active_boosters = get_active_boosters_grouped(user_id)
    
    for booster_type, expires_at in active_boosters:
        if booster_type == "discount_trees":
            # Знижка 50%
            base_price *= 0.5
            break
    
    return base_price

def apply_profit_boosters(user_id: int, base_price: float) -> tuple[float, list]:
    """
    Застосовує бустери збільшення ціни продажу фруктів
    
    Args:
        user_id: ID користувача
        base_price: Базова ціна фрукта
        
    Returns:
        tuple: (ціна після застосування бустера, список застосованих бустерів)
    """
    active_boosters = get_active_boosters_grouped(user_id)
    final_price = base_price
    applied_boosters = []
    
    for booster_type, expires_at in active_boosters:
        booster_info = next((b for b in BOOSTERS if b['type'] == booster_type), None)
        if not booster_info:
            continue
            
        if booster_type == "mega_profit":
            # Збільшує ціну на 100%
            final_price *= 2
            applied_boosters.append(f"💎 {booster_info['name']} (+100% ціни)")
    
    return final_price, applied_boosters

def get_user_active_boosters_info(user_id: int) -> list:
    """
    Повертає інформацію про активні бустери користувача
    
    Args:
        user_id: ID користувача
        
    Returns:
        list: Список активних бустерів з інформацією
    """
    active_boosters = get_active_boosters_grouped(user_id)
    boosters_info = []
    
    for booster_type, expires_at in active_boosters:
        booster_info = next((b for b in BOOSTERS if b['type'] == booster_type), None)
        if not booster_info:
            continue
            
        # Розраховуємо час, що залишився
        now = int(time.time())
        time_left = expires_at - now if expires_at else 0
        hours_left = time_left / 3600
        
        boosters_info.append({
            'type': booster_type,
            'name': booster_info['name'],
            'emoji': booster_info['emoji'],
            'effect': booster_info['effect'],
            'hours_left': hours_left,
            'time_left_seconds': time_left
        })
    
    return boosters_info

def format_booster_info(booster_info: dict) -> str:
    """
    Форматує інформацію про бустер для відображення
    
    Args:
        booster_info: Інформація про бустер
        
    Returns:
        str: Відформатований рядок
    """
    hours = booster_info['hours_left']
    if hours >= 1:
        time_text = f"{hours:.1f}г"
    else:
        minutes = hours * 60
        time_text = f"{minutes:.0f}хв"
    
    return f"{booster_info['emoji']} {booster_info['name']} ({booster_info['effect']}) — {time_text}"

def check_autoharvest_needed(user_id: int) -> bool:
    """
    Перевіряє чи потрібен автоматичний збір для користувача
    
    Args:
        user_id: ID користувача
        
    Returns:
        bool: True якщо потрібен автозбір
    """
    active_boosters = get_active_boosters_grouped(user_id)
    
    for booster_type, expires_at in active_boosters:
        if booster_type == "autoharvest":
            return True
    
    return False

def get_booster_price_with_discount(user_id: int, booster_type: str) -> float:
    """
    Повертає ціну бустера з урахуванням можливих знижок
    
    Args:
        user_id: ID користувача
        booster_type: Тип бустера
        
    Returns:
        float: Ціна бустера
    """
    base_price = get_booster_price(booster_type) or 50.0
    
    # Тут можна додати логіку знижок для VIP користувачів
    # Наприклад, якщо у користувача є VIP статус
    
    active_boosters = get_active_boosters_grouped(user_id)
    for booster_type_active, expires_at in active_boosters:
        if booster_type_active == "vip_status":
            # VIP користувачі отримують знижку 20%
            base_price *= 0.8
            break
    
    return base_price 