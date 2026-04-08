#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from database import _db
import time

def check_promo_code(code, user_id):
    """
    Проверяет промокод и возвращает информацию о нем.
    
    Args:
        code (str): Промокод для проверки
        user_id (int): ID пользователя
        
    Returns:
        dict: Информация о промокоде или None если не найден/неактивен
    """
    try:
        with _db() as con:
            # Проверяем существование и активность промокода
            cur = con.execute("""
                SELECT id, code, bonus_amount, usage_limit, uses_count, 
                       expires_at, is_active
                FROM promo_codes
                WHERE code = ? AND is_active = 1
            """, (code,))
            promo = cur.fetchone()
            
            if not promo:
                return None
                
            promo_id, code, bonus_amount, usage_limit, uses_count, expires_at, is_active = promo
            
            # Проверяем срок действия
            if expires_at and int(time.time()) > expires_at:
                return None
                
            # Проверяем лимит использований
            if usage_limit and uses_count >= usage_limit:
                return None
            
            # Проверяем использовал ли уже пользователь этот промокод
            cur = con.execute("""
                SELECT 1 FROM promo_usages
                WHERE promo_id = ? AND user_id = ?
            """, (promo_id, user_id))
            if cur.fetchone():
                return None
            
            return {
                'id': promo_id,
                'code': code,
                'bonus_amount': bonus_amount,
                'usage_limit': usage_limit,
                'uses_count': uses_count,
                'expires_at': expires_at
            }
            
    except Exception as e:
        print(f"[ERROR] check_promo_code: {e}")
        return None

def use_promo_code(promo_id, user_id):
    """
    Активирует промокод для пользователя.
    
    Args:
        promo_id (int): ID промокода
        user_id (int): ID пользователя
        
    Returns:
        bool: True если промокод успешно использован
    """
    try:
        with _db() as con:
            # Записываем использование промокода
            con.execute("""
                INSERT INTO promo_usages (promo_id, user_id, used_at)
                VALUES (?, ?, ?)
            """, (promo_id, user_id, int(time.time())))
            
            # Увеличиваем счетчик использований
            con.execute("""
                UPDATE promo_codes 
                SET uses_count = uses_count + 1
                WHERE id = ?
            """, (promo_id,))
            
            con.commit()
            return True
            
    except Exception as e:
        print(f"[ERROR] use_promo_code: {e}")
        return False

def create_promo_code(code, bonus_amount, usage_limit=None, expires_at=None):
    """
    Создает новый промокод.
    
    Args:
        code (str): Промокод
        bonus_amount (float): Размер бонуса
        usage_limit (int, optional): Лимит использований
        expires_at (int, optional): Unix timestamp окончания действия
    
    Returns:
        bool: True если промокод успешно создан
    """
    try:
        with _db() as con:
            con.execute("""
                INSERT INTO promo_codes 
                (code, bonus_amount, usage_limit, expires_at, is_active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (code, bonus_amount, usage_limit, expires_at, int(time.time())))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERROR] create_promo_code: {e}")
        return False

def get_promo_code_info(code):
    """
    Получает информацию о промокоде.
    
    Args:
        code (str): Промокод для проверки
        
    Returns:
        dict: Информация о промокоде или None если не найден
    """
    try:
        with _db() as con:
            cur = con.execute("""
                SELECT id, code, bonus_amount, usage_limit, uses_count,
                       expires_at, is_active, created_at
                FROM promo_codes
                WHERE code = ?
            """, (code,))
            promo = cur.fetchone()
            
            if not promo:
                return None
                
            return {
                'id': promo[0],
                'code': promo[1],
                'bonus_amount': promo[2],
                'usage_limit': promo[3],
                'uses_count': promo[4],
                'expires_at': promo[5],
                'is_active': promo[6],
                'created_at': promo[7]
            }
    except Exception as e:
        print(f"[ERROR] get_promo_code_info: {e}")
        return None

def list_promo_codes(active_only=False):
    """
    Возвращает список промокодов.
    
    Args:
        active_only (bool): Только активные промокоды
    
    Returns:
        list: Список промокодов
    """
    try:
        with _db() as con:
            query = """
                SELECT id, code, bonus_amount, usage_limit, uses_count,
                       expires_at, is_active, created_at
                FROM promo_codes
            """
            if active_only:
                query += " WHERE is_active = 1"
                
            cur = con.execute(query)
            promos = []
            
            for row in cur.fetchall():
                promos.append({
                    'id': row[0],
                    'code': row[1],
                    'bonus_amount': row[2],
                    'usage_limit': row[3],
                    'uses_count': row[4],
                    'expires_at': row[5],
                    'is_active': row[6],
                    'created_at': row[7]
                })
                
            return promos
    except Exception as e:
        print(f"[ERROR] list_promo_codes: {e}")
        return []

def deactivate_promo_code(code):
    """
    Деактивирует промокод.
    
    Args:
        code (str): Промокод для деактивации
        
    Returns:
        bool: True если промокод успешно деактивирован
    """
    try:
        with _db() as con:
            con.execute("""
                UPDATE promo_codes
                SET is_active = 0
                WHERE code = ?
            """, (code,))
            con.commit()
            return True
    except Exception as e:
        print(f"[ERROR] deactivate_promo_code: {e}")
        return False
