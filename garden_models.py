from datetime import datetime

TREE_TYPES = [
    {"type": "apple", "name": "Яблуня", "fruit": "apple", "fruit_emoji": "🍏", "price_uah": 10, "base_income": 1},
    {"type": "pear", "name": "Груша", "fruit": "pear", "fruit_emoji": "🍐", "price_uah": 20, "base_income": 2},
    {"type": "cherry", "name": "Вишня", "fruit": "cherry", "fruit_emoji": "🍒", "price_uah": 35, "base_income": 3},
    {"type": "peach", "name": "Персик", "fruit": "peach", "fruit_emoji": "🍑", "price_uah": 50, "base_income": 4},
]

FRUITS = [
    {"type": "apple", "name": "Яблуко", "emoji": "🍏"},
    {"type": "pear", "name": "Груша", "emoji": "🍐"},
    {"type": "cherry", "name": "Вишня", "emoji": "🍒"},
    {"type": "peach", "name": "Персик", "emoji": "🍑"},
    {"type": "golden_apple", "name": "Золоте яблуко", "emoji": "🥇"},
]

def get_fruit_name_uk(fruit_type: str) -> str:
    """Повертає українську назву фрукту за його типом"""
    fruit = next((f for f in FRUITS if f['type'] == fruit_type), None)
    return fruit['name'] if fruit else fruit_type

def get_tree_name_uk(tree_type: str) -> str:
    """Повертає українську назву дерева за його типом"""
    tree = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
    return tree['name'] if tree else tree_type

# Логіка збору фруктів, продажу та підрахунку буде реалізована у відповідних функціях бота.

GARDEN_LEVELS = [
    {
        "level": 1,
        "name": "Стартовий садівник",
        "price_uah": 100,
        "available_trees": ["apple"],
        "withdraw_limit_per_day": 50,
        "commission_percent": 15,
        "bonus_percent": 0,
        "max_withdraw_per_tx": 50,
        "description": "Початковий рівень. Доступно лише яблуні. Базова комісія 15%. Без бонусів до врожайності."
    },
    {
        "level": 2,
        "name": "Срібний садівник",
        "price_uah": 300,
        "available_trees": ["apple", "pear"],
        "withdraw_limit_per_day": 150,
        "commission_percent": 10,
        "bonus_percent": 5,
        "max_withdraw_per_tx": 150,
        "description": "Доступні яблуні та груші. Комісія знижується до 10%. Бонус до врожаю +5%."
    },
    {
        "level": 3,
        "name": "Золотий садівник",
        "price_uah": 900,
        "available_trees": ["apple", "pear", "cherry"],
        "withdraw_limit_per_day": 10000,
        "commission_percent": 5,
        "bonus_percent": 10,
        "max_withdraw_per_tx": 500,
        "description": "Доступні три дерева (яблуня, груша, вишня). Комісія 5%. Бонус до врожаю +10%. Доступ до VIP-акцій."
    },
    {
        "level": 4,
        "name": "Платиновий садівник",
        "price_uah": 2500,
        "available_trees": ["apple", "pear", "cherry"],
        "withdraw_limit_per_day": 50000,
        "commission_percent": 4,
        "bonus_percent": 15,
        "max_withdraw_per_tx": 2000,
        "description": "Збільшені ліміти виводу. Комісія 4%. Бонус врожайності +15%. Ексклюзивні бустери зі знижкою."
    },
    {
        "level": 5,
        "name": "Діамантовий садівник",
        "price_uah": 6000,
        "available_trees": ["apple", "pear", "cherry", "peach"],
        "withdraw_limit_per_day": 999999,
        "commission_percent": 3,
        "bonus_percent": 20,
        "max_withdraw_per_tx": 10000,
        "description": "Максимальні можливості: мінімальна комісія 3%, бонус врожайності +20%, пріоритетна підтримка."
    },
]


BOOSTERS = [
    {"type": "double_harvest", "name": "Подвійний врожай", "description": "Подвоює кількість зібраних фруктів", "duration_hours": 1, "price_key": "booster_price_double_harvest", "emoji": "⚡", "effect": "x2 урожай"},
    {"type": "autoharvest", "name": "Автоматичний збір", "description": "Автоматично збирає фрукти кожну годину", "duration_hours": 24, "price_key": "booster_price_autoharvest", "emoji": "🤖", "effect": "авто-збір"},
    {"type": "discount_trees", "name": "Знижка на дерева", "description": "Знижка 50% на покупку всіх дерев", "duration_hours": 1, "price_key": "booster_price_discount_trees", "emoji": "💸", "effect": "-50% ціни"},
    {"type": "triple_harvest", "name": "Потрійний врожай", "description": "Потроює кількість зібраних фруктів", "duration_hours": 0.5, "price_key": "booster_price_triple_harvest", "emoji": "🚀", "effect": "x3 урожай"},
    {"type": "mega_profit", "name": "Мега прибуток", "description": "Збільшує ціну продажу фруктів на 100%", "duration_hours": 2, "price_key": "booster_price_mega_profit", "emoji": "💎", "effect": "+100% ціни"},
    {"type": "speed_growth", "name": "Прискорений ріст", "description": "Фрукти ростуть в 2 рази швидше", "duration_hours": 6, "price_key": "booster_price_speed_growth", "emoji": "🌪️", "effect": "x2 швидкість"},
    {"type": "lucky_harvest", "name": "Щасливий збір", "description": "Шанс отримати бонусні фрукти при збиранні", "duration_hours": 3, "price_key": "booster_price_lucky_harvest", "emoji": "🍀", "effect": "бонус фрукти"},
    {"type": "vip_status", "name": "VIP статус", "description": "Доступ до ексклюзивних функцій", "duration_hours": 168, "price_key": "booster_price_vip_status", "emoji": "👑", "effect": "VIP привілеї"},
    {"type": "autowater", "name": "Автополив", "description": "Автоматично поливає дерева, коли це потрібно", "duration_hours": 24, "price_key": "booster_price_autowater", "emoji": "💧", "effect": "авто-полив"}
]

# Новий бустер: нагадування про збір
REMIND_HARVEST_BOOST = {
    "type": "remind_harvest",
    "name": "Нагадувач збору",
    "description": "Надсилає пуш-нагадування, коли врожай готовий і дерева политі",
    "duration_hours": 24,
    "price_key": "booster_price_remind_harvest",
    "emoji": "🔔",
    "effect": "пуш-нагадування про збір"
}
BOOSTERS.append(REMIND_HARVEST_BOOST)

# Можна додати ще типи дерев і бустерів

def get_dynamic_income(tree_type):
    # Повертає дохідність ОДНОГО дерева (фрукти/год).
    # Якщо адміністратор налаштував конкретне значення — використовуємо його,
    # інакше повертаємо базове значення з TREE_TYPES без жодних масштабувань.
    from database import get_tree_income
    TREE = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
    if not TREE:
        return 1
    configured = get_tree_income(tree_type)
    if configured and configured > 0:
        return configured
    return TREE['base_income']

def get_effective_tree_income(tree_type: str, econ_multiplier: float) -> float:
    """Повертає дохідність ОДНОГО дерева з урахуванням економіки лише коли
    адмін не задав власне значення.

    - якщо admin задав `tree_income_*` > 0 → повертаємо це значення як остаточне
    - інакше → повертаємо base_income × econ_multiplier
    """
    from database import get_tree_income
    tree = next((t for t in TREE_TYPES if t['type'] == tree_type), None)
    if not tree:
        return 1.0
    configured = get_tree_income(tree_type)
    if configured and configured > 0:
        return float(configured)
    return float(tree['base_income']) * float(econ_multiplier)
