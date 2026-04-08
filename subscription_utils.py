"""
Утиліти для роботи з підписками та обмеженням доступу.
"""
from functools import wraps
from telebot import types
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_subscription_guards(bot):
    """
    Застосовує перевірку підписки до всіх обробників повідомлень та колбеків.
    
    Args:
        bot: Екземпляр TeleBot
    """
    logger.info("Застосовуємо глобальні перевірки підписки...")
    
    # Зберігаємо оригінальні методи
    original_message_handler = bot.message_handler
    original_callback_query_handler = bot.callback_query_handler
    
    # Створюємо обгортку для message_handler
    def wrapped_message_handler(*args, **kwargs):
        print(f"[DEBUG] wrapped_message_handler called with args={args}, kwargs={kwargs}")
        # Зберігаємо filter функцію в момент реєстрації
        original_filter = kwargs.get('func')
        
        def decorator(handler_func):
            @wraps(handler_func)
            def guarded_handler(message, *args2, **kwargs2):
                print(f"[SUB_UTILS DEBUG] guarded_handler called for message: user={message.from_user.id}, text='{message.text}'")
                # ПРОВЕРКА P2P СОСТОЯНИЯ - ВАЖНО: проверяем ДО фильтра!
                try:
                    from database import get_user_state
                    user_state = get_user_state(message.from_user.id)
                    if user_state and (user_state.startswith('p2p_') or user_state.startswith('simple_move_')):
                        print(f"[SUB_UTILS] P2P or simple_move state detected: {user_state}, calling handler directly")
                        # Пропускаем все проверки для P2P и simple_move состояний
                        return handler_func(message, *args2, **kwargs2)
                except Exception as e:
                    logger.debug(f"P2P state check error: {e}")
                
                # Отримуємо filter функцію - вона може бути і в kwargs2 від TELEGRAM
                filter_func = kwargs2.get('func') if kwargs2 else None
                
                # Перевіряємо filter функцію ЯКЩО ВОНА Є
                # Це критично для станів типу p2p_waiting_move_amount
                if filter_func is not None:
                    try:
                        filter_result = filter_func(message)
                        logger.debug(f"[FILTER DEBUG] filter_func result: {filter_result} for user {message.from_user.id}")
                        if not filter_result:
                            # Filter не пройшов - не викликаємо обробник
                            logger.debug(f"[FILTER DEBUG] filter returned False, skipping handler")
                            return
                    except Exception as e:
                        logger.debug(f"Filter function error: {e}")
                else:
                    # Якщо filter_func немає, перевіряємо стан вручну для P2P/SIMPLE_MOVE (дублирование для надежности)
                    try:
                        user_state = get_user_state(message.from_user.id)
                        if user_state and (user_state.startswith('p2p_') or user_state.startswith('p2p_waiting_') or user_state.startswith('simple_move_')):
                            print(f"[SUB_UTILS] No filter but P2P/SIMPLE_MOVE state detected: {user_state}, allowing through")
                            # Пропускаємо перевірку підписки для P2P/SIMPLE_MOVE станів
                            return handler_func(message, *args2, **kwargs2)
                    except Exception as e:
                        print(f"[SUB_UTILS] Manual state check error: {e}")
                
                try:
                    # Перевіряємо, чи потрібно ігнорувати цей тип повідомлень
                    if _should_ignore_message(message):
                        print(f"[SUB_UTILS] _should_ignore_message returned True, calling handler")
                        return handler_func(message, *args2, **kwargs2)
                    
                    # Отримуємо user_id
                    user_id = message.from_user.id
                    logger.debug(f"Обробка повідомлення від {user_id}")
                    
                    # Перевіряємо підписку
                    from subscription_system import check_subscription_before_action
                    if not check_subscription_before_action(message, bot):
                        logger.info(f"Користувач {user_id} не має доступу (не підписаний на всі канали)")
                        return
                    
                    # Якщо все гаразд - виконуємо оригінальний обробник
                    return handler_func(message, *args2, **kwargs2)
                except Exception as e:
                    logger.error(f"Помилка під час обробки повідомлення: {e}", exc_info=True)
            
            # Передаємо оригінальний filter при реєстрації
            if original_filter:
                kwargs['func'] = original_filter
            return original_message_handler(*args, **kwargs)(guarded_handler)
        return decorator
    
    # Створюємо обгортку для callback_query_handler
    def wrapped_callback_query_handler(*args, **kwargs):
        def decorator(handler_func):
            @wraps(handler_func)
            def guarded_handler(call, *args2, **kwargs2):
                try:
                    # Логируем все callback'ы для отладки
                    if hasattr(call, 'data') and call.data:
                        user_id = call.from_user.id if hasattr(call, 'from_user') else 'unknown'
                        print(f"[DEBUG] subscription_utils: guarded_handler called for callback: {call.data}, user: {user_id}")
                    
                    # ВАЖНО: Исключаем office callback'и из глобальной проверки
                    # Они имеют свои декораторы @subscription_required
                    office_callbacks = (
                        "office_menu", "office_agency", "office_info", "office_top",
                        "office_withdraw_profit", "office_confirm_withdraw",
                        "office_employee_already_hired", "office_insufficient_funds"
                    )
                    is_office_callback = (
                        hasattr(call, 'data') and (
                            call.data in office_callbacks or
                            call.data.startswith("office_employee_info:") or
                            call.data.startswith("office_buy_employee:")
                        )
                    )
                    
                    # ВАЖНО: Исключаем P2P callback'и из глобальной проверки
                    # Они обрабатывают подписку самостоятельно или являются админскими
                    is_p2p_callback = (
                        hasattr(call, 'data') and call.data and (
                            call.data == "p2p_menu" or
                            call.data == "admin_p2p_transfers" or
                            call.data == "p2p_create_transfer" or
                            call.data == "p2p_history" or
                            call.data == "p2p_pending" or
                            call.data == "p2p_move_to_transferable" or
                            call.data.startswith("p2p_")
                        )
                    )
                    
                    if is_office_callback:
                        # Для office callback'ов - просто выполняем обработчик
                        # Декораторы сами проверят подписку
                        user_id = call.from_user.id if hasattr(call, 'from_user') else 'unknown'
                        print(f"[DEBUG] subscription_utils: office callback {call.data} detected, user: {user_id}, calling handler (decorators will check subscription)")
                        logger.debug(f"Office callback {call.data} - пропускаем глобальную проверку")
                        try:
                            print(f"[DEBUG] subscription_utils: ВЫЗЫВАЕМ handler_func для {call.data}, user: {user_id}")
                            result = handler_func(call, *args2, **kwargs2)
                            print(f"[DEBUG] subscription_utils: office callback {call.data} handler returned, user: {user_id}, result={result}")
                            return result
                        except Exception as e:
                            print(f"[ERROR] subscription_utils: office callback {call.data} handler failed, user: {user_id}, error: {e}")
                            import traceback
                            traceback.print_exc()
                            raise
                    
                    if is_p2p_callback:
                        # Для P2P callback'ов - просто выполняем обработчик
                        # Обработчики сами проверят подписку или права администратора
                        # Обработчики сами отвечают на callback_query, поэтому не делаем это здесь
                        user_id = call.from_user.id if hasattr(call, 'from_user') else 'unknown'
                        print(f"[DEBUG] subscription_utils: P2P callback {call.data} detected, user: {user_id}, calling handler")
                        logger.debug(f"P2P callback {call.data} - пропускаем глобальную проверку")
                        try:
                            print(f"[DEBUG] subscription_utils: ВЫЗЫВАЕМ handler_func для P2P {call.data}, user: {user_id}")
                            result = handler_func(call, *args2, **kwargs2)
                            print(f"[DEBUG] subscription_utils: P2P callback {call.data} handler returned, user: {user_id}, result={result}")
                            return result
                        except Exception as e:
                            print(f"[ERROR] subscription_utils: P2P callback {call.data} handler failed, user: {user_id}, error: {e}")
                            logger.error(f"P2P callback {call.data} handler failed, user: {user_id}, error: {e}")
                            import traceback
                            traceback.print_exc()
                            # Отвечаем на callback_query в случае ошибки
                            try:
                                bot.answer_callback_query(call.id, text="❌ Помилка", show_alert=False)
                            except:
                                pass
                            raise
                    
                    # Для остальных callback'ов - применяем глобальную проверку
                    # ВАЖНО: Отвечаем на callback_query ПЕРВЫМ, чтобы убрать "загрузку"
                    try:
                        bot.answer_callback_query(call.id, text="", show_alert=False)
                    except:
                        pass
                    
                    # Отримуємо user_id
                    user_id = call.from_user.id
                    logger.debug(f"Обробка callback від {user_id}")
                    
                    # Перевіряємо підписку
                    # ВАЖНО: Не блокируем выполнение здесь, пусть декораторы сами решают
                    # Это нужно, чтобы декораторы @subscription_required могли работать правильно
                    from subscription_system import check_subscription_before_action
                    is_subscribed = check_subscription_before_action(call, bot)
                    if not is_subscribed:
                        logger.info(f"Користувач {user_id} не має доступу до callback (не підписаний на всі канали)")
                        # Пропускаем дальше к декораторам - они сами решат, что делать
                        # callback_query уже отвечен, так что кнопка не будет "висеть"
                        pass
                    
                    # Виконуємо оригінальний обробник (декораторы сами проверят подписку)
                    logger.debug(f"Виконуємо обробник для callback від {user_id}, data={call.data}")
                    try:
                        result = handler_func(call, *args2, **kwargs2)
                        return result
                    except Exception as func_error:
                        logger.error(f"Помилка в обробнику: {func_error}", exc_info=True)
                        raise
                except Exception as e:
                    logger.error(f"Помилка під час обробки callback: {e}", exc_info=True)
                    # Отвечаем на callback_query даже при ошибке
                    try:
                        bot.answer_callback_query(call.id, text="❌ Помилка", show_alert=False)
                    except:
                        pass
            
            return original_callback_query_handler(*args, **kwargs)(guarded_handler)
        return decorator
    
    # Підміняємо методи бота
    bot.message_handler = wrapped_message_handler
    bot.callback_query_handler = wrapped_callback_query_handler
    
    logger.info("Глобальні перевірки підписки успішно застосовано")

def _should_ignore_message(message):
    """
    Перевіряє, чи потрібно ігнорувати перевірку підписки для повідомлення.
    
    Args:
        message: Об'єкт повідомлення від Telegram
        
    Returns:
        bool: True, якщо перевірку підписки слід ігнорувати, інакше False
    """
    try:
        # Ігноруємо команду /start, оскільки вона обробляється окремо
        if message.text and message.text.startswith('/start'):
            return True
        
        # Ігноруємо команду /help
        if message.text and message.text.startswith('/help'):
            return True
        
        # Ігноруємо команду /subscription_status
        if message.text and message.text.startswith('/subscription_status'):
            return True
        
        # Ігноруємо команду /transfer (P2P-перекази)
        if message.text and message.text.startswith('/transfer'):
            return True
            
        # Ігноруємо повідомлення з контактом (перевірка номеру телефону)
        if hasattr(message, 'contact') and message.contact:
            return True
            
        # Ігноруємо сервісні повідомлення (нові учасники, пінані повідомлення тощо)
        if message.content_type in ['new_chat_members', 'left_chat_member', 'pinned_message']:
            return True

        # Ігноруємо повідомлення від користувачів у станах P2P-операцій
        # Користувачі в процесі P2P-переказу можуть продовжувати без перевірки підписки
        try:
            from database import get_user_state
            user_state = get_user_state(message.from_user.id)
            if user_state and (user_state.startswith('p2p_') or user_state.startswith('simple_move_')):
                logger.info(f"Користувач {message.from_user.id} у стані P2P/SIMPLE_MOVE: {user_state} - перевірка підписки ігнорується")
                return True
        except Exception as e:
            logger.debug(f"Помилка перевірки стану користувача: {e}")
            pass

        # ВАЖНО: Игнорируем комментарии к розыгрышам - пользователи должны иметь возможность участвовать
        # независимо от подписки на каналы/чаты (проверяем ПЕРВЫМ, до других проверок)
        # Убираем требование наличия text: комментарии со слот-машиной 🎰 приходят как message.dice
        if message.reply_to_message:
            # Проверяем, является ли это комментарием к посту розыгрыша
            try:
                from database import get_all_giveaways
                active_giveaways = get_all_giveaways(status='active')
                
                reply_to = message.reply_to_message
                reply_message_id = reply_to.message_id if reply_to else None
                
                if reply_message_id:
                    for giveaway in active_giveaways:
                        started_post_id = giveaway.get('started_post_message_id')
                        original_post_id = giveaway.get('post_message_id')
                        
                        # Проверяем оба поста (оригинальный и о начале)
                        if started_post_id == reply_message_id or original_post_id == reply_message_id:
                            # Это комментарий к посту розыгрыша - игнорируем проверку подписки
                            logger.info(f"Комментарий к розыгрышу #{giveaway['id']} - проверка подписки игнорируется")
                            return True
            except Exception as e:
                logger.debug(f"Ошибка проверки комментария к розыгрышу: {e}")
                # В случае ошибки продолжаем обычную проверку
                pass
        
        # Додаткові перевірки для адмінів
        from database import is_admin
        if is_admin(message.from_user.id):
            # Адміни можуть використовувати будь-які команди
            if message.text and message.text.startswith('/'):
                return True
                
        # Ігноруємо повідомлення з групи, якщо вони не є командами
        if message.chat.type in ['group', 'supergroup'] and not (message.text and message.text.startswith('/')):
            return True
            
    except Exception as e:
        logger.error(f"Помилка у _should_ignore_message: {e}", exc_info=True)
        # У разі помилки краще перевірити підписку
        return False
    
    return False
