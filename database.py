# database.py
import sqlite3, pathlib
import os
import json
import time
from datetime import datetime

# Файл со списком ID админов (по одному ID в строке)
ADMIN_IDS_FILE = 'admin_ids.txt'
ADMIN_IDS_CACHE = None


def _load_admin_ids_from_file():
    """Завантажує список admin ID з текстового файлу admin_ids.txt"""
    try:
        base_dir = pathlib.Path(__file__).resolve().parent
        path = base_dir / ADMIN_IDS_FILE
        if not path.exists():
            return set()
        ids = set()
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                ids.add(int(line))
            except ValueError:
                continue
        return ids
    except Exception:
        return set()


# Кеш для зберігання даних про чати
chat_info_cache = {}

def cache_chat_info(chat_id, title, username=None):
    """Зберігає інформацію про чат у кеші"""
    chat_info_cache[str(chat_id)] = (title, username)
    # Також зберігаємо за username, якщо він є
    if username:
        chat_info_cache[f"@{username}"] = (title, username)

def get_cached_chat_info(chat_identifier):
    """Отримує інформацію про чат з кешу"""
    return chat_info_cache.get(str(chat_identifier))

def format_duration(seconds):
    """Форматує секунди в читабельний формат"""
    units = [
        ('рік', 'роки', 'років', 31536000),
        ('місяць', 'місяці', 'місяців', 2592000),
        ('тиждень', 'тижні', 'тижнів', 604800),
        ('день', 'дні', 'днів', 86400),
        ('година', 'години', 'годин', 3600),
        ('хвилина', 'хвилини', 'хвилин', 60),
        ('секунда', 'секунди', 'секунд', 1)
    ]
    
    for single, few, many, unit_seconds in units:
        if seconds >= unit_seconds:
            count = seconds // unit_seconds
            if count == 1:
                return f"{count} {single}"
            elif 2 <= count <= 4:
                return f"{count} {few}"
            else:
                return f"{count} {many}"
    
    return "0 секунд"

def round_float(value, decimals=2):
    """
    Правильно округлює число з плаваючою комою до вказаної кількості знаків після коми.
    Вирішує проблему з числами типу 8.299999999999999 -> 8.30
    """
    if value is None:
        return 0.0
    
    # Конвертуємо в float якщо це не число
    try:
        value = float(value)
    except (ValueError, TypeError):
        return 0.0
    
    # Використовуємо round() для правильного округлення
    return round(value, decimals)

# Выбор файла БД:
_BASE_DIR = pathlib.Path(__file__).resolve().parent
_ENV_DB = os.getenv("DB_FILE")
if _ENV_DB:
    DB_FILE = pathlib.Path(_ENV_DB)
else:
    # Amvera: персистентное хранилище по абсолютному пути /data
    _ABS_DATA_DB = pathlib.Path("/data/tg.db")
    if _ABS_DATA_DB.exists():
        DB_FILE = _ABS_DATA_DB
    else:
        # Fallback: локальная база рядом с кодом
        DB_FILE = _BASE_DIR / "tg.db"

def ensure_garden_transactions_table():
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS garden_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount REAL,
                currency TEXT,
                timestamp INTEGER,
                comment TEXT
            );
        """)
        con.commit()

def ensure_users_table():
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                balance REAL DEFAULT 0,
                withdrawn REAL DEFAULT 0,
                last_bonus INTEGER DEFAULT 0
            );
        """)
        cur.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in cur.fetchall()}
        if 'transferable_balance' not in cols:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN transferable_balance REAL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass
        if 'locked_balance' not in cols:
            try:
                cur.execute("ALTER TABLE users ADD COLUMN locked_balance REAL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass
        con.commit()

# Створюємо таблиці автоматично при імпорті модуля
ensure_garden_transactions_table()
ensure_users_table()

def _db():
    # Убрали debug сообщение - оно вызывается слишком часто
    # print(f"[DEBUG] Using database at: {DB_FILE.resolve()}")
    try:
        # Додаємо timeout та інші параметри для кращої обробки блокування
        return sqlite3.connect(
            DB_FILE, 
            check_same_thread=False, 
            timeout=30.0,
            isolation_level=None  # Автоматичні транзакції
        )
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e).lower():
            print(f"[WARNING] База даних заблокована. Спробуємо ще раз...")
            import time
            time.sleep(1)  # Чекаємо 1 секунду
            return sqlite3.connect(
                DB_FILE, 
                check_same_thread=False, 
                timeout=60.0,
                isolation_level=None
            )
        else:
            raise e

def ensure_support_tables():
    """Creates support ticket tables if missing."""
    with _db() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                subject TEXT,
                category TEXT DEFAULT 'general',
                priority INTEGER DEFAULT 0,
                source TEXT DEFAULT 'webapp',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_message_at INTEGER NOT NULL,
                last_message_from TEXT,
                last_user_reply_at INTEGER,
                last_admin_reply_at INTEGER,
                assigned_admin_id INTEGER,
                closed_at INTEGER,
                closed_reason TEXT,
                balance_delta REAL DEFAULT 0,
                user_unread_count INTEGER DEFAULT 0,
                admin_unread_count INTEGER DEFAULT 0,
                meta TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender_id INTEGER,
                sender_role TEXT,
                body TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                is_internal INTEGER DEFAULT 0,
                meta TEXT,
                FOREIGN KEY(ticket_id) REFERENCES support_tickets(id) ON DELETE CASCADE
            );
        """)
        # Ensure new unread columns exist for legacy databases.
        cur.execute("PRAGMA table_info(support_tickets)")
        columns = {row[1] for row in cur.fetchall()}
        if 'category' not in columns:
            cur.execute("ALTER TABLE support_tickets ADD COLUMN category TEXT DEFAULT 'general'")
        if 'last_user_reply_at' not in columns:
            cur.execute("ALTER TABLE support_tickets ADD COLUMN last_user_reply_at INTEGER")
        if 'last_admin_reply_at' not in columns:
            cur.execute("ALTER TABLE support_tickets ADD COLUMN last_admin_reply_at INTEGER")
        if 'user_unread_count' not in columns:
            cur.execute("ALTER TABLE support_tickets ADD COLUMN user_unread_count INTEGER DEFAULT 0")
        if 'admin_unread_count' not in columns:
            cur.execute("ALTER TABLE support_tickets ADD COLUMN admin_unread_count INTEGER DEFAULT 0")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned ON support_tickets(assigned_admin_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_support_messages_ticket ON support_messages(ticket_id);")
        cur.execute("UPDATE support_tickets SET category = 'general' WHERE category IS NULL")
        con.commit()

# Ensure support tables exist on import.
ensure_support_tables()

# --- Інвайти ---
def ensure_invites_table():
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS invites (
                token TEXT PRIMARY KEY,
                is_used INTEGER DEFAULT 0,
                who_used INTEGER
            );
        ''')
        con.commit()

import uuid

def create_invite():
    token = str(uuid.uuid4())
    with _db() as con:
        con.execute("INSERT INTO invites (token, is_used) VALUES (?, 0)", (token,))
    return token

def use_invite(token, user_id):
    with _db() as con:
        con.execute("UPDATE invites SET is_used=1, who_used=? WHERE token=? AND is_used=0", (user_id, token))
        return con.total_changes > 0

def is_valid_invite(token):
    with _db() as con:
        row = con.execute("SELECT is_used FROM invites WHERE token=?", (token,)).fetchone()
        return row is not None and row[0] == 0

# --- Pending Users (ті, хто пробував зайти, коли бот закритий) ---
def ensure_pending_users_table():
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS pending_users (
                user_id INTEGER PRIMARY KEY
            );
        ''')
        con.commit()

ensure_pending_users_table()

def add_pending_user(user_id):
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO pending_users (user_id) VALUES (?)", (user_id,))

def get_pending_users():
    with _db() as con:
        rows = con.execute("SELECT user_id FROM pending_users").fetchall()
        return [r[0] for r in rows]

def clear_pending_users():
    with _db() as con:
        con.execute("DELETE FROM pending_users")
        con.commit()

def init_db() -> None:
    print("INIT_DB CALLED")
    try:
        with _db() as con:
            cur = con.cursor()
            print(f"[DB] Using database at: {DB_FILE}")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    balance REAL DEFAULT 0,
                    withdrawn REAL DEFAULT 0,
                    last_bonus INTEGER DEFAULT 0
                );
            """)
            cur.execute("PRAGMA table_info(users)")
            cols_early = {row[1] for row in cur.fetchall()}
            try:
                if 'transferable_balance' not in cols_early:
                    cur.execute("ALTER TABLE users ADD COLUMN transferable_balance REAL DEFAULT 0.0")
                if 'locked_balance' not in cols_early:
                    cur.execute("ALTER TABLE users ADD COLUMN locked_balance REAL DEFAULT 0.0")
            except sqlite3.OperationalError as e:
                # На случай если таблица users почему-то ещё не существует в конкретном окружении
                if 'no such table: users' in str(e).lower():
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            user_id INTEGER PRIMARY KEY,
                            user_name TEXT,
                            balance REAL DEFAULT 0,
                            withdrawn REAL DEFAULT 0,
                            last_bonus INTEGER DEFAULT 0
                        );
                    """)
                    # Повторная спроба додати колонки
                    cur.execute("PRAGMA table_info(users)")
                    cols_retry = {row[1] for row in cur.fetchall()}
                    if 'transferable_balance' not in cols_retry:
                        cur.execute("ALTER TABLE users ADD COLUMN transferable_balance REAL DEFAULT 0.0")
                    if 'locked_balance' not in cols_retry:
                        cur.execute("ALTER TABLE users ADD COLUMN locked_balance REAL DEFAULT 0.0")
                else:
                    raise
            # ... (інші таблиці)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    admin_id INTEGER,
                    action TEXT,
                    details TEXT,
                    timestamp INTEGER
                );
            """)

            # Журнал балансу (повний леджер усіх змін балансу)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS balance_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    delta REAL NOT NULL,
                    balance_before REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    reason TEXT,
                    details TEXT,
                    created_at INTEGER NOT NULL
                );
            """)

            # Службова таблиця для придушення тригера при ручному логуванні
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ledger_suppress (
                    user_id INTEGER PRIMARY KEY
                );
            """)

            # Таблиця для транзакцій Stars
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stars_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    uah_amount REAL NOT NULL,
                    telegram_charge_id TEXT,
                    provider_payment_charge_id TEXT,
                    status TEXT DEFAULT 'pending',
                    timestamp INTEGER NOT NULL
                );
            """)

            # Таблиця для налаштувань Stars
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stars_settings (
                    exchange_rate INTEGER DEFAULT 100,
                    min_deposit INTEGER DEFAULT 100,
                    enabled BOOLEAN DEFAULT 1,
                    admin_fee_percent REAL DEFAULT 0
                );
            """)

            # Таблиця для виплат Stars
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stars_payouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    timestamp INTEGER NOT NULL
                );
            """)

            # Перевіряємо чи є записи в stars_settings, якщо ні - вставляємо за замовчуванням
            cursor = cur.execute("SELECT COUNT(*) FROM stars_settings")
            count = cursor.fetchone()[0]
            if count == 0:
                cur.execute("""
                    INSERT INTO stars_settings (exchange_rate, min_deposit, enabled, admin_fee_percent)
                    VALUES (100, 100, 1, 0)
                """)

            # Таблиця лімітів для розіграшів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS giveaway_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    max_prize_amount REAL DEFAULT 1000.0,
                    max_per_day INTEGER DEFAULT 5,
                    max_participants INTEGER DEFAULT 0,
                    approval_threshold REAL DEFAULT 250.0,
                    updated_at INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER))
                );
            """)

            # Таблиця лімітів для виплат
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payout_limits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    max_amount REAL DEFAULT 5000.0,
                    max_per_day INTEGER DEFAULT 10,
                    daily_total_limit REAL DEFAULT 50000.0,
                    approval_threshold REAL DEFAULT 1000.0,
                    updated_at INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER))
                );
            """)

            # Таблиця статистики розіграшів за день
            cur.execute("""
                CREATE TABLE IF NOT EXISTS giveaway_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0.0,
                    UNIQUE(user_id, date)
                );
            """)

            # Таблиця статистики виплат за день
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payout_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0.0,
                    UNIQUE(user_id, date)
                );
            """)

            # Таблиця персональних лімітів для розіграшів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_giveaway_limits (
                    user_id INTEGER PRIMARY KEY,
                    max_prize_amount REAL,
                    max_per_day INTEGER,
                    updated_at INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
                    updated_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
            """)

            # ========== СИСТЕМА P2P-ПЕРЕВОДІВ ==========
            # Розширена таблиця балансів користувачів
            # Додаємо нові колонки до таблиці users (якщо їх немає)
            # Примітка: міграції для таблиці users виконуються ПІСЛЯ гарантії її створення нижче
            
            # Таблиця P2P транзакцій
            cur.execute("""
                CREATE TABLE IF NOT EXISTS p2p_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user_id INTEGER NOT NULL,
                    to_user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    processed_at INTEGER,
                    processed_by INTEGER,
                    rejection_reason TEXT,
                    FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                    FOREIGN KEY (to_user_id) REFERENCES users(user_id),
                    FOREIGN KEY (processed_by) REFERENCES users(user_id)
                );
            """)
            
            # Індекси для швидкого пошуку
            cur.execute("CREATE INDEX IF NOT EXISTS idx_p2p_from_user ON p2p_transactions(from_user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_p2p_to_user ON p2p_transactions(to_user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_p2p_status ON p2p_transactions(status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_p2p_created ON p2p_transactions(created_at)")
            
            # Таблиця налаштувань P2P-переводів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS p2p_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    min_amount REAL DEFAULT 10.0,
                    max_amount REAL DEFAULT 10000.0,
                    fee_percent REAL DEFAULT 2.0,
                    fee_fixed REAL DEFAULT 0.0,
                    daily_limit REAL DEFAULT 50000.0,
                    daily_transactions_limit INTEGER DEFAULT 50,
                    cooldown_seconds INTEGER DEFAULT 60,
                    auto_approve_enabled INTEGER DEFAULT 0,
                    auto_approve_threshold REAL DEFAULT 100.0,
                    updated_at INTEGER DEFAULT (CAST(strftime('%%s','now') AS INTEGER))
                );
            """)
            
            # Ініціалізація налаштувань за замовчуванням
            cursor = cur.execute("SELECT COUNT(*) FROM p2p_settings")
            if cursor.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO p2p_settings 
                    (min_amount, max_amount, fee_percent, fee_fixed, daily_limit, 
                     daily_transactions_limit, cooldown_seconds, auto_approve_enabled, auto_approve_threshold)
                    VALUES (10.0, 10000.0, 2.0, 0.0, 50000.0, 50, 60, 0, 100.0)
                """)
            
            # Таблиця статистики P2P за день
            cur.execute("""
                CREATE TABLE IF NOT EXISTS p2p_daily_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    transactions_count INTEGER DEFAULT 0,
                    total_sent REAL DEFAULT 0.0,
                    total_received REAL DEFAULT 0.0,
                    total_fees_paid REAL DEFAULT 0.0,
                    UNIQUE(user_id, date)
                );
            """)
            
            # Таблиця логів P2P транзакцій (для аудиту)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS p2p_transaction_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    performed_by INTEGER,
                    details TEXT,
                    timestamp INTEGER NOT NULL,
                    FOREIGN KEY (transaction_id) REFERENCES p2p_transactions(id),
                    FOREIGN KEY (performed_by) REFERENCES users(user_id)
                );
            """)

            # Ініціалізуємо ліміти за замовчуванням, якщо їх немає
            cursor = cur.execute("SELECT COUNT(*) FROM giveaway_limits")
            if cursor.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO giveaway_limits (max_prize_amount, max_per_day, max_participants, approval_threshold)
                    VALUES (1000.0, 5, 0, 250.0)
                """)
            
            cursor = cur.execute("SELECT COUNT(*) FROM payout_limits")
            if cursor.fetchone()[0] == 0:
                cur.execute("""
                    INSERT INTO payout_limits (max_amount, max_per_day, daily_total_limit, approval_threshold)
                    VALUES (5000.0, 10, 50000.0, 1000.0)
                """)
            # Тригер: логувати КОЖНУ зміну балансу, якщо вона не пройшла через add_balance
            cur.execute("""
                CREATE TRIGGER IF NOT EXISTS trg_balance_update
                AFTER UPDATE OF balance ON users
                WHEN NOT EXISTS (SELECT 1 FROM ledger_suppress s WHERE s.user_id = NEW.user_id)
                BEGIN
                    INSERT INTO balance_ledger (
                        user_id, delta, balance_before, balance_after, reason, details, created_at
                    ) VALUES (
                        NEW.user_id,
                        NEW.balance - OLD.balance,
                        OLD.balance,
                        NEW.balance,
                        'auto_trigger',
                        NULL,
                        CAST(strftime('%s','now') AS INTEGER)
                    );
                END;
            """)

        with _db() as con:
            cur = con.cursor()

            # 1. Таблиця адмінів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY
                );
            """)

            # 1a. Таблиця ролей користувачів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    granted_at INTEGER DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
                    granted_by INTEGER,
                    PRIMARY KEY (user_id, role)
                );
            """)

            # 2. Таблиця користувачів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    user_name TEXT,
                    balance REAL DEFAULT 0,
                    withdrawn REAL DEFAULT 0,
                    last_bonus INTEGER DEFAULT 0
                );
            """)

            # ПІСЛЯ гарантії існування таблиці users — додаємо нові колонки, якщо їх немає
            cur.execute("PRAGMA table_info(users)")
            existing_columns = {row[1] for row in cur.fetchall()}
            if 'transferable_balance' not in existing_columns:
                cur.execute("ALTER TABLE users ADD COLUMN transferable_balance REAL DEFAULT 0.0")
            if 'locked_balance' not in existing_columns:
                cur.execute("ALTER TABLE users ADD COLUMN locked_balance REAL DEFAULT 0.0")

            # 3. Таблиця транзакцій
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tx (
                    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    comment TEXT,
                    status TEXT DEFAULT 'pending'
                );
            """)

            # 3a. Таблиця депозитів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS deposit_tx (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    user_name TEXT,
                    amount REAL,
                    comment TEXT,
                    proof TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Таблиця рефералів
            cur.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    user_id INTEGER PRIMARY KEY,
                    invited_by INTEGER
                );
            """)

            # 5. Таблиця налаштувань (реферальний бонус)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
             # 5. Таблиця налаштувань (реферальний бонус)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            # 5b. Новини та перегляди
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    cover_url TEXT,
                    cta_label TEXT,
                    cta_url TEXT,
                    status TEXT DEFAULT 'published',
                    pinned INTEGER DEFAULT 0,
                    author_id INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s','now')),
                    updated_at INTEGER DEFAULT (strftime('%s','now'))
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news_views (
                    news_id INTEGER,
                    user_id INTEGER,
                    viewed_at INTEGER DEFAULT (strftime('%s','now')),
                    liked INTEGER DEFAULT 0,
                    PRIMARY KEY (news_id, user_id)
                );
            """)
            # 6. Встановити дефолтний реферальний бонус (якщо ще не встановлений)
            cur.execute("""
                INSERT OR IGNORE INTO config (key, value)
                VALUES ('ref_bonus', '0.1');
            """)
            # 8. Сад — рівень, досвід, валюта (окремо від балансу, якщо треба)
            con.execute("""
                CREATE TABLE IF NOT EXISTS gardens (
                    user_id INTEGER PRIMARY KEY,
                    exp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 0,
                    currency REAL DEFAULT 0
                );
            """)
            # 9. Дерева у саду
            con.execute("""
                CREATE TABLE IF NOT EXISTS trees (
                    user_id INTEGER,
                    type TEXT,
                    count INTEGER DEFAULT 0,
                    last_harvest INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, type)
                );
            """)
            # 10. Фрукти у саду
            con.execute("""
                CREATE TABLE IF NOT EXISTS fruits (
                    user_id INTEGER,
                    fruit_type TEXT,
                    amount REAL DEFAULT 0,
                    PRIMARY KEY (user_id, fruit_type)
                );
            """)
            # 11. Ціни на ринку
            con.execute("""
                CREATE TABLE IF NOT EXISTS market_prices (
                    fruit_type TEXT PRIMARY KEY,
                    price REAL DEFAULT 1.0
                );
            """)
            # 12. Ціни на дерева
            con.execute("""
                CREATE TABLE IF NOT EXISTS tree_prices (
                    type TEXT PRIMARY KEY,
                    price REAL DEFAULT 10.0
                );
            """)
            # 13. Бустери
            con.execute("""
                CREATE TABLE IF NOT EXISTS boosters (
                    user_id INTEGER,
                    booster_type TEXT,
                    expires_at INTEGER,
                    PRIMARY KEY (user_id, booster_type)
                );
            """)
            # 14. Ціни на бустери
            con.execute("""
                CREATE TABLE IF NOT EXISTS booster_prices (
                    booster_type TEXT PRIMARY KEY,
                    price REAL DEFAULT 5.0
                );
            """)
            # 15. Промо-коди
            con.execute("""
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    reward_type TEXT,
                    reward_value REAL,
                    max_uses INTEGER,
                    current_uses INTEGER DEFAULT 0,
                    expiry INTEGER,
                    item_type TEXT,
                    item_value TEXT
                );
            """)
            # 16. Історія саду
            con.execute("""
                CREATE TABLE IF NOT EXISTS garden_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    type TEXT,
                    amount REAL,
                    currency TEXT,
                    timestamp INTEGER,
                    comment TEXT
                );
            """)
            # 17. Рівні саду
            con.execute("""
                CREATE TABLE IF NOT EXISTS garden_levels (
                    user_id INTEGER PRIMARY KEY,
                    level INTEGER DEFAULT 0,
                    purchased_at INTEGER
                );
            """)
            # 18. Досягнення
            con.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    user_id INTEGER,
                    achievement_key TEXT,
                    value INTEGER,
                    achieved_at INTEGER,
                    PRIMARY KEY (user_id, achievement_key)
                );
            """)
            # 19. Бета-тестери
            con.execute("""
                CREATE TABLE IF NOT EXISTS beta_testers (
                    user_id INTEGER PRIMARY KEY,
                    added_by INTEGER,
                    added_at INTEGER
                );
            """)
            # 20. Телефони користувачів
            con.execute("""
                CREATE TABLE IF NOT EXISTS user_phones (
                    user_id INTEGER PRIMARY KEY,
                    phone TEXT,
                    verified INTEGER DEFAULT 0
                );
            """)
            # 21. Канали для виводів
            con.execute("""
                CREATE TABLE IF NOT EXISTS withdraw_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT
                );
            """)
            # 22. Обов'язкові канали
            con.execute("""
                CREATE TABLE IF NOT EXISTS required_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_username TEXT
                );
            """)
            # 23. Бани користувачів
            con.execute("""
                CREATE TABLE IF NOT EXISTS user_bans (
                    user_id INTEGER PRIMARY KEY,
                    banned_by INTEGER,
                    reason TEXT,
                    banned_at INTEGER,
                    expires_at INTEGER
                );
            """)
            # 24. Мут користувачів
            con.execute("""
                CREATE TABLE IF NOT EXISTS user_mutes (
                    user_id INTEGER PRIMARY KEY,
                    muted_by INTEGER,
                    reason TEXT,
                    muted_at INTEGER,
                    expires_at INTEGER
                );
            """)
            # 25. Стани користувачів
            con.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    state TEXT,
                    data TEXT
                );
            """)
            # 26. Ігрові чати
            con.execute("""
                CREATE TABLE IF NOT EXISTS gaming_chats (
                    chat_id INTEGER PRIMARY KEY,
                    chat_title TEXT,
                    added_by INTEGER,
                    added_at INTEGER
                );
            """)
            # 27. Ігрові сесії
            con.execute("""
                CREATE TABLE IF NOT EXISTS game_sessions (
                    session_id TEXT PRIMARY KEY,
                    chat_id INTEGER,
                    user_id INTEGER,
                    game_type TEXT,
                    bet_amount REAL,
                    created_at INTEGER,
                    status TEXT DEFAULT 'active'
                );
            """)
            # 28. Налаштування ігор
            con.execute("""
                CREATE TABLE IF NOT EXISTS game_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            # 29. Комісія саду
            con.execute("""
                CREATE TABLE IF NOT EXISTS garden_commission (
                    id INTEGER PRIMARY KEY,
                    commission_percent REAL DEFAULT 0.05
                );
            """)
            # 30. Головний адмін
            con.execute("""
                CREATE TABLE IF NOT EXISTS main_admin (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER
                );
            """)

            # 31. Аукціони
            con.execute("""
                CREATE TABLE IF NOT EXISTS auctions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    item_type TEXT,
                    item_key TEXT,
                    title TEXT,
                    description TEXT,
                    start_price REAL,
                    min_step REAL,
                    buy_now REAL,
                    reserve_price REAL,
                    started_at INTEGER,
                    ends_at INTEGER,
                    anti_snipe_sec INTEGER DEFAULT 10,
                    status TEXT DEFAULT 'active',
                    winner_user_id INTEGER,
                    winner_price REAL
                );
            """)

            # 32. Ставки аукціону
            con.execute("""
                CREATE TABLE IF NOT EXISTS auction_bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auction_id INTEGER,
                    user_id INTEGER,
                    amount REAL,
                    created_at INTEGER
                );
            """)
            
            # Ініціалізувати налаштування
            init_settings()
            
            # Ініціалізувати систему поливу
            ensure_watering_system()
            
            # Ініціалізувати систему квестів
            ensure_quest_chats_table()
            
            # Ініціалізувати дефолтні ціни бустів
            init_default_booster_prices()
            
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("[WARNING] База даних заблокована. Можливо, бот вже запущений на хостингу.")
            print("[INFO] Продовжуємо роботу без ініціалізації бази даних.")
        else:
            print(f"[ERROR] Помилка бази даних: {e}")
            raise
    except Exception as e:
        print(f"[ERROR] Помилка ініціалізації бази даних: {e}")
        raise

# --- Фрукти та біржа ---

def log_admin_action(user_id, admin_id, action, details):
    import time
    with _db() as con:
        con.execute(
            "INSERT INTO logs (user_id, admin_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, admin_id, action, details, int(time.time()))
        )
        con.commit()

def get_fruit_amount(user_id: int, fruit_type: str) -> float:
    with _db() as con:
        row = con.execute("SELECT amount FROM fruits WHERE user_id=? AND fruit_type=?", (user_id, fruit_type)).fetchone()
        return round_float(row[0]) if row else 0.0

def add_fruit(user_id: int, fruit_type: str, amount: float):
    """Додає фрукти користувачу. Якщо запис існує — збільшує кількість, інакше створює новий. Уникає помилки UNIQUE constraint."""
    amount = round_float(amount)
    with _db() as con:
        con.execute("""
            INSERT INTO fruits (user_id, fruit_type, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, fruit_type) DO UPDATE SET amount = amount + excluded.amount
        """, (user_id, fruit_type, amount))
        con.commit()

def remove_fruit(user_id: int, fruit_type: str, amount: float):
    with _db() as con:
        current = get_fruit_amount(user_id, fruit_type)
        amount = round_float(amount)
        if current < amount:
            raise ValueError('Недостатньо фруктів')
        new_amt = round_float(current - amount)
        con.execute("UPDATE fruits SET amount=? WHERE user_id=? AND fruit_type=?", (new_amt, user_id, fruit_type))
        con.commit()

def get_all_fruits(user_id: int):
    with _db() as con:
        rows = con.execute("SELECT fruit_type, amount FROM fruits WHERE user_id=?", (user_id,)).fetchall()
        return {ftype: round_float(amt) for ftype, amt in rows}

def get_fruit_price(fruit_type: str) -> float:
    with _db() as con:
        row = con.execute("SELECT price FROM market_prices WHERE fruit_type=?", (fruit_type,)).fetchone()
        return float(row[0]) if row else 1.0

def set_fruit_price(fruit_type: str, price: float):
    old_price = None
    with _db() as con:
        try:
            row = con.execute("SELECT price FROM market_prices WHERE fruit_type=?", (fruit_type,)).fetchone()
            old_price = float(row[0]) if row else None
        except Exception:
            old_price = None
        con.execute("INSERT INTO market_prices (fruit_type, price) VALUES (?, ?) ON CONFLICT(fruit_type) DO UPDATE SET price=excluded.price", (fruit_type, price))
        con.commit()
    try:
        if old_price is None or float(old_price) != float(price):
            _notify_price_change('fruit', fruit_type, float(price), float(old_price) if old_price is not None else None)
    except Exception:
        pass

def get_all_fruit_prices():
    with _db() as con:
        rows = con.execute("SELECT fruit_type, price FROM market_prices").fetchall()
        return {ftype: price for ftype, price in rows}

# ==========================
# ФРУКТИ: множники та акції
# ==========================
def get_setting(key: str, default: str | None = None) -> str | None:
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row and row[0] is not None else default

def set_setting(key: str, value: str):
    with _db() as con:
        old = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        old_val = old[0] if old and old[0] is not None else None
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
        con.commit()
    # Нотифікації для окремих налаштувань (наприклад, ціна рівня саду)
    try:
        if key.startswith('garden_level_price_'):
            lvl = key.split('_')[-1]
            _notify_price_change('level', str(lvl), float(value), float(old_val) if old_val is not None else None)
    except Exception:
        pass


# ==========================
# БРЕНДИНГ ТА ШАПКА
# ==========================
_BRANDING_KEYS = {
    "hero_badge": "🚀 INVESTING TEAM",
    "hero_title": "INVESTING PALMARON BOT",
    "hero_subtitle": "Ласкаво просимо до світу інвестицій!",
    "hero_cta_primary": "Відкрити сад",
    "hero_cta_secondary": "Поповнити баланс",
    "channel_title": "Офіційний канал",
    "channel_description": "Приєднуйтесь, щоб першими отримувати оновлення та бонуси.",
    "channel_url": "https://t.me/PalmaronInvesting",
    "channel_cta": "Відкрити канал",
    "news_widget_title": "Новини проєкту",
    "news_widget_hint": "Слідкуйте за ключовими оновленнями платформи",
    "legal_text": "© 2024 INVESTING PALMARON BOT • Усі права захищено",
}


def get_branding_settings() -> dict:
    settings = {}
    for key, default in _BRANDING_KEYS.items():
        settings[key] = get_setting(f"branding_{key}", default)
    return settings


def update_branding_settings(updates: dict) -> dict:
    if not isinstance(updates, dict):
        return get_branding_settings()
    for key in _BRANDING_KEYS.keys():
        if key in updates and updates[key] is not None:
            set_setting(f"branding_{key}", str(updates[key]))
    return get_branding_settings()


# ==========================
# НОВИНИ ТА ОНОВЛЕННЯ
# ==========================
def _news_row_to_dict(row):
    if not row:
        return None
    return {
        'id': row[0],
        'title': row[1],
        'content': row[2],
        'cover_url': row[3],
        'cta_label': row[4],
        'cta_url': row[5],
        'status': row[6],
        'pinned': bool(row[7]),
        'author_id': row[8],
        'created_at': int(row[9]) if row[9] is not None else None,
        'updated_at': int(row[10]) if row[10] is not None else None,
    }


def ensure_news_tables():
    """Створює таблиці новин, якщо вони не існують"""
    with _db() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                cover_url TEXT,
                cta_label TEXT,
                cta_url TEXT,
                status TEXT DEFAULT 'published',
                pinned INTEGER DEFAULT 0,
                author_id INTEGER,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                updated_at INTEGER DEFAULT (strftime('%s','now'))
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news_views (
                news_id INTEGER,
                user_id INTEGER,
                viewed_at INTEGER DEFAULT (strftime('%s','now')),
                liked INTEGER DEFAULT 0,
                PRIMARY KEY (news_id, user_id)
            );
        """)
        con.commit()

# Ensure news tables exist on import.
ensure_news_tables()

def create_news(title: str, content: str, author_id: int | None = None, **kwargs) -> int:
    ensure_news_tables()  # Додаткова перевірка перед створенням
    if not title or not content:
        raise ValueError("Title and content are required")
    data = {
        'cover_url': kwargs.get('cover_url'),
        'cta_label': kwargs.get('cta_label'),
        'cta_url': kwargs.get('cta_url'),
        'status': kwargs.get('status', 'published'),
        'pinned': 1 if kwargs.get('pinned') else 0,
    }
    ts = int(time.time())
    with _db() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO news (title, content, cover_url, cta_label, cta_url, status, pinned, author_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, content, data['cover_url'], data['cta_label'], data['cta_url'],
            data['status'], data['pinned'], author_id, ts, ts
        ))
        news_id = cur.lastrowid
        con.commit()
        return news_id


def update_news(news_id: int, **fields) -> bool:
    ensure_news_tables()  # Перевірка перед оновленням
    allowed = {'title', 'content', 'cover_url', 'cta_label', 'cta_url', 'status', 'pinned'}
    updates = []
    values = []
    for key, value in fields.items():
        if key not in allowed or value is None:
            continue
        if key == 'pinned':
            value = 1 if value else 0
        updates.append(f"{key}=?")
        values.append(value)
    if not updates:
        return False
    updates.append("updated_at=?")
    values.append(int(time.time()))
    values.append(news_id)
    with _db() as con:
        con.execute(f"UPDATE news SET {', '.join(updates)} WHERE id=?", values)
        con.commit()
        return con.total_changes > 0


def delete_news(news_id: int) -> bool:
    ensure_news_tables()  # Перевірка перед видаленням
    with _db() as con:
        con.execute("DELETE FROM news WHERE id=?", (news_id,))
        deleted = con.total_changes > 0
        con.execute("DELETE FROM news_views WHERE news_id=?", (news_id,))
        con.commit()
        return deleted


def get_news(news_id: int) -> dict | None:
    ensure_news_tables()  # Перевірка перед отриманням новини
    with _db() as con:
        row = con.execute("""
            SELECT id, title, content, cover_url, cta_label, cta_url,
                   status, pinned, author_id, created_at, updated_at
            FROM news WHERE id=?
        """, (news_id,)).fetchone()
    return _news_row_to_dict(row)


def list_news(limit: int = 50, status: str | None = None, include_drafts: bool = True) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    query = """
        SELECT n.id, n.title, n.content, n.cover_url, n.cta_label, n.cta_url,
               n.status, n.pinned, n.author_id, n.created_at, n.updated_at,
               COALESCE((SELECT COUNT(*) FROM news_views v WHERE v.news_id = n.id), 0) AS views_count,
               COALESCE((SELECT COUNT(*) FROM news_views v WHERE v.news_id = n.id AND v.liked = 1), 0) AS likes_count
        FROM news n
    """
    conditions = []
    params: list = []
    if include_drafts:
        if status:
            conditions.append("n.status = ?")
            params.append(status)
    else:
        conditions.append("n.status = 'published'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY n.pinned DESC, n.created_at DESC LIMIT ?"
    params.append(limit)
    with _db() as con:
        rows = con.execute(query, params).fetchall()
    result = []
    for row in rows:
        item = _news_row_to_dict(row)
        item['views'] = row[11]
        item['likes'] = row[12]
        result.append(item)
    return result


def get_news_stats(news_id: int) -> dict:
    with _db() as con:
        row = con.execute("""
            SELECT 
                COALESCE((SELECT COUNT(*) FROM news_views WHERE news_id=?), 0) AS views_count,
                COALESCE((SELECT COUNT(*) FROM news_views WHERE news_id=? AND liked=1), 0) AS likes_count
        """, (news_id, news_id)).fetchone()
    return {
        'news_id': news_id,
        'views': row[0] if row else 0,
        'likes': row[1] if row else 0
    }


def get_latest_news_for_user(user_id: int, limit: int = 5) -> list[dict]:
    limit = max(1, min(int(limit or 5), 10))
    with _db() as con:
        rows = con.execute("""
            SELECT n.id, n.title, n.content, n.cover_url, n.cta_label, n.cta_url,
                   n.status, n.pinned, n.author_id, n.created_at, n.updated_at,
                   COALESCE(v.viewed_at, 0) AS viewed_at,
                   COALESCE(v.liked, 0) AS liked_flag,
                   COALESCE((SELECT COUNT(*) FROM news_views vv WHERE vv.news_id = n.id), 0) AS views_count
            FROM news n
            LEFT JOIN news_views v ON v.news_id = n.id AND v.user_id = ?
            WHERE n.status = 'published'
            ORDER BY n.pinned DESC, n.created_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
    feed = []
    for row in rows:
        item = _news_row_to_dict(row)
        viewed_at = int(row[11]) if row[11] else None
        liked = bool(row[12])
        item['viewed_at'] = viewed_at
        item['is_viewed'] = viewed_at is not None and viewed_at > 0
        item['liked'] = liked
        item['views'] = row[13]
        feed.append(item)
    return feed


def mark_news_viewed(news_id: int, user_id: int, liked: bool = False):
    ensure_news_tables()  # Перевірка перед відміткою перегляду
    if not user_id:
        return
    liked_flag = 1 if liked else 0
    ts = int(time.time())
    with _db() as con:
        con.execute("""
            INSERT INTO news_views (news_id, user_id, viewed_at, liked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(news_id, user_id) DO UPDATE SET
                viewed_at=excluded.viewed_at,
                liked=CASE 
                    WHEN excluded.liked = 1 THEN 1
                    ELSE news_views.liked
                END
        """, (news_id, user_id, ts, liked_flag))
        con.commit()


def set_news_like(news_id: int, user_id: int, liked: bool):
    if not user_id:
        return
    ts = int(time.time())
    liked_flag = 1 if liked else 0
    with _db() as con:
        con.execute("""
            INSERT INTO news_views (news_id, user_id, viewed_at, liked)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(news_id, user_id) DO UPDATE SET
                viewed_at=COALESCE(news_views.viewed_at, excluded.viewed_at),
                liked=excluded.liked
        """, (news_id, user_id, ts, liked_flag))
        con.commit()


def get_unread_news_count(user_id: int) -> int:
    if not user_id:
        return 0
    with _db() as con:
        row = con.execute("""
            SELECT COUNT(*) FROM news n
            LEFT JOIN news_views v ON v.news_id = n.id AND v.user_id = ?
            WHERE n.status = 'published' AND v.news_id IS NULL
        """, (user_id,)).fetchone()
        return row[0] if row else 0

# ==========================
# НАЛАШТУВАННЯ: Перевірка номера телефону
# ==========================
def is_phone_verification_enabled() -> bool:
    """Повертає True, якщо перевірка номера увімкнена (за замовчуванням увімкнено)."""
    val = get_setting("phone_verification_enabled", "1")
    try:
        return str(val) != "0"
    except Exception:
        return True

def set_phone_verification_enabled(enabled: bool):
    """Вмикає/вимикає вимогу перевірки номера телефону."""
    set_setting("phone_verification_enabled", "1" if enabled else "0")

def get_tree_income(tree_type: str) -> float:
    """Повертає налаштовану дохідність (фрукти/год) для конкретного типу дерева або 0 якщо не задано."""
    try:
        val = get_setting(f"tree_income_{tree_type}")
        return float(val) if val is not None else 0.0
    except Exception:
        return 0.0

def set_tree_income(tree_type: str, income_per_hour: float):
    """Встановлює дохідність (фрукти/год) для конкретного типу дерева."""
    set_setting(f"tree_income_{tree_type}", str(float(income_per_hour)))

def get_fruit_multiplier(fruit_type: str) -> float:
    val = get_setting(f"fruit_multiplier_{fruit_type}", "1.0")
    try:
        return float(val)
    except Exception:
        return 1.0

def set_fruit_multiplier(fruit_type: str, mult: float):
    set_setting(f"fruit_multiplier_{fruit_type}", str(float(mult)))

def get_fruit_multiplier_global() -> float:
    val = get_setting("fruit_multiplier_global", "1.0")
    try:
        return float(val)
    except Exception:
        return 1.0

def set_fruit_multiplier_global(mult: float):
    set_setting("fruit_multiplier_global", str(float(mult)))

def get_fruit_promo(fruit_type: str) -> dict | None:
    import json
    raw = get_setting(f"fruit_promo_{fruit_type}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None

def set_fruit_promo(fruit_type: str, mult: float, until_ts: int):
    import json
    set_setting(f"fruit_promo_{fruit_type}", json.dumps({"mult": float(mult), "until": int(until_ts)}))

def clear_fruit_promo(fruit_type: str):
    set_setting(f"fruit_promo_{fruit_type}", "")

def get_effective_fruit_price(fruit_type: str) -> float:
    import time
    base = get_fruit_price(fruit_type)
    mult = get_fruit_multiplier(fruit_type) * get_fruit_multiplier_global()
    promo = get_fruit_promo(fruit_type)
    if promo and promo.get("until") and int(time.time()) < int(promo["until"]):
        try:
            mult *= float(promo.get("mult", 1.0))
        except Exception:
            pass
    return float(base) * float(mult)

# ==========================
# ДЕПОЗИТИ: бонуси/множники
# ==========================
def get_deposit_multiplier() -> float:
    val = get_setting("deposit_multiplier", "1.0")
    try:
        return float(val)
    except Exception:
        return 1.0

def set_deposit_multiplier(mult: float):
    set_setting("deposit_multiplier", str(float(mult)))

def get_deposit_bonus_fixed() -> float:
    val = get_setting("deposit_bonus_fixed", "0.0")
    try:
        return float(val)
    except Exception:
        return 0.0

def set_deposit_bonus_fixed(amount: float):
    set_setting("deposit_bonus_fixed", str(float(amount)))

def get_deposit_bonus_percent() -> float:
    val = get_setting("deposit_bonus_percent", "0.0")
    try:
        return float(val)
    except Exception:
        return 0.0

def set_deposit_bonus_percent(pct: float):
    set_setting("deposit_bonus_percent", str(float(pct)))

def get_deposit_rules() -> list:
    import json
    raw = get_setting("deposit_rules_json", "[]")
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def set_deposit_rules(rules_json: str):
    # Очікуємо валідний JSON (масив правил)
    set_setting("deposit_rules_json", rules_json)

def calculate_deposit_bonus(amount: float) -> dict:
    """Повертає деталі нарахування: {base, multiplier_bonus, percent_bonus, fixed_bonus, rule_bonus, total, effective} """
    base = float(amount)
    mult = get_deposit_multiplier()
    pct = get_deposit_bonus_percent()
    fixed = get_deposit_bonus_fixed()
    rules = get_deposit_rules()
    # Правило з найбільшим threshold, що підходить
    rule_pct = 0.0
    try:
        eligible = [r for r in rules if float(r.get("min", 0)) <= base]
        if eligible:
            rule_pct = float(sorted(eligible, key=lambda r: float(r.get("min", 0)))[-1].get("bonus_percent", 0.0))
    except Exception:
        rule_pct = 0.0
    multiplier_bonus = base * max(0.0, mult - 1.0)
    percent_bonus = base * (pct / 100.0)
    rule_bonus = base * (rule_pct / 100.0)
    total_bonus = multiplier_bonus + percent_bonus + fixed + rule_bonus
    effective = base + total_bonus
    return {
        "base": base,
        "multiplier_bonus": round(total_bonus - percent_bonus - fixed - rule_bonus, 2),
        "percent_bonus": round(percent_bonus, 2),
        "fixed_bonus": round(fixed, 2),
        "rule_bonus": round(rule_bonus, 2),
        "total": round(total_bonus, 2),
        "effective": round(effective, 2)
    }

# ==========================
# АУКЦІОНИ: Налаштування
# ==========================
def get_auction_settings():
    with _db() as con:
        row_c = con.execute("SELECT value FROM settings WHERE key='auction_commission_percent'").fetchone()
        row_s = con.execute("SELECT value FROM settings WHERE key='auction_default_min_step'").fetchone()
        row_a = con.execute("SELECT value FROM settings WHERE key='auction_default_antisnipe'").fetchone()
        commission = float(row_c[0]) if row_c and row_c[0] else 1.0
        min_step = float(row_s[0]) if row_s and row_s[0] else 10.0
        anti = int(row_a[0]) if row_a and row_a[0] else 15
        return { 'commission_percent': commission, 'default_min_step': min_step, 'default_antisnipe': anti }

def set_auction_commission(percent: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('auction_commission_percent',?)", (str(float(percent)),))
        con.commit()

def set_auction_min_step(amount: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('auction_default_min_step',?)", (str(float(amount)),))
        con.commit()

def set_auction_default_antisnipe(seconds: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('auction_default_antisnipe',?)", (str(int(seconds)),))
        con.commit()

# Куди публікувати аукціони (чат/канал)
def get_auction_chat():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key='auction_chat_id'").fetchone()
        try:
            return int(row[0]) if row and row[0] else None
        except Exception:
            return row[0] if row else None

def set_auction_chat(chat_id):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('auction_chat_id',?)", (str(chat_id),))
        con.commit()

# ==========================
# АУКЦІОНИ: CRUD
# ==========================
def create_auction(chat_id: int, item_type: str, item_key: str, title: str, description: str,
                   start_price: float, min_step: float, buy_now: float | None,
                   reserve_price: float | None, duration_minutes: int, anti_snipe_sec: int = 15) -> int:
    import time
    started = int(time.time())
    ends = started + max(60, int(duration_minutes) * 60)
    with _db() as con:
        cur = con.execute(
            """
            INSERT INTO auctions (chat_id, item_type, item_key, title, description, start_price, min_step, buy_now,
                                  reserve_price, started_at, ends_at, anti_snipe_sec, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'active')
            """,
            (chat_id, item_type, item_key, title, description, float(start_price), float(min_step),
             float(buy_now) if buy_now is not None else None,
             float(reserve_price) if reserve_price is not None else None,
             started, ends, int(anti_snipe_sec))
        )
        con.commit()
        return cur.lastrowid

def get_auction(auction_id: int):
    with _db() as con:
        row = con.execute("SELECT * FROM auctions WHERE id=?", (auction_id,)).fetchone()
        return row

def list_active_auctions(limit: int = 20):
    with _db() as con:
        rows = con.execute("SELECT * FROM auctions WHERE status='active' ORDER BY ends_at ASC LIMIT ?", (limit,)).fetchall()
        return rows

def add_auction_bid(auction_id: int, user_id: int, amount: float):
    import time
    with _db() as con:
        con.execute("INSERT INTO auction_bids (auction_id, user_id, amount, created_at) VALUES (?,?,?,?)",
                    (auction_id, user_id, float(amount), int(time.time())))
        con.commit()

def get_current_price(auction_id: int) -> float:
    with _db() as con:
        start_price = con.execute("SELECT start_price FROM auctions WHERE id=?", (auction_id,)).fetchone()
        if not start_price:
            return 0.0
        sp = float(start_price[0])
        row = con.execute("SELECT MAX(amount) FROM auction_bids WHERE auction_id=?", (auction_id,)).fetchone()
        return max(sp, float(row[0]) if row and row[0] is not None else 0.0)

def get_top_bids(auction_id: int, limit: int = 5):
    with _db() as con:
        rows = con.execute("SELECT user_id, amount, created_at FROM auction_bids WHERE auction_id=? ORDER BY amount DESC, created_at ASC LIMIT ?",
                           (auction_id, limit)).fetchall()
        return rows

def extend_auction(auction_id: int, extra_seconds: int):
    with _db() as con:
        con.execute("UPDATE auctions SET ends_at = ends_at + ? WHERE id=?", (int(extra_seconds), auction_id))
        con.commit()

def finish_auction(auction_id: int, winner_user_id: int | None, winner_price: float | None):
    with _db() as con:
        con.execute("UPDATE auctions SET status='finished', winner_user_id=?, winner_price=? WHERE id=?",
                    (winner_user_id, winner_price, auction_id))
        con.commit()

def list_expired_auctions(now_ts: int | None = None):
    """Активні аукціони, у яких сплив час."""
    import time
    if now_ts is None:
        now_ts = int(time.time())
    with _db() as con:
        rows = con.execute(
            "SELECT * FROM auctions WHERE status='active' AND ends_at <= ? ORDER BY ends_at ASC",
            (int(now_ts),)
        ).fetchall()
        return rows

def get_highest_bid(auction_id: int):
    """Повертає (user_id, amount) або None, якщо ставок немає."""
    with _db() as con:
        row = con.execute(
            "SELECT user_id, amount FROM auction_bids WHERE auction_id=? ORDER BY amount DESC, created_at ASC LIMIT 1",
            (auction_id,)
        ).fetchone()
        return (row[0], float(row[1])) if row else None

def get_highest_valid_bid(auction_id: int):
    """Повертає найвищу ставку, виключаючи користувачів, видалених із цього лота."""
    ensure_auction_removed_table()
    with _db() as con:
        row = con.execute(
            """
            SELECT b.user_id, b.amount
            FROM auction_bids b
            LEFT JOIN auction_removed r
              ON r.auction_id = b.auction_id AND r.user_id = b.user_id
            WHERE b.auction_id = ? AND r.user_id IS NULL
            ORDER BY b.amount DESC, b.created_at ASC
            LIMIT 1
            """,
            (auction_id,)
        ).fetchone()
        return (row[0], float(row[1])) if row else None

# ==========================
# АУКЦІОНИ: Холди коштів
# ==========================
def ensure_auction_holds_table():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auction_holds (
                auction_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                created_at INTEGER
            );
            """
        )
        con.commit()

def get_auction_hold(auction_id: int):
    ensure_auction_holds_table()
    with _db() as con:
        row = con.execute("SELECT user_id, amount FROM auction_holds WHERE auction_id=?", (auction_id,)).fetchone()
        return (row[0], float(row[1])) if row else None

def set_auction_hold(auction_id: int, user_id: int, amount: float):
    ensure_auction_holds_table()
    import time
    with _db() as con:
        con.execute(
            """
            INSERT INTO auction_holds (auction_id, user_id, amount, created_at)
            VALUES (?,?,?,?)
            ON CONFLICT(auction_id) DO UPDATE SET user_id=excluded.user_id, amount=excluded.amount, created_at=excluded.created_at
            """,
            (auction_id, user_id, float(amount), int(time.time()))
        )
        con.commit()

def clear_auction_hold(auction_id: int):
    ensure_auction_holds_table()
    with _db() as con:
        con.execute("DELETE FROM auction_holds WHERE auction_id=?", (auction_id,))
        con.commit()

# ==========================
# АУКЦІОНИ: СТАТУСИ ТА ВИДАЛЕННЯ
# ==========================
def set_auction_status(auction_id: int, status: str):
    """Оновлює статус аукціону: active | paused | finished."""
    with _db() as con:
        con.execute("UPDATE auctions SET status=? WHERE id=?", (status, auction_id))
        con.commit()

def pause_auction(auction_id: int):
    set_auction_status(auction_id, 'paused')

def resume_auction(auction_id: int):
    set_auction_status(auction_id, 'active')

def delete_auction(auction_id: int):
    """Видаляє аукціон і всі пов'язані записи (ставки, холди)."""
    ensure_auction_holds_table()
    with _db() as con:
        con.execute("DELETE FROM auction_bids WHERE auction_id=?", (auction_id,))
        con.execute("DELETE FROM auction_holds WHERE auction_id=?", (auction_id,))
        con.execute("DELETE FROM auctions WHERE id=?", (auction_id,))
        con.commit()

# ==========================
# АУКЦІОНИ: БАНИ, СПИСКИ ТА АДМІН-УПРАВЛІННЯ УЧАСНИКАМИ
# ==========================
def ensure_auction_bans_table():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auction_bans (
                user_id INTEGER PRIMARY KEY,
                until_ts INTEGER,
                reason TEXT
            );
            """
        )
        con.commit()

def set_auction_ban(user_id: int, duration_seconds: int, reason: str):
    ensure_auction_bans_table()
    import time
    until_ts = int(time.time()) + int(duration_seconds)
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO auction_bans(user_id, until_ts, reason) VALUES(?,?,?)",
            (user_id, until_ts, reason)
        )
        con.commit()

def clear_auction_ban(user_id: int):
    ensure_auction_bans_table()
    with _db() as con:
        con.execute("DELETE FROM auction_bans WHERE user_id=?", (user_id,))
        con.commit()

def get_active_auction_ban(user_id: int):
    ensure_auction_bans_table()
    import time
    now = int(time.time())
    with _db() as con:
        row = con.execute("SELECT until_ts, reason FROM auction_bans WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return None
        until_ts, reason = int(row[0]), row[1]
        if until_ts <= now:
            # автоочистка прострочених
            con.execute("DELETE FROM auction_bans WHERE user_id=?", (user_id,))
            con.commit()
            return None
        return { 'until_ts': until_ts, 'reason': reason }

def list_auction_bidders(auction_id: int):
    """Повертає список (user_id, max_amount, bids_count) відсортований за сумою DESC."""
    with _db() as con:
        rows = con.execute(
            """
            SELECT user_id, MAX(amount) AS max_amt, COUNT(*) AS cnt
            FROM auction_bids
            WHERE auction_id=?
            GROUP BY user_id
            ORDER BY max_amt DESC, cnt DESC
            """,
            (auction_id,)
        ).fetchall()
        return [(r[0], float(r[1]) if r[1] is not None else 0.0, int(r[2])) for r in rows]

def remove_user_from_auction(auction_id: int, user_id: int):
    """Видаляє всі ставки користувача з аукціону, коригує hold і повертає кошти лідеру за потреби."""
    ensure_auction_holds_table()
    from database import get_highest_bid  # type: ignore  # safe self-import when executed as module
    from database import get_auction_hold, clear_auction_hold, set_auction_hold  # type: ignore
    from database import add_balance  # type: ignore
    with _db() as con:
        # Повертаємо hold якщо він належить цьому користувачу
        hold = None
        try:
            hold = get_auction_hold(auction_id)
        except Exception:
            hold = None
        if hold and hold[0] == user_id:
            try:
                add_balance(user_id, float(hold[1]))
            except Exception:
                pass
            try:
                clear_auction_hold(auction_id)
            except Exception:
                pass
        # Видаляємо ставки користувача
        con.execute("DELETE FROM auction_bids WHERE auction_id=? AND user_id=?", (auction_id, user_id))
        con.commit()
        # Визначаємо нового лідера
        try:
            top = get_highest_bid(auction_id)
            if top:
                set_auction_hold(auction_id, top[0], float(top[1]))
        except Exception:
            pass

def admin_set_user_bid(auction_id: int, user_id: int, new_amount: float):
    """Повністю змінює ставку користувача: очищає його попередні ставки, коригує hold і виставляє нову ставку."""
    ensure_auction_holds_table()
    from database import get_auction_hold, clear_auction_hold, set_auction_hold  # type: ignore
    from database import add_auction_bid, add_balance  # type: ignore
    with _db() as con:
        # Якщо попередній лідер інший — повернути йому кошти
        hold = None
        try:
            hold = get_auction_hold(auction_id)
        except Exception:
            hold = None
        if hold and hold[0] != user_id:
            try:
                add_balance(hold[0], float(hold[1]))
            except Exception:
                pass
            try:
                clear_auction_hold(auction_id)
            except Exception:
                pass
        elif hold and hold[0] == user_id:
            # Вирівнюємо різницю по hold
            diff = float(new_amount) - float(hold[1])
            try:
                add_balance(user_id, -diff)
            except Exception:
                pass
            try:
                clear_auction_hold(auction_id)
            except Exception:
                pass
        # Видаляємо старі ставки користувача, щоб MAX(amount) відображав нове значення
        con.execute("DELETE FROM auction_bids WHERE auction_id=? AND user_id=?", (auction_id, user_id))
        con.commit()
        # Додаємо нову ставку і встановлюємо hold
        add_auction_bid(auction_id, user_id, float(new_amount))
        set_auction_hold(auction_id, user_id, float(new_amount))

# ==========================
# АУКЦІОНИ: ВИДАЛЕНІ З ЛОТА (ЛОКАЛЬНА ЗАБОРОНА)
# ==========================
def ensure_auction_removed_table():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS auction_removed (
                auction_id INTEGER,
                user_id INTEGER,
                removed_at INTEGER,
                reason TEXT,
                PRIMARY KEY(auction_id, user_id)
            );
            """
        )
        con.commit()

def add_auction_removed(auction_id: int, user_id: int, reason: str | None = None):
    ensure_auction_removed_table()
    import time
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO auction_removed(auction_id, user_id, removed_at, reason) VALUES(?,?,?,?)",
            (auction_id, user_id, int(time.time()), reason or '')
        )
        con.commit()

def is_user_removed_from_auction(auction_id: int, user_id: int) -> bool:
    ensure_auction_removed_table()
    with _db() as con:
        row = con.execute("SELECT 1 FROM auction_removed WHERE auction_id=? AND user_id=?", (auction_id, user_id)).fetchone()
        return bool(row)

def list_removed_users(auction_id: int, limit: int = 3):
    ensure_auction_removed_table()
    with _db() as con:
        rows = con.execute(
            "SELECT user_id, reason, removed_at FROM auction_removed WHERE auction_id=? ORDER BY removed_at DESC LIMIT ?",
            (auction_id, limit)
        ).fetchall()
        return [(r[0], r[1], r[2]) for r in rows]

def remove_user_from_auction_with_reason(auction_id: int, user_id: int, reason: str | None = None):
    remove_user_from_auction(auction_id, user_id)
    add_auction_removed(auction_id, user_id, reason or '')

# ==========================
# АУКЦІОНИ: СТАТИСТИКА
# ==========================
def get_auction_statistics(days: int = 30):
    """Повертає загальну статистику аукціонів за період"""
    import time
    cutoff_time = int(time.time()) - (days * 24 * 3600)
    with _db() as con:
        # Загальна статистика
        total_auctions = con.execute(
            "SELECT COUNT(*) FROM auctions WHERE started_at >= ?", (cutoff_time,)
        ).fetchone()[0]
        
        finished_auctions = con.execute(
            "SELECT COUNT(*) FROM auctions WHERE status='finished' AND started_at >= ?", (cutoff_time,)
        ).fetchone()[0]
        
        active_auctions = con.execute(
            "SELECT COUNT(*) FROM auctions WHERE status='active'", ()
        ).fetchone()[0]
        
        # Загальний об'єм ставок
        total_bids_volume = con.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM auction_bids 
            WHERE created_at >= ?
        """, (cutoff_time,)).fetchone()[0] or 0.0
        
        # Загальний дохід (комісія з виграшних ставок)
        total_revenue = con.execute("""
            SELECT COALESCE(SUM(winner_price), 0) 
            FROM auctions 
            WHERE status='finished' AND winner_price IS NOT NULL AND started_at >= ?
        """, (cutoff_time,)).fetchone()[0] or 0.0
        
        settings = get_auction_settings()
        commission_revenue = total_revenue * (settings['commission_percent'] / 100)
        
        # Середня ціна виграшу
        avg_win_price = con.execute("""
            SELECT COALESCE(AVG(winner_price), 0) 
            FROM auctions 
            WHERE status='finished' AND winner_price IS NOT NULL AND started_at >= ?
        """, (cutoff_time,)).fetchone()[0] or 0.0
        
        # Кількість унікальних учасників
        unique_bidders = con.execute("""
            SELECT COUNT(DISTINCT user_id) 
            FROM auction_bids 
            WHERE created_at >= ?
        """, (cutoff_time,)).fetchone()[0]
        
        # Загальна кількість ставок
        total_bids_count = con.execute("""
            SELECT COUNT(*) 
            FROM auction_bids 
            WHERE created_at >= ?
        """, (cutoff_time,)).fetchone()[0]
        
        return {
            'total_auctions': total_auctions,
            'finished_auctions': finished_auctions,
            'active_auctions': active_auctions,
            'total_bids_volume': float(total_bids_volume),
            'total_revenue': float(total_revenue),
            'commission_revenue': float(commission_revenue),
            'avg_win_price': float(avg_win_price),
            'unique_bidders': unique_bidders,
            'total_bids_count': total_bids_count,
            'days': days
        }

def get_top_auction_bidders(limit: int = 10, days: int = 30):
    """Повертає топ учасників аукціонів за об'ємом ставок"""
    import time
    cutoff_time = int(time.time()) - (days * 24 * 3600)
    with _db() as con:
        rows = con.execute("""
            SELECT 
                user_id,
                COUNT(DISTINCT auction_id) as auctions_count,
                COUNT(*) as bids_count,
                SUM(amount) as total_bids,
                MAX(amount) as max_bid
            FROM auction_bids
            WHERE created_at >= ?
            GROUP BY user_id
            ORDER BY total_bids DESC
            LIMIT ?
        """, (cutoff_time, limit)).fetchall()
        
        return [
            {
                'user_id': r[0],
                'auctions_count': r[1],
                'bids_count': r[2],
                'total_bids': float(r[3]),
                'max_bid': float(r[4])
            } for r in rows
        ]

def get_top_auction_winners(limit: int = 10, days: int = 30):
    """Повертає топ переможців аукціонів"""
    import time
    cutoff_time = int(time.time()) - (days * 24 * 3600)
    with _db() as con:
        rows = con.execute("""
            SELECT 
                winner_user_id,
                COUNT(*) as wins_count,
                SUM(winner_price) as total_spent,
                AVG(winner_price) as avg_price
            FROM auctions
            WHERE status='finished' 
                AND winner_user_id IS NOT NULL 
                AND started_at >= ?
            GROUP BY winner_user_id
            ORDER BY total_spent DESC
            LIMIT ?
        """, (cutoff_time, limit)).fetchall()
        
        return [
            {
                'user_id': r[0],
                'wins_count': r[1],
                'total_spent': float(r[2]),
                'avg_price': float(r[3])
            } for r in rows
        ]

def get_auction_participation_stats(user_id: int, days: int = 30):
    """Повертає статистику участі конкретного користувача"""
    import time
    cutoff_time = int(time.time()) - (days * 24 * 3600)
    with _db() as con:
        # Загальна статистика ставок
        bids_stats = con.execute("""
            SELECT 
                COUNT(*) as bids_count,
                COUNT(DISTINCT auction_id) as auctions_count,
                SUM(amount) as total_bids,
                MAX(amount) as max_bid,
                MIN(amount) as min_bid
            FROM auction_bids
            WHERE user_id = ? AND created_at >= ?
        """, (user_id, cutoff_time)).fetchone()
        
        # Статистика перемог
        wins_stats = con.execute("""
            SELECT 
                COUNT(*) as wins_count,
                SUM(winner_price) as total_spent,
                AVG(winner_price) as avg_price
            FROM auctions
            WHERE winner_user_id = ? 
                AND status='finished' 
                AND started_at >= ?
        """, (user_id, cutoff_time)).fetchone()
        
        return {
            'bids_count': bids_stats[0] or 0,
            'auctions_count': bids_stats[1] or 0,
            'total_bids': float(bids_stats[2] or 0),
            'max_bid': float(bids_stats[3] or 0),
            'min_bid': float(bids_stats[4] or 0),
            'wins_count': wins_stats[0] or 0,
            'total_spent': float(wins_stats[1] or 0),
            'avg_win_price': float(wins_stats[2] or 0)
        }

# --- Garden Level Functions ---
def get_garden_history(user_id: int, limit: int = 50):
    """Повертає історію дій у саду користувача (покупки, продажі, збори, ціни, часи)"""
    with _db() as con:
        rows = con.execute("SELECT id, type, amount, currency, timestamp, comment FROM garden_transactions WHERE user_id=? ORDER BY timestamp DESC LIMIT ?", (user_id, limit)).fetchall()
        return [
            {"id": r[0], "type": r[1], "amount": r[2], "currency": r[3], "timestamp": r[4], "comment": r[5]} for r in rows
        ]

def get_garden_history_summary(user_id: int, days: int = 7):
    """Повертає згруповану статистику історії саду за останні дні"""
    import time
    with _db() as con:
        cutoff_time = int(time.time()) - (days * 24 * 3600)
        rows = con.execute("""
            SELECT type, COUNT(*) as count, SUM(amount) as total_amount, currency
            FROM garden_transactions 
            WHERE user_id=? AND timestamp >= ?
            GROUP BY type, currency
            ORDER BY type
        """, (user_id, cutoff_time)).fetchall()
        
        return [
            {
                "type": r[0], 
                "count": r[1], 
                "total_amount": r[2], 
                "currency": r[3]
            } for r in rows
        ]

def get_garden_history_by_date(user_id: int, date_filter: str = "today"):
    """Повертає історію саду за певний період"""
    import time
    from datetime import datetime, timedelta
    
    now = datetime.now()
    
    if date_filter == "today":
        start_time = int(datetime(now.year, now.month, now.day).timestamp())
    elif date_filter == "week":
        start_time = int((now - timedelta(days=7)).timestamp())
    elif date_filter == "month":
        start_time = int((now - timedelta(days=30)).timestamp())
    else:
        start_time = 0
    
    with _db() as con:
        rows = con.execute("""
            SELECT id, type, amount, currency, timestamp, comment 
            FROM garden_transactions 
            WHERE user_id=? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (user_id, start_time)).fetchall()
        
        return [
            {"id": r[0], "type": r[1], "amount": r[2], "currency": r[3], "timestamp": r[4], "comment": r[5]} for r in rows
        ]

def cleanup_old_garden_history(days_to_keep: int = 90):
    """Видаляє старі записи історії саду (старіше вказаної кількості днів)"""
    import time
    cutoff_time = int(time.time()) - (days_to_keep * 24 * 3600)
    
    with _db() as con:
        # Отримуємо кількість записів для видалення
        count_row = con.execute("SELECT COUNT(*) FROM garden_transactions WHERE timestamp < ?", (cutoff_time,)).fetchone()
        count_to_delete = count_row[0] if count_row else 0
        
        if count_to_delete > 0:
            # Видаляємо старі записи
            con.execute("DELETE FROM garden_transactions WHERE timestamp < ?", (cutoff_time,))
            con.commit()
            return count_to_delete
        return 0

def get_garden_history_stats(user_id: int = None):
    """Повертає статистику історії саду"""
    with _db() as con:
        if user_id:
            # Статистика для конкретного користувача
            total_rows = con.execute("SELECT COUNT(*) FROM garden_transactions WHERE user_id=?", (user_id,)).fetchone()
            oldest_row = con.execute("SELECT MIN(timestamp) FROM garden_transactions WHERE user_id=?", (user_id,)).fetchone()
            newest_row = con.execute("SELECT MAX(timestamp) FROM garden_transactions WHERE user_id=?", (user_id,)).fetchone()
        else:
            # Загальна статистика
            total_rows = con.execute("SELECT COUNT(*) FROM garden_transactions").fetchone()
            oldest_row = con.execute("SELECT MIN(timestamp) FROM garden_transactions").fetchone()
            newest_row = con.execute("SELECT MAX(timestamp) FROM garden_transactions").fetchone()
        
        return {
            "total_records": total_rows[0] if total_rows else 0,
            "oldest_timestamp": oldest_row[0] if oldest_row and oldest_row[0] else None,
            "newest_timestamp": newest_row[0] if newest_row and newest_row[0] else None
        }

def add_garden_transaction(user_id: int, type: str, amount: float, currency: str, timestamp: int, comment: str = None):
    """Додає запис про дію у саду користувача (покупка, продаж, збір тощо)"""
    with _db() as con:
        con.execute(
            "INSERT INTO garden_transactions (user_id, type, amount, currency, timestamp, comment) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, type, amount, currency, timestamp, comment)
        )
        con.commit()

def add_ledger_note_chat_change(user_id: int, delta: float, admin_id: int, chat_id: int):
    """Додає допоміжний запис у balance_ledger.details, що зміна прийшла з чату"""
    import time
    try:
        with _db() as con:
            con.execute(
                """
                INSERT INTO balance_ledger (user_id, delta, balance_before, balance_after, reason, details, created_at)
                VALUES (?, ?, COALESCE((SELECT balance FROM users WHERE user_id=?),0),
                        COALESCE((SELECT balance FROM users WHERE user_id=?),0),
                        'admin_chat_meta', ?, ?)
                """,
                (user_id, float(delta), user_id, user_id, f'by {admin_id} in chat {chat_id}', int(time.time()))
            )
            con.commit()
    except Exception:
        pass

def create_stars_transaction(user_id: int, stars_amount: int, uah_amount: float):
    """Створює транзакцію Stars"""
    import time
    with _db() as con:
        cursor = con.execute(
            "INSERT INTO stars_transactions (user_id, stars_amount, uah_amount, status, timestamp) VALUES (?, ?, ?, 'pending', ?)",
            (user_id, stars_amount, uah_amount, int(time.time()))
        )
        con.commit()
        return cursor.lastrowid

def update_stars_transaction(transaction_id: int, telegram_charge_id: str = None, provider_payment_charge_id: str = None, status: str = 'completed'):
    """Оновлює статус транзакції Stars"""
    with _db() as con:
        con.execute(
            "UPDATE stars_transactions SET telegram_charge_id = ?, provider_payment_charge_id = ?, status = ? WHERE id = ?",
            (telegram_charge_id, provider_payment_charge_id, status, transaction_id)
        )
        con.commit()

def get_stars_transaction(transaction_id: int):
    """Отримує інформацію про транзакцію Stars"""
    with _db() as con:
        cursor = con.execute("SELECT * FROM stars_transactions WHERE id = ?", (transaction_id,))
        return cursor.fetchone()

def stars_to_uah_rate():
    """Курс обміну Stars на гривні (1 Star = 0.01 UAH)"""
    return 0.01

def uah_to_stars_rate():
    """Курс обміну гривень на Stars (1 UAH = 100 Stars)"""
    return 100

# === НАСТРОЙКИ STARS ===

def get_stars_settings():
    """Получает настройки Stars"""
    with _db() as con:
        cursor = con.execute("SELECT * FROM stars_settings LIMIT 1")
        row = cursor.fetchone()
        if row:
            return {
                'exchange_rate': row[0],      # Курс обмена (Stars за 1 UAH)
                'min_deposit': row[1],        # Минимальная сумма депозита в Stars
                'enabled': bool(row[2]),      # Включены ли Stars
                'admin_fee_percent': row[3]   # Комиссия админа (%)
            }
        else:
            # Настройки по умолчанию
            return {
                'exchange_rate': 100,         # 100 Stars = 1 UAH
                'min_deposit': 100,           # Минимум 100 Stars
                'enabled': True,              # Включены
                'admin_fee_percent': 0        # Без комиссии
            }

def update_stars_settings(exchange_rate=None, min_deposit=None, enabled=None, admin_fee_percent=None):
    """Обновляет настройки Stars"""
    with _db() as con:
        # Обновляем только указанные параметры
        updates = []
        params = []
        
        if exchange_rate is not None:
            updates.append("exchange_rate = ?")
            params.append(exchange_rate)
        
        if min_deposit is not None:
            updates.append("min_deposit = ?")
            params.append(min_deposit)
            
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(int(enabled))
            
        if admin_fee_percent is not None:
            updates.append("admin_fee_percent = ?")
            params.append(admin_fee_percent)
        
        if updates:
            query = f"UPDATE stars_settings SET {', '.join(updates)}"
            con.execute(query, params)
        
        con.commit()

def get_stars_balance():
    """Получает баланс Stars бота (примерная функция)"""
    # Это примерная функция - реальный баланс нужно получать через Telegram API
    with _db() as con:
        cursor = con.execute("SELECT SUM(stars_amount) FROM stars_transactions WHERE status = 'completed'")
        total_received = cursor.fetchone()[0] or 0
        
        cursor = con.execute("SELECT SUM(stars_amount) FROM stars_payouts WHERE status = 'completed'")
        total_paid = cursor.fetchone()[0] or 0
        
        return total_received - total_paid

def create_stars_payout(user_id, stars_amount, description=""):
    """Создает выплату Stars пользователю"""
    import time
    with _db() as con:
        cursor = con.execute(
            "INSERT INTO stars_payouts (user_id, stars_amount, description, status, timestamp) VALUES (?, ?, ?, 'pending', ?)",
            (user_id, stars_amount, description, int(time.time()))
        )
        con.commit()
        return cursor.lastrowid

def get_user_garden_level(user_id: int):
    """Повертає словник з level та purchased_at або None"""
    with _db() as con:
        row = con.execute("SELECT level, purchased_at FROM user_garden_level WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return {"level": row[0], "purchased_at": row[1]}
        return None

def set_user_garden_level(user_id: int, level: int, purchased_at: int):
    """Встановлює/оновлює рівень саду користувача"""
    with _db() as con:
        con.execute("INSERT INTO user_garden_level (user_id, level, purchased_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET level=excluded.level, purchased_at=excluded.purchased_at", (user_id, level, purchased_at))
        con.commit()

def get_all_user_garden_levels():
    """Повертає список усіх garden level користувачів"""
    with _db() as con:
        rows = con.execute("SELECT user_id, level, purchased_at FROM user_garden_level").fetchall()
        return [{"user_id": r[0], "level": r[1], "purchased_at": r[2]} for r in rows]

# ─── депозити ───────────────────────────────
def get_deposits_sum(user_id):
    with _db() as con:
        row = con.execute("SELECT deposits FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

def create_deposit(user_id: int, user_name: str, amount: float, comment: str = None, proof: str = None):
    with _db() as con:
        cur = con.execute("""
            INSERT INTO deposit_tx (user_id, user_name, amount, comment, proof, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (user_id, user_name, amount, comment, proof))
        dep_id = cur.lastrowid
        con.commit()
    return dep_id

def get_deposits(status: str = None):
    with _db() as con:
        if status:
            rows = con.execute("SELECT * FROM deposit_tx WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT * FROM deposit_tx ORDER BY created_at DESC").fetchall()
    return rows

def approve_deposit(deposit_id: int):
    with _db() as con:
        con.execute("UPDATE deposit_tx SET status = 'approved' WHERE id = ?", (deposit_id,))
        # Зарахувати баланс користувачу
        row = con.execute("SELECT user_id, amount FROM deposit_tx WHERE id = ?", (deposit_id,)).fetchone()
        if row:
            uid, amt = row
            # З урахуванням бонусів/множника
            try:
                info = calculate_deposit_bonus(float(amt))
                effective = float(info.get('effective', amt))
            except Exception:
                effective = float(amt)
            # Обновляем баланс с бонусами
            con.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (effective, uid))
            # Обновляем сумму депозитов БЕЗ бонусов (только реальная сумма пополнения)
            con.execute("UPDATE users SET deposits = COALESCE(deposits, 0) + ? WHERE user_id = ?", (float(amt), uid))
        con.commit()

def reject_deposit(deposit_id: int):
    with _db() as con:
        con.execute("UPDATE deposit_tx SET status = 'rejected' WHERE id = ?", (deposit_id,))
        con.commit()

def reject_deposit_with_reason(deposit_id: int, reason: str):
    with _db() as con:
        con.execute("UPDATE deposit_tx SET status = 'rejected', comment = ? WHERE id = ?", (reason, deposit_id))
        con.commit()


def get_deposit_by_id(deposit_id: int):
    with _db() as con:
        row = con.execute("SELECT * FROM deposit_tx WHERE id = ?", (deposit_id,)).fetchone()
    return row

# --- юзери ────────────────────────────────────
def get_next_local_user_id():
    """Генерирует следующий локальный ID для пользователей без Telegram (начинается с -1, -2, -3...)"""
    with _db() as con:
        # Ищем максимальный отрицательный ID (локальные пользователи)
        result = con.execute("SELECT MIN(user_id) FROM users WHERE user_id < 0").fetchone()
        if result and result[0] is not None:
            # Если есть отрицательные ID, берем минимальный и вычитаем 1
            next_id = result[0] - 1
        else:
            # Если нет отрицательных ID, начинаем с -1
            next_id = -1
        return next_id

def create_local_user(name: str = "Гість"):
    """Создает нового локального пользователя (без Telegram) с автоматическим ID"""
    import time
    with _db() as con:
        now = int(time.time())
        local_id = get_next_local_user_id()
        
        # Создаем пользователя с отрицательным ID и нулевыми значениями
        con.execute("""
            INSERT INTO users (user_id, user_name, date_joined, last_active, balance, withdrawn, last_bonus, deposits) 
            VALUES (?, ?, ?, ?, 0, 0, 0, 0)
        """, (local_id, name, now, now))
        con.commit()
        
        return local_id

def get_or_create_local_user(session_id: str, name: str = "Гість"):
    """Получает или создает локального пользователя на основе session_id"""
    import time
    with _db() as con:
        now = int(time.time())
        
        # Проверяем, есть ли уже пользователь для этой сессии
        # Используем таблицу local_user_sessions для связи session_id с user_id
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS local_user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at INTEGER,
                    last_active INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            con.commit()
        except Exception:
            pass
        
        # Ищем существующую сессию
        row = con.execute("SELECT user_id FROM local_user_sessions WHERE session_id = ?", (session_id,)).fetchone()
        
        if row:
            user_id = row[0]
            # Обновляем last_active
            con.execute("UPDATE local_user_sessions SET last_active = ? WHERE session_id = ?", (now, session_id))
            con.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))
            con.commit()
            return user_id
        else:
            # Создаем нового пользователя
            local_id = get_next_local_user_id()
            con.execute("""
                INSERT INTO users (user_id, user_name, date_joined, last_active, balance, withdrawn, last_bonus, deposits) 
                VALUES (?, ?, ?, ?, 0, 0, 0, 0)
            """, (local_id, name, now, now))
            con.execute("""
                INSERT INTO local_user_sessions (session_id, user_id, created_at, last_active)
                VALUES (?, ?, ?, ?)
            """, (session_id, local_id, now, now))
            con.commit()
            return local_id

def ensure_user(uid: int, name: str):
    import time
    with _db() as con:
        now = int(time.time())
        
        # Спочатку перевіряємо, чи існує користувач
        existing = con.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,)).fetchone()
        
        created = False
        if existing:
            # Якщо існує — оновлюємо last_active та user_name
            con.execute("UPDATE users SET last_active=?, user_name=? WHERE user_id=?", (now, name, uid))
        else:
            # Якщо не існує — створюємо нового
            con.execute("INSERT INTO users (user_id, user_name, date_joined, last_active, balance, withdrawn, last_bonus, deposits) VALUES (?, ?, ?, ?, 0, 0, 0, 0)", (uid, name, now, now))
            created = True
        
        con.commit()

        # Якщо створено нового користувача — записуємо в чергу сповіщень (щоб бот відправив адміну)
        # Только для Telegram пользователей (положительные ID)
        if created and uid > 0:
            try:
                con.execute("INSERT OR REPLACE INTO new_user_notifications (user_id, user_name, created_at, notified) VALUES (?, ?, ?, 0)", (uid, name, now))
                con.commit()
            except Exception:
                pass

def get_user(uid: int):
    with _db() as con:
        row = con.execute("""
            SELECT user_id, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username,
                   COALESCE(transferable_balance, 0.0), COALESCE(locked_balance, 0.0)
            FROM users WHERE user_id = ?
        """, (uid,)).fetchone()
        if not row:
            # Легка авто-реєстрація при першому зверненні (без імені)
            try:
                ensure_user(uid, str(uid))
                row = con.execute("SELECT user_id, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username FROM users WHERE user_id = ?", (uid,)).fetchone()
            except Exception:
                pass
        return row if row else None

def set_user_balance(user_id: int, new_balance: float):
    """Встановлює баланс користувача на конкретне значення."""
    with _db() as con:
        con.execute("UPDATE users SET balance = ? WHERE user_id = ?", (float(new_balance), user_id))
        con.commit()

def get_user_by_username(username: str):
    '''Повертає кортеж (user_id, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username) або None'''
    if username.startswith("@"): username = username[1:]
    with _db() as con:
        row = con.execute("SELECT user_id, user_name, balance, withdrawn, last_bonus, deposits, date_joined, last_active, username FROM users WHERE LOWER(user_name) = LOWER(?) OR LOWER(username) = LOWER(?)", (username, username)).fetchone()
        return row if row else None

def add_balance(uid: int, amt: float, force_admin: bool = False, reason: str | None = None, details: str | None = None):
    import time
    import json
    with _db() as con:
        # Поточний баланс до змін
        row = con.execute("SELECT balance FROM users WHERE user_id = ?", (uid,)).fetchone()
        if not row:
            return
        balance_before = float(row[0])

        # Вносимо suppress, щоб тригер не дублював запис
        try:
            con.execute("INSERT OR REPLACE INTO ledger_suppress (user_id) VALUES (?)", (uid,))
        except Exception:
            pass

        if force_admin:
            # Дозволяємо будь-який баланс, навіть від'ємний
            new_balance = round_float(balance_before + amt)
            con.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, uid))
        else:
            # Не дозволяємо баланс < 0
            new_balance = round_float(balance_before + amt)
            if new_balance < 0:
                new_balance = 0
            con.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, uid))

        # Видаляємо suppress перед ручним записом у леджер
        try:
            con.execute("DELETE FROM ledger_suppress WHERE user_id = ?", (uid,))
        except Exception:
            pass

        # Ручний запис у леджер із причиною
        try:
            con.execute(
                """
                INSERT INTO balance_ledger (user_id, delta, balance_before, balance_after, reason, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    float(new_balance) - float(balance_before),
                    float(balance_before),
                    float(new_balance),
                    reason or 'auto',
                    details,
                    int(time.time())
                )
            )
        except Exception:
            # Навіть якщо леджер не записався — баланс має оновитись
            pass

        con.commit()
        
        # Создаем уведомление об изменении баланса (если изменение значительное)
        delta = float(new_balance) - float(balance_before)
        if abs(delta) > 0.01:  # Только если изменение больше 1 копейки
            try:
                ensure_notifications_table()
                if delta > 0:
                    title = "💰 Баланс поповнено"
                    message = f"Ваш баланс збільшено на {delta:.2f}₴\nНовий баланс: {new_balance:.2f}₴"
                else:
                    title = "💸 Баланс зменшено"
                    message = f"З вашого балансу списано {abs(delta):.2f}₴\nНовий баланс: {new_balance:.2f}₴"
                
                if reason:
                    message += f"\nПричина: {reason}"
                if details:
                    message += f"\n{details}"
                
                data_json = json.dumps({'delta': delta, 'balance_before': balance_before, 'balance_after': new_balance}) if 'json' in dir() else None
                con.execute("""
                    INSERT INTO notifications (user_id, type, title, message, data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (uid, 'balance_change', title, message, data_json, int(time.time())))
                con.commit()
            except Exception as e:
                # Если не удалось создать уведомление - не критично
                pass

# ─── виведення ───────────────────────────────

def delete_withdrawals_by_status(status=None):
    """Видаляє заявки за статусом. Якщо status=None, видаляє всі заявки."""
    with _db() as con:
        if status is None:
            con.execute("DELETE FROM tx")
        else:
            con.execute("DELETE FROM tx WHERE status=?", (status,))

def count_withdrawals_by_status(status=None):
    """Повертає кількість заявок за статусом. Якщо status=None, рахує всі заявки."""
    with _db() as con:
        if status is None:
            row = con.execute("SELECT COUNT(*) FROM tx").fetchone()
        else:
            row = con.execute("SELECT COUNT(*) FROM tx WHERE status=?", (status,)).fetchone()
        return row[0] if row else 0

def create_withdraw(user_id, amount, service_name, requisites):
    with _db() as con:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cur = con.execute(
            "INSERT INTO tx (user_id, amount, comment, status, requisites, created_at) VALUES (?, ?, ?, 'pending', ?, ?)",
            (user_id, amount, service_name, requisites, now)
        )
        tx_id = cur.lastrowid
        con.commit()
        return tx_id

def confirm_withdraw(tx_id:int):
    with _db() as con:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        tx = con.execute("SELECT user_id,amount,status FROM tx WHERE tx_id=?", (tx_id,)).fetchone()
        if not tx or tx[2] != 'pending':
            return False
        uid, amt, _ = tx
        cur = con.execute("UPDATE users SET balance = balance - ?, withdrawn = withdrawn + ? WHERE user_id=? AND balance>=?",
                          (amt, amt, uid, amt))
        if cur.rowcount:
            con.execute("UPDATE tx SET status='done', processed_at=? WHERE tx_id=?", (now, tx_id))
            return True
        return False

def reject_withdraw(tx_id:int):
    with _db() as con:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        con.execute("UPDATE tx SET status='rejected', processed_at=? WHERE tx_id=? AND status='pending'", (now, tx_id))

def reject_withdraw_with_reason(tx_id: int, reason: str):
    """Відхиляє заявку на вивід з вказаною причиною. Зберігає причину у полі comment, додаючи префікс."""
    if reason is None:
        reason = ""
    # Обрізаємо довгі причини, щоб не поламати форматування/базу
    reason = str(reason).strip()
    if len(reason) > 500:
        reason = reason[:500]
    with _db() as con:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Дістаємо поточний коментар, щоб не втратити попередні дані (наприклад назву сервісу)
        row = con.execute("SELECT comment FROM tx WHERE tx_id=?", (tx_id,)).fetchone()
        existing_comment = row[0] if row else None
        new_comment = existing_comment or ""
        if reason:
            # Додаємо видимий префікс причини
            prefix = " | REJECT_REASON: "
            if prefix in new_comment:
                # При повторному встановленні замінюємо стару причину
                new_comment = new_comment.split(prefix)[0]
            new_comment = f"{new_comment}{prefix}{reason}" if new_comment else f"REJECT_REASON: {reason}"
        con.execute(
            "UPDATE tx SET status='rejected', processed_at=?, comment=? WHERE tx_id=? AND status='pending'",
            (now, new_comment, tx_id)
        )

def reject_and_burn_with_reason(tx_id: int, reason: str) -> bool:
    """Скасовує заявку та списує суму заявки з балансу користувача. Повертає True якщо успішно."""
    if reason is None:
        reason = ""
    reason = str(reason).strip()
    if len(reason) > 500:
        reason = reason[:500]
    with _db() as con:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        # Отримуємо заявку
        row = con.execute("SELECT user_id, amount, status, comment FROM tx WHERE tx_id=?", (tx_id,)).fetchone()
        if not row or row[2] != 'pending':
            return False
        uid, amt, _, existing_comment = row
        new_comment = existing_comment or ""
        prefix = " | REJECT_BURN_REASON: "
        if prefix in new_comment:
            new_comment = new_comment.split(prefix)[0]
        if reason:
            new_comment = f"{new_comment}{prefix}{reason}" if new_comment else f"REJECT_BURN_REASON: {reason}"

        # Спробуємо списати баланс (не допускаємо від'ємного балансу)
        # Якщо балансу недостатньо — списати те, що є (встановити в 0)
        cur = con.execute("SELECT balance FROM users WHERE user_id=?", (uid,)).fetchone()
        current_balance = cur[0] if cur else 0
        try:
            if current_balance >= amt:
                con.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amt, uid))
            else:
                # спишемо все і встановимо баланс в 0
                con.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (uid,))
        except Exception:
            # якщо щось пішло не так — повертаємо False
            return False

        # Встановлюємо статус заявки як rejected та зберігаємо причину
        con.execute("UPDATE tx SET status='rejected', processed_at=?, comment=? WHERE tx_id=? AND status='pending'", (now, new_comment, tx_id))
        con.commit()
        return True

def total_withdrawn():
    with _db() as con:
        return con.execute("SELECT COALESCE(SUM(amount),0) FROM tx WHERE status='done'").fetchone()[0]
    
# ─── Адміни ───────────────────────────────
def is_admin(user_id: int) -> bool:
    """Повертає True, якщо користувач є адміном.
    
    Джерела прав адміна:
    1) Створювач бота (жорстко прописаний ID)
    2) Список ID у файлі admin_ids.txt (рядок = один ID)
    3) Таблиця admins в БД
    """
    global ADMIN_IDS_CACHE

    # 1) Створювач бота
    if user_id == 6029312631:
        print(f"[DEBUG] is_admin: {user_id} - це створювач бота")
        return True

    # 2) Список ID з текстового файлу admin_ids.txt
    if ADMIN_IDS_CACHE is None:
        ADMIN_IDS_CACHE = _load_admin_ids_from_file()
        print(f"[DEBUG] Loaded admin_ids from file: {ADMIN_IDS_CACHE}")

    if ADMIN_IDS_CACHE and user_id in ADMIN_IDS_CACHE:
        print(f"[DEBUG] is_admin: {user_id} знайдено в admin_ids.txt")
        return True

    # 3) Перевірка в таблиці admins
    with _db() as con:
        cur = con.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        result = cur.fetchone() is not None
        print(f"[DEBUG] is_admin: {user_id} - результат перевірки в БД: {result}")
        return result

def is_bot_creator(user_id: int) -> bool:
    """Перевіряє, чи є користувач створювачем бота"""
    return user_id == 6029312631

def grant_admin(user_id: int):
    with _db() as con:
        print(f"[DEBUG] grant_admin: додаємо user_id {user_id} в таблицю admins")
        result = con.execute("INSERT OR IGNORE INTO admins(user_id) VALUES(?)", (user_id,))
        con.commit()
        print(f"[DEBUG] grant_admin: результат INSERT: {result.rowcount} рядків змінено")
        
        # Додаткова перевірка для створювача бота
        if user_id == 6029312631:
            print(f"[DEBUG] grant_admin: підтверджуємо права створювача бота {user_id}")
            # Перевіряємо, чи є він в таблиці
            check = con.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)).fetchone()
            if check:
                print(f"[DEBUG] grant_admin: створювач бота {user_id} знайдений в таблиці admins")
            else:
                print(f"[DEBUG] grant_admin: створювач бота {user_id} НЕ знайдений в таблиці admins - додаємо примусово")
                con.execute("INSERT INTO admins(user_id) VALUES(?)", (user_id,))
                con.commit()

def revoke_admin(user_id: int):
    with _db() as con:
        con.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        con.commit()

# ─── СИСТЕМА РОЛЕЙ ───────────────────────────────
def grant_role(user_id: int, role: str, granted_by: int = None):
    """Видає роль користувачу"""
    with _db() as con:
        import time
        granted_at = int(time.time())
        con.execute("""
            INSERT OR REPLACE INTO user_roles (user_id, role, granted_at, granted_by)
            VALUES (?, ?, ?, ?)
        """, (user_id, role, granted_at, granted_by))
        con.commit()

def revoke_role(user_id: int, role: str):
    """Знімає роль у користувача"""
    with _db() as con:
        con.execute("DELETE FROM user_roles WHERE user_id = ? AND role = ?", (user_id, role))
        con.commit()

def has_role(user_id: int, role: str) -> bool:
    """Перевіряє, чи є у користувача певна роль"""
    with _db() as con:
        row = con.execute("SELECT 1 FROM user_roles WHERE user_id = ? AND role = ?", (user_id, role)).fetchone()
        return row is not None

def is_giveaway_manager(user_id: int) -> bool:
    """Перевіряє, чи є користувач менеджером розіграшів"""
    return has_role(user_id, 'giveaway_manager') or is_admin(user_id)

def is_payout_manager(user_id: int) -> bool:
    """Перевіряє, чи є користувач менеджером виплат"""
    return has_role(user_id, 'payout_manager') or is_admin(user_id)

def get_user_roles(user_id: int) -> list:
    """Повертає список ролей користувача"""
    with _db() as con:
        rows = con.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,)).fetchall()
        return [row[0] for row in rows]

def get_all_users_with_roles() -> list:
    """Повертає список усіх користувачів з ролями"""
    with _db() as con:
        rows = con.execute("""
            SELECT ur.user_id, ur.role, ur.granted_at, ur.granted_by, u.user_name
            FROM user_roles ur
            LEFT JOIN users u ON ur.user_id = u.user_id
            ORDER BY ur.user_id, ur.role
        """).fetchall()
        # Групуємо по user_id
        users_dict = {}
        for row in rows:
            user_id = row[0]
            if user_id not in users_dict:
                users_dict[user_id] = {
                    'user_id': user_id,
                    'user_name': row[4] or f"Користувач {user_id}",
                    'roles': []
                }
            users_dict[user_id]['roles'].append({
                'role': row[1],
                'granted_at': row[2],
                'granted_by': row[3]
            })
        return list(users_dict.values())

# ─── СИСТЕМА ЛІМІТІВ ДЛЯ РОЗІГРАШІВ ───────────────────────────────
def get_giveaway_limits() -> dict:
    """Повертає поточні ліміти для розіграшів"""
    with _db() as con:
        row = con.execute("""
            SELECT max_prize_amount, max_per_day, max_participants, approval_threshold
            FROM giveaway_limits
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        if row:
            return {
                'max_prize_amount': float(row[0]),
                'max_per_day': int(row[1]),
                'max_participants': int(row[2]),
                'approval_threshold': float(row[3])
            }
        # Значення за замовчуванням
        return {
            'max_prize_amount': 1000.0,
            'max_per_day': 5,
            'max_participants': 0,
            'approval_threshold': 250.0
        }

def set_giveaway_limits(max_prize_amount: float = None, max_per_day: int = None, 
                        max_participants: int = None, approval_threshold: float = None):
    """Встановлює ліміти для розіграшів"""
    with _db() as con:
        import time
        current = get_giveaway_limits()
        cur = con.execute("""
            INSERT INTO giveaway_limits (
                max_prize_amount, max_per_day, max_participants, approval_threshold, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            max_prize_amount if max_prize_amount is not None else current['max_prize_amount'],
            max_per_day if max_per_day is not None else current['max_per_day'],
            max_participants if max_participants is not None else current['max_participants'],
            approval_threshold if approval_threshold is not None else current['approval_threshold'],
            int(time.time())
        ))
        con.commit()

def get_giveaway_daily_stats(user_id: int, date: str = None) -> dict:
    """Повертає статистику розіграшів за день для користувача"""
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
    
    with _db() as con:
        row = con.execute("""
            SELECT count, total_amount
            FROM giveaway_daily_stats
            WHERE user_id = ? AND date = ?
        """, (user_id, date)).fetchone()
        
        if row:
            return {'count': int(row[0]), 'total_amount': float(row[1])}
        return {'count': 0, 'total_amount': 0.0}

def increment_giveaway_daily_stats(user_id: int, amount: float, date: str = None):
    """Збільшує статистику розіграшів за день"""
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
    
    with _db() as con:
        con.execute("""
            INSERT INTO giveaway_daily_stats (user_id, date, count, total_amount)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                count = count + 1,
                total_amount = total_amount + ?
        """, (user_id, date, amount, amount))
        con.commit()

def get_user_giveaway_limits(user_id: int) -> dict:
    """Повертає персональні ліміти користувача для розіграшів (якщо встановлені)"""
    with _db() as con:
        row = con.execute("""
            SELECT max_prize_amount, max_per_day
            FROM user_giveaway_limits
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        if row:
            return {
                'max_prize_amount': float(row[0]) if row[0] else None,
                'max_per_day': int(row[1]) if row[1] else None
            }
        return {'max_prize_amount': None, 'max_per_day': None}

def set_user_giveaway_limits(user_id: int, max_prize_amount: float = None, 
                            max_per_day: int = None, updated_by: int = None):
    """Встановлює персональні ліміти для користувача"""
    with _db() as con:
        import time
        # Перевіряємо чи є вже записи
        existing = con.execute("SELECT 1 FROM user_giveaway_limits WHERE user_id = ?", (user_id,)).fetchone()
        
        if existing:
            # Оновлюємо існуючі
            updates = []
            params = []
            if max_prize_amount is not None:
                updates.append("max_prize_amount = ?")
                params.append(max_prize_amount)
            if max_per_day is not None:
                updates.append("max_per_day = ?")
                params.append(max_per_day)
            if updated_by is not None:
                updates.append("updated_by = ?")
                params.append(updated_by)
            updates.append("updated_at = ?")
            params.append(int(time.time()))
            params.append(user_id)
            
            if updates:
                con.execute(f"""
                    UPDATE user_giveaway_limits
                    SET {', '.join(updates)}
                    WHERE user_id = ?
                """, params)
        else:
            # Створюємо нові
            con.execute("""
                INSERT INTO user_giveaway_limits (user_id, max_prize_amount, max_per_day, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, max_prize_amount, max_per_day, int(time.time()), updated_by))
        con.commit()

def delete_user_giveaway_limits(user_id: int):
    """Видаляє персональні ліміти користувача (використовуватимуться глобальні)"""
    with _db() as con:
        con.execute("DELETE FROM user_giveaway_limits WHERE user_id = ?", (user_id,))
        con.commit()

def check_giveaway_limits(user_id: int, prize_amount: float, participants: int = 0) -> tuple:
    """Перевіряє чи не перевищені ліміти для розіграшу
    
    Спочатку перевіряє персональні ліміти, потім глобальні.
    Повертає (is_valid, error_message, needs_approval)
    """
    global_limits = get_giveaway_limits()
    user_limits = get_user_giveaway_limits(user_id)
    stats = get_giveaway_daily_stats(user_id)
    
    # Використовуємо персональні ліміти якщо вони встановлені, інакше глобальні
    max_prize = user_limits['max_prize_amount'] if user_limits['max_prize_amount'] is not None else global_limits['max_prize_amount']
    max_per_day = user_limits['max_per_day'] if user_limits['max_per_day'] is not None else global_limits['max_per_day']
    
    # Перевірка максимальної суми призу
    if prize_amount > max_prize:
        return (False, f"Максимальна сума призу: {max_prize}₴", False)
    
    # Перевірка ліміту розіграшів за день
    if stats['count'] >= max_per_day:
        return (False, f"Досягнуто ліміт розіграшів за день: {max_per_day}", False)
    
    # Перевірка максимальної кількості учасників (якщо встановлено)
    max_participants = global_limits.get('max_participants', 0)
    if max_participants > 0 and participants > max_participants:
        return (False, f"Максимальна кількість учасників: {max_participants}", False)
    
    # Перевірка чи потрібне підтвердження
    approval_threshold = global_limits.get('approval_threshold', float('inf'))
    needs_approval = prize_amount > approval_threshold
    
    return (True, None, needs_approval)

# ─── СИСТЕМА ЛІМІТІВ ДЛЯ ВИПЛАТ ───────────────────────────────
def get_payout_limits() -> dict:
    """Повертає поточні ліміти для виплат"""
    with _db() as con:
        row = con.execute("""
            SELECT max_amount, max_per_day, daily_total_limit, approval_threshold
            FROM payout_limits
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        if row:
            return {
                'max_amount': float(row[0]),
                'max_per_day': int(row[1]),
                'daily_total_limit': float(row[2]),
                'approval_threshold': float(row[3])
            }
        # Значення за замовчуванням
        return {
            'max_amount': 5000.0,
            'max_per_day': 10,
            'daily_total_limit': 50000.0,
            'approval_threshold': 1000.0
        }

def set_payout_limits(max_amount: float = None, max_per_day: int = None,
                      daily_total_limit: float = None, approval_threshold: float = None):
    """Встановлює ліміти для виплат"""
    with _db() as con:
        import time
        current = get_payout_limits()
        cur = con.execute("""
            INSERT INTO payout_limits (
                max_amount, max_per_day, daily_total_limit, approval_threshold, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            max_amount if max_amount is not None else current['max_amount'],
            max_per_day if max_per_day is not None else current['max_per_day'],
            daily_total_limit if daily_total_limit is not None else current['daily_total_limit'],
            approval_threshold if approval_threshold is not None else current['approval_threshold'],
            int(time.time())
        ))
        con.commit()

def get_payout_daily_stats(user_id: int, date: str = None) -> dict:
    """Повертає статистику виплат за день для користувача"""
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
    
    with _db() as con:
        row = con.execute("""
            SELECT count, total_amount
            FROM payout_daily_stats
            WHERE user_id = ? AND date = ?
        """, (user_id, date)).fetchone()
        
        if row:
            return {'count': int(row[0]), 'total_amount': float(row[1])}
        return {'count': 0, 'total_amount': 0.0}

def increment_payout_daily_stats(user_id: int, amount: float, date: str = None):
    """Збільшує статистику виплат за день"""
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
    
    with _db() as con:
        con.execute("""
            INSERT INTO payout_daily_stats (user_id, date, count, total_amount)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                count = count + 1,
                total_amount = total_amount + ?
        """, (user_id, date, amount, amount))
        con.commit()

def check_payout_limits(user_id: int, amount: float) -> tuple:
    """Перевіряє чи не перевищені ліміти для виплати
    
    Повертає (is_valid, error_message, needs_approval)
    """
    limits = get_payout_limits()
    stats = get_payout_daily_stats(user_id)
    
    # Перевірка максимальної суми однієї виплати
    if amount > limits['max_amount']:
        return (False, f"Максимальна сума однієї виплати: {limits['max_amount']}₴", False)
    
    # Перевірка ліміту виплат за день
    if stats['count'] >= limits['max_per_day']:
        return (False, f"Досягнуто ліміт виплат за день: {limits['max_per_day']}", False)
    
    # Перевірка денного ліміту на загальну суму
    if stats['total_amount'] + amount > limits['daily_total_limit']:
        remaining = limits['daily_total_limit'] - stats['total_amount']
        return (False, f"Денний ліміт на загальну суму: {limits['daily_total_limit']}₴. Залишилось: {remaining:.2f}₴", False)
    
    # Перевірка чи потрібне підтвердження
    needs_approval = amount > limits['approval_threshold']
    
    return (True, None, needs_approval)

# ─── ЦЕ ВИДАЧА АДМІНКИ СОБІ ───────────────────────────────
def grant_me_admin(my_id: int):
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (my_id,))
def set_referrer(user_id: int, referrer_id: int):
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO referrals (user_id, invited_by) VALUES (?, ?)", (user_id, referrer_id))# ─── Функція підрахунку рефералів: ───────────────────────────────
def get_ref_count(user_id: int) -> int:
    with _db() as con:
        row = con.execute("SELECT COUNT(*) FROM referrals WHERE invited_by=?", (user_id,)).fetchone()
        return row[0] if row else 0
# ─── Функція зберігання реферала (викликати в /start): ───────────────────────────────
def save_referral(user_id: int, inviter_id: int):
    with _db() as con:
        con.execute(
            "INSERT OR IGNORE INTO referrals(user_id, invited_by) VALUES(?, ?)",
            (user_id, inviter_id),
        )
        con.commit()  # Додаємо коміт
        try:
            # Додатково зберігаємо час першої успішної реєстрації реферала
            import time
            con.execute("CREATE TABLE IF NOT EXISTS referral_timestamps (user_id INTEGER PRIMARY KEY, invited_by INTEGER, invited_at INTEGER)")
            now_ts = int(time.time())
            con.execute(
                "INSERT OR IGNORE INTO referral_timestamps (user_id, invited_by, invited_at) VALUES (?, ?, ?)",
                (user_id, inviter_id, now_ts),
            )
            con.commit()
        except Exception:
            # Не критично, якщо додатковий стовпець/таблицю не вдалось створити
            pass
        
        # Перевіряємо завдання типу invite_users для реферера
        try:
            check_invite_users_tasks(inviter_id)
        except Exception:
            pass  # Не критично, якщо помилка
# ─── Функція отримання реф-бонусу: ───────────────────────────────
def get_ref_bonus():
    with _db() as con:
        # Спочатку пробуємо settings, потім config
        row = con.execute("SELECT value FROM settings WHERE key = 'ref_bonus'").fetchone()
        if not row:
            row = con.execute("SELECT value FROM config WHERE key = 'ref_bonus'").fetchone()
        return float(row[0]) if row else 1.5  # якщо нема, повертає дефолт
def get_referrals(user_id: int):
    with _db() as con:
        cur = con.execute(
            """
            SELECT r.user_id, COALESCE(u.user_name, 'Невідомий користувач') as user_name
            FROM referrals r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.invited_by = ?
            """,
            (user_id,)
        )
        return cur.fetchall()

def get_inactive_referrals_count(user_id: int, inactive_days: int = 30) -> int:
    """Повертає кількість неактивних рефералів користувача.
    
    Args:
        user_id: ID користувача
        inactive_days: Кількість днів без активності для вважання неактивним (за замовчуванням 30)
    
    Returns:
        Кількість неактивних рефералів
    """
    import time
    with _db() as con:
        cutoff_time = int(time.time()) - (inactive_days * 24 * 3600)
        cur = con.execute(
            """
            SELECT COUNT(*)
            FROM referrals r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.invited_by = ?
            AND (u.last_active IS NULL OR u.last_active < ?)
            """,
            (user_id, cutoff_time)
        )
        result = cur.fetchone()
        return result[0] if result else 0

def get_active_referrals_count(user_id: int, active_days: int = 30) -> int:
    """Повертає кількість активних рефералів користувача.
    
    Args:
        user_id: ID користувача
        active_days: Кількість днів активності для вважання активним (за замовчуванням 30)
    
    Returns:
        Кількість активних рефералів
    """
    import time
    with _db() as con:
        cutoff_time = int(time.time()) - (active_days * 24 * 3600)
        cur = con.execute(
            """
            SELECT COUNT(*)
            FROM referrals r
            LEFT JOIN users u ON r.user_id = u.user_id
            WHERE r.invited_by = ?
            AND u.last_active IS NOT NULL 
            AND u.last_active >= ?
            """,
            (user_id, cutoff_time)
        )
        result = cur.fetchone()
        return result[0] if result else 0
def get_withdrawn_total(user_id: int) -> float:
    with _db() as con:
        row = con.execute("SELECT withdrawn FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else 0

def set_withdrawn_total(user_id: int, new_total: float) -> bool:
    """Жорстко встановлює поле withdrawn користувача до new_total."""
    try:
        with _db() as con:
            con.execute("UPDATE users SET withdrawn = ? WHERE user_id = ?", (float(new_total), user_id))
            con.commit()
        return True
    except Exception:
        return False

def get_top_referrers(limit=5):
    with _db() as con:
        rows = con.execute("""
            SELECT r.invited_by, u.user_name, COUNT(*) as cnt
            FROM referrals r
            JOIN users u ON r.invited_by = u.user_id
            GROUP BY r.invited_by
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return rows

def get_referral_earnings(user_id):
    """Подсчитывает заработанное пользователем на реферальной системе"""
    with _db() as con:
        # Подсчитываем все транзакции с reason "referral_bonus"
        cursor = con.execute("""
            SELECT SUM(delta) FROM balance_ledger 
            WHERE user_id = ? AND reason = 'referral_bonus'
        """, (user_id,))
        earnings = cursor.fetchone()[0]
        return earnings or 0

def get_top_referrers_with_earnings(limit=5):
    """Возвращает топ рефералов с подсчетом заработанного"""
    with _db() as con:
        rows = con.execute("""
            SELECT r.invited_by, u.user_name, COUNT(*) as cnt
            FROM referrals r
            JOIN users u ON r.invited_by = u.user_id
            GROUP BY r.invited_by
            ORDER BY cnt DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        # Добавляем информацию о заработанном для каждого реферала
        result = []
        for user_id, name, cnt in rows:
            earnings = get_referral_earnings(user_id)
            result.append((user_id, name, cnt, earnings))
        
        return result
def is_user_referred(user_id: int) -> bool:
    with _db() as con:
        row = con.execute("SELECT 1 FROM referrals WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None

def get_referral_info(user_id: int):
    """Отримує повну інформацію про реферала користувача"""
    with _db() as con:
        row = con.execute("""
            SELECT r.invited_by, u.user_name, u.username
            FROM referrals r
            JOIN users u ON r.invited_by = u.user_id
            WHERE r.user_id = ?
        """, (user_id,)).fetchone()
        # Додаємо спробу отримати мітку часу зі збереженої таблиці
        try:
            ts_row = con.execute("SELECT invited_at FROM referral_timestamps WHERE user_id = ?", (user_id,)).fetchone()
            invited_at = ts_row[0] if ts_row else None
        except Exception:
            invited_at = None
        if row:
            # повертаємо (invited_by, user_name, username, invited_at)
            return (row[0], row[1], row[2] if len(row) > 2 else None, invited_at)
        return None

def get_referral_stats():
    """Отримує статистику реферальної системи"""
    with _db() as con:
        total_referrals = con.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        total_users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        ref_bonus = get_ref_bonus()
        
        return {
            'total_referrals': total_referrals,
            'total_users': total_users,
            'referral_rate': (total_referrals / total_users * 100) if total_users > 0 else 0,
            'ref_bonus': ref_bonus
        }

def add_test_user(user_id: int, user_name: str = "Тестовий користувач"):
    """Додає тестового користувача для тестування"""
    with _db() as con:
        con.execute("""
            INSERT OR IGNORE INTO users (user_id, user_name, balance)
            VALUES (?, ?, 0)
        """, (user_id, user_name))
        con.commit()
def set_ref_bonus(new_bonus: float):
    with _db() as con:
        # Зберігаємо в обидві таблиці для сумісності
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ref_bonus', ?)", (str(new_bonus),))
        con.execute("INSERT OR REPLACE INTO config (key, value) VALUES ('ref_bonus', ?)", (str(new_bonus),))
        con.commit()

# ─── Нагорода реф бонусу: ───────────────────────────────
def init_settings():
    try:
        with _db() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            con.execute("""
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('ref_bonus', '1.5')
            """)
            con.execute("""
                INSERT OR IGNORE INTO settings (key, value)
                VALUES ('daily_bonus', '0.10')
            """)
            # Одноразова міграція: перевести всіх із рівня саду 1 на 0
            try:
                flag = con.execute("SELECT value FROM settings WHERE key='garden_level_migrated_1_to_0'").fetchone()
                if not flag or str(flag[0]) != '1':
                    # Оновлюємо лише явні записи рівня 1
                    con.execute("UPDATE garden_levels SET level=0 WHERE level=1")
                    # Також таблиця gardens, якщо використовується
                    try:
                        con.execute("UPDATE gardens SET level=0 WHERE level=1")
                    except Exception:
                        pass
                    con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('garden_level_migrated_1_to_0','1')")
                    con.commit()
            except Exception:
                pass
            
            # Додати дефолтні ціни для бустів
            try:
                from garden_models import BOOSTERS
                for booster in BOOSTERS:
                    price_key = booster.get('price_key')
                    if price_key:
                        con.execute("""
                            INSERT OR IGNORE INTO settings (key, value)
                            VALUES (?, '50.0')
                        """, (price_key,))
            except Exception:
                pass  # Якщо не вдалося імпортувати BOOSTERS
                
            # Додати дефолтні ціни для дерев (тепер в окремій таблиці tree_prices)
            try:
                from garden_models import TREE_TYPES
                for tree in TREE_TYPES:
                    con.execute("""
                        INSERT OR IGNORE INTO tree_prices (type, price)
                        VALUES (?, ?)
                    """, (tree['type'], tree['price_uah']))
            except Exception:
                pass  # Якщо не вдалося імпортувати TREE_TYPES
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("[WARNING] База даних заблокована в init_settings. Продовжуємо роботу.")
        else:
            print(f"[ERROR] Помилка в init_settings: {e}")
            raise
    except Exception as e:
        print(f"[ERROR] Помилка в init_settings: {e}")
        raise

def get_daily_bonus():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'daily_bonus'").fetchone()
        return float(row[0]) if row else 0.10  # 0.10 — дефолтне значення

def add_deposit(user_id, amount):
    with _db() as con:
        con.execute("UPDATE users SET deposits = COALESCE(deposits, 0) + ? WHERE user_id = ?", (amount, user_id))
        print(f"[DEBUG] Updated deposits for {user_id} by {amount}")

def get_withdrawals_by_status(status=None):
    with _db() as con:
        if status:
            rows = con.execute("SELECT tx_id, user_id, amount, comment, status, created_at, processed_at, requisites FROM tx WHERE status = ? ORDER BY tx_id DESC", (status,)).fetchall()
        else:
            rows = con.execute("SELECT tx_id, user_id, amount, comment, status, created_at, processed_at, requisites FROM tx ORDER BY tx_id DESC").fetchall()
    return rows

def get_withdrawal_by_id(tx_id):
    with _db() as con:
        row = con.execute("SELECT tx_id, user_id, amount, comment, status, created_at, processed_at, requisites FROM tx WHERE tx_id = ?", (tx_id,)).fetchone()
    return row

def get_last_successful_withdrawal(user_id: int):
    """Повертає останній успішний вивід користувача як dict або None.
    Поля: amount, requisites, created_at, processed_at, comment.
    """
    with _db() as con:
        row = con.execute(
            """
            SELECT amount, requisites, created_at, processed_at, comment
            FROM tx
            WHERE user_id = ? AND status = 'done'
            ORDER BY COALESCE(processed_at, created_at) DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
    if not row:
        return None
    return {
        'amount': float(row[0]) if row[0] is not None else 0.0,
        'requisites': row[1],
        'created_at': row[2],
        'processed_at': row[3],
        'comment': row[4],
    }

def get_user_activity_feed(user_id: int, limit: int = 50):
    """Повертає комбіновану історію операцій користувача з розширеними метаданими."""
    limit = max(1, min(int(limit), 200))
    fetch_cap = min(400, limit * 3)

    def parse_ts(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(datetime.fromisoformat(str(value)).timestamp())
        except Exception:
            try:
                return int(datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").timestamp())
            except Exception:
                try:
                    return int(float(value))
                except Exception:
                    return None

    def normalize_status(raw):
        mapping = {
            'approved': 'completed',
            'done': 'completed',
            'success': 'completed',
            'completed': 'completed',
            'pending': 'pending',
            'processing': 'pending',
            'rejected': 'rejected',
            'failed': 'rejected',
            'cancelled': 'rejected'
        }
        if not raw:
            return 'pending'
        key = str(raw).lower()
        return mapping.get(key, key)

    def status_label(kind, status):
        labels = {
            'deposit': {
                'pending': 'Очікує підтвердження',
                'completed': 'Зараховано',
                'rejected': 'Відхилено'
            },
            'withdraw': {
                'pending': 'Очікує виплати',
                'completed': 'Виплачено',
                'rejected': 'Відхилено'
            },
            'garden': {
                'completed': 'Завершено'
            },
            'adjustment': {
                'completed': 'Застосовано'
            }
        }
        return labels.get(kind, {}).get(status, status.capitalize())

    def build_entry(**kwargs):
        entry = {
            'id': kwargs.get('entry_id'),
            'kind': kwargs.get('kind'),
            'subtype': kwargs.get('subtype'),
            'status': kwargs.get('status', 'completed'),
            'status_label': kwargs.get('status_label'),
            'amount': float(kwargs.get('amount', 0.0)),
            'currency': kwargs.get('currency', 'UAH'),
            'timestamp': kwargs.get('timestamp'),
            'created_at': kwargs.get('timestamp'),
            'updated_at': kwargs.get('updated_at'),
            'icon': kwargs.get('icon'),
            'title': kwargs.get('title'),
            'description': kwargs.get('description'),
            'direction': kwargs.get('direction', 'neutral'),
            'category': kwargs.get('category', kwargs.get('kind')),
            'meta': kwargs.get('meta', {})
        }
        return entry

    garden_meta = {
        'harvest': {'title': 'Збір врожаю', 'icon': '🍎', 'direction': 'in'},
        'watering': {'title': 'Полив дерев', 'icon': '💧', 'direction': 'neutral'},
        'buy_tree': {'title': 'Покупка дерева', 'icon': '🌳', 'direction': 'out'},
        'level_up': {'title': 'Покращення саду', 'icon': '🚀', 'direction': 'out'},
        'admin_add_tree': {'title': 'Адмін додав дерева', 'icon': '🛠', 'direction': 'in'},
        'admin_remove_tree': {'title': 'Адмін видалив дерева', 'icon': '🪓', 'direction': 'out'},
        'admin_add_fruit': {'title': 'Адмін додав фрукти', 'icon': '🍇', 'direction': 'in'},
        'admin_remove_fruit': {'title': 'Адмін видалив фрукти', 'icon': '🥀', 'direction': 'out'},
    }

    skip_ledger_reasons = {'auto_trigger', 'buy_tree', 'garden_level_up'}

    with _db() as con:
        con.row_factory = sqlite3.Row
        deposits = con.execute(
            """
            SELECT id, amount, status, created_at, comment, proof
            FROM deposit_tx
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, fetch_cap),
        ).fetchall()
        withdrawals = con.execute(
            """
            SELECT tx_id, amount, status, created_at, processed_at, comment, requisites
            FROM tx
            WHERE user_id = ?
            ORDER BY COALESCE(processed_at, created_at) DESC
            LIMIT ?
            """,
            (user_id, fetch_cap),
        ).fetchall()
        garden_rows = con.execute(
            """
            SELECT type, amount, currency, timestamp, comment
            FROM garden_transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_id, fetch_cap),
        ).fetchall()
        ledger_rows = con.execute(
            """
            SELECT id, delta, reason, details, created_at
            FROM balance_ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, fetch_cap),
        ).fetchall()

    feed = []

    current_ts = int(time.time())
    for dep in deposits:
        created_ts = parse_ts(dep['created_at']) or current_ts
        status = normalize_status(dep['status'])
        feed.append(
            build_entry(
                entry_id=f"deposit-{dep['id']}",
                kind='deposit',
                subtype='deposit',
                status=status,
                status_label=status_label('deposit', status),
                amount=dep['amount'] or 0,
                currency='UAH',
                timestamp=created_ts,
                icon='💳',
                title='Поповнення балансу',
                description=dep['comment'] or status_label('deposit', status),
                direction='in',
                category='finance',
                meta={
                    'comment': dep['comment'],
                    'proof': dep['proof'],
                    'raw_status': dep['status'],
                },
            )
        )

    for wd in withdrawals:
        processed_ts = parse_ts(wd['processed_at'])
        created_ts = parse_ts(wd['created_at']) or processed_ts or current_ts
        status = normalize_status(wd['status'])
        feed.append(
            build_entry(
                entry_id=f"withdraw-{wd['tx_id']}",
                kind='withdraw',
                subtype='withdraw',
                status=status,
                status_label=status_label('withdraw', status),
                amount=wd['amount'] or 0,
                currency='UAH',
                timestamp=processed_ts or created_ts,
                updated_at=processed_ts,
                icon='🏦',
                title='Заявка на вивід',
                description=wd['comment'] or status_label('withdraw', status),
                direction='out',
                category='finance',
                meta={
                    'comment': wd['comment'],
                    'requisites': wd['requisites'],
                    'raw_status': wd['status'],
                },
            )
        )

    for gr in garden_rows:
        subtype = (gr['type'] or 'garden').strip().lower()
        if subtype == 'sell_fruit':
            # Грошовий еквівалент відображаємо через леджер
            continue
        meta = garden_meta.get(subtype, {})
        icon = meta.get('icon', '🌿')
        direction = meta.get('direction', 'neutral')
        title = meta.get('title', 'Подія саду')
        comment = gr['comment'] or title
        ts_value = parse_ts(gr['timestamp']) or current_ts
        feed.append(
            build_entry(
                entry_id=f"garden-{subtype}-{gr['timestamp']}",
                kind='garden',
                subtype=subtype,
                status='completed',
                status_label=status_label('garden', 'completed'),
                amount=gr['amount'] or 0,
                currency=gr['currency'] or '',
                timestamp=ts_value,
                icon=icon,
                title=title,
                description=comment,
                direction=direction,
                category='garden',
                meta={
                    'comment': gr['comment'],
                    'type': gr['type'],
                },
            )
        )

    for ledger in ledger_rows:
        reason_raw = (ledger['reason'] or '').strip()
        reason_key = reason_raw.lower()
        if reason_key in skip_ledger_reasons:
            continue
        delta = float(ledger['delta'] or 0.0)
        if abs(delta) < 0.0001:
            continue
        direction = 'in' if delta > 0 else 'out'
        amount = abs(delta)
        ts_value = parse_ts(ledger['created_at']) or current_ts
        if reason_key == 'sell_fruit':
            title = 'Продаж фруктів'
            icon = '💰'
            category = 'garden'
        elif reason_key.startswith('penalty'):
            title = 'Штраф'
            icon = '⚖️'
            category = 'adjustment'
        elif reason_key.startswith('gift_reward'):
            title = 'Подарунок'
            icon = '🎁'
            category = 'adjustment'
        elif reason_key.startswith('admin'):
            title = 'Операція адміністратора'
            icon = '🛠'
            category = 'adjustment'
        else:
            title = 'Корекція балансу'
            icon = '🧾'
            category = 'adjustment'

        description = ledger['details'] or reason_raw or title
        feed.append(
            build_entry(
                entry_id=f"ledger-{ledger['id']}",
                kind='adjustment',
                subtype=reason_key or 'adjustment',
                status='completed',
                status_label=status_label('adjustment', 'completed'),
                amount=amount,
                currency='UAH',
                timestamp=ts_value,
                icon=icon,
                title=title,
                description=description,
                direction=direction,
                category=category,
                meta={
                    'reason': reason_raw,
                    'details': ledger['details'],
                    'raw_delta': delta,
                },
            )
        )

    feed.sort(key=lambda item: item.get('timestamp') or 0, reverse=True)
    return feed[:limit]

def set_deposit_requisites(requisites: str):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("deposit_requisites", requisites))
        con.commit()

def get_deposit_requisites() -> str:
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", ("deposit_requisites",)).fetchone()
        return row[0] if row else "Реквізити не встановлені. Зверніться до адміністратора."

def set_last_bonus(uid: int, ts: int):
    with _db() as con:
        con.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (ts, uid))
        con.commit()

def get_last_bonus(uid: int) -> int:
    with _db() as con:
        row = con.execute("SELECT last_bonus FROM users WHERE user_id = ?", (uid,)).fetchone()
        return row[0] if row else 0

def set_daily_bonus(new_bonus: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('daily_bonus', ?)", (str(new_bonus),))
        con.commit()

def get_min_deposit():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'min_deposit'").fetchone()
        return float(row[0]) if row else 10.0  # дефолт 10 грн

def set_min_deposit(new_min: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('min_deposit', ?)", (str(new_min),))
        con.commit()

def get_maintenance_mode():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'maintenance_mode'").fetchone()
        return bool(int(row[0])) if row else False

def set_maintenance_mode(enabled: bool):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('maintenance_mode', ?)", ("1" if enabled else "0",))
        con.commit()

def get_user_trees(user_id: int):
    """Повертає список дерев користувача з таблиці trees."""
    with _db() as con:
        rows = con.execute("SELECT id, type, level, planted_at, last_harvest FROM trees WHERE user_id=?", (user_id,)).fetchall()
        return [
            {
                "id": r[0],
                "type": r[1],
                "level": r[2],
                "planted_at": r[3],
                "last_harvest": r[4],
            }
            for r in rows
        ]

def get_tree_price(tree_type: str) -> float:
    """Повертає поточну ціну дерева з таблиці tree_prices або дефолтну з TREE_TYPES."""
    try:
        with _db() as con:
            row = con.execute("SELECT price FROM tree_prices WHERE type=?", (tree_type,)).fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except Exception as e:
        print(f"Error in get_tree_price: {e}")
        pass
    
    # Якщо не знайдено, шукаємо дефолтну ціну в TREE_TYPES
    try:
        from garden_models import TREE_TYPES
        for t in TREE_TYPES:
            if t['type'] == tree_type:
                return t['price_uah']
    except Exception as e:
        print(f"Error getting default tree price: {e}")
        pass
    return 10.0  # дефолтна ціна, якщо нічого не знайдено

def set_tree_price(tree_type: str, price: float):
    """Встановлює ціну дерева в таблиці tree_prices і тригерить розсилку при зміні."""
    old_price = None
    try:
        with _db() as con:
            try:
                row = con.execute("SELECT price FROM tree_prices WHERE type=?", (tree_type,)).fetchone()
                old_price = float(row[0]) if row else None
            except Exception:
                old_price = None
            con.execute("INSERT INTO tree_prices (type, price) VALUES (?, ?) ON CONFLICT(type) DO UPDATE SET price=excluded.price", (tree_type, price))
            con.commit()
        try:
            if old_price is None or float(old_price) != float(price):
                _notify_price_change('tree', tree_type, float(price), float(old_price) if old_price is not None else None)
        except Exception:
            pass
    except Exception as e:
        print(f"Error in set_tree_price: {e}")
        raise e

def get_booster_price(booster_type: str) -> float:
    """Повертає ціну бустера за типом з таблиці booster_prices або дефолтну."""
    try:
        with _db() as con:
            row = con.execute("SELECT price FROM booster_prices WHERE booster_type=?", (booster_type,)).fetchone()
            if row and row[0] is not None:
                return float(row[0])
    except Exception as e:
        print(f"Error in get_booster_price: {e}")
        pass
    return 50.0  # Дефолтна ціна 50₴

def set_booster_price(booster_type: str, price: float):
    """Встановлює ціну бустера в таблиці booster_prices і тригерить розсилку при зміні."""
    old_price = None
    try:
        with _db() as con:
            try:
                row = con.execute("SELECT price FROM booster_prices WHERE booster_type=?", (booster_type,)).fetchone()
                old_price = float(row[0]) if row else None
            except Exception:
                old_price = None
            con.execute("INSERT INTO booster_prices (booster_type, price) VALUES (?, ?) ON CONFLICT(booster_type) DO UPDATE SET price=excluded.price", (booster_type, price))
            con.commit()
        try:
            if old_price is None or float(old_price) != float(price):
                _notify_price_change('booster', booster_type, float(price), float(old_price) if old_price is not None else None)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"Error in set_booster_price: {e}")
        return False

def init_default_booster_prices():
    """Ініціалізує дефолтні ціни бустів при першому запуску."""
    try:
        from garden_models import BOOSTERS
        with _db() as con:
            for booster in BOOSTERS:
                booster_type = booster['type']
                # Перевіряємо, чи вже є ціна для цього бустера
                existing = con.execute("SELECT price FROM booster_prices WHERE booster_type=?", (booster_type,)).fetchone()
                if not existing:
                    # Встановлюємо дефолтну ціну 50₴
                    con.execute("INSERT INTO booster_prices (booster_type, price) VALUES (?, ?)", (booster_type, 50.0))
            con.commit()
        print("Default booster prices initialized")
    except Exception as e:
        print(f"Error in init_default_booster_prices: {e}")

# --- Broadcast price changes helper ---
def _notify_price_change(kind: str, key: str, new_price: float, old_price: float | None):
    """Розсилає повідомлення про зміну ціни у всі ігрові чати і (за наявності) канал виводів."""
    try:
        # імпортуємо тут, щоб уникнути циклічного імпорту під час завантаження модулів
        from bot import bot  # active telebot instance
        text = None
        if kind == 'fruit':
            from garden_models import get_fruit_name_uk
            name = get_fruit_name_uk(key)
            text = f"📈 <b>Зміна ціни біржі</b>\n{name}: <b>{new_price:.2f}₴</b>" + (f" (було {old_price:.2f}₴)" if old_price is not None else '')
        elif kind == 'tree':
            from garden_models import get_tree_name_uk
            name = get_tree_name_uk(key)
            text = f"🌳 <b>Зміна ціни дерева</b>\n{name}: <b>{new_price:.2f}₴</b>" + (f" (було {old_price:.2f}₴)" if old_price is not None else '')
        elif kind == 'booster':
            text = f"⚡ <b>Зміна ціни бустера</b>\n{key}: <b>{new_price:.2f}₴</b>" + (f" (було {old_price:.2f}₴)" if old_price is not None else '')
        elif kind == 'level':
            text = f"🏆 <b>Оновлено ціну рівня саду {key}</b> → <b>{new_price:.2f}₴</b>" + (f" (було {old_price:.2f}₴)" if old_price is not None else '')
        if not text:
            return
        # Чати для розсилки
        try:
            chats = get_gaming_chats()
        except Exception:
            chats = []
        try:
            ch = get_withdraw_channel()
            if ch:
                chats = chats + [(ch, 'withdraws', None, None)]
        except Exception:
            pass
        for chat_id, *_ in (chats or []):
            try:
                bot.send_message(chat_id, text, parse_mode='HTML')
            except Exception:
                continue
    except Exception:
        pass

def _ensure_promo_schema(con):
    cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
    # Add 'uses' column if missing (some schemas use 'current_uses')
    if 'uses' not in cols:
        try:
            con.execute("ALTER TABLE promo_codes ADD COLUMN uses INTEGER DEFAULT 0")
        except Exception:
            pass
    # Ensure max_uses column exists
    if 'max_uses' not in cols:
        try:
            con.execute("ALTER TABLE promo_codes ADD COLUMN max_uses INTEGER")
        except Exception:
            pass
    # Ensure expiry column exists
    if 'expiry' not in cols:
        try:
            con.execute("ALTER TABLE promo_codes ADD COLUMN expiry INTEGER")
        except Exception:
            pass

def create_promo_code(code, reward_type, reward_value, max_uses, expiry, item_type=None, item_value=None):
    """Створює новий промокод.
    Підтримує 2 сигнатури виклику:
      1) (code, reward_type, reward_value, max_uses, expiry, item_type=None, item_value=None)
      2) (code, reward_value, max_uses, expiry, item_type)  ← reward_type буде визначено автоматично
    """
    # Автовизначення типу винагороди, якщо другим аргументом прийшла сума
    inferred = False
    if isinstance(reward_type, (int, float)) and not isinstance(reward_type, bool):
        # Зсув аргументів згідно старого виклику
        reward_value, max_uses, expiry, item_type = float(reward_type), reward_value, max_uses, expiry
        # Тип винагороди
        if not item_type:
            reward_type = 'money'
        else:
            try:
                from garden_models import FRUITS, BOOSTERS, TREE_TYPES
                fruit_types = {f['type'] for f in FRUITS}
                booster_types = {b['type'] for b in BOOSTERS}
                tree_types = {t['type'] for t in TREE_TYPES}
                if item_type in fruit_types:
                    reward_type = 'fruit'
                elif item_type in booster_types:
                    reward_type = 'booster'
                elif item_type in tree_types:
                    reward_type = 'tree'
                else:
                    reward_type = 'achievement'
            except Exception:
                reward_type = 'achievement' if item_type else 'money'
        inferred = True

    # Нормалізація полів
    try:
        reward_value = float(reward_value)
    except Exception:
        reward_value = 0.0
    try:
        max_uses = int(max_uses) if max_uses is not None else None
    except Exception:
        max_uses = None
    try:
        expiry = int(expiry) if expiry else None
    except Exception:
        expiry = None

    with _db() as con:
        _ensure_promo_schema(con)
        # Забезпечимо наявність колонки current_uses для сумісності, але основна — uses
        cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
        if 'current_uses' in cols:
            con.execute(
                """
                INSERT OR REPLACE INTO promo_codes (code, reward_type, reward_value, max_uses, expiry, item_type, item_value, current_uses, uses)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT current_uses FROM promo_codes WHERE code=?), 0), COALESCE((SELECT uses FROM promo_codes WHERE code=?), 0))
                """,
                (code, reward_type, reward_value, max_uses, expiry, item_type, item_value, code, code)
            )
        else:
            con.execute(
                """
                INSERT OR REPLACE INTO promo_codes (code, reward_type, reward_value, max_uses, expiry, item_type, item_value, uses)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT uses FROM promo_codes WHERE code=?), 0))
                """,
                (code, reward_type, reward_value, max_uses, expiry, item_type, item_value, code)
            )
        con.commit()

def clear_withdraw_history():
    """Видаляє всі заявки на вивід з таблиці tx."""
    with _db() as con:
        con.execute("DELETE FROM tx")
        con.commit()

def ensure_promo_code_usages_table():
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS promo_code_usages (
                code TEXT,
                user_id INTEGER,
                used_at INTEGER,
                PRIMARY KEY (code, user_id)
            );
        """)
        con.commit()

# Викликати при старті (наприклад, у init_db)
ensure_promo_code_usages_table()

# Оновлена функція use_promo_code

def use_promo_code(code, user_id):
    """Активує промокод для користувача. Повертає (ok, (reward, item_type)) або (False, reason)."""
    with _db() as con:
        # Визначаємо назву лічильника
        cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
        counter_col = 'uses' if 'uses' in cols else ('current_uses' if 'current_uses' in cols else 'uses')
        row = con.execute(
            f"SELECT code, reward_type, reward_value, max_uses, {counter_col}, expiry, item_type, item_value FROM promo_codes WHERE code=?",
            (code,)
        ).fetchone()
        if not row:
            return False, "Промокод не знайдено."
        code, reward_type, reward_value, max_uses, uses, expiry, item_type, item_value = row
        # Нормалізація типів
        try:
            uses = int(uses) if uses is not None else 0
        except Exception:
            uses = 0
        try:
            max_uses = int(max_uses) if max_uses is not None else None
        except Exception:
            max_uses = None
        # Перевірка ліміту використань
        if max_uses is not None and uses >= max_uses:
            return False, "Промокод вже використано максимальну кількість разів."
        # Перевірка терміну дії
        import time
        now = int(time.time())
        if expiry and expiry < now:
            return False, "Термін дії промокоду закінчився."
        # Перевірка, чи вже використовував цей користувач
        usage = con.execute("SELECT 1 FROM promo_code_usages WHERE code=? AND user_id=?", (code, user_id)).fetchone()
        if usage:
            return False, "Ви вже використали цей промокод."
        # Записати використання та інкрементувати лічильник атомарно
        con.execute("INSERT INTO promo_code_usages (code, user_id, used_at) VALUES (?, ?, ?)", (code, user_id, now))
        con.execute(f"UPDATE promo_codes SET {counter_col} = COALESCE({counter_col},0) + 1 WHERE code=?", (code,))
        con.commit()
        # Повертаємо тип винагороди та значення
        if reward_type == "money":
            return True, (float(reward_value), None)
        elif reward_type == "fruit":
            return True, (int(reward_value), {"type": "fruit", "item": item_type})
        elif reward_type == "booster":
            # item_value може зберігати тривалість у секундах, інакше reward_value —
            duration_seconds = None
            try:
                duration_seconds = int(item_value) if item_value else int(reward_value)
            except Exception:
                duration_seconds = int(reward_value) if str(reward_value).isdigit() else 3600
            return True, (duration_seconds, {"type": "booster", "item": item_type})
        elif reward_type == "tree":
            return True, (int(reward_value), {"type": "tree", "item": item_type})
        elif reward_type == "achievement":
            # item_type: key досягнення (унікальний). reward_value не використовується
            return True, (1, {"type": "achievement", "item": item_type})
        else:
            return True, (reward_value, {"type": "unknown", "item": item_type})

def get_promo_by_code(code: str):
    """Повертає рядок промокоду або None."""
    with _db() as con:
        cols = [c[1] for c in con.execute("PRAGMA table_info(promo_codes)").fetchall()]
        counter_col = 'uses' if 'uses' in cols else ('current_uses' if 'current_uses' in cols else 'uses')
        row = con.execute(
            f"SELECT code, reward_type, reward_value, max_uses, {counter_col}, expiry, item_type, item_value FROM promo_codes WHERE code=?",
            (code,)
        ).fetchone()
        return row

def get_promo_usages(code: str):
    """Повертає список використань промокоду із іменем користувача (id, name, username, used_at)."""
    with _db() as con:
        rows = con.execute(
            """
            SELECT u.user_id, u.user_name, u.username, p.used_at
            FROM promo_code_usages p
            LEFT JOIN users u ON u.user_id = p.user_id
            WHERE p.code=?
            ORDER BY p.used_at DESC
            """,
            (code,)
        ).fetchall()
        return rows

def get_user_registration_date(user_id: int):
    with _db() as con:
        row = con.execute("SELECT date_joined FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row and row[0] else None

def get_user_last_active(user_id: int):
    with _db() as con:
        row = con.execute("SELECT last_active FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row and row[0] else None

def update_last_active(user_id: int):
    """Оновлює мітку останньої активності користувача до поточного часу."""
    import time
    with _db() as con:
        con.execute("UPDATE users SET last_active=? WHERE user_id=?", (int(time.time()), user_id))
        con.commit()

def get_active_boosters(user_id: int):
    import time
    now = int(time.time())
    with _db() as con:
        rows = con.execute("SELECT type, expires_at FROM boosters WHERE user_id=? AND (expires_at IS NULL OR expires_at > ?)", (user_id, now)).fetchall()
        return rows

def grant_booster(user_id: int, booster_type: str, duration_seconds: int) -> bool:
    """Нараховує бустер користувачу на вказаний час (у секундах)."""
    import time
    now = int(time.time())
    expires_at = now + max(0, int(duration_seconds))
    with _db() as con:
        con.execute(
            "INSERT INTO boosters (user_id, type, expires_at) VALUES (?, ?, ?)",
            (user_id, booster_type, expires_at)
        )
        con.commit()
    return True

def grant_tree(user_id: int, tree_type: str, count: int = 1) -> int:
    """Видає користувачу дерева (створює записи у таблиці trees). Повертає кількість доданих дерев."""
    import time
    added = 0
    with _db() as con:
        for _ in range(max(1, int(count))):
            try:
                con.execute(
                    "INSERT INTO trees (user_id, type, level, planted_at, last_harvest) VALUES (?, ?, 1, ?, NULL)",
                    (user_id, tree_type, int(time.time()))
                )
                added += 1
            except Exception:
                pass
        con.commit()
    return added

def grant_achievement(user_id: int, achievement_key: str) -> bool:
    """Додає користувачу унікальне досягнення (idempotent)."""
    import time
    with _db() as con:
        con.execute(
            "INSERT OR IGNORE INTO achievements (user_id, achievement, achieved_at) VALUES (?, ?, ?)",
            (user_id, achievement_key, int(time.time()))
        )
        con.commit()
    return True

def get_active_boosters_grouped(user_id: int):
    """Повертає активні бустери, згруповані за типом з сумарним часом"""
    import time
    now = int(time.time())
    
    with _db() as con:
        # Отримуємо всі активні бустери
        rows = con.execute("SELECT type, expires_at FROM boosters WHERE user_id=? AND (expires_at IS NULL OR expires_at > ?)", (user_id, now)).fetchall()
        
        # Групуємо бустери за типом
        boosters_by_type = {}
        for booster_type, expires_at in rows:
            if booster_type not in boosters_by_type:
                boosters_by_type[booster_type] = []
            boosters_by_type[booster_type].append(expires_at)
        
        # Обчислюємо сумарний час для кожного типу
        result = []
        for booster_type, expires_times in boosters_by_type.items():
            if not expires_times:
                continue
                
            # Якщо є кілька бустерів одного типу, сумуємо їх час дії
            if len(expires_times) > 1:
                # Обчислюємо загальний час дії
                total_duration = 0
                for expires_at in expires_times:
                    if expires_at:
                        # Припускаємо, що кожен буст має стандартну тривалість
                        # Це можна покращити, додавши поле duration до таблиці
                        duration = expires_at - now
                        if duration > 0:
                            total_duration += duration
                
                # Встановлюємо час закінчення як поточний час + загальний час дії
                new_expires_at = now + total_duration
                result.append((booster_type, new_expires_at))
            else:
                # Один бустер
                result.append((booster_type, expires_times[0]))
        
        return result

def get_user_achievements(user_id: int):
    with _db() as con:
        rows = con.execute("SELECT achievement, achieved_at FROM achievements WHERE user_id=?", (user_id,)).fetchall()
        return rows

# --- Досягнення ---
ACHIEVEMENT_RULES = [
    {"key": "fruits_total", "threshold": 100, "title": "Зібрав 100 фруктів 🍏", "desc": "Перші 100 фруктів!"},
    {"key": "fruits_total", "threshold": 1000, "title": "Зібрав 1000 фруктів 🍏", "desc": "Ти справжній садівник!"},
    {"key": "trees_total", "threshold": 10, "title": "Купив 10 дерев 🌳", "desc": "Твій сад росте!"},
    {"key": "deposits_total", "threshold": 1000, "title": "Поповнив на 1000₴ 💵", "desc": "Великий інвестор!"},
    {"key": "withdraws_total", "threshold": 500, "title": "Вивів 500₴ 💸", "desc": "Перші великі гроші!"},
    {"key": "referrals_total", "threshold": 5, "title": "Запросив 5 друзів 👥", "desc": "Ти справжній амбасадор!"},
    {"key": "boosters_total", "threshold": 3, "title": "Використав 3 бустери ⚡", "desc": "Любиш прискорення!"},
]

def add_achievement_if_needed(user_id, key, value):
    """Перевіряє і додає досягнення, якщо користувач досяг порогу."""
    with _db() as con:
        for rule in ACHIEVEMENT_RULES:
            if rule["key"] == key and value >= rule["threshold"]:
                # Чи вже є це досягнення?
                exists = con.execute("SELECT 1 FROM achievements WHERE user_id=? AND achievement=?", (user_id, rule["title"])).fetchone()
                if not exists:
                    import time
                    con.execute("INSERT INTO achievements (user_id, achievement, achieved_at) VALUES (?, ?, ?)", (user_id, rule["title"], int(time.time())))
                    con.commit()
                    return rule["title"]  # Повертає назву нового досягнення
    return None

# Приклад використання:
# add_achievement_if_needed(user_id, "fruits_total", total_fruits)
# add_achievement_if_needed(user_id, "trees_total", total_trees)
# add_achievement_if_needed(user_id, "deposits_total", total_deposits)
# add_achievement_if_needed(user_id, "withdraws_total", total_withdraws)
# add_achievement_if_needed(user_id, "referrals_total", total_referrals)
# add_achievement_if_needed(user_id, "boosters_total", total_boosters)

def ensure_achievements_table():
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                user_id INTEGER,
                achievement TEXT,
                achieved_at INTEGER,
                PRIMARY KEY (user_id, achievement)
            );
        """)
        con.commit()

# Викликати при імпорті модуля
ensure_achievements_table()

# --- Бета-тестери ---
def ensure_beta_testers_table():
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS beta_testers (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at INTEGER
            );
        ''')
        con.commit()


# =========================
# Events storage
# =========================
def ensure_events_tables():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                params TEXT,
                start_time INTEGER,
                end_time INTEGER,
                status TEXT,
                created_by INTEGER,
                chat_id INTEGER
            );
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS event_participation (
                event_id INTEGER,
                user_id INTEGER,
                action TEXT,
                data TEXT,
                ts INTEGER,
                PRIMARY KEY(event_id, user_id)
            );
            """
        )
        con.commit()


ensure_events_tables()


def ensure_tree_damage_table():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS tree_damage (
                user_id INTEGER,
                tree_rowid INTEGER,
                damaged_until INTEGER,
                damage_pct REAL DEFAULT 0.0,
                reason TEXT,
                PRIMARY KEY(user_id, tree_rowid)
            );
            """
        )
        con.commit()


ensure_tree_damage_table()


def ensure_new_user_notifications_table():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS new_user_notifications (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                created_at INTEGER,
                notified INTEGER DEFAULT 0
            );
            """
        )
        con.commit()

ensure_new_user_notifications_table()


def ensure_broadcast_tables():
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                created_at INTEGER,
                status TEXT,
                total_recipients INTEGER,
                sent INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                text TEXT,
                photo_id TEXT,
                filter_days INTEGER
            );
            """
        )
        # Міграція: додати відсутні колонки (на старих БД)
        try:
            con.execute("ALTER TABLE broadcast_runs ADD COLUMN filter_days INTEGER")
        except Exception:
            pass
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcast_results (
                run_id INTEGER,
                user_id INTEGER,
                status TEXT,
                error_code TEXT,
                error_type TEXT,
                error_desc TEXT,
                sent_at INTEGER,
                PRIMARY KEY (run_id, user_id)
            );
            """
        )
        # Індекси для швидких агрегацій
        try:
            con.execute("CREATE INDEX IF NOT EXISTS idx_broadcast_results_run ON broadcast_results(run_id)")
        except Exception:
            pass
        con.commit()

ensure_broadcast_tables()


def create_broadcast_run(admin_id: int, text: str, photo_id: str | None, filter_days: int | None, total_recipients: int) -> int:
    import time
    with _db() as con:
        cur = con.execute(
            """
            INSERT INTO broadcast_runs (admin_id, created_at, status, total_recipients, sent, failed, text, photo_id, filter_days)
            VALUES (?, ?, 'running', ?, 0, 0, ?, ?, ?)
            """,
            (int(admin_id), int(time.time()), int(total_recipients), str(text or ''), str(photo_id or ''), int(filter_days) if filter_days is not None else None)
        )
        rid = cur.lastrowid
        con.commit()
        return int(rid)


def add_broadcast_result(run_id: int, user_id: int, status: str, error_code: str | None, error_type: str | None, error_desc: str | None) -> None:
    import time
    status = str(status or '').lower()
    with _db() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO broadcast_results (run_id, user_id, status, error_code, error_type, error_desc, sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(run_id), int(user_id), status, error_code, error_type, error_desc, int(time.time()))
        )
        # Оновлюємо агрегати
        if status == 'sent':
            con.execute("UPDATE broadcast_runs SET sent = sent + 1 WHERE id=?", (int(run_id),))
        elif status == 'failed':
            con.execute("UPDATE broadcast_runs SET failed = failed + 1 WHERE id=?", (int(run_id),))
        con.commit()


def finish_broadcast_run(run_id: int) -> None:
    with _db() as con:
        con.execute("UPDATE broadcast_runs SET status='completed' WHERE id=?", (int(run_id),))
        con.commit()


def list_recent_broadcast_runs(limit: int = 10):
    import datetime
    with _db() as con:
        rows = con.execute(
            """
            SELECT id, created_at, admin_id, status, total_recipients, sent, failed
            FROM broadcast_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),)
        ).fetchall()
        out = []
        for rid, ts, admin_id, status, total, sent, failed in rows:
            try:
                dt = datetime.datetime.fromtimestamp(int(ts)).strftime('%d.%m.%Y %H:%M') if ts else '—'
            except Exception:
                dt = str(ts)
            out.append((rid, dt, admin_id, status, total, sent, failed))
        return out


def get_broadcast_overview(run_id: int) -> dict | None:
    with _db() as con:
        head = con.execute(
            "SELECT id, created_at, admin_id, status, total_recipients, sent, failed FROM broadcast_runs WHERE id=?",
            (int(run_id),)
        ).fetchone()
        if not head:
            return None
        errs = con.execute(
            "SELECT error_type, COUNT(*) FROM broadcast_results WHERE run_id=? AND status='failed' GROUP BY error_type",
            (int(run_id),)
        ).fetchall()
        return {
            'id': head[0],
            'created_at': head[1],
            'admin_id': head[2],
            'status': head[3],
            'total_recipients': head[4],
            'sent': head[5],
            'failed': head[6],
            'errors': { (e[0] or 'other'): int(e[1] or 0) for e in errs }
        }


def fetch_broadcast_results(run_id: int):
    with _db() as con:
        rows = con.execute(
            """
            SELECT user_id, status, error_code, error_type, error_desc, sent_at
            FROM broadcast_results
            WHERE run_id=?
            ORDER BY sent_at ASC
            """,
            (int(run_id),)
        ).fetchall()
        return rows

def get_unnotified_new_users():
    with _db() as con:
        rows = con.execute("SELECT user_id, user_name, created_at FROM new_user_notifications WHERE notified=0").fetchall()
        return rows


def mark_new_user_notified(user_id: int):
    with _db() as con:
        con.execute("UPDATE new_user_notifications SET notified=1 WHERE user_id=?", (user_id,))
        con.commit()


def mark_tree_damaged(user_id: int, tree_rowid: int, damaged_until: int, damage_pct: float = 0.0, reason: str = None):
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO tree_damage (user_id, tree_rowid, damaged_until, damage_pct, reason) VALUES (?, ?, ?, ?, ?)",
            (user_id, tree_rowid, int(damaged_until), float(damage_pct), reason),
        )
        con.commit()


def get_tree_damage(user_id: int, tree_rowid: int):
    with _db() as con:
        row = con.execute("SELECT damaged_until, damage_pct, reason FROM tree_damage WHERE user_id=? AND tree_rowid=?", (user_id, tree_rowid)).fetchone()
        if not row:
            return None
        return { 'damaged_until': row[0], 'damage_pct': float(row[1] or 0.0), 'reason': row[2] }


def clear_expired_tree_damage(user_id: int = None):
    import time
    now = int(time.time())
    with _db() as con:
        if user_id:
            con.execute("DELETE FROM tree_damage WHERE user_id=? AND damaged_until <= ?", (user_id, now))
        else:
            con.execute("DELETE FROM tree_damage WHERE damaged_until <= ?", (now,))
        con.commit()


def create_event(event_type: str, params: dict, duration_minutes: int, created_by: int, chat_id: int = None, start_in_minutes: int = 0) -> int:
    import time, json
    now = int(time.time())
    start_time = now + max(0, int(start_in_minutes)) * 60
    end_time = start_time + max(1, int(duration_minutes)) * 60
    status = 'scheduled' if start_time > now else 'active'
    with _db() as con:
        cur = con.execute(
            "INSERT INTO events (type, params, start_time, end_time, status, created_by, chat_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_type, json.dumps(params or {}), start_time, end_time, status, created_by, chat_id)
        )
        event_id = cur.lastrowid
        con.commit()
    return int(event_id)


def end_event(event_id: int) -> None:
    with _db() as con:
        con.execute("UPDATE events SET status='ended', end_time = MAX(end_time, strftime('%s','now')) WHERE id=?", (event_id,))
        con.commit()


def get_event_by_id(event_id: int):
    with _db() as con:
        row = con.execute("SELECT id, type, params, start_time, end_time, status, created_by, chat_id FROM events WHERE id=?", (event_id,)).fetchone()
        return row


def get_active_events() -> list:
    import time
    now = int(time.time())
    with _db() as con:
        rows = con.execute(
            """
            SELECT id, type, params, start_time, end_time, status, created_by, chat_id
            FROM events
            WHERE status IN ('active','scheduled')
              AND end_time > ?
            ORDER BY start_time ASC
            """,
            (now,)
        ).fetchall()
        # Promote scheduled→active when time passes
        for row in rows:
            if row[5] == 'scheduled' and row[3] <= now:
                try:
                    with _db() as con2:
                        con2.execute("UPDATE events SET status='active' WHERE id=?", (row[0],))
                        con2.commit()
                except Exception:
                    pass
        return rows


def get_active_event_by_type(event_type: str):
    import time
    now = int(time.time())
    with _db() as con:
        row = con.execute(
            """
            SELECT id, type, params, start_time, end_time, status, created_by, chat_id
            FROM events
            WHERE type=? AND status IN ('active','scheduled') AND end_time > ?
            ORDER BY start_time DESC
            LIMIT 1
            """,
            (event_type, now)
        ).fetchone()
        return row


def set_event_params(event_id: int, params: dict) -> None:
    import json
    with _db() as con:
        con.execute("UPDATE events SET params=? WHERE id=?", (json.dumps(params or {}), event_id))
        con.commit()


def record_event_participation(event_id: int, user_id: int, action: str = None, data: dict = None) -> None:
    import time, json
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO event_participation (event_id, user_id, action, data, ts) VALUES (?, ?, ?, ?, ?)",
            (event_id, user_id, action or '', json.dumps(data or {}), int(time.time()))
        )
        con.commit()


def has_participated(event_id: int, user_id: int) -> bool:
    with _db() as con:
        row = con.execute("SELECT 1 FROM event_participation WHERE event_id=? AND user_id=?", (event_id, user_id)).fetchone()
        return bool(row)


def get_event_participants(event_id: int) -> list:
    """Повертає список учасників події як кортежі (user_id, action, data, ts)."""
    with _db() as con:
        rows = con.execute(
            "SELECT user_id, action, data, ts FROM event_participation WHERE event_id = ?",
            (event_id,)
        ).fetchall()
        return rows


def list_recent_events(limit: int = 20) -> list:
    with _db() as con:
        rows = con.execute(
            "SELECT id, type, params, start_time, end_time, status FROM events ORDER BY id DESC LIMIT ?",
            (max(1, int(limit)),)
        ).fetchall()
        return rows

def ensure_beta_testers_table():
    """Забезпечує правильну структуру таблиці beta_testers"""
    with _db() as con:
        # Перевіряємо існування таблиці та додаємо необхідні поля
        con.execute("""
            CREATE TABLE IF NOT EXISTS beta_testers (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER,
                added_at INTEGER
            );
        """)
        
        # Додаємо поля, якщо їх немає
        try:
            con.execute("ALTER TABLE beta_testers ADD COLUMN added_by INTEGER")
        except:
            pass  # Поле вже існує
            
        try:
            con.execute("ALTER TABLE beta_testers ADD COLUMN added_at INTEGER")
        except:
            pass  # Поле вже існує
            
        con.commit()

def add_beta(user_id: int, added_by: int):
    import time
    ensure_beta_testers_table()  # Забезпечуємо правильну структуру таблиці
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO beta_testers (user_id, added_by, added_at) VALUES (?, ?, ?)", (user_id, added_by, int(time.time())))
        con.commit()

def remove_beta(user_id: int):
    with _db() as con:
        con.execute("DELETE FROM beta_testers WHERE user_id = ?", (user_id,))
        con.commit()

def is_beta(user_id: int) -> bool:
    with _db() as con:
        row = con.execute("SELECT 1 FROM beta_testers WHERE user_id = ?", (int(user_id),)).fetchone()
        return row is not None

# --- Функції для системи закритого доступу ---
def get_invite_only():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'invite_only'").fetchone()
        return int(row[0]) if row else 0

def is_whitelisted(user_id):
    with _db() as con:
        row = con.execute("SELECT 1 FROM beta_testers WHERE user_id = ?", (int(user_id),)).fetchone()
        return row is not None

def add_to_whitelist(user_id):
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO beta_testers (user_id) VALUES (?)", (int(user_id),))
        con.commit()

def get_inactive_beta_testers(hours_threshold=12):
    """Повертає список неактивних бета-тестерів за останні N годин"""
    import time
    threshold_time = int(time.time()) - (hours_threshold * 3600)  # N годин у секундах
    
    with _db() as con:
        query = """
        SELECT 
            bt.user_id, 
            bt.added_by, 
            bt.added_at,
            u.user_name,
            u.username,
            u.last_active,
            u.date_joined
        FROM beta_testers bt
        LEFT JOIN users u ON bt.user_id = u.user_id
        WHERE u.last_active IS NOT NULL AND u.last_active < ?
        ORDER BY u.last_active ASC
        """
        rows = con.execute(query, (threshold_time,)).fetchall()
        
        # Додаємо логування для діагностики
        print(f"[DEBUG] Пошук неактивних бета-тестерів:")
        print(f"[DEBUG] Поточний час: {int(time.time())}")
        print(f"[DEBUG] Поріг активності: {threshold_time}")
        print(f"[DEBUG] Знайдено неактивних: {len(rows)}")
        
        # Показуємо деталі для перших 5 користувачів
        for i, row in enumerate(rows[:5]):
            user_id, added_by, added_at, user_name, username, last_active, date_joined = row
            print(f"[DEBUG] Користувач {i+1}: ID={user_id}, Ім'я={user_name}, Остання активність={last_active}")
        
        return rows

def remove_inactive_beta_testers(hours_threshold=12):
    """Видаляє неактивних бета-тестерів та повертає інформацію про них"""
    inactive_testers = get_inactive_beta_testers(hours_threshold)
    removed_count = 0
    
    with _db() as con:
        for tester in inactive_testers:
            user_id = tester[0]
            con.execute("DELETE FROM beta_testers WHERE user_id = ?", (user_id,))
            removed_count += 1
        con.commit()
    
    return inactive_testers, removed_count

def get_beta_testers_stats():
    """Повертає статистику по бета-тестерам"""
    import time
    current_time = time.time()
    
    with _db() as con:
        # Загальна кількість бета-тестерів
        total = con.execute("SELECT COUNT(*) FROM beta_testers").fetchone()[0]
        
        # Активні за останні 12 годин
        threshold_12h = current_time - (12 * 3600)
        active_12h = con.execute("""
            SELECT COUNT(*) FROM beta_testers bt
            LEFT JOIN users u ON bt.user_id = u.user_id
            WHERE u.last_active >= ?
        """, (threshold_12h,)).fetchone()[0]
        
        # Активні за останні 24 години
        threshold_24h = current_time - (24 * 3600)
        active_24h = con.execute("""
            SELECT COUNT(*) FROM beta_testers bt
            LEFT JOIN users u ON bt.user_id = u.user_id
            WHERE u.last_active >= ?
        """, (threshold_24h,)).fetchone()[0]
        
        # Неактивні більше 12 годин (тільки з активністю)
        inactive_12h = con.execute("""
            SELECT COUNT(*) FROM beta_testers bt
            LEFT JOIN users u ON bt.user_id = u.user_id
            WHERE u.last_active IS NOT NULL AND u.last_active < ?
        """, (threshold_12h,)).fetchone()[0]
        
        return {
            'total': total,
            'active_12h': active_12h,
            'active_24h': active_24h,
            'inactive_12h': inactive_12h
        }

def get_beta_testers(limit=200):
    """Повертає список бета-тестерів з бази"""
    ensure_beta_testers_table()
    with _db() as con:
        rows = con.execute("""
            SELECT 
                bt.user_id,
                bt.added_by,
                bt.added_at,
                u.user_name,
                u.username,
                u.last_active,
                u.date_joined
            FROM beta_testers bt
            LEFT JOIN users u ON bt.user_id = u.user_id
            ORDER BY bt.added_at DESC
            LIMIT ?
        """, (max(1, int(limit)),)).fetchall()
    
    testers = []
    for row in rows:
        testers.append({
            'user_id': row[0],
            'added_by': row[1],
            'added_at': row[2],
            'user_name': row[3],
            'username': row[4],
            'last_active': row[5],
            'date_joined': row[6]
        })
    return testers

# --- Система номерів телефонів ---
def ensure_phone_table():
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS user_phones (
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                verified INTEGER DEFAULT 1,
                created_at INTEGER
            );
        ''')
        con.commit()

ensure_phone_table()

def get_user_phone(user_id):
    with _db() as con:
        row = con.execute("SELECT phone FROM user_phones WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

def set_user_phone(user_id, phone):
    import time
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO user_phones (user_id, phone, verified, created_at) VALUES (?, ?, 1, ?)", 
                   (user_id, phone, int(time.time())))
        con.commit()

def is_phone_verified(user_id):
    with _db() as con:
        row = con.execute("SELECT verified FROM user_phones WHERE user_id = ?", (user_id,)).fetchone()
        return bool(row and row[0]) if row else False

# --- Канал для виводів ---
def get_withdraw_channel():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'withdraw_channel'").fetchone()
        # Повертаємо як є: підтримуємо і числовий ID (-100...), і @username
        return row[0] if row and row[0] else None

def set_withdraw_channel(channel_id):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('withdraw_channel', ?)", (str(channel_id),))
        con.commit()

# --- Обов'язковий канал для підписки ---
def get_required_channel():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'required_channel'").fetchone()
        return row[0] if row and row[0] else None

def set_required_channel(channel_username):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('required_channel', ?)", (channel_username,))
        con.commit()

# --- Система банів ---
def ensure_bans_table():
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS user_bans (
                user_id INTEGER PRIMARY KEY,
                banned_by INTEGER,
                reason TEXT,
                banned_at INTEGER,
                unban_at INTEGER,
                is_permanent INTEGER DEFAULT 0
            );
        ''')
        con.commit()

ensure_bans_table()

def ban_user(user_id, banned_by, reason, duration_seconds=None):
    import time
    banned_at = int(time.time())
    unban_at = banned_at + duration_seconds if duration_seconds else None
    is_permanent = 1 if duration_seconds is None else 0
    
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO user_bans (user_id, banned_by, reason, banned_at, unban_at, is_permanent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, banned_by, reason, banned_at, unban_at, is_permanent))
        con.commit()

def unban_user(user_id):
    with _db() as con:
        con.execute("DELETE FROM user_bans WHERE user_id = ?", (user_id,))
        con.commit()

def is_user_banned(user_id):
    import time
    current_time = int(time.time())
    
    with _db() as con:
        row = con.execute("""
            SELECT banned_at, unban_at, is_permanent, reason 
            FROM user_bans 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not row:
            return False, None
        
        banned_at, unban_at, is_permanent, reason = row
        
        # Якщо постійний бан
        if is_permanent:
            return True, reason
        
        # Якщо тимчасовий бан і час ще не вийшов
        if unban_at and current_time < unban_at:
            return True, reason
        
        # Якщо час бану вийшов - видаляємо з БД
        if unban_at and current_time >= unban_at:
            unban_user(user_id)
            return False, None
        
        return False, None

def get_ban_info(user_id):
    import time
    current_time = int(time.time())
    
    with _db() as con:
        row = con.execute("""
            SELECT banned_by, reason, banned_at, unban_at, is_permanent 
            FROM user_bans 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if not row:
            return None
        
        banned_by, reason, banned_at, unban_at, is_permanent = row
        
        if is_permanent:
            return {
                'banned_by': banned_by,
                'reason': reason,
                'banned_at': banned_at,
                'is_permanent': True,
                'time_left': None
            }
        
        if unban_at and current_time < unban_at:
            return {
                'banned_by': banned_by,
                'reason': reason,
                'banned_at': banned_at,
                'is_permanent': False,
                'time_left': unban_at - current_time
            }
        
        return None

def get_user_id_by_username(username):
    """Шукає ID користувача за username (без @)"""
    username = username.replace('@', '').lower()
    
    with _db() as con:
        # Шукаємо в таблиці users за username
        row = con.execute("""
            SELECT user_id FROM users WHERE LOWER(username) = ?
        """, (username,)).fetchone()
        
        if row:
            return row[0]
        return None

def save_user_username(user_id, username):
    """Зберігає username користувача при першому контакті"""
    if not username:
        return
        
    username = username.replace('@', '')
    
    with _db() as con:
        # Перевіряємо чи існує колонка username
        try:
            con.execute("ALTER TABLE users ADD COLUMN username TEXT")
            con.commit()
        except:
            pass  # Колонка вже існує
        
        # Оновлюємо username
        con.execute("""
            UPDATE users SET username = ? WHERE user_id = ?
        """, (username, user_id))
        con.commit()

# --- Система ігрових чатів ---
def ensure_gaming_tables():
    with _db() as con:
        # Таблиця дозволених ігрових чатів
        con.execute('''
            CREATE TABLE IF NOT EXISTS gaming_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                added_by INTEGER,
                added_at INTEGER,
                min_bet REAL DEFAULT 1.0,
                max_bet REAL DEFAULT 1000.0,
                enabled_games TEXT DEFAULT 'guess_number'
            );
        ''')
        # Таблиця активних ігрових сесій
        con.execute('''
            CREATE TABLE IF NOT EXISTS game_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                game_type TEXT,
                bet_amount REAL,
                target_number INTEGER,
                user_guess INTEGER,
                created_at INTEGER,
                status TEXT DEFAULT 'active'
            );
        ''')
        # Історія ігор
        con.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                game_type TEXT,
                bet_amount REAL,
                result TEXT,
                win_amount REAL,
                played_at INTEGER
            );
        ''')
        con.commit()

ensure_gaming_tables()

def add_gaming_chat(chat_id, chat_title, added_by):
    import time
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gaming_chats (chat_id, chat_title, added_by, added_at) VALUES (?, ?, ?, ?)", 
                   (chat_id, chat_title, added_by, int(time.time())))
        con.commit()

def remove_gaming_chat(chat_id):
    with _db() as con:
        con.execute("DELETE FROM gaming_chats WHERE chat_id = ?", (chat_id,))
        con.commit()

def is_gaming_chat(chat_id):
    with _db() as con:
        row = con.execute("SELECT 1 FROM gaming_chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return row is not None

def get_gaming_chats():
    with _db() as con:
        rows = con.execute("SELECT chat_id, chat_title, added_by, added_at FROM gaming_chats").fetchall()
        return rows

def create_guess_game(chat_id, user_id, bet_amount):
    import random, time
    target_number = random.randint(1, 4)
    with _db() as con:
        # Перевіряємо баланс і резервуємо кошти
        current_balance = con.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not current_balance or current_balance[0] < bet_amount:
            return None, None  # Недостатньо коштів
        
        # Резервуємо кошти (віднімаємо ставку)
        new_balance = current_balance[0] - bet_amount
        con.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        
        # Створюємо сесію гри
        cur = con.execute("""
            INSERT INTO game_sessions (chat_id, user_id, game_type, bet_amount, target_number, created_at)
            VALUES (?, ?, 'guess_number', ?, ?, ?)
        """, (chat_id, user_id, bet_amount, target_number, int(time.time())))
        session_id = cur.lastrowid
        con.commit()
    return session_id, target_number

def process_guess(session_id, user_guess):
    import time
    with _db() as con:
        session = con.execute("SELECT chat_id, user_id, bet_amount, target_number FROM game_sessions WHERE id = ? AND status = 'active'", 
                             (session_id,)).fetchone()
        if not session:
            return None
        
        chat_id, user_id, bet_amount, target_number = session
        won = (user_guess == target_number)
        win_amount = bet_amount * 2 if won else 0
        
        # Оновлюємо сесію
        con.execute("UPDATE game_sessions SET user_guess = ?, status = 'completed' WHERE id = ?", (user_guess, session_id))
        
        # Додаємо в історію
        con.execute("""
            INSERT INTO game_history (chat_id, user_id, game_type, bet_amount, result, win_amount, played_at)
            VALUES (?, ?, 'guess_number', ?, ?, ?, ?)
        """, (chat_id, user_id, bet_amount, 'win' if won else 'lose', win_amount, int(time.time())))
        
        # Оновлюємо баланс ВСЕРЕДИНІ цієї ж транзакції
        current_balance = con.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if current_balance:
            current_balance = current_balance[0]
            if won:
                new_balance = current_balance + bet_amount  # Повертаємо ставку + виграш (ставка)
            else:
                new_balance = current_balance  # Ставка вже знята в create_guess_game
            con.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        
        con.commit()
        return {
            'won': won,
            'target_number': target_number,
            'user_guess': user_guess,
            'bet_amount': bet_amount,
            'win_amount': win_amount
        }

def delete_user_completely(user_id):
    """Повністю видаляє користувача з всіх таблиць бази даних"""
    with _db() as con:
        # Видаляємо з основної таблиці користувачів
        con.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        
        # Видаляємо всі транзакції
        con.execute("DELETE FROM tx WHERE user_id = ?", (user_id,))
        
        # Видаляємо депозити
        con.execute("DELETE FROM deposit_tx WHERE user_id = ?", (user_id,))
        
        # Видаляємо з саду
        con.execute("DELETE FROM gardens WHERE user_id = ?", (user_id,))
        try:
            con.execute("DELETE FROM users_garden WHERE user_id = ?", (user_id,))
        except:
            pass
        try:
            con.execute("DELETE FROM user_garden_level WHERE user_id = ?", (user_id,))
        except:
            pass
        try:
            con.execute("DELETE FROM garden_stats WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо садові транзакції
        try:
            con.execute("DELETE FROM garden_transactions WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо промокоди користувача (з promo_code_usages)
        try:
            con.execute("DELETE FROM promo_code_usages WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо ігрові чати користувача (можливо gaming_chats)
        try:
            con.execute("DELETE FROM gaming_chats WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо історію ігор
        try:
            con.execute("DELETE FROM game_history WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо бани
        try:
            con.execute("DELETE FROM user_bans WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо з очікуючих користувачів
        try:
            con.execute("DELETE FROM pending_users WHERE user_id = ?", (user_id,))
        except:
            pass
        
        # Видаляємо використані інвайти
        con.execute("UPDATE invites SET is_used = 0, who_used = NULL WHERE who_used = ?", (user_id,))
        
        # Видаляємо з реферальної системи (якщо є)
        try:
            con.execute("DELETE FROM referrals WHERE user_id = ? OR invited_by = ?", (user_id, user_id))
        except:
            pass
            
        # Видаляємо телефони
        try:
            con.execute("DELETE FROM user_phones WHERE user_id = ?", (user_id,))
        except:
            pass
            
        con.commit()
        
def get_user_exists(user_id):
    """Перевіряє чи існує користувач в базі"""
    with _db() as con:
        row = con.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None

def wipe_all_data_except_admins():
    """Повністю очищує всю базу даних окрім таблиці адмінів"""
    with _db() as con:
        # Отримуємо список всіх таблиць
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        
        for table in tables:
            table_name = table[0]
            
            # Пропускаємо системні таблиці та таблицю адмінів
            if table_name in ['sqlite_sequence', 'admins']:
                continue
                
            try:
                # Видаляємо всі дані з таблиці
                con.execute(f"DELETE FROM {table_name}")
                print(f"[WIPE] Очищено таблицю: {table_name}")
            except Exception as e:
                print(f"[WIPE ERROR] Помилка очищення {table_name}: {e}")
        
        # Скидаємо автоінкремент для всіх таблиць
        try:
            con.execute("DELETE FROM sqlite_sequence")
            print("[WIPE] Скинуто автоінкремент")
        except:
            pass
            
        con.commit()
        print("[WIPE] ✅ ПОВНИЙ ВАЙП ЗАВЕРШЕНО!")

def get_database_stats():
    """Отримує статистику по всіх таблицях бази"""
    stats = {}
    with _db() as con:
        tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        print(f"[DEBUG] Знайдено таблиць: {[t[0] for t in tables]}")
        
        for table in tables:
            table_name = table[0]
            if table_name == 'sqlite_sequence':
                continue
                
            try:
                count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                stats[table_name] = count
                if table_name == 'admins':
                    print(f"[DEBUG] Адміни: {count}")
            except Exception as e:
                stats[table_name] = "ERROR"
                print(f"[DEBUG ERROR] {table_name}: {e}")
    
    return stats

# --- Комісія саду ---
def get_garden_commission():
    """Отримує поточний відсоток комісії саду"""
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'garden_commission'").fetchone()
        return float(row[0]) if row else 10.0  # За замовчуванням 10%

def get_user_garden_commission(user_id: int) -> float:
    """Отримує комісію саду для конкретного користувача на основі його рівня"""
    from garden_models import GARDEN_LEVELS
    
    # Отримуємо рівень користувача
    user_level = get_user_garden_level(user_id)
    
    # Знаходимо інформацію про рівень
    level_info = next((l for l in GARDEN_LEVELS if l['level'] == user_level), None)
    
    if level_info:
        return level_info['commission_percent']
    else:
        # Якщо рівень не знайдено, повертаємо комісію за замовчуванням
        return get_garden_commission()

def set_garden_commission(commission_percent):
    """Встановлює відсоток комісії саду"""
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", 
                   ("garden_commission", str(commission_percent)))
        con.commit()

def get_main_admin():
    """Отримує ID головного адміністратора (першого в списку)"""
    with _db() as con:
        row = con.execute("SELECT user_id FROM admins ORDER BY user_id LIMIT 1").fetchone()
        return row[0] if row else None

# --- Рівні саду ---
def get_user_garden_level(user_id):
    """Отримує поточний рівень саду користувача"""
    with _db() as con:
        row = con.execute("SELECT level FROM garden_levels WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else 0  # За замовчуванням рівень 0 (потрібно купити рівень 1)

def set_user_garden_level(user_id, level):
    """Встановлює рівень саду користувача"""
    import time
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO garden_levels (user_id, level, purchased_at) 
            VALUES (?, ?, ?)
        """, (user_id, level, int(time.time())))
        con.commit()

def get_available_trees_for_level(level):
    """Отримує список доступних дерев для рівня"""
    from garden_models import GARDEN_LEVELS
    level_info = next((l for l in GARDEN_LEVELS if l['level'] == level), None)
    return level_info['available_trees'] if level_info else ['apple', 'pear', 'cherry', 'peach']

def get_garden_level_info(level):
    """Отримує інформацію про рівень саду"""
    from garden_models import GARDEN_LEVELS
    return next((l for l in GARDEN_LEVELS if l['level'] == level), None)

def can_upgrade_garden_level(user_id):
    """Перевіряє чи може користувач підвищити рівень саду"""
    current_level = get_user_garden_level(user_id)
    from garden_models import GARDEN_LEVELS
    next_level = next((l for l in GARDEN_LEVELS if l['level'] == current_level + 1), None)
    return next_level is not None

def get_next_garden_level_price(user_id):
    """Отримує ціну наступного рівня саду"""
    current_level = get_user_garden_level(user_id)
    from garden_models import GARDEN_LEVELS
    next_level = next((l for l in GARDEN_LEVELS if l['level'] == current_level + 1), None)
    if not next_level:
        return None
    # Використовуємо ціну з налаштувань якщо є
    return get_level_price(next_level['level'])

def get_level_price(level: int) -> float:
    """Повертає актуальну ціну рівня (із налаштувань або дефолт з моделей)."""
    try:
        key = f'garden_level_price_{level}'
        val = get_game_setting(key, None)
        if val is not None:
            return float(val)
        # Фолбек на дефолтну модель
        from garden_models import GARDEN_LEVELS
        level_info = next((l for l in GARDEN_LEVELS if l['level'] == level), None)
        return float(level_info['price_uah']) if level_info else 0.0
    except Exception:
        from garden_models import GARDEN_LEVELS
        level_info = next((l for l in GARDEN_LEVELS if l['level'] == level), None)
        return float(level_info['price_uah']) if level_info else 0.0

def set_level_price(level: int, price: float):
    """Встановлює ціну рівня у налаштуваннях гри."""
    set_game_setting(f'garden_level_price_{level}', str(float(price)))

# =============================================================================
# 🎰 НАЛАШТУВАННЯ ІГОР - Додано для групових чатів
# =============================================================================

def ensure_game_settings_table():
    """Створює таблицю налаштувань ігор"""
    with _db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS game_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT
            );
        ''')
        
        # Встановлюємо дефолтні налаштування якщо їх немає
        default_settings = [
            ('games_enabled', '1'),
            ('dice_enabled', '1'),
            ('coin_enabled', '1'),
            ('number_enabled', '1'),
            ('slot_enabled', '1'),
            ('dice_multiplier', '5.5'),
            ('coin_multiplier', '1.9'),
            ('number_high_multiplier', '9.0'),
            ('number_medium_multiplier', '3.5'),
            ('number_low_multiplier', '1.8'),
            ('slot_diamond_multiplier', '50.0'),
            ('slot_seven_multiplier', '25.0'),
            ('slot_bell_multiplier', '15.0'),
            ('slot_other_multiplier', '10.0'),
            ('min_bet', '1.0'),
            ('max_bet', '1000.0'),
            # Глобальне налаштування економіки саду: множник врожайності
            # 1.0 = без змін, 0.25 = 25% від базового врожаю
            ('economy_harvest_multiplier', '0.25'),
            ('trees_purchase_enabled', '1'),
            ('daily_bonus_enabled', '1'),
            ('ref_bonus_enabled', '1'),
            # Комісія на вивід коштів (% від суми)
            ('withdraw_commission_percent', '3.0'),
            # Авто-нагадування (розсилка)
            ('auto_reminders_enabled', '1'),
            ('auto_reminders_interval_hours', '6'),
            # values: all | non_ambassador | low_level
            ('auto_reminders_segment', 'all'),
            ('auto_reminders_low_level_max', '1'),
            # Реферальні правила (вестинг)
            ('ref_vest_days', '7'),
            ('ref_require_subscription', '1'),
            ('ref_min_actions', '5'),
            ('ref_min_level', '1'),
            ('ref_min_deposit', '0'),
            ('ref_allow_clawback', '1'),
            ('ref_clawback_days', '14')
        ]
        
        for key, value in default_settings:
            con.execute("INSERT OR IGNORE INTO game_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
        
        con.commit()

# Викликаємо функцію при ініціалізації
ensure_game_settings_table()

def get_game_setting(key: str, default_value: str = "1") -> str:
    """Отримує налаштування гри"""
    with _db() as con:
        row = con.execute("SELECT setting_value FROM game_settings WHERE setting_key = ?", (key,)).fetchone()
        return row[0] if row else default_value

def set_game_setting(key: str, value: str):
    """Встановлює налаштування гри"""
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO game_settings (setting_key, setting_value) VALUES (?, ?)", (key, value))
        con.commit()

# ==========================
# 👥 РЕФЕРАЛЬНІ ВИНАГОРОДИ (вестинг)
# ==========================

def ensure_referral_rewards_table():
    """Таблиця для відкладених реферальних винагород (pending → unlocked/canceled)."""
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS referral_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER NOT NULL,
                referred_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,            -- pending|unlocked|canceled|clawedback
                created_at INTEGER NOT NULL,
                unlock_at INTEGER NOT NULL,
                reason TEXT,
                last_check_at INTEGER
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_ref_rewards_referrer ON referral_rewards(referrer_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_ref_rewards_referred ON referral_rewards(referred_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_ref_rewards_status ON referral_rewards(status)")
        con.commit()

ensure_referral_rewards_table()

def create_referral_reward_pending(referrer_id: int, referred_id: int, amount: float) -> int | None:
    """Створює pending нагороду з unlock_at згідно налаштувань ref_vest_days."""
    import time
    try:
        vest_days = int(get_game_setting('ref_vest_days', '7'))
    except Exception:
        vest_days = 7
    now = int(time.time())
    unlock_at = now + max(1, vest_days) * 24 * 3600
    with _db() as con:
        cur = con.execute(
            """
            INSERT INTO referral_rewards(referrer_id, referred_id, amount, status, created_at, unlock_at)
            VALUES(?, ?, ?, 'pending', ?, ?)
            """,
            (int(referrer_id), int(referred_id), float(amount), now, unlock_at)
        )
        con.commit()
        return int(cur.lastrowid)

def list_due_pending_referral_rewards() -> list[tuple]:
    """Список pending, у яких настав час розблокування (unlock_at <= now)."""
    import time
    now = int(time.time())
    with _db() as con:
        rows = con.execute(
            "SELECT id, referrer_id, referred_id, amount, created_at, unlock_at FROM referral_rewards WHERE status='pending' AND unlock_at<=? ORDER BY unlock_at ASC",
            (now,)
        ).fetchall()
        return rows or []

def mark_referral_reward_status(reward_id: int, status: str, reason: str | None = None):
    import time
    with _db() as con:
        con.execute(
            "UPDATE referral_rewards SET status=?, reason=?, last_check_at=? WHERE id=?",
            (status, reason, int(time.time()), int(reward_id))
        )
        con.commit()

def safe_clawback_balance(user_id: int, amount: float) -> float:
    """Пробує списати до amount з балансу. Повертає фактично списане."""
    try:
        amt = float(amount)
    except Exception:
        return 0.0
    if amt <= 0:
        return 0.0
    with _db() as con:
        row = con.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        bal = float(row[0] or 0.0) if row else 0.0
        to_deduct = min(bal, amt)
        if to_deduct > 0:
            new_bal = bal - to_deduct
            con.execute("UPDATE users SET balance=? WHERE user_id=?", (new_bal, user_id))
            con.commit()
        return to_deduct

def get_user_actions_count_since(user_id: int, since_ts: int) -> int:
    """К-сть дій у саду з моменту since_ts (за історією garden_transactions)."""
    with _db() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM garden_transactions WHERE user_id=? AND timestamp>=?",
            (user_id, since_ts)
        ).fetchone()
        return int(row[0] or 0)

# ==========================
# 🎁 ПОДАРУНОК — Налаштування/сесії
# ==========================

def ensure_gift_tables():
    with _db() as con:
        # Конфіги рівнів та глобальні
        con.execute('''
            CREATE TABLE IF NOT EXISTS gift_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # За замовчуванням
        defaults = [
            ('gift_bombs_count', '2'),
            ('gift_cooldown_hours', '24'),
            ('gift_session_version', '1'),
        ]
        for k, v in defaults:
            con.execute("INSERT OR IGNORE INTO gift_settings (key, value) VALUES (?, ?)", (k, v))
        # Рівневі налаштування: спроби, баланс, фрукти
        con.execute('''
            CREATE TABLE IF NOT EXISTS gift_level_settings (
                level INTEGER PRIMARY KEY,
                attempts INTEGER DEFAULT 3,
                reward_balance REAL DEFAULT 1.0,
                fruit_type TEXT DEFAULT 'apple',
                fruit_amount REAL DEFAULT 1.0
            )
        ''')
        # Сохран даты последней игры
        con.execute('''
            CREATE TABLE IF NOT EXISTS gift_last_play (
                user_id INTEGER PRIMARY KEY,
                last_play_ts INTEGER
            )
        ''')
        # Таблица для наград за каждую попытку
        con.execute('''
            CREATE TABLE IF NOT EXISTS gift_attempt_rewards (
                level INTEGER NOT NULL,
                attempt_number INTEGER NOT NULL,
                reward_balance REAL DEFAULT 0.0,
                fruit_type TEXT DEFAULT 'apple',
                fruit_amount REAL DEFAULT 0.0,
                PRIMARY KEY (level, attempt_number)
            )
        ''')
        
        # Миграция: проверяем наличие колонки attempt_number
        try:
            # Проверяем структуру таблицы
            cursor = con.execute("PRAGMA table_info(gift_attempt_rewards)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'attempt_number' not in columns:
                # Таблица существует, но без колонки attempt_number - пересоздаем
                print("[MIGRATION] gift_attempt_rewards: пересоздаем таблицу с колонкой attempt_number")
                # Сохраняем данные, если они есть
                old_data = con.execute("SELECT * FROM gift_attempt_rewards").fetchall()
                # Удаляем старую таблицу
                con.execute("DROP TABLE IF EXISTS gift_attempt_rewards")
                # Создаем новую таблицу с правильной структурой
                con.execute('''
                    CREATE TABLE gift_attempt_rewards (
                        level INTEGER NOT NULL,
                        attempt_number INTEGER NOT NULL,
                        reward_balance REAL DEFAULT 0.0,
                        fruit_type TEXT DEFAULT 'apple',
                        fruit_amount REAL DEFAULT 0.0,
                        PRIMARY KEY (level, attempt_number)
                    )
                ''')
                # Если в старой таблице были данные без attempt_number, 
                # мы их не можем восстановить, так как не знаем номер попытки
                print("[MIGRATION] gift_attempt_rewards: таблица пересоздана")
        except Exception as e:
            print(f"[WARNING] gift_attempt_rewards migration check failed: {e}")
        
        con.commit()

ensure_gift_tables()

def get_gift_bombs_count() -> int:
    with _db() as con:
        row = con.execute("SELECT value FROM gift_settings WHERE key='gift_bombs_count'").fetchone()
        return int(row[0]) if row and str(row[0]).isdigit() else 2

def set_gift_bombs_count(cnt: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_settings (key, value) VALUES ('gift_bombs_count', ?)", (str(int(cnt)),))
        con.commit()

def get_gift_cooldown_hours() -> int:
    with _db() as con:
        row = con.execute("SELECT value FROM gift_settings WHERE key='gift_cooldown_hours'").fetchone()
        return int(row[0]) if row and str(row[0]).isdigit() else 24

def set_gift_cooldown_hours(hours: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_settings (key, value) VALUES ('gift_cooldown_hours', ?)", (str(int(hours)),))
        con.commit()

def get_gift_session_version() -> int:
    with _db() as con:
        row = con.execute("SELECT value FROM gift_settings WHERE key='gift_session_version'").fetchone()
        return int(row[0]) if row and str(row[0]).isdigit() else 1

def set_gift_session_version(ver: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_settings (key, value) VALUES ('gift_session_version', ?)", (str(int(ver)),))
        con.commit()

def get_gift_attempts(level: int) -> int:
    with _db() as con:
        row = con.execute("SELECT attempts FROM gift_level_settings WHERE level=?", (int(level),)).fetchone()
        if not row:
            con.execute("INSERT OR REPLACE INTO gift_level_settings (level) VALUES (?)", (int(level),))
            con.commit()
            return 3
        return int(row[0] if row[0] is not None else 3)

def set_gift_attempts(level: int, attempts: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_level_settings (level, attempts) VALUES (?, ?)", (int(level), int(attempts)))
        con.commit()

def get_gift_reward_balance(level: int) -> float:
    with _db() as con:
        row = con.execute("SELECT reward_balance FROM gift_level_settings WHERE level=?", (int(level),)).fetchone()
        if not row:
            con.execute("INSERT OR REPLACE INTO gift_level_settings (level) VALUES (?)", (int(level),))
            con.commit()
            return 1.0
        return float(row[0] if row[0] is not None else 1.0)

def set_gift_reward_balance(level: int, amount: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_level_settings (level, reward_balance) VALUES (?, ?)", (int(level), float(amount)))
        con.commit()

def get_gift_reward_fruit(level: int) -> tuple[str, float]:
    with _db() as con:
        row = con.execute("SELECT fruit_type, fruit_amount FROM gift_level_settings WHERE level=?", (int(level),)).fetchone()
        if not row:
            con.execute("INSERT OR REPLACE INTO gift_level_settings (level) VALUES (?)", (int(level),))
            con.commit()
            return 'apple', 1.0
        ftype = row[0] or 'apple'
        famt = float(row[1] if row[1] is not None else 1.0)
        return ftype, famt

def set_gift_reward_fruit(level: int, fruit_type: str, amount: float):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_level_settings (level, fruit_type, fruit_amount) VALUES (?, ?, ?)", (int(level), str(fruit_type), float(amount)))
        con.commit()

def get_gift_last_play(user_id: int) -> int | None:
    with _db() as con:
        row = con.execute("SELECT last_play_ts FROM gift_last_play WHERE user_id=?", (int(user_id),)).fetchone()
        return int(row[0]) if row and row[0] is not None else None

def set_gift_last_play(user_id: int, ts: int):
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO gift_last_play (user_id, last_play_ts) VALUES (?, ?)", (int(user_id), int(ts)))
        con.commit()

def reset_all_gift_cooldowns():
    with _db() as con:
        con.execute("DELETE FROM gift_last_play")
        con.commit()
        return con.total_changes

def bump_gift_session_version():
    """Збільшує версію сесій гри, що призводить до скидання всіх активних сесій."""
    current = int(get_gift_session_version())
    new_version = current + 1
    set_gift_session_version(new_version)
    return new_version

def reset_all_gift_sessions():
    # Сесії зберігаються у user_states -> gift_session, глобально очищати не будемо тут
    # Опціонально можна інкрементувати версію, щоб скинути всі активні сесії
    cur = get_gift_session_version()
    set_gift_session_version(cur + 1)

def get_gift_attempt_reward(level: int, attempt_number: int) -> tuple[float, str, float]:
    """Получает награду за конкретную попытку. Возвращает (reward_balance, fruit_type, fruit_amount)"""
    with _db() as con:
        row = con.execute(
            "SELECT reward_balance, fruit_type, fruit_amount FROM gift_attempt_rewards WHERE level=? AND attempt_number=?",
            (int(level), int(attempt_number))
        ).fetchone()
        if row:
            return (float(row[0] or 0.0), str(row[1] or 'apple'), float(row[2] or 0.0))
        # Если нет настроек для этой попытки - возвращаем нули
        return (0.0, 'apple', 0.0)

def set_gift_attempt_reward(level: int, attempt_number: int, reward_balance: float, fruit_type: str, fruit_amount: float):
    """Устанавливает награду за конкретную попытку"""
    with _db() as con:
        con.execute(
            "INSERT OR REPLACE INTO gift_attempt_rewards (level, attempt_number, reward_balance, fruit_type, fruit_amount) VALUES (?, ?, ?, ?, ?)",
            (int(level), int(attempt_number), float(reward_balance), str(fruit_type), float(fruit_amount))
        )
        con.commit()

def get_gift_level_attempts(level: int) -> list[tuple[int, float, str, float]]:
    """Получает все награды для уровня. Возвращает список (attempt_number, reward_balance, fruit_type, fruit_amount)"""
    with _db() as con:
        rows = con.execute(
            "SELECT attempt_number, reward_balance, fruit_type, fruit_amount FROM gift_attempt_rewards WHERE level=? ORDER BY attempt_number",
            (int(level),)
        ).fetchall()
        return [(int(r[0]), float(r[1] or 0.0), str(r[2] or 'apple'), float(r[3] or 0.0)) for r in rows]

def init_default_gift_attempts(level: int, attempts_count: int):
    """Инициализирует дефолтные награды для всех попыток уровня на основе базовых настроек уровня"""
    with _db() as con:
        # Получаем базовые настройки уровня
        base_bal = float(get_gift_reward_balance(level))
        ftype, base_famt = get_gift_reward_fruit(level)
        
        # Удаляем старые настройки для этого уровня
        con.execute("DELETE FROM gift_attempt_rewards WHERE level=?", (int(level),))
        
        # Создаем прогрессивную систему: попытка N дает base * (2*N - 1) для баланса и base * N для фруктов
        for attempt in range(1, attempts_count + 1):
            bal_add = base_bal * (2 * attempt - 1)
            fruit_add = float(base_famt) * attempt
            con.execute(
                "INSERT INTO gift_attempt_rewards (level, attempt_number, reward_balance, fruit_type, fruit_amount) VALUES (?, ?, ?, ?, ?)",
                (int(level), attempt, float(bal_add), str(ftype), float(fruit_add))
            )
        con.commit()

def get_withdraw_commission_percent() -> float:
    """Повертає відсоток комісії для виводу коштів."""
    try:
        return float(get_game_setting('withdraw_commission_percent', '5.0'))
    except Exception:
        return 3.0

def is_ambassador(user_id: int) -> bool:
    """Повертає True, якщо у ніку/username користувача є 'palmaron_bot'.
    Враховує як відображуване ім'я (user_name), так і username (без @).
    """
    try:
        with _db() as con:
            row = con.execute("SELECT user_name, username FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False
        name_text = f"{row[0] or ''} {row[1] or ''}".lower()
        # Підтримуємо обидва написання: palamron та palmaron
        variants = ['palamron_bot', '@palamron_bot', 'palmaron_bot', '@palmaron_bot']
        return any(v in name_text for v in variants)
    except Exception:
        return False

def get_inactive_referral_commission_percent() -> float:
    """Повертає відсоток додаткової комісії за неактивних рефералів."""
    try:
        return float(get_game_setting('inactive_referral_commission_percent', '1.0'))
    except Exception:
        return 1.0  # За замовчуванням 1% за кожного неактивного реферала

def set_inactive_referral_commission_percent(percent: float):
    """Встановлює відсоток додаткової комісії за неактивних рефералів."""
    try:
        p = max(0.0, float(percent))
    except Exception:
        p = 1.0
    set_game_setting('inactive_referral_commission_percent', str(p))

def get_inactive_referral_days() -> int:
    """Повертає кількість днів без активності для вважання реферала неактивним."""
    try:
        return int(get_game_setting('inactive_referral_days', '30'))
    except Exception:
        return 30  # За замовчуванням 30 днів

def set_inactive_referral_days(days: int):
    """Встановлює кількість днів без активності для вважання реферала неактивним."""
    try:
        d = max(1, int(days))
    except Exception:
        d = 30
    set_game_setting('inactive_referral_days', str(d))

def get_effective_withdraw_commission_percent(user_id: int) -> float:
    """Дає ефективну комісію для виводу з урахуванням амбасадорів та неактивних рефералів.
    Амбасадори (нік містить @palmaron_bot) мають 0% комісію (тимчасово).
    За кожного неактивного реферала додається додаткова комісія.
    """
    try:
        if is_ambassador(user_id):
            return 0.0
    except Exception:
        pass
    
    # Базова комісія
    base_commission = get_withdraw_commission_percent()
    
    # Додаткова комісія за неактивних рефералів
    try:
        inactive_count = get_inactive_referrals_count(user_id, get_inactive_referral_days())
        inactive_commission_per_referral = get_inactive_referral_commission_percent()
        additional_commission = inactive_count * inactive_commission_per_referral
        
        total_commission = base_commission + additional_commission
        return total_commission
    except Exception as e:
        print(f"[ERROR] Помилка розрахунку комісії за неактивних рефералів: {e}")
        return base_commission

def set_withdraw_commission_percent(percent: float):
    """Встановлює відсоток комісії для виводу коштів."""
    try:
        p = max(0.0, float(percent))
    except Exception:
        p = 0.0
    set_game_setting('withdraw_commission_percent', str(p))

# --- Ambassador status persistence (to avoid duplicate notifications) ---
def _ensure_ambassador_columns():
    """Guarantee ambassador columns exist in users table."""
    try:
        with _db() as con:
            try:
                con.execute("ALTER TABLE users ADD COLUMN ambassador_active INTEGER DEFAULT 0")
                con.commit()
            except Exception:
                pass
            try:
                con.execute("ALTER TABLE users ADD COLUMN ambassador_updated_at INTEGER")
                con.commit()
            except Exception:
                pass
    except Exception:
        pass

def get_ambassador_active(user_id: int) -> bool:
    _ensure_ambassador_columns()
    try:
        with _db() as con:
            row = con.execute("SELECT ambassador_active FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return bool(row[0]) if row and row[0] is not None else False
    except Exception:
        return False

def set_ambassador_active(user_id: int, active: bool):
    _ensure_ambassador_columns()
    import time
    try:
        with _db() as con:
            con.execute(
                "UPDATE users SET ambassador_active = ?, ambassador_updated_at = ? WHERE user_id = ?",
                (1 if active else 0, int(time.time()), user_id)
            )
            con.commit()
    except Exception:
        pass

def update_ambassador_flag_from_profile(user_id: int) -> tuple[bool, bool]:
    """Синхронізує прапорець ambassador_active з поточним профілем.
    Повертає (changed, new_active)."""
    current = is_ambassador(user_id)
    stored = get_ambassador_active(user_id)
    if current != stored:
        set_ambassador_active(user_id, current)
        return True, current
    return False, current

# --- Segmentation helpers for reminders/broadcasts ---
def get_non_ambassador_user_ids() -> list[int]:
    _ensure_ambassador_columns()
    try:
        with _db() as con:
            rows = con.execute("SELECT user_id FROM users WHERE COALESCE(ambassador_active,0)=0").fetchall()
            return [r[0] for r in rows]
    except Exception:
        return []

def get_user_ids_below_level(max_level: int) -> list[int]:
    try:
        max_level = int(max_level)
    except Exception:
        max_level = 1
    try:
        with _db() as con:
            rows = con.execute(
                """
                SELECT u.user_id
                FROM users u
                LEFT JOIN garden_levels g ON g.user_id = u.user_id
                WHERE COALESCE(g.level, 0) <= ?
                """,
                (max_level,)
            ).fetchall()
            return [r[0] for r in rows]
    except Exception:
        return []

def get_all_game_settings():
    """Отримує всі налаштування ігор"""
    with _db() as con:
        rows = con.execute("SELECT setting_key, setting_value FROM game_settings ORDER BY setting_key").fetchall()
        return {row[0]: row[1] for row in rows}

# --- Керування доступністю покупки дерев ---
def get_trees_purchase_enabled() -> bool:
    """Повертає чи дозволено покупку дерев (глобально)."""
    try:
        return get_game_setting('trees_purchase_enabled', '1') == '1'
    except Exception:
        return True

def set_trees_purchase_enabled(enabled: bool):
    """Вмикає/вимикає можливість покупки дерев (глобально)."""
    set_game_setting('trees_purchase_enabled', '1' if enabled else '0')

def is_tree_purchase_enabled(tree_type: str) -> bool:
    """Чи дозволена покупка конкретного дерева."""
    try:
        return get_game_setting(f'tree_enabled_{tree_type}', '1') == '1'
    except Exception:
        return True

def set_tree_purchase_enabled(tree_type: str, enabled: bool):
    """Увімкнути/вимкнути покупку конкретного дерева."""
    set_game_setting(f'tree_enabled_{tree_type}', '1' if enabled else '0')

def is_daily_bonus_enabled() -> bool:
    try:
        return get_game_setting('daily_bonus_enabled', '1') == '1'
    except Exception:
        return True

def set_daily_bonus_enabled(enabled: bool):
    set_game_setting('daily_bonus_enabled', '1' if enabled else '0')

def is_ref_bonus_enabled() -> bool:
    try:
        return get_game_setting('ref_bonus_enabled', '1') == '1'
    except Exception:
        return True

def set_ref_bonus_enabled(enabled: bool):
    set_game_setting('ref_bonus_enabled', '1' if enabled else '0')

def get_economy_harvest_multiplier() -> float:
    """Повертає глобальний множник врожайності для всіх дерев (0..1)."""
    try:
        return float(get_game_setting('economy_harvest_multiplier', '0.25'))
    except Exception:
        return 0.25

def set_economy_harvest_multiplier(value: float):
    """Встановлює глобальний множник врожайності (0..1)."""
    try:
        v = max(0.0, min(1.0, float(value)))
        set_game_setting('economy_harvest_multiplier', str(v))
    except Exception:
        set_game_setting('economy_harvest_multiplier', '0.25')

def are_games_enabled() -> bool:
    """Перевіряє чи увімкнені ігри"""
    return get_game_setting('games_enabled', '1') == '1'

def is_game_enabled(game_type: str) -> bool:
    """Перевіряє чи увімкнена конкретна гра"""
    return get_game_setting(f'{game_type}_enabled', '1') == '1'

def is_booster_enabled(booster_type: str) -> bool:
    """Перевіряє чи увімкнений конкретний бустер для покупки."""
    return get_game_setting(f'booster_enabled_{booster_type}', '1') == '1'

def set_booster_enabled(booster_type: str, enabled: bool):
    """Вмикає/вимикає конкретний бустер для покупки."""
    set_game_setting(f'booster_enabled_{booster_type}', '1' if enabled else '0')

def get_game_multiplier(game_type: str, subtype: str = '') -> float:
    """Отримує множник для гри"""
    if subtype:
        key = f'{game_type}_{subtype}_multiplier'
    else:
        key = f'{game_type}_multiplier'
    
    default_multipliers = {
        'dice_multiplier': '5.5',
        'coin_multiplier': '1.9',
        'number_high_multiplier': '9.0',
        'number_medium_multiplier': '3.5',
        'number_low_multiplier': '1.8',
        'slot_diamond_multiplier': '50.0',
        'slot_seven_multiplier': '25.0',
        'slot_bell_multiplier': '15.0',
        'slot_other_multiplier': '10.0'
    }
    
    return float(get_game_setting(key, default_multipliers.get(key, '1.0')))

# =============================================================================
# Кінець блоку НАЛАШТУВАННЯ ІГОР
# =============================================================================

# --- Обов'язкові канали для підписки (оновлено) ---

def get_required_channels():
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'required_channels'").fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except Exception:
                # fallback: якщо збережено як рядок через кому
                return [c.strip() for c in row[0].split(',') if c.strip()]
        # fallback: підтримка старого ключа
        row_old = con.execute("SELECT value FROM settings WHERE key = 'required_channel'").fetchone()
        if row_old and row_old[0]:
            return [row_old[0].strip()]
        return []


def mark_subscription_verified(user_id: int):
    """Позначає, що користувач підтвердив підписку та зберігає timestamp.
    Також тут можна додати бізнес-логіку на нарахування бонусу.
    """
    import time
    with _db() as con:
        try:
            # Додаємо колонку якщо її нема
            cur = con.execute("PRAGMA table_info(users)").fetchall()
            cols = [c[1] for c in cur]
            if 'subscription_verified_at' not in cols:
                try:
                    con.execute("ALTER TABLE users ADD COLUMN subscription_verified_at INTEGER DEFAULT 0")
                except Exception:
                    pass

            now = int(time.time())
            con.execute("UPDATE users SET subscription_verified_at = ? WHERE user_id = ?", (now, user_id))
            con.commit()
            print(f"[INFO] subscription_verified_at set for {user_id} at {now}")
        except Exception as e:
            print(f"[ERROR] mark_subscription_verified: {e}")

def set_required_channels(channels):
    # channels: list of usernames (без @)
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('required_channels', ?)", (json.dumps(channels),))
        con.commit()

def add_required_channel(channel):
    channels = get_required_channels()
    if channel not in channels:
        channels.append(channel)
        set_required_channels(channels)

def remove_required_channel(channel):
    channels = get_required_channels()
    channels = [c for c in channels if c != channel]
    set_required_channels(channels)

def cleanup_promo_codes():
    """Видаляє застарілі промокоди"""
    import time
    with _db() as con:
        con.execute("DELETE FROM promo_codes WHERE expiry < ?", (int(time.time()),))
        con.commit()
    
# Функції для перевірки банів та мутів
def is_user_banned_in_bot(user_id: int) -> bool:
    """Перевіряє чи заблокований користувач в боті"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT id FROM user_bans 
            WHERE user_id = ? AND ban_type = 'bot' 
            AND (end_time = 0 OR end_time > ?)
        """, (user_id, now)).fetchone()
        return row is not None

def is_user_muted_in_bot(user_id: int) -> bool:
    """Перевіряє чи замучений користувач в боті"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT id FROM user_mutes 
            WHERE user_id = ? AND mute_type = 'bot' 
            AND (end_time = 0 OR end_time > ?)
        """, (user_id, now)).fetchone()
        return row is not None

def get_user_ban_info(user_id: int):
    """Отримує інформацію про бан користувача"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT * FROM user_bans 
            WHERE user_id = ? AND ban_type = 'bot' 
            AND (end_time = 0 OR end_time > ?)
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, now)).fetchone()
        return row

def get_user_mute_info(user_id: int):
    """Отримує інформацію про мут користувача"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT * FROM user_mutes 
            WHERE user_id = ? AND mute_type = 'bot' 
            AND (end_time = 0 OR end_time > ?)
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, now)).fetchone()
        return row

def unban_user_in_bot(user_id: int):
    """Розбанує користувача в боті"""
    import time
    with _db() as con:
        con.execute("""
            UPDATE user_bans 
            SET end_time = ? 
            WHERE user_id = ? AND ban_type = 'bot' AND (end_time = 0 OR end_time > ?)
        """, (int(time.time()), user_id, int(time.time())))
        con.commit()
        
def unmute_user_in_bot(user_id: int):
    """Розмучує користувача в боті"""
    import time
    with _db() as con:
        con.execute("""
            UPDATE user_mutes 
            SET end_time = ? 
            WHERE user_id = ? AND mute_type = 'bot' AND (end_time = 0 OR end_time > ?)
        """, (int(time.time()), user_id, int(time.time())))
        con.commit()

# Функції для роботи зі станами користувачів
def set_user_state(user_id: int, state: str):
    """Встановлює стан користувача"""
    print(f"[DEBUG] set_user_state: встановлюємо стан '{state}' для користувача {user_id}")
    with _db() as con:
        # Створюємо таблицю якщо її немає
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        if state is None:
            # Видаляємо стан
            print(f"[DEBUG] set_user_state: видаляємо стан для користувача {user_id}")
            con.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        else:
            # Встановлюємо або оновлюємо стан
            import time
            print(f"[DEBUG] set_user_state: встановлюємо стан '{state}' для користувача {user_id}")
            con.execute("""
                INSERT OR REPLACE INTO user_states (user_id, state, updated_at)
                VALUES (?, ?, ?)
            """, (user_id, state, int(time.time())))
        
        con.commit()
        print(f"[DEBUG] set_user_state: стан успішно встановлено")

def get_user_state(user_id: int) -> str:
    """Отримує стан користувача"""
    with _db() as con:
        # Створюємо таблицю якщо її немає
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        
        row = con.execute("SELECT state FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
        result = row[0] if row else ""
        print(f"[DEBUG] get_user_state: для користувача {user_id} стан: '{result}'")
        return result

def clear_user_state(user_id: int):
    """Очищує стан користувача"""
    print(f"[DEBUG] clear_user_state: очищуємо стан для користувача {user_id}")
    set_user_state(user_id, None)

def mute_user_in_chat(user_id: int, chat_id: int, duration_seconds: int, reason: str, muted_by: int):
    """Мутить користувача в чаті"""
    import time
    with _db() as con:
        end_time = int(time.time()) + duration_seconds if duration_seconds else 0
        con.execute("""
            INSERT OR REPLACE INTO user_mutes 
            (user_id, chat_id, mute_type, duration_seconds, end_time, reason, muted_by, created_at)
            VALUES (?, ?, 'chat', ?, ?, ?, ?, ?)
        """, (user_id, chat_id, duration_seconds, end_time, reason, muted_by, int(time.time())))
        con.commit()
        return {'success': True, 'duration_text': format_duration(duration_seconds), 'date': time.strftime("%d.%m.%Y %H:%M")}

def is_user_muted_in_chat(user_id: int, chat_id: int) -> bool:
    """Перевіряє чи замучений користувач в чаті"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT id FROM user_mutes 
            WHERE user_id = ? AND chat_id = ? AND mute_type = 'chat' 
            AND (end_time = 0 OR end_time > ?)
        """, (user_id, chat_id, now)).fetchone()
        return row is not None

def get_user_chat_mute_info(user_id: int, chat_id: int):
    """Отримує інформацію про мут користувача в чаті"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT * FROM user_mutes 
            WHERE user_id = ? AND chat_id = ? AND mute_type = 'chat' 
            AND (end_time = 0 OR end_time > ?)
            ORDER BY created_at DESC LIMIT 1
        """, (user_id, chat_id, now)).fetchone()
        return row

def unmute_user_in_chat(user_id: int, chat_id: int):
    """Розмучує користувача в чаті"""
    import time
    with _db() as con:
        con.execute("""
            UPDATE user_mutes 
            SET end_time = ? 
            WHERE user_id = ? AND chat_id = ? AND mute_type = 'chat' AND (end_time = 0 OR end_time > ?)
        """, (int(time.time()), user_id, chat_id, int(time.time())))
        con.commit()

def ban_user_in_chat(user_id: int, chat_id: int, duration_seconds: int, reason: str, banned_by: int):
    """Банить користувача в чаті"""
    import time
    with _db() as con:
        end_time = int(time.time()) + duration_seconds if duration_seconds else 0
        con.execute("""
            INSERT OR REPLACE INTO user_bans 
            (user_id, chat_id, ban_type, duration_seconds, end_time, reason, banned_by, created_at)
            VALUES (?, ?, 'chat', ?, ?, ?, ?, ?)
        """, (user_id, chat_id, duration_seconds, end_time, reason, banned_by, int(time.time())))
        con.commit()
        return {'success': True, 'duration_text': format_duration(duration_seconds), 'date': time.strftime("%d.%m.%Y %H:%M")}

def is_user_banned_in_chat(user_id: int, chat_id: int) -> bool:
    """Перевіряє чи заблокований користувач в чаті"""
    import time
    with _db() as con:
        now = int(time.time())
        row = con.execute("""
            SELECT id FROM user_bans 
            WHERE user_id = ? AND chat_id = ? AND ban_type = 'chat' 
            AND (end_time = 0 OR end_time > ?)
        """, (user_id, chat_id, now)).fetchone()
        return row is not None

def unban_user_in_chat(user_id: int, chat_id: int):
    """Розбанує користувача в чаті"""
    import time
    with _db() as con:
        con.execute("""
            UPDATE user_bans 
            SET end_time = ? 
            WHERE user_id = ? AND chat_id = ? AND ban_type = 'chat' AND (end_time = 0 OR end_time > ?)
        """, (int(time.time()), user_id, chat_id, int(time.time())))
        con.commit()

def update_user_activity(user_id: int):
    """Примусово оновлює активність користувача"""
    import time
    with _db() as con:
        now = int(time.time())
        con.execute("UPDATE users SET last_active = ? WHERE user_id = ?", (now, user_id))
        con.commit()
        print(f"[DEBUG] Оновлено активність користувача {user_id}: {now}")

def get_inactive_beta_testers(hours_threshold=24):
    """Повертає список неактивних бета-тестерів за останні N годин"""
    import time
    current_time = int(time.time())
    threshold_time = current_time - (hours_threshold * 3600)  # N годин у секундах
    
    with _db() as con:
        query = """
        SELECT 
            bt.user_id, 
            bt.added_by, 
            bt.added_at,
            u.user_name,
            u.username,
            u.last_active,
            u.date_joined
        FROM beta_testers bt
        LEFT JOIN users u ON bt.user_id = u.user_id
        WHERE u.last_active IS NOT NULL 
        AND u.last_active < ?
        AND bt.added_at < ?  -- Додано більше N годин тому
        ORDER BY u.last_active ASC
        """
        rows = con.execute(query, (threshold_time, threshold_time)).fetchall()
        
        # Додаємо логування для діагностики
        print(f"[DEBUG] Пошук неактивних бета-тестерів:")
        print(f"[DEBUG] Поточний час: {current_time}")
        print(f"[DEBUG] Поріг активності: {threshold_time}")
        print(f"[DEBUG] Знайдено неактивних: {len(rows)}")
        
        # Показуємо деталі для перших 5 користувачів
        for i, row in enumerate(rows[:5]):
            user_id, added_by, added_at, user_name, username, last_active, date_joined = row
            print(f"[DEBUG] Користувач {i+1}: ID={user_id}, Ім'я={user_name}, Остання активність={last_active}, Додано={added_at}")
        
        return rows

def cleanup_inactive_beta_testers():
    """Видаляє бета-тестерів, які ніколи не взаємодіяли з ботом"""
    with _db() as con:
        # Знаходимо бета-тестерів без активності
        query = """
        SELECT bt.user_id, u.user_name
        FROM beta_testers bt
        LEFT JOIN users u ON bt.user_id = u.user_id
        WHERE u.last_active IS NULL
        """
        inactive_users = con.execute(query).fetchall()
        
        if inactive_users:
            print(f"[DEBUG] Знайдено {len(inactive_users)} бета-тестерів без активності:")
            for user_id, user_name in inactive_users:
                print(f"[DEBUG] Видаляємо: ID={user_id}, Ім'я={user_name}")
                con.execute("DELETE FROM beta_testers WHERE user_id = ?", (user_id,))
            
            con.commit()
            print(f"[DEBUG] Видалено {len(inactive_users)} неактивних бета-тестерів")
            return len(inactive_users)
        else:
            print("[DEBUG] Неактивних бета-тестерів не знайдено")
            return 0

def get_watering_settings():
    """Повертає налаштування системи поливу"""
    with _db() as con:
        settings = {}
        rows = con.execute("SELECT key, value FROM watering_settings").fetchall()
        for key, value in rows:
            settings[key] = int(value)
        return settings

def ensure_watering_system():
    """Створює таблиці для системи поливу дерев та квестів"""
    with _db() as con:
        # Міграція: додаємо колонку tree_type якщо її немає
        try:
            con.execute("ALTER TABLE tree_watering ADD COLUMN tree_type TEXT")
            print("[MIGRATION] Додано колонку tree_type до таблиці tree_watering")
        except:
            # Колонка вже існує
            pass
        
        # Таблиця для поливу дерев
        con.execute("""
            CREATE TABLE IF NOT EXISTS tree_watering (
                user_id INTEGER,
                tree_type TEXT,
                last_watered INTEGER,
                water_level INTEGER DEFAULT 100,
                is_withered INTEGER DEFAULT 0,
                created_at INTEGER,
                PRIMARY KEY (user_id, tree_type)
            )
        """)
        
        # Таблиця для налаштувань поливу
        con.execute("""
            CREATE TABLE IF NOT EXISTS watering_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Таблиця активних квестів
        con.execute("""
            CREATE TABLE IF NOT EXISTS active_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fruit_type TEXT,
                amount INTEGER,
                start_time INTEGER,
                end_time INTEGER,
                status TEXT DEFAULT 'waiting',
                winner_id INTEGER,
                winner_username TEXT,
                winner_time INTEGER,
                chat_id INTEGER,
                warning_sent INTEGER DEFAULT 0,
                drop_sent INTEGER DEFAULT 0,
                warning_message_id INTEGER DEFAULT NULL
            )
        """)
        
        # Додаємо поля якщо їх немає
        try:
            con.execute("ALTER TABLE active_quests ADD COLUMN warning_message_id INTEGER DEFAULT NULL")
        except sqlite3.OperationalError:
            # Поле вже існує
            pass
            
        try:
            con.execute("ALTER TABLE active_quests ADD COLUMN winner_username TEXT")
        except sqlite3.OperationalError:
            # Поле вже існує
            pass
            
        try:
            con.execute("ALTER TABLE active_quests ADD COLUMN winner_time INTEGER")
        except sqlite3.OperationalError:
            # Поле вже існує
            pass
        
        # Таблиця історії квестів
        con.execute("""
            CREATE TABLE IF NOT EXISTS quest_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_id INTEGER,
                fruit_type TEXT,
                amount INTEGER,
                winner_id INTEGER,
                winner_username TEXT,
                start_time INTEGER,
                end_time INTEGER,
                chat_id INTEGER
            )
        """)
        
        # Встановлюємо налаштування за замовчуванням
        con.execute("INSERT OR IGNORE INTO watering_settings (key, value) VALUES ('watering_interval', '900')")  # 15 хвилин
        con.execute("INSERT OR IGNORE INTO watering_settings (key, value) VALUES ('water_decrease_rate', '10')")  # 10% за інтервал
        con.execute("INSERT OR IGNORE INTO watering_settings (key, value) VALUES ('wither_threshold', '57600')")  # 16 годин
        con.execute("INSERT OR IGNORE INTO watering_settings (key, value) VALUES ('water_restore_amount', '100')")  # 100% при поливі
        
        con.commit()

def set_watering_setting(key, value):
    """Встановлює налаштування системи поливу"""
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO watering_settings (key, value) VALUES (?, ?)", (key, str(value)))
        con.commit()

def get_tree_watering_status(user_id, tree_type):
    """Повертає статус поливу для конкретного типу дерева"""
    import time
    with _db() as con:
        current_time = int(time.time())
        
        # Отримуємо запис про полив
        row = con.execute("""
            SELECT last_watered, water_level, is_withered 
            FROM tree_watering 
            WHERE user_id = ? AND tree_type = ?
        """, (user_id, tree_type)).fetchone()
        
        if not row:
            # Створюємо новий запис
            con.execute("""
                INSERT INTO tree_watering 
                (user_id, tree_type, last_watered, water_level, is_withered, created_at) 
                VALUES (?, ?, ?, 100, 0, ?)
            """, (user_id, tree_type, None, current_time))
            con.commit()
            last_watered = None
            water_level = 100
            is_withered = 0
        else:
            last_watered, water_level, is_withered = row
        
        # Отримуємо налаштування
        settings = get_watering_settings()
        # Переводимо систему поливу на модель «зборів»: 1 полив ≈ 2-3 збори
        # Тут таймери залишаємо як фолбек, але рівень води не зменшуємо часом
        watering_interval = settings.get('watering_interval', 3600)  # 1 година (не критично)
        water_decrease_rate = settings.get('water_decrease_rate', 50)  # використовуватимемо при фактичному зборі
        wither_threshold = settings.get('wither_threshold', 172800)  # 48 годин
        
        time_passed = 0
        intervals_passed = 0
        current_water_level = float(water_level or 0)
        current_withered = int(is_withered or 0)
        
        # Розраховуємо поточний рівень води
        if last_watered:
            time_passed = current_time - last_watered
            intervals_passed = time_passed // watering_interval
            
            if intervals_passed > 0:
                # У цій моделі час не зменшує воду між зборами
                # Перевіряємо чи дерево завяло
                if time_passed > wither_threshold:
                    current_withered = 1
                
                # Оновлюємо в базі
                con.execute("""
                    UPDATE tree_watering 
                    SET water_level = ?, is_withered = ? 
                    WHERE user_id = ? AND tree_type = ?
                """, (current_water_level, current_withered, user_id, tree_type))
                con.commit()
        else:
            time_passed = 0
            intervals_passed = 0
        
        next_allowed_at = None
        seconds_until_next = 0
        can_water_now = True
        if last_watered:
            next_allowed_at = last_watered + watering_interval
            seconds_until_next = max(0, next_allowed_at - current_time)
            can_water_now = seconds_until_next <= 0
        
        return {
            'water_level': current_water_level,
            'is_withered': bool(current_withered),
            'last_watered': last_watered,
            'time_passed': time_passed,
            'intervals_passed': intervals_passed,
            'next_water_allowed_at': next_allowed_at,
            'seconds_until_next_water': seconds_until_next,
            'can_water_now': can_water_now,
            'watering_interval': watering_interval,
            'wither_threshold': wither_threshold,
            'water_restore_amount': settings.get('water_restore_amount', 100)
        }

def water_tree(user_id, tree_type):
    """Поливає дерево"""
    import time
    try:
        with _db() as con:
            current_time = int(time.time())
            settings = get_watering_settings()
            watering_interval = settings.get('watering_interval', 900)  # 15 хвилин
            
            # Перевіряємо чи дерева вже политі
            row = con.execute("""
                SELECT last_watered, water_level 
                FROM tree_watering 
                WHERE user_id = ? AND tree_type = ?
            """, (user_id, tree_type)).fetchone()
            
            if row:
                last_watered, water_level = row
                if last_watered:
                    time_since_watering = current_time - last_watered
                    # Якщо пройшло менше інтервалу та вода ще повна — вважаємо політым
                    if time_since_watering < watering_interval and water_level >= 100:
                        remaining_time = watering_interval - time_since_watering
                        minutes = remaining_time // 60
                        seconds = remaining_time % 60
                        if minutes > 0:
                            time_text = f"{minutes} хв {seconds} сек"
                        else:
                            time_text = f"{seconds} сек"
                        return False, f"🌱 Дерева типу '{tree_type}' вже политі! Спробуйте через {time_text}."
            
            water_restore_amount = settings.get('water_restore_amount', 100)
            
            # Оновлюємо або створюємо запис
            con.execute("""
                INSERT OR REPLACE INTO tree_watering 
                (user_id, tree_type, last_watered, water_level, is_withered, created_at) 
                VALUES (?, ?, ?, ?, 0, ?)
            """, (user_id, tree_type, current_time, water_restore_amount, current_time))
            
            con.commit()
            
            # Не скидаємо прогрес росту при поливі — збереження поточного прогресу

            # Додаємо запис про полив в історію саду (окремо, щоб не блокувати основну транзакцію)
            try:
                from garden_models import get_tree_name_uk
                tree_name = get_tree_name_uk(tree_type)
                add_garden_transaction(
                    user_id=user_id,
                    type="watering",
                    amount=1,
                    currency="",
                    timestamp=current_time,
                    comment=f"Полив дерев: {tree_name}"
                )
            except Exception as e:
                print(f"Помилка додавання транзакції поливу: {e}")
                # Продовжуємо навіть якщо не вдалося додати транзакцію
            
            return True, f"💧 Дерева типу '{tree_type}' успішно политі!"
            
    except Exception as e:
        print(f"Помилка в water_tree: {e}")
        return False, f"❌ Помилка поливу дерева: {str(e)}"

def get_user_trees_with_watering(user_id):
    """Повертає дерева користувача з інформацією про полив"""
    with _db() as con:
        # Отримуємо всі дерева користувача
        trees = con.execute("""
            SELECT type, COUNT(*) as count
            FROM trees
            WHERE user_id = ?
            GROUP BY type
        """, (user_id,)).fetchall()
        
        result = []
        for tree_type, count in trees:
            # Отримуємо статус поливу для цього типу дерев
            watering_status = get_tree_watering_status(user_id, tree_type)
            
            result.append({
                'tree_type': tree_type,
                'count': count,
                'watering_status': watering_status
            })
        
        return result

def harvest_user_garden(user_id: int):
    """Збирає врожай з усіх дерев користувача та повертає деталі."""
    import time
    now = int(time.time())
    
    with _db() as con:
        tree_rows = con.execute(
            "SELECT id, type, last_harvest FROM trees WHERE user_id=?",
            (user_id,)
        ).fetchall()
    
    if not tree_rows:
        return {
            'success': False,
            'message': '🌱 У вас ще немає дерев для збору.',
            'harvested': [],
            'skipped': []
        }
    
    try:
        from garden_models import (
            TREE_TYPES,
            FRUITS,
            get_tree_name_uk,
            get_fruit_name_uk,
            get_effective_tree_income
        )
    except ImportError:
        TREE_TYPES = []
        FRUITS = []
        def get_tree_name_uk(code):  # type: ignore
            return code
        def get_fruit_name_uk(code):  # type: ignore
            return code
        def get_effective_tree_income(*_, **__):  # type: ignore
            return 1.0
    
    tree_meta = {t['type']: t for t in TREE_TYPES}
    fruit_meta = {f['type']: f for f in FRUITS}
    
    econ_multiplier = get_economy_harvest_multiplier()
    garden_level = get_user_garden_level(user_id)
    level_info = get_garden_level_info(garden_level)
    bonus_multiplier = 1 + ((level_info.get('bonus_percent', 0) / 100) if level_info else 0)
    
    harvested = {}
    trees_participated = {}
    water_after = {}
    skipped = []
    
    min_growth_seconds = 900  # 15 хвилин
    settings = get_watering_settings()
    water_decrease = float(settings.get('water_decrease_rate', 35))
    
    with _db() as con:
        for tree_id, tree_type, last_harvest in tree_rows:
            meta = tree_meta.get(tree_type)
            if not meta:
                continue
            
            row = con.execute(
                "SELECT water_level, is_withered FROM tree_watering WHERE user_id=? AND tree_type=?",
                (user_id, tree_type)
            ).fetchone()
            
            if not row:
                water_level = 100.0
                is_withered = 0
                con.execute(
                    "INSERT INTO tree_watering (user_id, tree_type, water_level, is_withered, created_at) VALUES (?, ?, ?, 0, ?)",
                    (user_id, tree_type, water_level, now)
                )
            else:
                water_level = float(row[0] or 0)
                is_withered = int(row[1] or 0)
            
            tree_name = get_tree_name_uk(tree_type)
            
            if is_withered:
                skipped.append({'tree_type': tree_type, 'tree_name': tree_name, 'reason': 'withered'})
                continue
            
            if water_level <= 5:
                skipped.append({'tree_type': tree_type, 'tree_name': tree_name, 'reason': 'dry'})
                continue
            
            last_ts = int(last_harvest or (now - min_growth_seconds))
            growth_seconds = max(0, now - last_ts)
            if growth_seconds < min_growth_seconds:
                continue
            
            income_per_hour = get_effective_tree_income(tree_type, econ_multiplier) * bonus_multiplier
            produced = (growth_seconds / 3600.0) * income_per_hour
            if produced <= 0:
                continue
            
            fruit_type = meta.get('fruit', tree_type)
            harvested[fruit_type] = harvested.get(fruit_type, 0.0) + produced
            trees_participated[tree_type] = trees_participated.get(tree_type, 0) + 1
            
            con.execute("UPDATE trees SET last_harvest=? WHERE id=?", (now, tree_id))
            
            new_water_level = max(0.0, water_level - water_decrease)
            is_withered_after = 1 if new_water_level <= 0 else 0
            con.execute(
                "UPDATE tree_watering SET water_level=?, is_withered=? WHERE user_id=? AND tree_type=?",
                (new_water_level, is_withered_after, user_id, tree_type)
            )
            water_after[tree_type] = new_water_level
        
        con.commit()
    
    if not harvested:
        return {
            'success': False,
            'message': '⏳ Ще зарано для збору. Дайте деревам трохи часу та перевірте полив.',
            'harvested': [],
            'skipped': skipped,
            'water_after': {k: round_float(v) for k, v in water_after.items()}
        }
    
    harvested_list = []
    total_amount = 0.0
    
    for fruit_type, amount in harvested.items():
        rounded_amount = round_float(amount)
        total_amount += rounded_amount
        fruit_info = fruit_meta.get(fruit_type, {})
        trees_for_fruit = sum(
            count for tree_code, count in trees_participated.items()
            if (tree_meta.get(tree_code, {}).get('fruit', tree_code) == fruit_type)
        )
        
        harvested_list.append({
            'fruit_type': fruit_type,
            'fruit_name': fruit_info.get('name', get_fruit_name_uk(fruit_type)),
            'emoji': fruit_info.get('emoji', '🍎'),
            'amount': rounded_amount,
            'trees': trees_for_fruit
        })
        
        add_fruit(user_id, fruit_type, rounded_amount)
        add_garden_transaction(
            user_id=user_id,
            type="harvest",
            amount=rounded_amount,
            currency="FRUIT",
            timestamp=now,
            comment=f"Збір {fruit_info.get('name', get_fruit_name_uk(fruit_type))}"
        )
    
    try:
        check_harvest_tasks(user_id)
    except Exception as exc:
        print(f"[garden] Не вдалося оновити завдання збору: {exc}")
    
    return {
        'success': True,
        'message': f'🎉 Зібрано {len(harvested_list)} вид(и) фруктів',
        'harvested': harvested_list,
        'skipped': skipped,
        'water_after': {k: round_float(v) for k, v in water_after.items()},
        'total_amount': round_float(total_amount)
    }

def check_and_remove_withered_trees(user_id):
    """Перевіряє і видаляє завялі дерева"""
    import time
    with _db() as con:
        # Знаходимо завялі дерева
        withered_trees = con.execute("""
            SELECT tree_type 
            FROM tree_watering 
            WHERE user_id = ? AND is_withered = 1
        """, (user_id,)).fetchall()
        
        removed_count = 0
        for (tree_type,) in withered_trees:
            # Видаляємо одне дерево (перше знайдене)
            con.execute("""
                DELETE FROM trees 
                WHERE user_id = ? AND type = ? 
                AND rowid = (SELECT MIN(rowid) FROM trees WHERE user_id = ? AND type = ?)
            """, (user_id, tree_type, user_id, tree_type))
            # Видаляємо запис про полив
            con.execute("DELETE FROM tree_watering WHERE user_id = ? AND tree_type = ?", (user_id, tree_type))
            removed_count += 1
        
        con.commit()
        return removed_count

# === СИСТЕМА КВЕСТІВ ===

def create_fruit_quest(fruit_type: str, amount: int, chat_id: int, wait_time: int = 180):
    """Створює новий квест з падаючими фруктами"""
    import time
    current_time = int(time.time())
    created_time = current_time
    activation_time = current_time + wait_time  # Час коли квест стане активним
    end_time = activation_time + 300  # 5 хвилин на ловлю
    
    with _db() as con:
        # Перевіряємо чи немає вже активного квесту
        active_quest = con.execute("""
            SELECT id FROM active_quests 
            WHERE chat_id = ? AND status IN ('waiting', 'active')
        """, (chat_id,)).fetchone()
        
        if active_quest:
            # Замість повернення помилки, автоматично очищаємо старий квест
            con.execute("""
                DELETE FROM active_quests 
                WHERE chat_id = ? AND status IN ('waiting', 'active')
            """, (chat_id,))
            print(f"[DEBUG] Автоматично очищено старий квест для чату {chat_id}")
        
        # Створюємо новий квест
        cursor = con.execute("""
            INSERT INTO active_quests 
            (fruit_type, amount, created_time, activation_time, end_time, chat_id, status) 
            VALUES (?, ?, ?, ?, ?, ?, 'waiting')
        """, (fruit_type, amount, created_time, activation_time, end_time, chat_id))
        
        quest_id = cursor.lastrowid
        con.commit()
        
        return True, quest_id

def get_active_quest(chat_id: int):
    """Отримує активний квест для чату"""
    with _db() as con:
        quest = con.execute("""
            SELECT id, fruit_type, amount, start_time, end_time, status, winner_id
            FROM active_quests 
            WHERE chat_id = ? AND status IN ('waiting', 'active')
            ORDER BY id DESC LIMIT 1
        """, (chat_id,)).fetchone()
        
        return quest

def update_quest_status(quest_id: int, status: str, winner_id: int = None):
    """Оновлює статус квесту"""
    with _db() as con:
        if winner_id:
            con.execute("""
                UPDATE active_quests 
                SET status = ?, winner_id = ? 
                WHERE id = ?
            """, (status, winner_id, quest_id))
        else:
            con.execute("""
                UPDATE active_quests 
                SET status = ? 
                WHERE id = ?
            """, (status, quest_id))
        con.commit()

def mark_quest_warning_sent(quest_id: int):
    """Позначає що попередження квесту вже відправлено"""
    with _db() as con:
        con.execute("""
            UPDATE active_quests 
            SET warning_sent = 1 
            WHERE id = ?
        """, (quest_id,))
        con.commit()

def mark_quest_drop_sent(quest_id: int):
    """Позначає що повідомлення про падіння фрукту вже відправлено та встановлює start_time"""
    import time
    current_time = int(time.time())
    with _db() as con:
        con.execute("""
            UPDATE active_quests 
            SET drop_sent = 1, start_time = ?
            WHERE id = ?
        """, (current_time, quest_id))
        con.commit()

def save_warning_message_id(quest_id: int, message_id: int):
    """Зберігає ID повідомлення про попередження"""
    with _db() as con:
        con.execute("UPDATE active_quests SET warning_message_id = ? WHERE id = ?", (message_id, quest_id))
        con.commit()

def get_warning_message_id(quest_id: int) -> int:
    """Отримує ID повідомлення про попередження"""
    with _db() as con:
        row = con.execute("SELECT warning_message_id FROM active_quests WHERE id = ?", (quest_id,)).fetchone()
        return row[0] if row and row[0] else None

def get_quests_for_countdown():
    """Отримує квести які потребують оновлення відліку"""
    import time
    current_time = int(time.time())
    
    with _db() as con:
        quests = con.execute("""
            SELECT id, fruit_type, amount, activation_time, chat_id, warning_message_id
            FROM active_quests 
            WHERE status = 'waiting' 
            AND warning_message_id IS NOT NULL
            AND activation_time IS NOT NULL
            AND activation_time > ?
        """, (current_time,)).fetchall()
        
        return quests

def catch_fruit_quest(quest_id: int, user_id: int, username: str):
    """Обробляє ловлю фрукту в квесті"""
    import time
    current_time = int(time.time())
    
    with _db() as con:
        # Отримуємо інформацію про квест
        quest = con.execute("""
            SELECT fruit_type, amount, status, winner_id, end_time, start_time, chat_id
            FROM active_quests 
            WHERE id = ?
        """, (quest_id,)).fetchone()
        
        if not quest:
            return False, "❌ Квест не знайдено!"
        
        fruit_type, amount, status, winner_id, end_time, start_time, chat_id = quest
        
        if status != 'active':
            return False, "❌ Квест не активний!"
        
        if winner_id:
            return False, "❌ Фрукт вже зловлений!"
        
        # Перевіряємо чи не закінчився час
        if end_time and current_time > end_time:
            con.execute("UPDATE active_quests SET status = 'expired' WHERE id = ?", (quest_id,))
            con.commit()
            return False, "❌ Час квесту закінчився!"
        
        # Встановлюємо переможця
        con.execute("""
            UPDATE active_quests 
            SET status = 'completed', winner_id = ?, winner_username = ?, winner_time = ?
            WHERE id = ?
        """, (user_id, username, current_time, quest_id))
        
        # Додаємо фрукти переможцю
        add_fruit(user_id, fruit_type, amount)
        
        # Додаємо в історію
        con.execute("""
            INSERT INTO quest_history 
            (quest_id, fruit_type, amount, winner_id, winner_username, start_time, end_time, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (quest_id, fruit_type, amount, user_id, username, start_time, current_time, chat_id))
        
        # Додаємо статистику
        reaction_time = current_time - start_time
        print(f"[DEBUG] Додаємо статистику: user_id={user_id}, username={username}, fruit_type={fruit_type}, amount={amount}, reaction_time={reaction_time}")
        add_quest_statistics(user_id, username, fruit_type, amount, reaction_time)
        print(f"[DEBUG] Статистика додана успішно")
        
        con.commit()
        
        return True, f"🏆 Вітаємо! Ви зловили {amount} {fruit_type}! Ви перший!"

def get_quests_to_process():
    """Отримує квести які потрібно обробити (відправити попередження або падіння)"""
    import time
    current_time = int(time.time())
    
    with _db() as con:
        # Квести які потребують попередження (за 1 хвилину до запуску)
        warning_quests = con.execute("""
            SELECT id, fruit_type, amount, activation_time, chat_id
            FROM active_quests 
            WHERE status = 'waiting' 
            AND (warning_sent = 0 OR warning_sent IS NULL)
            AND activation_time IS NOT NULL
            AND activation_time <= ? + 60
            AND activation_time > ?
        """, (current_time, current_time)).fetchall()
        
        # Квести які потребують падіння фрукту (час запуску настав)
        drop_quests = con.execute("""
            SELECT id, fruit_type, amount, activation_time, chat_id
            FROM active_quests 
            WHERE status = 'waiting' 
            AND (drop_sent = 0 OR drop_sent IS NULL)
            AND activation_time IS NOT NULL
            AND activation_time <= ?
        """, (current_time,)).fetchall()
        
        # Убрали debug сообщения - они вызываются слишком часто (каждые 5 секунд)
        # Логируем только если есть квесты для обработки
        # if warning_quests or drop_quests:
        #     print(f"[DEBUG] get_quests_to_process: знайдено {len(warning_quests)} попереджень, {len(drop_quests)} падінь")
        
        return warning_quests, drop_quests

def cleanup_expired_quests():
    """Очищує закінчені квести"""
    import time
    current_time = int(time.time())
    
    with _db() as con:
        # Знаходимо закінчені квести
        expired_quests = con.execute("""
            SELECT id, chat_id
            FROM active_quests 
            WHERE status = 'active' 
            AND end_time < ?
        """, (current_time,)).fetchall()
        
        # Позначаємо їх як закінчені
        for quest_id, chat_id in expired_quests:
            con.execute("""
                UPDATE active_quests 
                SET status = 'expired' 
                WHERE id = ?
            """, (quest_id,))
        
        # Додатково очищаємо зависли квести (старіше 10 хвилин)
        stuck_quests = con.execute("""
            SELECT id, chat_id
            FROM active_quests 
            WHERE status = 'waiting' 
            AND start_time < ? - 600
        """, (current_time,)).fetchall()
        
        for quest_id, chat_id in stuck_quests:
            con.execute("""
                DELETE FROM active_quests 
                WHERE id = ?
            """, (quest_id,))
            print(f"[DEBUG] Очищено завислий квест {quest_id} для чату {chat_id}")
        
        con.commit()
        return len(expired_quests) + len(stuck_quests)

def force_clear_chat_quests(chat_id: int):
    """Примусово очищає всі квести для конкретного чату"""
    with _db() as con:
        deleted_count = con.execute("""
            DELETE FROM active_quests 
            WHERE chat_id = ?
        """, (chat_id,)).rowcount
        
        con.commit()
        return deleted_count

def get_quest_statistics(chat_id: int = None, days: int = 7):
    """Отримує статистику квестів"""
    import time
    current_time = int(time.time())
    start_time = current_time - (days * 24 * 3600)
    
    with _db() as con:
        if chat_id:
            # Статистика для конкретного чату
            stats = con.execute("""
                SELECT 
                    COUNT(*) as total_quests,
                    SUM(CASE WHEN winner_id IS NOT NULL THEN 1 ELSE 0 END) as completed_quests,
                    SUM(amount) as total_fruits_given,
                    fruit_type,
                    COUNT(*) as quests_by_fruit
                FROM quest_history 
                WHERE chat_id = ? AND start_time >= ?
                GROUP BY fruit_type
                ORDER BY quests_by_fruit DESC
            """, (chat_id, start_time)).fetchall()
        else:
            # Загальна статистика
            stats = con.execute("""
                SELECT 
                    COUNT(*) as total_quests,
                    SUM(CASE WHEN winner_id IS NOT NULL THEN 1 ELSE 0 END) as completed_quests,
                    SUM(amount) as total_fruits_given,
                    fruit_type,
                    COUNT(*) as quests_by_fruit
                FROM quest_history 
                WHERE start_time >= ?
                GROUP BY fruit_type
                ORDER BY quests_by_fruit DESC
            """, (start_time,)).fetchall()
        
        return stats

def get_top_quest_winners(chat_id: int = None, limit: int = 10):
    """Отримує топ переможців квестів"""
    try:
        print(f"[DEBUG] get_top_quest_winners: chat_id={chat_id}, limit={limit}")
        
        with _db() as con:
            if chat_id:
                print(f"[DEBUG] Шукаємо переможців для чату {chat_id}")
                winners = con.execute("""
                    SELECT 
                        winner_id,
                        winner_username,
                        COUNT(*) as wins,
                        SUM(amount) as total_fruits
                    FROM quest_history 
                    WHERE chat_id = ? AND winner_id IS NOT NULL
                    GROUP BY winner_id, winner_username
                    ORDER BY wins DESC, total_fruits DESC
                    LIMIT ?
                """, (chat_id, limit)).fetchall()
            else:
                print(f"[DEBUG] Шукаємо загальних переможців")
                winners = con.execute("""
                    SELECT 
                        winner_id,
                        winner_username,
                        COUNT(*) as wins,
                        SUM(amount) as total_fruits
                    FROM quest_history 
                    WHERE winner_id IS NOT NULL
                    GROUP BY winner_id, winner_username
                    ORDER BY wins DESC, total_fruits DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            
            print(f"[DEBUG] Знайдено {len(winners)} переможців")
            return winners
    except Exception as e:
        print(f"[DEBUG] Помилка в get_top_quest_winners: {e}")
        return []

# --- Система чатів для квестів ---
def ensure_quest_chats_table():
    """Створює таблицю для чатів квестів"""
    with _db() as con:
        # Міграція: додаємо таблицю quest_chats якщо її немає
        con.execute("""
            CREATE TABLE IF NOT EXISTS quest_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT,
                added_by INTEGER,
                added_at INTEGER
            )
        """)
        
        con.commit()

ensure_quest_chats_table()

def add_quest_chat(chat_id, chat_title, added_by):
    import time
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO quest_chats (chat_id, chat_title, added_by, added_at) VALUES (?, ?, ?, ?)", 
                   (chat_id, chat_title, added_by, int(time.time())))
        con.commit()

def remove_quest_chat(chat_id):
    with _db() as con:
        con.execute("DELETE FROM quest_chats WHERE chat_id = ?", (chat_id,))
        con.commit()

def is_quest_chat(chat_id):
    with _db() as con:
        row = con.execute("SELECT 1 FROM quest_chats WHERE chat_id = ?", (chat_id,)).fetchone()
        return row is not None

def get_quest_chats():
    with _db() as con:
        rows = con.execute("SELECT chat_id, chat_title, added_by, added_at FROM quest_chats").fetchall()
        return rows

# --- Система статистики квестів ---
def ensure_quest_statistics_table():
    """Створює таблицю для статистики квестів"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS quest_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                fruit_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                reaction_time INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)
        con.commit()

def add_quest_statistics(user_id: int, username: str, fruit_type: str, amount: int, reaction_time: int):
    """Додає статистику квесту"""
    import time
    try:
        with _db() as con:
            con.execute("""
                INSERT INTO quest_statistics (user_id, username, fruit_type, amount, reaction_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, fruit_type, amount, reaction_time, int(time.time())))
            con.commit()
            print(f"[DEBUG] Статистика збережена в БД: user_id={user_id}, username={username}")
    except Exception as e:
        print(f"[DEBUG] Помилка збереження статистики: {e}")
        raise

def get_quest_top(limit: int = 10):
    """Отримує топ гравців квестів"""
    try:
        with _db() as con:
            print(f"[DEBUG] Отримуємо топ квестів, ліміт: {limit}")
            
            # Топ за кількістю виграних квестів
            top_winners = con.execute("""
                SELECT user_id, username, COUNT(*) as wins, SUM(amount) as total_fruits
                FROM quest_statistics 
                GROUP BY user_id, username
                ORDER BY wins DESC, total_fruits DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            print(f"[DEBUG] Топ переможців отримано: {len(top_winners)} записів")
            
            # Топ за швидкістю реакції
            top_speed = con.execute("""
                SELECT user_id, username, fruit_type, amount, reaction_time, created_at
                FROM quest_statistics 
                WHERE reaction_time > 0
                ORDER BY reaction_time ASC
                LIMIT ?
            """, (limit,)).fetchall()
            
            print(f"[DEBUG] Топ швидкості отримано: {len(top_speed)} записів")
            
            return top_winners, top_speed
    except Exception as e:
        print(f"[DEBUG] Помилка в get_quest_top: {e}")
        return [], []

def get_user_quest_stats(user_id: int):
    """Отримує статистику користувача в квестах"""
    with _db() as con:
        stats = con.execute("""
            SELECT 
                COUNT(*) as total_wins,
                SUM(amount) as total_fruits,
                AVG(reaction_time) as avg_reaction,
                MIN(reaction_time) as best_reaction,
                COUNT(CASE WHEN fruit_type = 'apple' THEN 1 END) as apple_wins,
                COUNT(CASE WHEN fruit_type = 'pear' THEN 1 END) as pear_wins,
                COUNT(CASE WHEN fruit_type = 'orange' THEN 1 END) as orange_wins,
                COUNT(CASE WHEN fruit_type = 'grape' THEN 1 END) as grape_wins
            FROM quest_statistics 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        print(f"[DEBUG] Статистика користувача {user_id}: {stats}")
        return stats

# Ініціалізуємо таблицю статистики
ensure_quest_statistics_table()

def get_user_total_income_on_level(user_id: int, level: int) -> float:
    """Повертає загальний дохід користувача на конкретному рівні саду"""
    try:
        with _db() as con:
            # Отримуємо час, коли користувач досяг цього рівня
            level_start_time = con.execute(
                "SELECT purchased_at FROM garden_levels WHERE user_id=? AND level=? ORDER BY purchased_at ASC LIMIT 1",
                (user_id, level)
            ).fetchone()
            
            if not level_start_time:
                return 0.0
            
            # Підраховуємо всі транзакції збору фруктів з моменту досягнення рівня
            total_income = con.execute("""
                SELECT COALESCE(SUM(gt.amount * fp.price), 0) 
                FROM garden_transactions gt
                JOIN market_prices fp ON gt.currency = fp.fruit_type
                WHERE gt.user_id = ? 
                AND gt.type = 'harvest' 
                AND gt.timestamp >= ?
            """, (user_id, level_start_time[0])).fetchone()[0]
            
            return float(total_income) if total_income else 0.0
    except Exception as e:
        print(f"Помилка при підрахунку доходу на рівні: {e}")
        return 0.0

def get_level_income_limit(level: int) -> float:
    """Повертає ліміт загального доходу для рівня саду"""
    limits = {
        1: 500.0,   # Рівень 1: максимум 500₴
        2: 2000.0,  # Рівень 2: максимум 2000₴  
        3: 10000.0  # Рівень 3: максимум 10000₴
    }
    return limits.get(level, float('inf'))

def get_income_multiplier_for_level(user_id: int, level: int) -> float:
    """Повертає множник доходу залежно від досягнутого ліміту на рівні"""
    try:
        total_income = get_user_total_income_on_level(user_id, level)
        income_limit = get_level_income_limit(level)
        
        if total_income >= income_limit:
            # Після досягнення ліміту - мінімальний дохід
            return 0.1  # 10% від нормального доходу
        elif total_income >= income_limit * 0.8:
            # При 80-100% ліміту - зменшений дохід
            return 0.5  # 50% від нормального доходу
        else:
            # До 80% ліміту - звичайний дохід
            return 1.0  # 100% від нормального доходу
    except Exception as e:
        print(f"Помилка при розрахунку множника доходу: {e}")
        return 1.0

def should_show_level_upgrade_warning(user_id: int, level: int) -> bool:
    """Перевіряє чи потрібно показати попередження про апгрейд рівня"""
    try:
        total_income = get_user_total_income_on_level(user_id, level)
        income_limit = get_level_income_limit(level)
        
        # Показуємо попередження при 80% ліміту
        return total_income >= income_limit * 0.8
    except Exception as e:
        print(f"Помилка при перевірці попередження апгрейду: {e}")
        return False

def get_level_income_stats(user_id: int, level: int) -> dict:
    """Повертає статистику доходу на рівні"""
    try:
        total_income = get_user_total_income_on_level(user_id, level)
        income_limit = get_level_income_limit(level)
        percentage = (total_income / income_limit * 100) if income_limit > 0 else 0
        
        return {
            'total_income': total_income,
            'income_limit': income_limit,
            'percentage': min(percentage, 100),
            'remaining': max(0, income_limit - total_income),
            'is_limited': total_income >= income_limit,
            'should_warn': total_income >= income_limit * 0.8
        }
    except Exception as e:
        print(f"Помилка при отриманні статистики доходу: {e}")
        return {
            'total_income': 0,
            'income_limit': 0,
            'percentage': 0,
            'remaining': 0,
            'is_limited': False,
            'should_warn': False
        }

# --- Функції для роботи з часовим поясом ---

def ensure_timezone_table():
    """Створює таблицю для зберігання часових поясів користувачів"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_timezones (
                user_id INTEGER PRIMARY KEY,
                timezone TEXT DEFAULT 'Europe/Kiev',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.commit()

def get_user_timezone(user_id: int) -> str:
    """Отримує часовий пояс користувача"""
    ensure_timezone_table()
    with _db() as con:
        row = con.execute("SELECT timezone FROM user_timezones WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return row[0]
        else:
            # Якщо користувача немає в таблиці, додаємо з дефолтним часовим поясом
            set_user_timezone(user_id, 'Europe/Kiev')
            return 'Europe/Kiev'

def set_user_timezone(user_id: int, timezone: str):
    """Встановлює часовий пояс користувача"""
    ensure_timezone_table()
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO user_timezones (user_id, timezone, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (user_id, timezone))
        con.commit()

def get_all_user_timezones():
    """Отримує всі часові зони користувачів (для адміністраторів)"""
    ensure_timezone_table()
    with _db() as con:
        return con.execute("SELECT user_id, timezone, updated_at FROM user_timezones ORDER BY updated_at DESC").fetchall()

def get_total_users_count():
    """Отримує загальну кількість користувачів"""
    with _db() as con:
        row = con.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0

def get_user_referrer(user_id):
    """Отримує реферера користувача"""
    with _db() as con:
        # Перевіряємо чи є колонка referrer_id
        cursor = con.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'referrer_id' in columns:
            row = con.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return row[0] if row else None
        else:
            # Якщо колонки немає, повертаємо None
            return None

def get_user_registration_info(user_id):
    """Отримує інформацію про реєстрацію користувача"""
    with _db() as con:
        # Перевіряємо структуру таблиці users
        cursor = con.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"[DEBUG] Наявні колонки в таблиці users: {columns}")
        
        # Формуємо запит в залежності від наявних колонок
        if 'name' in columns and 'created_at' in columns and 'referrer_id' in columns:
            query = "SELECT user_id, name, created_at, referrer_id FROM users WHERE user_id = ?"
        elif 'name' in columns and 'created_at' in columns:
            query = "SELECT user_id, name, created_at FROM users WHERE user_id = ?"
        elif 'name' in columns and 'referrer_id' in columns:
            query = "SELECT user_id, name, referrer_id FROM users WHERE user_id = ?"
        elif 'created_at' in columns and 'referrer_id' in columns:
            query = "SELECT user_id, created_at, referrer_id FROM users WHERE user_id = ?"
        elif 'name' in columns:
            query = "SELECT user_id, name FROM users WHERE user_id = ?"
        elif 'created_at' in columns:
            query = "SELECT user_id, created_at FROM users WHERE user_id = ?"
        elif 'referrer_id' in columns:
            query = "SELECT user_id, referrer_id FROM users WHERE user_id = ?"
        else:
            query = "SELECT user_id FROM users WHERE user_id = ?"
        
        row = con.execute(query, (user_id,)).fetchone()
        
        if row:
            # Ініціалізуємо змінні
            name = "Невідомий користувач"
            created_at = None
            referrer_id = None
            
            # Розбираємо результат в залежності від кількості колонок
            if len(row) == 4:  # user_id, name, created_at, referrer_id
                user_id, name, created_at, referrer_id = row
            elif len(row) == 3:  # user_id, name, created_at або user_id, name, referrer_id або user_id, created_at, referrer_id
                if 'name' in columns and 'created_at' in columns:
                    user_id, name, created_at = row
                elif 'name' in columns and 'referrer_id' in columns:
                    user_id, name, referrer_id = row
                elif 'created_at' in columns and 'referrer_id' in columns:
                    user_id, created_at, referrer_id = row
            elif len(row) == 2:  # user_id, name або user_id, created_at або user_id, referrer_id
                if 'name' in columns:
                    user_id, name = row
                elif 'created_at' in columns:
                    user_id, created_at = row
                elif 'referrer_id' in columns:
                    user_id, referrer_id = row
            else:  # тільки user_id
                user_id = row[0]
            
            return {
                'user_id': user_id,
                'name': name,
                'created_at': created_at,
                'referrer_id': referrer_id
            }
        return None

def get_all_admins():
    """Отримує список всіх адміністраторів"""
    with _db() as con:
        # Перевіряємо чи є колонка is_admin
        cursor = con.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_admin' in columns:
            rows = con.execute("SELECT user_id FROM users WHERE is_admin = 1").fetchall()
            return [row[0] for row in rows]
        else:
            # Якщо колонки немає, використовуємо функцію is_admin
            rows = con.execute("SELECT user_id FROM users").fetchall()
            admin_ids = []
            for row in rows:
                if is_admin(row[0]):
                    admin_ids.append(row[0])
            return admin_ids

def get_all_user_ids() -> list[int]:
    with _db() as con:
        rows = con.execute("SELECT user_id FROM users").fetchall()
        return [r[0] for r in rows]

# Backward-compatible alias for older modules expecting this name
def get_all_users() -> list[int]:
    """Return list of all user IDs.

    Some modules (e.g., channel/chat monitoring) import get_all_users.
    Keep a thin wrapper to avoid import errors on deployments.
    """
    try:
        return get_all_user_ids()
    except Exception:
        return []

def get_required_chats():
    """Отримує список обов'язкових чатів (груп)"""
    with _db() as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'required_chats'").fetchone()
        if row and row[0]:
            try:
                return json.loads(row[0])
            except Exception:
                return [c.strip() for c in row[0].split(',') if c.strip()]
        return []

def set_required_chats(chats):
    """Встановлює список обов'язкових чатів"""
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('required_chats', ?)", (json.dumps(chats),))
        con.commit()

def add_required_chat(chat_id):
    """Додає обов'язковий чат"""
    chats = get_required_chats()
    if str(chat_id) not in chats:
        chats.append(str(chat_id))
        set_required_chats(chats)

def remove_required_chat(chat_id):
    """Видаляє обов'язковий чат"""
    chats = get_required_chats()
    chats = [c for c in chats if c != str(chat_id)]
    set_required_chats(chats)

def is_user_blocked(user_id: int) -> bool:
    """Перевіряє чи заблокований користувач за вихід з чату або каналу"""
    with _db() as con:
        row = con.execute("SELECT 1 FROM user_blocks WHERE user_id = ? AND block_type IN ('chat_leave', 'channel_leave') AND is_active = 1", (user_id,)).fetchone()
        return row is not None

def block_user_for_chat_leave(user_id: int, chat_id: str, chat_title: str):
    """Блокує користувача за вихід з чату"""
    import time
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO user_blocks 
            (user_id, block_type, reason, chat_id, chat_title, blocked_at, is_active) 
            VALUES (?, 'chat_leave', ?, ?, ?, ?, 1)
        """, (user_id, f"Вихід з обов'язкового чату: {chat_title}", chat_id, chat_title, int(time.time())))
        con.commit()

def block_user_for_channel_leave(user_id: int, channel_id: str, channel_title: str):
    """Блокує користувача за вихід з каналу"""
    import time
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO user_blocks 
            (user_id, block_type, reason, chat_id, chat_title, blocked_at, is_active) 
            VALUES (?, 'channel_leave', ?, ?, ?, ?, 1)
        """, (user_id, f"Вихід з обов'язкового каналу: {channel_title}", channel_id, channel_title, int(time.time())))
        con.commit()

def unblock_user(user_id: int):
    """Розблоковує користувача"""
    with _db() as con:
        con.execute("UPDATE user_blocks SET is_active = 0 WHERE user_id = ? AND block_type IN ('chat_leave', 'channel_leave')", (user_id,))
        con.commit()

def get_user_block_info(user_id: int):
    """Отримує інформацію про блокування користувача"""
    with _db() as con:
        row = con.execute("""
            SELECT * FROM user_blocks 
            WHERE user_id = ? AND block_type IN ('chat_leave', 'channel_leave') AND is_active = 1
            ORDER BY blocked_at DESC LIMIT 1
        """, (user_id,)).fetchone()
        return row

def get_all_blocked_users():
    """Отримує список всіх заблокованих користувачів"""
    with _db() as con:
        rows = con.execute("""
            SELECT user_id, reason, chat_title, blocked_at, block_type
            FROM user_blocks 
            WHERE block_type IN ('chat_leave', 'channel_leave') AND is_active = 1
            ORDER BY blocked_at DESC
        """).fetchall()
        return rows

def get_banners_disabled():
    """Отримує статус відключення банерів з бази даних"""
    with _db() as con:
        # Створюємо таблицю settings якщо її немає
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        row = con.execute("SELECT value FROM settings WHERE key = 'banners_disabled'").fetchone()
        if row:
            return row[0] == '1'
        return False

def set_banners_disabled(disabled):
    """Встановлює статус відключення банерів в базі даних"""
    with _db() as con:
        # Створюємо таблицю settings якщо її немає
        con.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        con.execute("""
            INSERT OR REPLACE INTO settings (key, value) 
            VALUES ('banners_disabled', ?)
        """, ('1' if disabled else '0',))
        con.commit()

def freeze_user_account(user_id, reason="Account frozen by administrator"):
    """Заморожує акаунт користувача"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS frozen_accounts (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        con.execute("""
            INSERT OR REPLACE INTO frozen_accounts (user_id, reason) 
            VALUES (?, ?)
        """, (user_id, reason))
        con.commit()

def unfreeze_user_account(user_id):
    """Розморожує акаунт користувача"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS frozen_accounts (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        con.execute("DELETE FROM frozen_accounts WHERE user_id = ?", (user_id,))
        con.commit()

def is_user_frozen(user_id):
    """Перевіряє чи заморожений акаунт користувача"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS frozen_accounts (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        row = con.execute("SELECT user_id FROM frozen_accounts WHERE user_id = ?", (user_id,)).fetchone()
        return row is not None

def get_user_freeze_info(user_id):
    """Повертає інформацію про заморозку користувача: (is_frozen, freeze_info)"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS frozen_accounts (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        row = con.execute("SELECT reason, frozen_at FROM frozen_accounts WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            return True, {
                'reason': row[0],
                'frozen_at': row[1]
            }
        else:
            return False, None

def get_frozen_users():
    """Отримує список всіх заморожених користувачів"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS frozen_accounts (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        rows = con.execute("""
            SELECT user_id, reason, frozen_at 
            FROM frozen_accounts 
            ORDER BY frozen_at DESC
        """).fetchall()
        return rows

# ==========================
# 🛡️ СИСТЕМА ВЕРИФІКАЦІЇ
# ==========================

def ensure_verification_table():
    """Створює таблицю для верифікації користувачів"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_verification (
                user_id INTEGER PRIMARY KEY,
                status TEXT DEFAULT 'not_verified', -- 'not_verified', 'pending', 'verified', 'rejected'
                verification_data TEXT, -- JSON з даними верифікації
                suspicious_activity_score INTEGER DEFAULT 0,
                suspicious_activity_reasons TEXT, -- JSON масив причин
                verification_requested_at INTEGER,
                verification_verified_at INTEGER,
                verification_verified_by INTEGER, -- admin_id
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        """)
        con.commit()

def get_user_verification_status(user_id):
    """Отримує статус верифікації користувача"""
    ensure_verification_table()
    with _db() as con:
        row = con.execute("""
            SELECT status, verification_data, suspicious_activity_score, 
                   suspicious_activity_reasons, verification_requested_at,
                   verification_verified_at, verification_verified_by
            FROM user_verification 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if row:
            import json
            verification_data = {}
            reasons = []
            try:
                if row[1]:
                    verification_data = json.loads(row[1])
                if row[3]:
                    reasons = json.loads(row[3])
            except Exception:
                pass
            
            return {
                'status': row[0],
                'verification_data': verification_data,
                'suspicious_activity_score': row[2] or 0,
                'suspicious_activity_reasons': reasons,
                'verification_requested_at': row[4],
                'verification_verified_at': row[5],
                'verification_verified_by': row[6]
            }
        else:
            # Створюємо запис за замовчуванням
            con.execute("""
                INSERT OR IGNORE INTO user_verification (user_id, status) 
                VALUES (?, 'not_verified')
            """, (user_id,))
            con.commit()
            return {
                'status': 'not_verified',
                'verification_data': {},
                'suspicious_activity_score': 0,
                'suspicious_activity_reasons': [],
                'verification_requested_at': None,
                'verification_verified_at': None,
                'verification_verified_by': None
            }

def set_user_verification_status(user_id, status, verification_data=None, verified_by=None):
    """Встановлює статус верифікації користувача"""
    ensure_verification_table()
    import time
    import json
    
    with _db() as con:
        # Проверяем существование записи
        exists = con.execute("SELECT 1 FROM user_verification WHERE user_id = ?", (user_id,)).fetchone()
        
        if exists:
            # Обновляем существующую запись
            update_fields = ["status = ?", "updated_at = ?"]
            params = [status, int(time.time())]
            
            if verification_data is not None:
                update_fields.append("verification_data = ?")
                params.append(json.dumps(verification_data))
            
            if status == 'pending':
                update_fields.append("verification_requested_at = ?")
                params.append(int(time.time()))
            
            if status == 'verified' and verified_by:
                update_fields.append("verification_verified_at = ?")
                update_fields.append("verification_verified_by = ?")
                params.append(int(time.time()))
                params.append(verified_by)
            
            params.append(user_id)
            
            con.execute(f"""
                UPDATE user_verification 
                SET {', '.join(update_fields)}
                WHERE user_id = ?
            """, params)
        else:
            # Создаем новую запись
            params = [user_id, status, int(time.time())]
            fields = ["user_id", "status", "updated_at"]
            placeholders = ["?", "?", "?"]
            
            if verification_data is not None:
                fields.append("verification_data")
                placeholders.append("?")
                params.insert(-1, json.dumps(verification_data))
            
            if status == 'pending':
                fields.append("verification_requested_at")
                placeholders.append("?")
                params.insert(-1, int(time.time()))
            
            if status == 'verified' and verified_by:
                fields.append("verification_verified_at")
                fields.append("verification_verified_by")
                placeholders.append("?")
                placeholders.append("?")
                params.insert(-1, int(time.time()))
                params.insert(-1, verified_by)
            
            con.execute(f"""
                INSERT INTO user_verification ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            """, params)
        
        con.commit()

def submit_verification_request(user_id, verification_data):
    """Відправляє запит на верифікацію"""
    ensure_verification_table()
    import time
    import json
    
    with _db() as con:
        con.execute("""
            INSERT INTO user_verification 
            (user_id, status, verification_data, verification_requested_at, updated_at)
            VALUES (?, 'pending', ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                status = 'pending',
                verification_data = ?,
                verification_requested_at = ?,
                updated_at = ?
        """, (user_id, json.dumps(verification_data), int(time.time()), int(time.time()),
              json.dumps(verification_data), int(time.time()), int(time.time())))
        con.commit()

def verify_user(user_id, admin_id):
    """Верифікує користувача (викликається адміном)"""
    ensure_verification_table()
    import time
    
    with _db() as con:
        con.execute("""
            UPDATE user_verification 
            SET status = 'verified',
                verification_verified_at = ?,
                verification_verified_by = ?,
                updated_at = ?
            WHERE user_id = ?
        """, (int(time.time()), admin_id, int(time.time()), user_id))
        con.commit()

def reject_verification(user_id, admin_id):
    """Відхиляє верифікацію користувача"""
    ensure_verification_table()
    import time
    
    with _db() as con:
        con.execute("""
            UPDATE user_verification 
            SET status = 'rejected',
                verification_verified_at = ?,
                verification_verified_by = ?,
                updated_at = ?
            WHERE user_id = ?
        """, (int(time.time()), admin_id, int(time.time()), user_id))
        con.commit()

def update_suspicious_activity_score(user_id, score, reasons=None):
    """Оновлює оцінку підозрілої активності"""
    ensure_verification_table()
    import json
    import time
    
    with _db() as con:
        # Отримуємо поточні причини
        row = con.execute("""
            SELECT suspicious_activity_reasons FROM user_verification WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        current_reasons = []
        if row and row[0]:
            try:
                current_reasons = json.loads(row[0])
            except Exception:
                pass
        
        # Додаємо нові причини
        if reasons:
            if isinstance(reasons, list):
                current_reasons.extend(reasons)
            else:
                current_reasons.append(reasons)
        
        # Видаляємо дублікати
        current_reasons = list(dict.fromkeys(current_reasons))
        
        con.execute("""
            INSERT INTO user_verification (user_id, suspicious_activity_score, suspicious_activity_reasons, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                suspicious_activity_score = ?,
                suspicious_activity_reasons = ?,
                updated_at = ?
        """, (user_id, score, json.dumps(current_reasons), int(time.time()),
              score, json.dumps(current_reasons), int(time.time())))
        con.commit()

def get_pending_verifications():
    """Отримує список користувачів, що очікують верифікації"""
    ensure_verification_table()
    with _db() as con:
        rows = con.execute("""
            SELECT user_id, verification_data, verification_requested_at, suspicious_activity_score
            FROM user_verification 
            WHERE status = 'pending'
            ORDER BY verification_requested_at ASC
        """).fetchall()
        
        result = []
        import json
        for row in rows:
            verification_data = {}
            try:
                if row[1]:
                    verification_data = json.loads(row[1])
            except Exception:
                pass
            
            result.append({
                'user_id': row[0],
                'verification_data': verification_data,
                'verification_requested_at': row[2],
                'suspicious_activity_score': row[3] or 0
            })
        
        return result

def is_user_verified(user_id):
    """Перевіряє чи верифікований користувач"""
    status_info = get_user_verification_status(user_id)
    return status_info['status'] == 'verified'

def analyze_suspicious_activity(user_id):
    """Аналізує підозрілу активність користувача та повертає оцінку (0-100) та причини"""
    ensure_verification_table()
    import time
    
    score = 0
    reasons = []
    
    with _db() as con:
        # Отримуємо дані користувача
        user_row = con.execute("SELECT balance, withdrawn FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if not user_row:
            return 0, []
        
        balance = float(user_row[0] or 0)
        withdrawn = float(user_row[1] or 0)
        
        # Отримуємо дату реєстрації
        reg_date_row = con.execute("SELECT date_joined FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if reg_date_row and reg_date_row[0]:
            reg_date = reg_date_row[0]
            days_since_reg = (int(time.time()) - reg_date) / 86400
        else:
            days_since_reg = 999  # Якщо немає дати реєстрації
        
        # 1. Швидкий вивід після реєстрації (< 7 днів)
        if days_since_reg < 7 and withdrawn > 0:
            score += 30
            reasons.append(f"Швидкий вивід після реєстрації ({int(days_since_reg)} днів)")
        
        # 2. Великий вивід відразу після реєстрації
        if days_since_reg < 3 and withdrawn > 500:
            score += 40
            reasons.append(f"Великий вивід ({withdrawn:.2f}₴) через {int(days_since_reg)} днів після реєстрації")
        
        # 3. Баланс значно перевищує виведені кошти (можливо арбітраж)
        if balance > withdrawn * 10 and withdrawn > 0:
            score += 20
            reasons.append(f"Баланс ({balance:.2f}₴) значно перевищує виведені кошти ({withdrawn:.2f}₴)")
        
        # 4. Багато транзакцій за короткий час
        recent_tx = con.execute("""
            SELECT COUNT(*) FROM balance_ledger 
            WHERE user_id = ? AND created_at > ?
        """, (user_id, int(time.time()) - 3600)).fetchone()[0]
        
        if recent_tx > 20:
            score += 25
            reasons.append(f"Багато транзакцій за годину ({recent_tx})")
        
        # 5. Швидкі зміни балансу
        recent_deltas = con.execute("""
            SELECT ABS(delta) FROM balance_ledger 
            WHERE user_id = ? AND created_at > ? 
            ORDER BY created_at DESC LIMIT 10
        """, (user_id, int(time.time()) - 86400)).fetchall()
        
        if recent_deltas:
            large_changes = sum(1 for d in recent_deltas if abs(d[0]) > 1000)
            if large_changes >= 5:
                score += 30
                reasons.append(f"Багато великих змін балансу за добу ({large_changes})")
        
        # Оновлюємо оцінку в базі
        if score > 0:
            update_suspicious_activity_score(user_id, score, reasons)
        
        # Якщо оцінка висока (>70), автоматично заморожуємо акаунт
        if score >= 70:
            from database import freeze_user_account, is_user_frozen
            if not is_user_frozen(user_id):
                freeze_user_account(user_id, f"Автоматична заморозка через підозрілу активність (оцінка: {score}/100)")
                reasons.append("АКАУНТ АВТОМАТИЧНО ЗАМОРОЖЕНО")
    
    return min(score, 100), reasons

def get_cryptobot_settings():
    """Отримує налаштування CryptoBot"""
    with _db() as con:
        # Сначала проверяем, существует ли таблица и какая у неё структура
        try:
            # Пробуем выполнить запрос с новой структурой
            rows = con.execute("SELECT key, value FROM cryptobot_settings").fetchall()
            settings = dict(rows) if rows else {}
        except sqlite3.OperationalError as e:
            if "no such column: key" in str(e):
                # Таблица существует, но со старой структурой - пересоздаём
                print("[CRYPTOBOT] Migrating cryptobot_settings table to new structure...")
                con.execute("DROP TABLE IF EXISTS cryptobot_settings")
                con.execute("""
                    CREATE TABLE cryptobot_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                con.commit()
                settings = {}
            else:
                # Другая ошибка - создаём таблицу заново
                con.execute("""
                    CREATE TABLE IF NOT EXISTS cryptobot_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                settings = {}
        
        # Если настроек нет, инициализируем значения по умолчанию
        if not settings:
            default_settings = {
                'enabled': False,
                'exchange_rate': 0.025,
                'min_deposit': 10,
                'admin_fee_percent': 2,
                'supported_currencies': 'BTC,ETH,USDT,USDC',
                'api_key': '',
                'bot_token': ''
            }
            for key, value in default_settings.items():
                con.execute("""
                    INSERT OR REPLACE INTO cryptobot_settings (key, value) 
                    VALUES (?, ?)
                """, (key, str(value)))
            con.commit()
            settings = default_settings
        
        # Преобразуем supported_currencies из строки в список
        if 'supported_currencies' in settings and isinstance(settings['supported_currencies'], str):
            settings['supported_currencies'] = [c.strip() for c in settings['supported_currencies'].split(',')]
        
        return settings

def update_cryptobot_settings(settings):
    """Оновлює налаштування CryptoBot"""
    with _db() as con:
        # Убеждаемся, что таблица имеет правильную структуру
        try:
            con.execute("SELECT key, value FROM cryptobot_settings LIMIT 1")
        except sqlite3.OperationalError as e:
            if "no such column: key" in str(e):
                print("[CRYPTOBOT] Migrating cryptobot_settings table in update function...")
                con.execute("DROP TABLE IF EXISTS cryptobot_settings")
                con.execute("""
                    CREATE TABLE cryptobot_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                con.commit()
            else:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS cryptobot_settings (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
        
        for key, value in settings.items():
            # Преобразуем supported_currencies из списка в строку для хранения
            if key == 'supported_currencies' and isinstance(value, list):
                value = ','.join(value)
            con.execute("""
                INSERT OR REPLACE INTO cryptobot_settings (key, value) 
                VALUES (?, ?)
            """, (key, str(value)))
        con.commit()

def create_cryptobot_transaction(user_id, amount, currency, description, status="pending", uah_amount=None):
    """Створює транзакцію CryptoBot"""
    with _db() as con:
        # Проверяем, существует ли таблица
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cryptobot_transactions'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Таблица существует - проверяем структуру
            cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
            table_info = cursor.fetchall()
            existing_columns = {row[1]: {'type': row[2], 'notnull': row[3], 'default': row[4]} for row in table_info}
            
            # Все возможные колонки таблицы (на основе всех версий схемы)
            all_possible_columns = {
                'amount': ('REAL', False, None),
                'currency': ('TEXT', False, None),
                'description': ('TEXT', False, None),
                'status': ('TEXT', False, 'pending'),
                'uah_amount': ('REAL', False, None),
                'invoice_id': ('TEXT', False, None),
                'crypto_amount': ('REAL', False, 0.0),
                'crypto_currency': ('TEXT', False, 'USDT')  # Значение по умолчанию
            }
            
            # Добавляем недостающие колонки
            for col_name, (col_type, notnull, default_val) in all_possible_columns.items():
                if col_name not in existing_columns:
                    try:
                        if default_val is not None:
                            if isinstance(default_val, str):
                                default_clause = f" DEFAULT '{default_val}'"
                            else:
                                default_clause = f" DEFAULT {default_val}"
                        else:
                            default_clause = ""
                        con.execute(f"ALTER TABLE cryptobot_transactions ADD COLUMN {col_name} {col_type}{default_clause}")
                        print(f"[CRYPTOBOT] Added column {col_name} to cryptobot_transactions")
                    except sqlite3.OperationalError as e:
                        print(f"[CRYPTOBOT] Error adding column {col_name}: {e}")
            
            # Проверяем, какие колонки нужно вставлять
            all_columns = set(existing_columns.keys()) | set(all_possible_columns.keys())
            # Исключаем только id (AUTOINCREMENT)
            # created_at включаем, если она есть и не имеет DEFAULT
            insert_columns = []
            for col in sorted(all_columns):
                if col == 'id':
                    continue  # Пропускаем id (AUTOINCREMENT)
                col_info = existing_columns.get(col, {})
                # Если колонка имеет DEFAULT, не включаем её в INSERT (SQLite использует DEFAULT)
                if col == 'created_at' and col_info.get('dflt_value'):
                    continue
                insert_columns.append(col)
            
            # Формируем список значений для INSERT
            import time
            values = []
            placeholders = []
            for col in insert_columns:
                if col == 'user_id':
                    values.append(user_id)
                elif col == 'amount':
                    values.append(amount)
                elif col == 'currency':
                    values.append(currency)
                elif col == 'description':
                    values.append(description)
                elif col == 'status':
                    values.append(status)
                elif col == 'uah_amount':
                    values.append(uah_amount)
                elif col == 'invoice_id':
                    values.append(None)
                elif col == 'crypto_amount':
                    values.append(0.0)
                elif col == 'crypto_currency':
                    values.append('USDT')
                elif col == 'created_at':
                    # Если created_at включена, используем текущее время
                    values.append(int(time.time()))
                else:
                    # Для любых других колонок - проверяем NOT NULL и DEFAULT
                    col_info = existing_columns.get(col, {})
                    if col_info.get('notnull') and not col_info.get('dflt_value'):
                        # NOT NULL без DEFAULT - используем значение по умолчанию в зависимости от типа
                        col_type = col_info.get('type', '').upper()
                        if 'INT' in col_type:
                            values.append(0)
                        elif 'REAL' in col_type or 'FLOAT' in col_type:
                            values.append(0.0)
                        elif 'TEXT' in col_type:
                            values.append('')
                        else:
                            values.append(None)
                    elif col_info.get('dflt_value'):
                        # Есть DEFAULT - не должно попасть сюда, но на всякий случай
                        values.append(None)
                    else:
                        values.append(None)
                placeholders.append('?')
            
            # Выполняем INSERT с динамическим списком колонок
            insert_sql = f"""
                INSERT INTO cryptobot_transactions ({', '.join(insert_columns)})
                VALUES ({', '.join(placeholders)})
            """
            cursor = con.execute(insert_sql, tuple(values))
        else:
            # Таблица не существует - создаем с правильной структурой
            con.execute("""
                CREATE TABLE cryptobot_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    uah_amount REAL,
                    invoice_id TEXT,
                    crypto_amount REAL DEFAULT 0.0,
                    crypto_currency TEXT DEFAULT 'USDT',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor = con.execute("""
                INSERT INTO cryptobot_transactions (user_id, amount, currency, description, status, uah_amount, crypto_amount, crypto_currency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, amount, currency, description, status, uah_amount, 0.0, 'USDT'))
        
        con.commit()
        return cursor.lastrowid

def get_cryptobot_transaction(transaction_id):
    """Отримує транзакцію CryptoBot за ID"""
    with _db() as con:
        # Используем ту же логику миграции, что и в create_cryptobot_transaction
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cryptobot_transactions'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Добавляем недостающие колонки
            cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            required_columns = {
                'amount': ('REAL', None),
                'currency': ('TEXT', None),
                'description': ('TEXT', None),
                'status': ('TEXT', "'pending'"),
                'uah_amount': ('REAL', None),
                'invoice_id': ('TEXT', None),
                'crypto_amount': ('REAL', '0.0'),
                'crypto_currency': ('TEXT', "'USDT'")
            }
            for col, (col_type, default) in required_columns.items():
                if col not in existing_columns:
                    try:
                        default_clause = f" DEFAULT {default}" if default else ""
                        con.execute(f"ALTER TABLE cryptobot_transactions ADD COLUMN {col} {col_type}{default_clause}")
                    except sqlite3.OperationalError:
                        pass
        else:
            con.execute("""
                CREATE TABLE cryptobot_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    uah_amount REAL,
                    invoice_id TEXT,
                    crypto_amount REAL DEFAULT 0.0,
                    crypto_currency TEXT DEFAULT 'USDT',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Получаем все колонки из таблицы
        cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        # Формируем SELECT запрос с учетом всех существующих колонок
        select_columns = ', '.join([col for col in columns if col not in []])
        
        row = con.execute(f"""
            SELECT {select_columns}
            FROM cryptobot_transactions WHERE id = ?
        """, (transaction_id,)).fetchone()
        return row

def update_cryptobot_transaction_status(transaction_id, status, invoice_id=None):
    """Оновлює статус транзакції CryptoBot"""
    with _db() as con:
        # Миграция таблицы при необходимости
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cryptobot_transactions'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            # Добавляем все недостающие колонки
            missing_cols = {
                'crypto_amount': ('REAL', '0.0'),
                'crypto_currency': ('TEXT', "'USDT'")
            }
            for col_name, (col_type, default) in missing_cols.items():
                if col_name not in existing_columns:
                    try:
                        con.execute(f"ALTER TABLE cryptobot_transactions ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                    except sqlite3.OperationalError:
                        pass
        else:
            con.execute("""
                CREATE TABLE cryptobot_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    uah_amount REAL,
                    invoice_id TEXT,
                    crypto_amount REAL DEFAULT 0.0,
                    crypto_currency TEXT DEFAULT 'USDT',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        if invoice_id:
            con.execute("""
                UPDATE cryptobot_transactions 
                SET status = ?, invoice_id = ?
                WHERE id = ?
            """, (status, invoice_id, transaction_id))
        else:
            con.execute("""
                UPDATE cryptobot_transactions 
                SET status = ? 
                WHERE id = ?
            """, (status, transaction_id))
        con.commit()

def update_cryptobot_transaction_amount(transaction_id, amount):
    """Оновлює суму транзакції CryptoBot"""
    with _db() as con:
        con.execute("""
            UPDATE cryptobot_transactions 
            SET amount = ? 
            WHERE id = ?
        """, (amount, transaction_id))
        con.commit()

def get_user_cryptobot_transactions(user_id, limit=10):
    """Отримує транзакції CryptoBot користувача"""
    with _db() as con:
        # Миграция таблицы при необходимости
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='cryptobot_transactions'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
            existing_columns = [row[1] for row in cursor.fetchall()]
            # Добавляем все недостающие колонки
            missing_cols = {
                'crypto_amount': ('REAL', '0.0'),
                'crypto_currency': ('TEXT', "'USDT'")
            }
            for col_name, (col_type, default) in missing_cols.items():
                if col_name not in existing_columns:
                    try:
                        con.execute(f"ALTER TABLE cryptobot_transactions ADD COLUMN {col_name} {col_type} DEFAULT {default}")
                    except sqlite3.OperationalError:
                        pass
        else:
            con.execute("""
                CREATE TABLE cryptobot_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount REAL,
                    currency TEXT,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    uah_amount REAL,
                    invoice_id TEXT,
                    crypto_amount REAL DEFAULT 0.0,
                    crypto_currency TEXT DEFAULT 'USDT',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # Получаем все колонки из таблицы
        cursor = con.execute("PRAGMA table_info(cryptobot_transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        select_columns = ', '.join([col for col in columns])
        
        rows = con.execute(f"""
            SELECT {select_columns}
            FROM cryptobot_transactions 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return rows

def get_garden_activity_log(user_id, limit=50):
    """Отримує лог активності саду користувача"""
    import json
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS garden_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                activity_type TEXT NOT NULL,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                cost REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'UAH',
                metadata TEXT
            )
        """)
        
        rows = con.execute("""
            SELECT id, user_id, timestamp, activity_type, item_name, quantity, cost, currency, metadata
            FROM garden_activity_log 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (user_id, limit)).fetchall()
        
        # Преобразуем в список словарей
        result = []
        for row in rows:
            metadata = json.loads(row[8]) if row[8] else {}
            result.append({
                'id': row[0],
                'user_id': row[1],
                'timestamp': row[2],
                'activity_type': row[3],
                'item_name': row[4],
                'quantity': row[5],
                'cost': row[6],
                'currency': row[7],
                'metadata': metadata
            })
        return result

def get_user_balance_summary(user_id):
    """Отримує зведену статистику балансу користувача"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS balance_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                delta REAL NOT NULL,
                balance_before REAL NOT NULL,
                balance_after REAL NOT NULL,
                reason TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        
        # Получаем текущий баланс
        user = get_user(user_id)
        current_balance = user[2] if user else 0.0
        
        # Получаем статистику по операциям из ledger
        stats = con.execute("""
            SELECT 
                COUNT(*) as total_operations,
                SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END) as total_income,
                SUM(CASE WHEN delta < 0 THEN ABS(delta) ELSE 0 END) as total_expenses,
                SUM(delta) as total_ledger_delta,
                MIN(created_at) as first_operation,
                MAX(created_at) as last_operation
            FROM balance_ledger 
            WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        # Получаем депозиты
        total_deposits = con.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM deposit_tx 
            WHERE user_id = ? AND status = 'approved'
        """, (user_id,)).fetchone()[0] or 0.0
        
        # Получаем виводы
        total_withdrawals = con.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM tx 
            WHERE user_id = ? AND status = 'done'
        """, (user_id,)).fetchone()[0] or 0.0
        
        total_ledger_delta = stats[3] or 0.0
        ledger_count = stats[0] or 0
        
        # Ожидаемый баланс = депозиты - виводы
        expected_balance = total_deposits - total_withdrawals
        discrepancy = current_balance - expected_balance
        
        return {
            'current_balance': current_balance,
            'total_operations': stats[0] or 0,
            'total_income': stats[1] or 0.0,
            'total_expenses': stats[2] or 0.0,
            'first_operation': stats[4],
            'last_operation': stats[5],
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'total_ledger_delta': total_ledger_delta,
            'ledger_count': ledger_count,
            'expected_balance': expected_balance,
            'discrepancy': discrepancy
        }

def get_user_balance_ledger(user_id, limit=200):
    """Отримує історію операцій балансу користувача"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS balance_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                delta REAL NOT NULL,
                balance_before REAL NOT NULL,
                balance_after REAL NOT NULL,
                reason TEXT,
                details TEXT,
                created_at INTEGER NOT NULL
            )
        """)
        
        rows = con.execute("""
            SELECT delta, balance_before, balance_after, reason, details, created_at
            FROM balance_ledger 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit)).fetchall()
        return rows

def get_user_setting(user_id, key, default=None):
    """Отримує налаштування користувача"""
    with _db() as con:
        # Проверяем существование таблицы
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_settings'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Проверяем структуру таблицы
            cursor = con.execute("PRAGMA table_info(user_settings)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Если колонки value нет, добавляем её
            if 'value' not in columns:
                try:
                    con.execute("ALTER TABLE user_settings ADD COLUMN value TEXT")
                    con.commit()
                except Exception as e:
                    print(f"[get_user_setting] error adding value column: {e}")
        else:
            # Создаем таблицу с правильной структурой
            con.execute("""
                CREATE TABLE user_settings (
                    user_id INTEGER,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            """)
            con.commit()
        
        # Пробуем получить значение
        try:
            row = con.execute("""
                SELECT value FROM user_settings 
                WHERE user_id = ? AND key = ?
            """, (user_id, key)).fetchone()
            return row[0] if row else default
        except Exception as e:
            # Если все еще ошибка, возможно старая структура
            print(f"[get_user_setting] error selecting: {e}, trying alternative...")
            try:
                # Пробуем старую структуру (если было key-value без user_id)
                row = con.execute("""
                    SELECT key FROM user_settings 
                    WHERE key = ?
                """, (key,)).fetchone()
                return row[0] if row else default
            except Exception:
                return default

def set_user_setting(user_id, key, value):
    """Встановлює налаштування користувача"""
    with _db() as con:
        # Проверяем существование таблицы
        cursor = con.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_settings'
        """)
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Проверяем структуру таблицы
            cursor = con.execute("PRAGMA table_info(user_settings)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Если колонки value нет, добавляем её
            if 'value' not in columns:
                try:
                    con.execute("ALTER TABLE user_settings ADD COLUMN value TEXT")
                    con.commit()
                except Exception as e:
                    print(f"[set_user_setting] error adding value column: {e}")
            
            # Если колонки user_id нет, добавляем её
            if 'user_id' not in columns:
                try:
                    con.execute("ALTER TABLE user_settings ADD COLUMN user_id INTEGER")
                    con.commit()
                except Exception as e:
                    print(f"[set_user_setting] error adding user_id column: {e}")
        else:
            # Создаем таблицу с правильной структурой
            con.execute("""
                CREATE TABLE user_settings (
                    user_id INTEGER,
                    key TEXT,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            """)
            con.commit()
        
        # Вставляем или обновляем значение
        try:
            con.execute("""
                INSERT OR REPLACE INTO user_settings (user_id, key, value)
                VALUES (?, ?, ?)
            """, (user_id, key, str(value)))
            con.commit()
        except Exception as e:
            print(f"[set_user_setting] error inserting: {e}")
            # Пробуем без user_id (старая структура)
            try:
                con.execute("""
                    INSERT OR REPLACE INTO user_settings (key, value)
                    VALUES (?, ?)
                """, (key, str(value)))
                con.commit()
            except Exception as e2:
                print(f"[set_user_setting] error with fallback: {e2}")

# =============================================================================
# Система заданий (Tasks/Quests)
# =============================================================================

def ensure_user_tasks_tables():
    """Создает таблицы для системы заданий если их нет"""
    with _db() as con:
        # Таблица заданий
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT NOT NULL,
                task_data TEXT,
                reward_amount REAL NOT NULL,
                reward_type TEXT DEFAULT 'balance',
                max_completions INTEGER,
                current_completions INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at INTEGER NOT NULL,
                expires_at INTEGER,
                created_by INTEGER,
                requirements TEXT
            )
        """)
        
        # Таблица выполнений заданий
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_task_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                completed_at INTEGER NOT NULL,
                reward_received REAL NOT NULL,
                proof_data TEXT,
                reverted INTEGER DEFAULT 0,
                reverted_at INTEGER,
                UNIQUE(task_id, user_id)
            )
        """)
        
        # Добавляем колонки для отката, если их нет
        try:
            con.execute("ALTER TABLE user_task_completions ADD COLUMN reverted INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            con.execute("ALTER TABLE user_task_completions ADD COLUMN reverted_at INTEGER")
        except Exception:
            pass
        
        con.commit()

def create_task(title, description, task_type, task_data, reward_amount, created_by, 
                reward_type='balance', max_completions=None, expires_at=None, requirements=None):
    """Создает новое задание"""
    import time
    import json
    ensure_user_tasks_tables()
    
    with _db() as con:
        task_data_json = json.dumps(task_data) if task_data else None
        requirements_json = json.dumps(requirements) if requirements else None
        
        cursor = con.execute("""
            INSERT INTO user_tasks 
            (title, description, task_type, task_data, reward_amount, reward_type, 
             max_completions, created_at, expires_at, created_by, requirements)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, task_type, task_data_json, reward_amount, reward_type,
              max_completions, int(time.time()), expires_at, created_by, requirements_json))
        con.commit()
        return cursor.lastrowid

def get_active_tasks(user_id=None):
    """Получает активные задания. Если указан user_id, показывает только те, которые пользователь еще не выполнил"""
    import time
    ensure_user_tasks_tables()
    
    with _db() as con:
        current_time = int(time.time())
        
        if user_id:
            # Получаем задания, которые пользователь еще не выполнял
            rows = con.execute("""
                SELECT t.id, t.title, t.description, t.task_type, t.task_data, 
                       t.reward_amount, t.reward_type, t.max_completions, t.current_completions,
                       t.status, t.created_at, t.expires_at, t.created_by, t.requirements
                FROM user_tasks t
                WHERE t.status = 'active'
                AND (t.expires_at IS NULL OR t.expires_at > ?)
                AND (t.max_completions IS NULL OR t.current_completions < t.max_completions)
                AND NOT EXISTS (
                    SELECT 1 FROM user_task_completions c 
                    WHERE c.task_id = t.id AND c.user_id = ?
                )
                ORDER BY t.created_at DESC
            """, (current_time, user_id)).fetchall()
        else:
            rows = con.execute("""
                SELECT id, title, description, task_type, task_data, 
                       reward_amount, reward_type, max_completions, current_completions,
                       status, created_at, expires_at, created_by, requirements
                FROM user_tasks
                WHERE status = 'active'
                AND (expires_at IS NULL OR expires_at > ?)
                AND (max_completions IS NULL OR current_completions < max_completions)
                ORDER BY created_at DESC
            """, (current_time,)).fetchall()
        
        import json
        result = []
        for row in rows:
            task_data = json.loads(row[4]) if row[4] else {}
            requirements = json.loads(row[13]) if row[13] else {}
            result.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'task_type': row[3],
                'task_data': task_data,
                'reward_amount': row[5],
                'reward_type': row[6],
                'max_completions': row[7],
                'current_completions': row[8],
                'status': row[9],
                'created_at': row[10],
                'expires_at': row[11],
                'created_by': row[12],
                'requirements': requirements
            })
        return result

def get_task_by_id(task_id):
    """Получает задание по ID"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        row = con.execute("""
            SELECT id, title, description, task_type, task_data, 
                   reward_amount, reward_type, max_completions, current_completions,
                   status, created_at, expires_at, created_by, requirements
            FROM user_tasks
            WHERE id = ?
        """, (task_id,)).fetchone()
        
        if not row:
            return None
        
        import json
        task_data = json.loads(row[4]) if row[4] else {}
        requirements = json.loads(row[13]) if row[13] else {}
        
        return {
            'id': row[0],
            'title': row[1],
            'description': row[2],
            'task_type': row[3],
            'task_data': task_data,
            'reward_amount': row[5],
            'reward_type': row[6],
            'max_completions': row[7],
            'current_completions': row[8],
            'status': row[9],
            'created_at': row[10],
            'expires_at': row[11],
            'created_by': row[12],
            'requirements': requirements
        }

def complete_task(task_id, user_id, reward_amount, proof_data=None):
    """Отмечает задание как выполненное пользователем"""
    import time
    import json
    ensure_user_tasks_tables()
    
    with _db() as con:
        # Проверяем, не выполнял ли пользователь уже это задание
        existing = con.execute("""
            SELECT id FROM user_task_completions 
            WHERE task_id = ? AND user_id = ?
        """, (task_id, user_id)).fetchone()
        
        if existing:
            return False  # Уже выполнено
        
        # Добавляем запись о выполнении
        proof_json = json.dumps(proof_data) if proof_data else None
        con.execute("""
            INSERT INTO user_task_completions 
            (task_id, user_id, completed_at, reward_received, proof_data)
            VALUES (?, ?, ?, ?, ?)
        """, (task_id, user_id, int(time.time()), reward_amount, proof_json))
        
        # Увеличиваем счетчик выполнений
        con.execute("""
            UPDATE user_tasks 
            SET current_completions = current_completions + 1
            WHERE id = ?
        """, (task_id,))
        
        con.commit()
        return True

def get_user_task_completions(user_id, limit=50):
    """Получает историю выполненных заданий пользователя"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        rows = con.execute("""
            SELECT c.id, c.task_id, c.completed_at, c.reward_received, c.proof_data,
                   t.title, t.task_type, t.task_data, c.reverted
            FROM user_task_completions c
            JOIN user_tasks t ON c.task_id = t.id
            WHERE c.user_id = ?
            ORDER BY c.completed_at DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        
        import json
        result = []
        for row in rows:
            proof_data = json.loads(row[4]) if row[4] else {}
            task_data = json.loads(row[7]) if row[7] else {}
            result.append({
                'id': row[0],
                'task_id': row[1],
                'completed_at': row[2],
                'reward_received': row[3],
                'proof_data': proof_data,
                'task_title': row[5],
                'task_type': row[6],
                'task_data': task_data,
                'reverted': bool(row[8]) if len(row) > 8 else False
            })
        return result

def get_all_active_task_completions():
    """Получает все активные выполнения заданий для проверки"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        rows = con.execute("""
            SELECT c.id, c.task_id, c.user_id, c.completed_at, c.reward_received, 
                   c.proof_data, t.task_type, t.task_data, t.title, c.reverted
            FROM user_task_completions c
            JOIN user_tasks t ON c.task_id = t.id
            WHERE c.reverted = 0 OR c.reverted IS NULL
            ORDER BY c.completed_at DESC
        """).fetchall()
        
        import json
        result = []
        for row in rows:
            proof_data = json.loads(row[5]) if row[5] else {}
            task_data = json.loads(row[7]) if row[7] else {}
            result.append({
                'id': row[0],
                'task_id': row[1],
                'user_id': row[2],
                'completed_at': row[3],
                'reward_received': row[4],
                'proof_data': proof_data,
                'task_type': row[6],
                'task_data': task_data,
                'task_title': row[8],
                'reverted': bool(row[9]) if len(row) > 9 else False
            })
        return result

def revert_task_completion(completion_id, user_id, task_id, reward_amount):
    """Откатывает выполнение задания и забирает награду"""
    ensure_user_tasks_tables()
    import time
    
    with _db() as con:
        # Помечаем выполнение как откатанное
        con.execute("""
            UPDATE user_task_completions 
            SET reverted = 1, reverted_at = ?
            WHERE id = ? AND user_id = ?
        """, (int(time.time()), completion_id, user_id))
        
        # Уменьшаем счетчик выполнений задания
        con.execute("""
            UPDATE user_tasks 
            SET current_completions = MAX(0, current_completions - 1)
            WHERE id = ?
        """, (task_id,))
        
        con.commit()
        return True

def get_user_tasks_stats(user_id):
    """Получает статистику заданий пользователя"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        # Количество выполненных заданий
        completed_count = con.execute("""
            SELECT COUNT(*) FROM user_task_completions WHERE user_id = ?
        """, (user_id,)).fetchone()[0] or 0
        
        # Общая сумма наград
        total_rewards = con.execute("""
            SELECT COALESCE(SUM(reward_received), 0) 
            FROM user_task_completions WHERE user_id = ?
        """, (user_id,)).fetchone()[0] or 0.0
        
        return {
            'completed_count': completed_count,
            'total_rewards': total_rewards
        }

def get_all_tasks(status=None):
    """Получает все задания (для админки)"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        if status:
            rows = con.execute("""
                SELECT id, title, description, task_type, task_data, 
                       reward_amount, reward_type, max_completions, current_completions,
                       status, created_at, expires_at, created_by, requirements
                FROM user_tasks
                WHERE status = ?
                ORDER BY created_at DESC
            """, (status,)).fetchall()
        else:
            rows = con.execute("""
                SELECT id, title, description, task_type, task_data, 
                       reward_amount, reward_type, max_completions, current_completions,
                       status, created_at, expires_at, created_by, requirements
                FROM user_tasks
                ORDER BY created_at DESC
            """).fetchall()
        
        import json
        result = []
        for row in rows:
            task_data = json.loads(row[4]) if row[4] else {}
            requirements = json.loads(row[13]) if row[13] else {}
            result.append({
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'task_type': row[3],
                'task_data': task_data,
                'reward_amount': row[5],
                'reward_type': row[6],
                'max_completions': row[7],
                'current_completions': row[8],
                'status': row[9],
                'created_at': row[10],
                'expires_at': row[11],
                'created_by': row[12],
                'requirements': requirements
            })
        return result

def update_task(task_id, title=None, description=None, task_data=None, reward_amount=None,
                max_completions=None, expires_at=None, status=None, requirements=None):
    """Обновляет задание"""
    import json
    ensure_user_tasks_tables()
    
    with _db() as con:
        updates = []
        values = []
        
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if task_data is not None:
            updates.append("task_data = ?")
            values.append(json.dumps(task_data))
        if reward_amount is not None:
            updates.append("reward_amount = ?")
            values.append(reward_amount)
        if max_completions is not None:
            updates.append("max_completions = ?")
            values.append(max_completions)
        if expires_at is not None:
            updates.append("expires_at = ?")
            values.append(expires_at)
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if requirements is not None:
            updates.append("requirements = ?")
            values.append(json.dumps(requirements))
        
        if not updates:
            return False
        
        values.append(task_id)
        con.execute(f"""
            UPDATE user_tasks 
            SET {', '.join(updates)}
            WHERE id = ?
        """, tuple(values))
        con.commit()
        return True

def delete_task(task_id):
    """Удаляет задание"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        con.execute("DELETE FROM user_tasks WHERE id = ?", (task_id,))
        con.commit()
        return True

def pause_task(task_id):
    """Приостанавливает задание"""
    return update_task(task_id, status='paused')

def activate_task(task_id):
    """Активирует задание"""
    return update_task(task_id, status='active')

def get_task_completions_stats(task_id):
    """Получает статистику выполнения задания"""
    ensure_user_tasks_tables()
    
    with _db() as con:
        # Количество выполнений
        count = con.execute("""
            SELECT COUNT(*) FROM user_task_completions WHERE task_id = ?
        """, (task_id,)).fetchone()[0] or 0
        
        # Список пользователей, выполнивших задание
        users = con.execute("""
            SELECT user_id, completed_at, reward_received
            FROM user_task_completions
            WHERE task_id = ?
            ORDER BY completed_at DESC
            LIMIT 50
        """, (task_id,)).fetchall()
        
        return {
            'completion_count': count,
            'users': users
        }

def check_deposit_tasks(user_id: int, deposit_amount: float):
    """Проверяет и выполняет задания типа deposit при пополнении баланса"""
    ensure_user_tasks_tables()
    
    # Получаем активные задания типа deposit, которые пользователь еще не выполнял
    active_tasks = get_active_tasks(user_id)
    deposit_tasks = [task for task in active_tasks if task['task_type'] == 'deposit']
    
    completed_tasks = []
    
    for task in deposit_tasks:
        task_data = task.get('task_data', {})
        required_amount = task_data.get('amount', 0)
        
        # Проверяем, что сумма депозита >= требуемой суммы
        if deposit_amount >= required_amount:
            # Выполняем задание
            if complete_task(task['id'], user_id, task['reward_amount'], 
                           proof_data={'deposit_amount': deposit_amount, 'required_amount': required_amount}):
                completed_tasks.append(task)
                
                # Добавляем награду на баланс
                if task['reward_type'] == 'balance':
                    add_balance(user_id, task['reward_amount'], reason='task_completion',
                              details=f'Завдання: {task["title"]}')
    
    return completed_tasks

def check_buy_tree_tasks(user_id: int, tree_type: str):
    """Проверяет и выполняет задания типа buy_tree при покупке дерева"""
    ensure_user_tasks_tables()
    
    active_tasks = get_active_tasks(user_id)
    buy_tree_tasks = [task for task in active_tasks if task['task_type'] == 'buy_tree']
    
    completed_tasks = []
    
    for task in buy_tree_tasks:
        task_data = task.get('task_data', {})
        required_tree_type = task_data.get('tree_type', '')
        
        # Проверяем, что тип дерева совпадает
        if tree_type == required_tree_type:
            if complete_task(task['id'], user_id, task['reward_amount'],
                           proof_data={'tree_type': tree_type}):
                completed_tasks.append(task)
                
                if task['reward_type'] == 'balance':
                    add_balance(user_id, task['reward_amount'], reason='task_completion',
                              details=f'Завдання: {task["title"]}')
    
    return completed_tasks

def check_harvest_tasks(user_id: int):
    """Проверяет и выполняет задания типа harvest при сборе урожая"""
    ensure_user_tasks_tables()
    
    active_tasks = get_active_tasks(user_id)
    harvest_tasks = [task for task in active_tasks if task['task_type'] == 'harvest']
    
    completed_tasks = []
    
    # Подсчитываем количество сборов урожая из истории
    harvest_count = 0
    with _db() as con:
        harvest_count = con.execute("""
            SELECT COUNT(*) FROM garden_transactions 
            WHERE user_id = ? AND type = 'harvest'
        """, (user_id,)).fetchone()[0] or 0
    
    for task in harvest_tasks:
        task_data = task.get('task_data', {})
        required_count = task_data.get('count', 0)
        
        # Проверяем, что количество сборов >= требуемого
        if harvest_count >= required_count:
            if complete_task(task['id'], user_id, task['reward_amount'],
                           proof_data={'harvest_count': harvest_count, 'required_count': required_count}):
                completed_tasks.append(task)
                
                if task['reward_type'] == 'balance':
                    add_balance(user_id, task['reward_amount'], reason='task_completion',
                              details=f'Завдання: {task["title"]}')
    
    return completed_tasks

def check_sell_fruits_tasks(user_id: int, sell_amount: float):
    """Проверяет и выполняет задания типа sell_fruits при продаже фруктов"""
    ensure_user_tasks_tables()
    
    active_tasks = get_active_tasks(user_id)
    sell_fruits_tasks = [task for task in active_tasks if task['task_type'] == 'sell_fruits']
    
    completed_tasks = []
    
    # Получаем общую сумму продаж пользователя
    total_sold = 0.0
    with _db() as con:
        result = con.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM garden_transactions 
            WHERE user_id = ? AND type = 'sale'
        """, (user_id,)).fetchone()
        total_sold = float(result[0]) if result else 0.0
    
    for task in sell_fruits_tasks:
        task_data = task.get('task_data', {})
        required_amount = task_data.get('amount', 0)
        
        # Проверяем, что общая сумма продаж >= требуемой
        if total_sold >= required_amount:
            if complete_task(task['id'], user_id, task['reward_amount'],
                           proof_data={'total_sold': total_sold, 'required_amount': required_amount}):
                completed_tasks.append(task)
                
                if task['reward_type'] == 'balance':
                    add_balance(user_id, task['reward_amount'], reason='task_completion',
                              details=f'Завдання: {task["title"]}')
    
    return completed_tasks

def check_invite_users_tasks(user_id: int):
    """Проверяет и выполняет задания типа invite_users при регистрации реферала"""
    ensure_user_tasks_tables()
    
    active_tasks = get_active_tasks(user_id)
    invite_tasks = [task for task in active_tasks if task['task_type'] == 'invite_users']
    
    completed_tasks = []
    
    # Получаем количество рефералов пользователя
    ref_count = get_ref_count(user_id)
    
    for task in invite_tasks:
        task_data = task.get('task_data', {})
        required_count = task_data.get('count', 0)
        
        # Проверяем, что количество рефералов >= требуемого
        if ref_count >= required_count:
            if complete_task(task['id'], user_id, task['reward_amount'],
                           proof_data={'ref_count': ref_count, 'required_count': required_count}):
                completed_tasks.append(task)
                
                if task['reward_type'] == 'balance':
                    add_balance(user_id, task['reward_amount'], reason='task_completion',
                              details=f'Завдання: {task["title"]}')
    
    return completed_tasks

# =============================================================================
# СИСТЕМА ІНВЕСТИЦІЙНИЙ ОФІС (INVESTMENT OFFICE)
# =============================================================================

def ensure_office_tables():
    """Створює таблиці для системи інвестиційного офісу"""
    with _db() as con:
        # Таблиця офисов пользователей
        con.execute("""
            CREATE TABLE IF NOT EXISTS investment_offices (
                user_id INTEGER PRIMARY KEY,
                total_profit REAL DEFAULT 0.0,
                available_profit REAL DEFAULT 0.0,
                last_profit_calculation INTEGER,
                created_at INTEGER NOT NULL,
                last_withdraw_at INTEGER
            )
        """)
        
        # Таблиця работников офиса
        con.execute("""
            CREATE TABLE IF NOT EXISTS office_employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                employee_type TEXT NOT NULL,
                hired_at INTEGER NOT NULL,
                last_profit_at INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблиця настроек офиса (для админа)
        con.execute("""
            CREATE TABLE IF NOT EXISTS office_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Дефолтные настройки
        defaults = [
            ('office_enabled', '1'),
            ('profit_calculation_interval_hours', '24'),  # Интервал расчета прибыли
        ]
        for k, v in defaults:
            con.execute("INSERT OR IGNORE INTO office_settings (key, value) VALUES (?, ?)", (k, v))
        
        con.commit()

ensure_office_tables()

def get_user_office(user_id: int):
    """Получает информацию об офисе пользователя"""
    ensure_office_tables()
    with _db() as con:
        row = con.execute("""
            SELECT user_id, total_profit, available_profit, last_profit_calculation, created_at, last_withdraw_at
            FROM investment_offices WHERE user_id = ?
        """, (user_id,)).fetchone()
        if not row:
            # Создаем офис если его нет
            import time
            con.execute("""
                INSERT INTO investment_offices (user_id, created_at)
                VALUES (?, ?)
            """, (user_id, int(time.time())))
            con.commit()
            return {
                'user_id': user_id,
                'total_profit': 0.0,
                'available_profit': 0.0,
                'last_profit_calculation': None,
                'created_at': int(time.time()),
                'last_withdraw_at': None
            }
        return {
            'user_id': row[0],
            'total_profit': float(row[1] or 0.0),
            'available_profit': float(row[2] or 0.0),
            'last_profit_calculation': row[3],
            'created_at': row[4],
            'last_withdraw_at': row[5]
        }

def get_user_office_employees(user_id: int):
    """Получает список активных работников офиса пользователя"""
    ensure_office_tables()
    with _db() as con:
        rows = con.execute("""
            SELECT id, employee_type, hired_at, last_profit_at
            FROM office_employees
            WHERE user_id = ? AND is_active = 1
            ORDER BY hired_at ASC
        """, (user_id,)).fetchall()
        return [
            {
                'id': r[0],
                'type': r[1],
                'hired_at': r[2],
                'last_profit_at': r[3]
            }
            for r in rows
        ]

def hire_office_employee(user_id: int, employee_type: str):
    """Нанять работника в офис"""
    ensure_office_tables()
    import time
    from office_models import get_employee_max_count
    
    with _db() as con:
        # Проверяем текущее количество работников этого типа
        existing_count = con.execute("""
            SELECT COUNT(*) FROM office_employees
            WHERE user_id = ? AND employee_type = ? AND is_active = 1
        """, (user_id, employee_type)).fetchone()[0]
        
        # Проверяем лимит для этого типа работника
        max_count = get_employee_max_count(employee_type)
        if existing_count >= max_count:
            from office_models import get_employee_name_uk
            employee_name = get_employee_name_uk(employee_type)
            return False, f"Ви вже найняли максимальну кількість {employee_name.lower()} ({max_count} шт.)"
        
        # Создаем офис если его нет
        con.execute("""
            INSERT OR IGNORE INTO investment_offices (user_id, created_at)
            VALUES (?, ?)
        """, (user_id, int(time.time())))
        
        # Добавляем работника
        con.execute("""
            INSERT INTO office_employees (user_id, employee_type, hired_at, last_profit_at, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_id, employee_type, int(time.time()), int(time.time())))
        con.commit()
        return True, "Працівника успішно найнято"

def calculate_office_profit(user_id: int):
    """Рассчитывает прибыль офиса на основе работников"""
    ensure_office_tables()
    import time
    from office_models import get_employee_daily_profit
    
    office = get_user_office(user_id)
    employees = get_user_office_employees(user_id)
    
    if not employees:
        return 0.0
    
    now = int(time.time())
    last_calc = office.get('last_profit_calculation') or office.get('created_at') or now
    
    # Рассчитываем прибыль за прошедшее время (в днях)
    hours_passed = (now - last_calc) / 3600.0
    days_passed = hours_passed / 24.0
    
    total_profit = 0.0
    with _db() as con:
        for emp in employees:
            daily_profit = get_employee_daily_profit(emp['type'])
            profit = daily_profit * days_passed
            total_profit += profit
            
            # Обновляем время последнего расчета прибыли для работника
            con.execute("""
                UPDATE office_employees
                SET last_profit_at = ?
                WHERE id = ?
            """, (now, emp['id']))
        
        # Обновляем офис
        new_available = office['available_profit'] + total_profit
        new_total = office['total_profit'] + total_profit
        
        con.execute("""
            UPDATE investment_offices
            SET available_profit = ?, total_profit = ?, last_profit_calculation = ?
            WHERE user_id = ?
        """, (new_available, new_total, now, user_id))
        con.commit()
    
    return total_profit

def withdraw_office_profit(user_id: int):
    """Забрать прибыль из офиса (увольняет всех работников)"""
    ensure_office_tables()
    import time
    with _db() as con:
        office = get_user_office(user_id)
        profit = office['available_profit']
        
        if profit <= 0:
            return False, 0.0, "Немає доступного прибутку для зняття"
        
        # Увольняем всех работников
        con.execute("""
            UPDATE office_employees
            SET is_active = 0
            WHERE user_id = ? AND is_active = 1
        """, (user_id,))
        
        # Обнуляем доступную прибыль и обновляем время последнего снятия
        con.execute("""
            UPDATE investment_offices
            SET available_profit = 0.0, last_withdraw_at = ?
            WHERE user_id = ?
        """, (int(time.time()), user_id))
        con.commit()
        
        return True, profit, "Прибуток успішно зараховано"

def get_office_settings():
    """Получает настройки офиса"""
    ensure_office_tables()
    with _db() as con:
        rows = con.execute("SELECT key, value FROM office_settings").fetchall()
        return {row[0]: row[1] for row in rows}

def set_office_setting(key: str, value: str):
    """Устанавливает настройку офиса"""
    ensure_office_tables()
    with _db() as con:
        con.execute("INSERT OR REPLACE INTO office_settings (key, value) VALUES (?, ?)", (key, str(value)))
        con.commit()

# =============================================================================
# СИСТЕМА РОЗЫГРЫШЕЙ (GIVEAWAYS)
# =============================================================================

def ensure_giveaways_tables():
    """Створює таблиці для системи розыгрышей"""
    with _db() as con:
        # Таблиця розыгрышей
        con.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                prize_type TEXT NOT NULL,
                prize_value TEXT NOT NULL,
                prize_extra TEXT,
                required_reactions INTEGER DEFAULT 0,
                channel_id INTEGER,
                post_message_id INTEGER,
                started_post_message_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_by INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                started_at INTEGER,
                completed_at INTEGER,
                winner_id INTEGER,
                winner_comment_id INTEGER,
                reactions_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0
            )
        """)
        
        # Міграція: додаємо колонку started_post_message_id якщо її немає
        try:
            con.execute("ALTER TABLE giveaways ADD COLUMN started_post_message_id INTEGER")
            con.commit()
        except Exception:
            # Колонка вже існує, ігноруємо помилку
            pass
        
        # Міграція: додаємо колонку winners_count якщо її немає
        try:
            con.execute("ALTER TABLE giveaways ADD COLUMN winners_count INTEGER DEFAULT 1")
            con.commit()
        except Exception:
            # Колонка вже існує, ігноруємо помилку
            pass
        
        # Міграція: додаємо колонку game_type (777 або blackjack)
        try:
            con.execute("ALTER TABLE giveaways ADD COLUMN game_type TEXT DEFAULT '777'")
            con.commit()
        except Exception:
            # Колонка вже існує, ігноруємо помилку
            pass
        
        # Таблиця участников розыгрышей
        con.execute("""
            CREATE TABLE IF NOT EXISTS giveaway_participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                comment_id INTEGER,
                reaction_count INTEGER DEFAULT 0,
                participated_at INTEGER NOT NULL,
                random_number INTEGER,
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE,
                UNIQUE(giveaway_id, user_id)
            )
        """)
        
        # Таблиця для блекджека
        con.execute("""
            CREATE TABLE IF NOT EXISTS blackjack_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giveaway_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                cards TEXT NOT NULL,
                score INTEGER NOT NULL,
                status TEXT DEFAULT 'playing',
                last_action_at INTEGER NOT NULL,
                FOREIGN KEY (giveaway_id) REFERENCES giveaways(id) ON DELETE CASCADE,
                UNIQUE(giveaway_id, user_id)
            )
        """)
        con.commit()

# Автоматически создаем таблицы при импорте
ensure_giveaways_tables()

def create_giveaway(title: str, prize_type: str, prize_value: str, prize_extra: str = None, 
                   required_reactions: int = 0, created_by: int = None, winners_count: int = 1, 
                   game_type: str = '777') -> int:
    """Створює новий розыгрыш"""
    import time
    ensure_giveaways_tables()
    with _db() as con:
        cursor = con.execute("""
            INSERT INTO giveaways (title, prize_type, prize_value, prize_extra, required_reactions, 
                                 created_by, created_at, status, winners_count, game_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (title, prize_type, prize_value, prize_extra or '', required_reactions, 
              created_by, int(time.time()), max(1, int(winners_count)), game_type))
        con.commit()
        return cursor.lastrowid

def get_giveaway(giveaway_id: int):
    """Отримує інформацію про розыгрыш"""
    ensure_giveaways_tables()
    with _db() as con:
        row = con.execute("""
            SELECT id, title, prize_type, prize_value, prize_extra, required_reactions,
                   channel_id, post_message_id, started_post_message_id, status, created_by, created_at, started_at,
                   completed_at, winner_id, winner_comment_id, reactions_count, comments_count, winners_count, game_type
            FROM giveaways WHERE id = ?
        """, (giveaway_id,)).fetchone()
        if not row:
            return None
        return {
            'id': row[0],
            'title': row[1],
            'prize_type': row[2],
            'prize_value': row[3],
            'prize_extra': row[4],
            'required_reactions': row[5],
            'channel_id': row[6],
            'post_message_id': row[7],
            'started_post_message_id': row[8],
            'status': row[9],
            'created_by': row[10],
            'created_at': row[11],
            'started_at': row[12],
            'completed_at': row[13],
            'winner_id': row[14],
            'winner_comment_id': row[15],
            'reactions_count': row[16],
            'comments_count': row[17],
            'winners_count': row[18] if len(row) > 18 else 1,
            'game_type': (row[19] if len(row) > 19 and row[19] is not None else '777')
        }

def update_giveaway_status(giveaway_id: int, status: str, **kwargs):
    """Оновлює статус розыгрыша та інші поля"""
    ensure_giveaways_tables()
    import time
    with _db() as con:
        updates = ["status = ?"]
        params = [status]
        
        if status == 'active' and 'channel_id' in kwargs and 'post_message_id' in kwargs:
            updates.append("channel_id = ?")
            updates.append("post_message_id = ?")
            updates.append("started_at = ?")
            params.extend([kwargs['channel_id'], kwargs['post_message_id'], int(time.time())])
        
        if 'started_post_message_id' in kwargs:
            updates.append("started_post_message_id = ?")
            params.append(kwargs['started_post_message_id'])
        
        if status == 'completed' and 'winner_id' in kwargs:
            updates.append("winner_id = ?")
            updates.append("completed_at = ?")
            params.extend([kwargs['winner_id'], int(time.time())])
            if 'winner_comment_id' in kwargs:
                updates.append("winner_comment_id = ?")
                params.append(kwargs['winner_comment_id'])
        
        if 'reactions_count' in kwargs:
            updates.append("reactions_count = ?")
            params.append(kwargs['reactions_count'])
        
        if 'comments_count' in kwargs:
            updates.append("comments_count = ?")
            params.append(kwargs['comments_count'])
        
        params.append(giveaway_id)
        con.execute(f"UPDATE giveaways SET {', '.join(updates)} WHERE id = ?", params)
        con.commit()

def add_giveaway_participant(giveaway_id: int, user_id: int, comment_id: int = None, 
                            random_number: int = None, emoji_count: int = None):
    """Додає учасника до розыгрыша или обновляет счетчик эмодзи
    
    Если emoji_count указан, увеличивает reaction_count на это значение.
    Если участник не существует, создает его с reaction_count = emoji_count.
    """
    ensure_giveaways_tables()
    import time
    with _db() as con:
        try:
            # Проверяем, существует ли уже участник
            existing = con.execute("""
                SELECT reaction_count FROM giveaway_participants 
                WHERE giveaway_id = ? AND user_id = ?
            """, (giveaway_id, user_id)).fetchone()
            
            if existing:
                # Участник существует - обновляем счетчик эмодзи
                current_count = existing[0] or 0
                if emoji_count is not None:
                    new_count = current_count + emoji_count
                    con.execute("""
                        UPDATE giveaway_participants 
                        SET reaction_count = ?, comment_id = ?, participated_at = ?
                        WHERE giveaway_id = ? AND user_id = ?
                    """, (new_count, comment_id, int(time.time()), giveaway_id, user_id))
                elif random_number is not None:
                    # Для обратной совместимости (старая логика)
                    con.execute("""
                        UPDATE giveaway_participants 
                        SET random_number = ?, comment_id = ?, participated_at = ?
                        WHERE giveaway_id = ? AND user_id = ?
                    """, (random_number, comment_id, int(time.time()), giveaway_id, user_id))
            else:
                # Новый участник
                reaction_count = emoji_count if emoji_count is not None else 0
                con.execute("""
                    INSERT INTO giveaway_participants 
                    (giveaway_id, user_id, comment_id, participated_at, random_number, reaction_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (giveaway_id, user_id, comment_id, int(time.time()), random_number, reaction_count))
            con.commit()
        except Exception as e:
            print(f"[ERROR] Помилка додавання учасника: {e}")
            import traceback
            traceback.print_exc()

def get_giveaway_participants(giveaway_id: int):
    """Отримує список учасників розыгрыша"""
    ensure_giveaways_tables()
    with _db() as con:
        rows = con.execute("""
            SELECT user_id, comment_id, participated_at, random_number, reaction_count
            FROM giveaway_participants
            WHERE giveaway_id = ?
            ORDER BY participated_at ASC
        """, (giveaway_id,)).fetchall()
        return [{
            'user_id': r[0],
            'comment_id': r[1],
            'participated_at': r[2],
            'random_number': r[3],
            'reaction_count': r[4] or 0  # emoji_count хранится в reaction_count
        } for r in rows]

def get_user_emoji_count(giveaway_id: int, user_id: int):
    """Получает текущее количество эмодзи пользователя в розыгрыше"""
    ensure_giveaways_tables()
    with _db() as con:
        row = con.execute("""
            SELECT reaction_count FROM giveaway_participants
            WHERE giveaway_id = ? AND user_id = ?
        """, (giveaway_id, user_id)).fetchone()
        return (row[0] or 0) if row else 0

def get_giveaway_stats(giveaway_id: int):
    """Отримує статистику розыгрыша"""
    ensure_giveaways_tables()
    giveaway = get_giveaway(giveaway_id)
    if not giveaway:
        return None
    
    participants = get_giveaway_participants(giveaway_id)
    
    return {
        'giveaway': giveaway,
        'participants_count': len(participants),
        'participants': participants,
        'reactions_collected': giveaway['reactions_count'],
        'reactions_needed': giveaway['required_reactions'],
        'reactions_progress': (giveaway['reactions_count'] / giveaway['required_reactions'] * 100) if giveaway['required_reactions'] > 0 else 0
    }

def get_all_giveaways(status: str = None, limit: int = 50):
    """Отримує список всіх розыгрышей з опціональною фільтрацією за статусом"""
    ensure_giveaways_tables()
    with _db() as con:
        if status:
            rows = con.execute("""
                SELECT id, title, prize_type, prize_value, prize_extra, status, created_at, 
                       reactions_count, comments_count, winner_id, channel_id, post_message_id,
                       started_post_message_id, required_reactions
                FROM giveaways
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit)).fetchall()
        else:
            rows = con.execute("""
                SELECT id, title, prize_type, prize_value, prize_extra, status, created_at,
                       reactions_count, comments_count, winner_id, channel_id, post_message_id,
                       started_post_message_id, required_reactions
                FROM giveaways
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        
        return [{
            'id': r[0],
            'title': r[1],
            'prize_type': r[2],
            'prize_value': r[3],
            'prize_extra': r[4],
            'status': r[5],
            'created_at': r[6],
            'reactions_count': r[7],
            'comments_count': r[8],
            'winner_id': r[9],
            'channel_id': r[10],
            'post_message_id': r[11],
            'started_post_message_id': r[12],
            'required_reactions': r[13]
        } for r in rows]

def get_active_giveaways():
    """Отримує список активних розыгрышей"""
    return get_all_giveaways(status='active')

def cancel_giveaway(giveaway_id: int):
    """Скасовує розыгрыш"""
    update_giveaway_status(giveaway_id, 'cancelled')

def delete_giveaway(giveaway_id: int):
    """Повністю видаляє розыгрыш з бази даних"""
    with _db() as con:
        # Сначала удаляем участников
        con.execute("DELETE FROM giveaway_participants WHERE giveaway_id = ?", (giveaway_id,))
        # Затем удаляем сам розыгрыш
        con.execute("DELETE FROM giveaways WHERE id = ?", (giveaway_id,))
        con.commit()

# ========== УПРАВЛЕНИЕ ДОСТУПНОСТЬЮ КНОПОК ==========

def ensure_disabled_buttons_table():
    """Создает таблицу для хранения отключенных кнопок"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS disabled_buttons (
                button_id TEXT PRIMARY KEY,
                button_name TEXT NOT NULL,
                is_disabled INTEGER DEFAULT 1,
                message TEXT DEFAULT 'Ця функція тимчасово недоступна. Система розробляється.',
                updated_at INTEGER DEFAULT 0
            )
        """)
        con.commit()

ensure_disabled_buttons_table()

def set_button_disabled(button_id: str, button_name: str, message: str = None, is_disabled: bool = True):
    """Включает или отключает кнопку"""
    ensure_disabled_buttons_table()
    import time
    default_message = 'Ця функція тимчасово недоступна. Система розробляється.'
    
    with _db() as con:
        con.execute("""
            INSERT OR REPLACE INTO disabled_buttons (button_id, button_name, is_disabled, message, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (button_id, button_name, 1 if is_disabled else 0, message or default_message, int(time.time())))
        con.commit()
    return True

def is_button_disabled(button_id: str) -> bool:
    """Проверяет, отключена ли кнопка"""
    ensure_disabled_buttons_table()
    with _db() as con:
        row = con.execute("""
            SELECT is_disabled FROM disabled_buttons WHERE button_id = ?
        """, (button_id,)).fetchone()
        if row:
            return bool(row[0])
    return False

def get_button_message(button_id: str) -> str:
    """Получает сообщение для отключенной кнопки"""
    ensure_disabled_buttons_table()
    with _db() as con:
        row = con.execute("""
            SELECT message FROM disabled_buttons WHERE button_id = ?
        """, (button_id,)).fetchone()
        if row and row[0]:
            return row[0]
    return 'Ця функція тимчасово недоступна. Система розробляється.'

def get_button_info(button_id: str):
    """Получает полную информацию о кнопке"""
    ensure_disabled_buttons_table()
    with _db() as con:
        row = con.execute("""
            SELECT button_id, button_name, is_disabled, message, updated_at
            FROM disabled_buttons WHERE button_id = ?
        """, (button_id,)).fetchone()
        if row:
            return {
                'button_id': row[0],
                'button_name': row[1],
                'is_disabled': bool(row[2]),
                'message': row[3],
                'updated_at': row[4]
            }
    return None

def get_all_disabled_buttons():
    """Получает список всех кнопок с их статусом"""
    ensure_disabled_buttons_table()
    with _db() as con:
        rows = con.execute("""
            SELECT button_id, button_name, is_disabled, message, updated_at
            FROM disabled_buttons
            ORDER BY button_name
        """).fetchall()
        return [
            {
                'button_id': r[0],
                'button_name': r[1],
                'is_disabled': bool(r[2]),
                'message': r[3],
                'updated_at': r[4]
            }
            for r in rows
        ]

def delete_button_config(button_id: str):
    """Удаляет конфигурацию кнопки (возвращает кнопку в работу)"""
    ensure_disabled_buttons_table()
    with _db() as con:
        con.execute("DELETE FROM disabled_buttons WHERE button_id = ?", (button_id,))
        con.commit()
    return True

# ==========================
# СИСТЕМА ПІДТРИМКИ / ТІКЕТИ
# ==========================

SUPPORT_ALLOWED_STATUSES = {'pending', 'answered', 'closed', 'open', 'escalated'}
DEFAULT_SUPPORT_STATUS = 'pending'
SUPPORT_ALLOWED_CATEGORIES = {
    'general',
    'deposits',
    'withdrawals',
    'garden',
    'gift',
    'technical',
    'verification'
}
DEFAULT_SUPPORT_CATEGORY = 'general'

def _normalize_support_status(status: str):
    if not status:
        return None
    status = str(status).strip().lower()
    return status if status in SUPPORT_ALLOWED_STATUSES else None

def _normalize_support_category(category: str):
    if not category:
        return DEFAULT_SUPPORT_CATEGORY
    category = str(category).strip().lower()
    if category not in SUPPORT_ALLOWED_CATEGORIES:
        return DEFAULT_SUPPORT_CATEGORY
    return category

def _serialize_meta(meta):
    if meta is None:
        return None
    if isinstance(meta, str):
        return meta
    try:
        return json.dumps(meta, ensure_ascii=False)
    except Exception:
        return json.dumps({'value': str(meta)}, ensure_ascii=False)

def _parse_meta(value):
    if not value:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value

def _support_ticket_row_to_dict(row):
    if row is None:
        return None
    data = dict(row)
    int_fields = ['id', 'user_id', 'priority', 'assigned_admin_id', 'user_unread_count', 'admin_unread_count']
    ts_fields = ['created_at', 'updated_at', 'last_message_at', 'closed_at', 'last_user_reply_at', 'last_admin_reply_at']
    for key in int_fields:
        if key in data and data[key] is not None:
            try:
                data[key] = int(data[key])
            except (TypeError, ValueError):
                pass
    for key in ts_fields:
        if key in data and data[key] is not None:
            try:
                data[key] = int(data[key])
            except (TypeError, ValueError):
                pass
    if 'balance_delta' in data and data['balance_delta'] is not None:
        try:
            data['balance_delta'] = float(data['balance_delta'])
        except (TypeError, ValueError):
            data['balance_delta'] = 0.0
    if 'meta' in data:
        data['meta'] = _parse_meta(data['meta'])
    if 'last_message_body' in data:
        data['last_message_preview'] = data.pop('last_message_body')
    if 'last_message_sender' in data:
        data['last_message_sender'] = data['last_message_sender']
    return data

def _support_message_row_to_dict(row):
    if row is None:
        return None
    data = dict(row)
    for key in ['id', 'ticket_id', 'sender_id']:
        if key in data and data[key] is not None:
            try:
                data[key] = int(data[key])
            except (TypeError, ValueError):
                pass
    if 'created_at' in data and data['created_at'] is not None:
        try:
            data['created_at'] = int(data['created_at'])
        except (TypeError, ValueError):
            pass
    data['is_internal'] = bool(data.get('is_internal'))
    if 'meta' in data:
        data['meta'] = _parse_meta(data['meta'])
    return data

def get_support_ticket(ticket_id: int):
    ensure_support_tables()
    with _db() as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""
            SELECT t.*, u.user_name AS user_name,
                   (SELECT body FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_body,
                   (SELECT sender_role FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_sender
            FROM support_tickets t
            LEFT JOIN users u ON u.user_id = t.user_id
            WHERE t.id = ?
        """, (ticket_id,)).fetchone()
        return _support_ticket_row_to_dict(row)

def get_support_message(message_id: int):
    ensure_support_tables()
    with _db() as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""
            SELECT id, ticket_id, sender_id, sender_role, body, created_at, is_internal, meta
            FROM support_messages
            WHERE id = ?
        """, (message_id,)).fetchone()
        return _support_message_row_to_dict(row)

def get_support_messages(ticket_id: int, limit: int = 100, offset: int = 0, include_internal: bool = True):
    ensure_support_tables()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    with _db() as con:
        con.row_factory = sqlite3.Row
        query = """
            SELECT id, ticket_id, sender_id, sender_role, body, created_at, is_internal, meta
            FROM support_messages
            WHERE ticket_id = ?
        """
        params = [ticket_id]
        if not include_internal:
            query += " AND is_internal = 0"
        query += " ORDER BY created_at ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = con.execute(query, params).fetchall()
        return [_support_message_row_to_dict(row) for row in rows]

def _normalize_status_filter(status):
    if status is None:
        return []
    if isinstance(status, (list, tuple, set)):
        statuses = [_normalize_support_status(s) for s in status]
    else:
        statuses = [_normalize_support_status(status)]
    return [s for s in statuses if s]

def get_support_tickets_for_user(user_id: int, status=None, limit: int = 20, offset: int = 0, category: str = None):
    ensure_support_tables()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    statuses = _normalize_status_filter(status)
    category_filter = None
    if category:
        raw = str(category).strip().lower()
        if raw not in ('all', 'any'):
            category_filter = _normalize_support_category(category)
    with _db() as con:
        con.row_factory = sqlite3.Row
        query = f"""
            SELECT t.*, u.user_name AS user_name,
                   (SELECT body FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_body,
                   (SELECT sender_role FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_sender
            FROM support_tickets t
            LEFT JOIN users u ON u.user_id = t.user_id
            WHERE t.user_id = ?
        """
        params = [user_id]
        if statuses:
            placeholders = ','.join('?' for _ in statuses)
            query += f" AND t.status IN ({placeholders})"
            params.extend(statuses)
        if category_filter:
            query += " AND t.category = ?"
            params.append(category_filter)
        query += " ORDER BY t.updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = con.execute(query, params).fetchall()
        return [_support_ticket_row_to_dict(row) for row in rows]

def list_support_tickets(status=None, assigned=None, search=None, limit: int = 50, offset: int = 0,
                         user_id=None, category: str = None):
    ensure_support_tables()
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    statuses = _normalize_status_filter(status)
    category_filter = None
    if category:
        raw = str(category).strip().lower()
        if raw not in ('all', 'any'):
            category_filter = _normalize_support_category(category)
    with _db() as con:
        con.row_factory = sqlite3.Row
        base = """
            FROM support_tickets t
            LEFT JOIN users u ON u.user_id = t.user_id
        """
        where = ["1=1"]
        params = []
        if statuses:
            placeholders = ','.join('?' for _ in statuses)
            where.append(f"t.status IN ({placeholders})")
            params.extend(statuses)
        if user_id:
            where.append("t.user_id = ?")
            params.append(int(user_id))
        if assigned == 'unassigned':
            where.append("t.assigned_admin_id IS NULL")
        elif assigned == 'assigned':
            where.append("t.assigned_admin_id IS NOT NULL")
        elif isinstance(assigned, int):
            where.append("t.assigned_admin_id = ?")
            params.append(int(assigned))
        if search:
            search_str = str(search).strip()
            if search_str.isdigit():
                where.append("(t.id = ? OR t.user_id = ?)")
                params.extend([int(search_str), int(search_str)])
            else:
                like = f"%{search_str.lower()}%"
                where.append("(LOWER(t.subject) LIKE ? OR LOWER(u.user_name) LIKE ?)")
                params.extend([like, like])
        if category_filter:
            where.append("t.category = ?")
            params.append(category_filter)
        where_clause = " AND ".join(where)
        rows = con.execute(f"""
            SELECT t.*, u.user_name AS user_name,
                   (SELECT body FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_body,
                   (SELECT sender_role FROM support_messages sm WHERE sm.ticket_id = t.id ORDER BY sm.created_at DESC LIMIT 1) AS last_message_sender
            {base}
            WHERE {where_clause}
            ORDER BY t.updated_at DESC
            LIMIT ? OFFSET ?
        """, (*params, limit, offset)).fetchall()
        total = con.execute(f"SELECT COUNT(*) {base} WHERE {where_clause}", params).fetchone()[0]
        return {
            'tickets': [_support_ticket_row_to_dict(row) for row in rows],
            'total': int(total or 0)
        }

def create_support_ticket(user_id: int, message: str, subject: str = None, source: str = 'webapp',
                          meta=None, priority: int = 0, category: str = None):
    ensure_support_tables()
    if not message or not str(message).strip():
        raise ValueError("Support message cannot be empty")
    message = str(message).strip()
    subject = (subject or '').strip()
    if not subject:
        subject = message[:80] if message else 'Запит користувача'
    now = int(time.time())
    normalized_category = _normalize_support_category(category)
    meta_value = _serialize_meta(meta)
    with _db() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO support_tickets (
                user_id, status, subject, category, priority, source,
                created_at, updated_at, last_message_at, last_message_from,
                last_user_reply_at, user_unread_count, admin_unread_count, meta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            DEFAULT_SUPPORT_STATUS,
            subject[:160],
            normalized_category,
            priority or 0,
            source or 'webapp',
            now,
            now,
            now,
            'user',
            now,
            0,
            1,
            meta_value
        ))
        ticket_id = cur.lastrowid
        cur.execute("""
            INSERT INTO support_messages (ticket_id, sender_id, sender_role, body, created_at, is_internal, meta)
            VALUES (?, ?, 'user', ?, ?, 0, NULL)
        """, (ticket_id, user_id, message[:4000], now))
        message_id = cur.lastrowid
        con.commit()
    return get_support_ticket(ticket_id), get_support_message(message_id)

def add_support_message(ticket_id: int, sender_id: int, sender_role: str, body: str,
                        is_internal: bool = False, meta=None, status: str = None, assigned_admin_id: int = None):
    ensure_support_tables()
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        raise ValueError("Ticket not found")
    if not body or not str(body).strip():
        raise ValueError("Message body cannot be empty")
    sender_role = (sender_role or '').strip() or 'user'
    normalized_status = _normalize_support_status(status) or ticket.get('status')
    now = int(time.time())
    meta_value = _serialize_meta(meta)
    with _db() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO support_messages (ticket_id, sender_id, sender_role, body, created_at, is_internal, meta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket_id,
            sender_id,
            sender_role,
            str(body).strip()[:4000],
            now,
            1 if is_internal else 0,
            meta_value
        ))
        message_id = cur.lastrowid
        update_fields = [
            "updated_at = ?",
            "last_message_at = ?",
            "last_message_from = ?",
            "status = ?"
        ]
        params = [now, now, sender_role, normalized_status]
        if sender_role == 'user':
            update_fields.append("last_user_reply_at = ?")
        else:
            update_fields.append("last_admin_reply_at = ?")
        params.append(now)
        if not is_internal:
            if sender_role == 'user':
                update_fields.append("admin_unread_count = COALESCE(admin_unread_count, 0) + 1")
                update_fields.append("user_unread_count = 0")
            else:
                update_fields.append("user_unread_count = COALESCE(user_unread_count, 0) + 1")
                update_fields.append("admin_unread_count = 0")
        if normalized_status == 'closed':
            update_fields.append("closed_at = COALESCE(closed_at, ?)")
            params.append(now)
        else:
            update_fields.append("closed_at = NULL")
            update_fields.append("closed_reason = NULL")
        if assigned_admin_id is not None:
            update_fields.append("assigned_admin_id = ?")
            params.append(int(assigned_admin_id))
        cur.execute(f"""
            UPDATE support_tickets
            SET {', '.join(update_fields)}
            WHERE id = ?
        """, (*params, ticket_id))
        con.commit()
    return get_support_message(message_id), get_support_ticket(ticket_id)

def update_support_ticket_status(ticket_id: int, status: str, admin_id: int = None,
                                 reason: str = None, balance_delta: float = None, meta_updates: dict = None):
    ensure_support_tables()
    ticket = get_support_ticket(ticket_id)
    if not ticket:
        return None
    normalized_status = _normalize_support_status(status)
    if not normalized_status:
        raise ValueError("Invalid status")
    now = int(time.time())
    merged_meta = ticket.get('meta') or {}
    if meta_updates:
        try:
            merged_meta.update(meta_updates)
        except Exception:
            merged_meta = meta_updates
    meta_value = _serialize_meta(merged_meta) if meta_updates is not None else _serialize_meta(ticket.get('meta'))
    with _db() as con:
        cur = con.cursor()
        update_fields = [
            "status = ?",
            "updated_at = ?"
        ]
        params = [normalized_status, now]
        if normalized_status == 'closed':
            update_fields.append("closed_at = ?")
            params.append(now)
        else:
            update_fields.append("closed_at = NULL")
        if reason is not None:
            update_fields.append("closed_reason = ?")
            params.append(reason.strip() or None)
        elif normalized_status != 'closed':
            update_fields.append("closed_reason = NULL")
        if balance_delta is not None:
            update_fields.append("balance_delta = ?")
            params.append(float(balance_delta))
        if admin_id is not None:
            update_fields.append("assigned_admin_id = ?")
            params.append(int(admin_id))
        if meta_updates is not None:
            update_fields.append("meta = ?")
            params.append(meta_value)
        cur.execute(f"""
            UPDATE support_tickets
            SET {', '.join(update_fields)}
            WHERE id = ?
        """, (*params, ticket_id))
        con.commit()
    return get_support_ticket(ticket_id)


def mark_support_ticket_read(ticket_id: int, reader_role: str, user_id: int = None):
    """Resets unread counters when a participant opens a ticket."""
    ensure_support_tables()
    role = (reader_role or '').lower()
    column = 'user_unread_count' if role == 'user' else 'admin_unread_count'
    with _db() as con:
        params = [ticket_id]
        where_clause = "id = ?"
        if column == 'user_unread_count' and user_id is not None:
            where_clause += " AND user_id = ?"
            params.append(int(user_id))
        con.execute(f"""
            UPDATE support_tickets
            SET {column} = 0
            WHERE {where_clause}
        """, tuple(params))
        con.commit()


def get_user_support_unread_count(user_id: int) -> int:
    """Returns number of tickets where user has unread admin replies."""
    ensure_support_tables()
    with _db() as con:
        row = con.execute("""
            SELECT COUNT(*) FROM support_tickets
            WHERE user_id = ? AND COALESCE(user_unread_count, 0) > 0
        """, (user_id,)).fetchone()
        return int(row[0]) if row and row[0] is not None else 0


def get_admin_support_unread_summary(admin_id: int = None):
    """Aggregates unread tickets for admin dashboards."""
    ensure_support_tables()
    with _db() as con:
        total_row = con.execute("""
            SELECT COUNT(*) FROM support_tickets
            WHERE COALESCE(admin_unread_count, 0) > 0
        """).fetchone()
        unassigned_row = con.execute("""
            SELECT COUNT(*) FROM support_tickets
            WHERE COALESCE(admin_unread_count, 0) > 0 AND assigned_admin_id IS NULL
        """).fetchone()
        assigned_row = None
        if admin_id:
            assigned_row = con.execute("""
                SELECT COUNT(*) FROM support_tickets
                WHERE COALESCE(admin_unread_count, 0) > 0 AND assigned_admin_id = ?
            """, (admin_id,)).fetchone()
        return {
            'total': int(total_row[0]) if total_row and total_row[0] is not None else 0,
            'unassigned': int(unassigned_row[0]) if unassigned_row and unassigned_row[0] is not None else 0,
            'assigned_to_me': int(assigned_row[0]) if assigned_row and assigned_row[0] is not None else 0
        }

# ==========================
# СИСТЕМА УВЕДОМЛЕНИЙ
# ==========================

def ensure_notifications_table():
    """Создает таблицу уведомлений если её нет"""
    with _db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                data TEXT,
                is_read INTEGER DEFAULT 0,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id 
            ON notifications(user_id)
        """)
        con.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_is_read 
            ON notifications(is_read)
        """)
        con.commit()

def create_notification(user_id: int, notification_type: str, title: str, message: str, data: dict = None):
    """Создает новое уведомление"""
    ensure_notifications_table()
    import json
    import time
    with _db() as con:
        data_json = json.dumps(data) if data else None
        con.execute("""
            INSERT INTO notifications (user_id, type, title, message, data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, notification_type, title, message, data_json, int(time.time())))
        con.commit()
        return con.lastrowid

def get_user_notifications(user_id: int, limit: int = 50, unread_only: bool = False):
    """Получает уведомления пользователя"""
    ensure_notifications_table()
    with _db() as con:
        query = """
            SELECT id, type, title, message, data, is_read, created_at
            FROM notifications
            WHERE user_id = ?
        """
        params = [user_id]
        if unread_only:
            query += " AND is_read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = con.execute(query, params).fetchall()
        import json
        notifications = []
        for row in rows:
            data = None
            if row[4]:
                try:
                    data = json.loads(row[4])
                except:
                    pass
            notifications.append({
                'id': row[0],
                'type': row[1],
                'title': row[2],
                'message': row[3],
                'data': data,
                'is_read': bool(row[5]),
                'created_at': row[6]
            })
        return notifications

def get_unread_notifications_count(user_id: int):
    """Получает количество непрочитанных уведомлений"""
    ensure_notifications_table()
    with _db() as con:
        row = con.execute("""
            SELECT COUNT(*) FROM notifications
            WHERE user_id = ? AND is_read = 0
        """, (user_id,)).fetchone()
        return row[0] if row else 0

def mark_notification_read(notification_id: int, user_id: int):
    """Отмечает уведомление как прочитанное"""
    ensure_notifications_table()
    with _db() as con:
        con.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        con.commit()

def mark_all_notifications_read(user_id: int):
    """Отмечает все уведомления пользователя как прочитанные"""
    ensure_notifications_table()
    with _db() as con:
        con.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE user_id = ? AND is_read = 0
        """, (user_id,))
        con.commit()

def delete_notification(notification_id: int, user_id: int):
    """Удаляет уведомление"""
    ensure_notifications_table()
    with _db() as con:
        con.execute("""
            DELETE FROM notifications
            WHERE id = ? AND user_id = ?
        """, (notification_id, user_id))
        con.commit()

# ==========================
# СИСТЕМА P2P-ПЕРЕВОДІВ
# ==========================

def get_user_balances(user_id: int) -> dict:
    """Повертає всі типи балансів користувача"""
    with _db() as con:
        # Перевіряємо чи є колонки
        cur = con.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in cur.fetchall()}
        
        # Формуємо SELECT залежно від наявності колонок
        select_cols = ["COALESCE(balance, 0.0) as main_balance"]
        
        if 'transferable_balance' in columns:
            select_cols.append("COALESCE(transferable_balance, 0.0) as transferable_balance")
        else:
            select_cols.append("0.0 as transferable_balance")
        
        if 'locked_balance' in columns:
            select_cols.append("COALESCE(locked_balance, 0.0) as locked_balance")
        else:
            select_cols.append("0.0 as locked_balance")
        
        query = f"""
            SELECT {', '.join(select_cols)}
            FROM users
            WHERE user_id = ?
        """
        
        row = con.execute(query, (user_id,)).fetchone()
        
        if row:
            return {
                'main_balance': float(row[0]),
                'transferable_balance': float(row[1]),
                'locked_balance': float(row[2])
            }
        return {
            'main_balance': 0.0,
            'transferable_balance': 0.0,
            'locked_balance': 0.0
        }

def add_to_transferable_balance(user_id: int, amount: float, reason: str = None, details: str = None):
    """Додає кошти до transferable_balance"""
    with _db() as con:
        import time
        # Отримуємо поточний баланс
        row = con.execute("SELECT COALESCE(transferable_balance, 0.0) FROM users WHERE user_id = ?", (user_id,)).fetchone()
        balance_before = float(row[0]) if row else 0.0
        balance_after = balance_before + amount
        
        # Оновлюємо баланс
        con.execute("""
            UPDATE users 
            SET transferable_balance = COALESCE(transferable_balance, 0.0) + ?
            WHERE user_id = ?
        """, (amount, user_id))
        
        # Логуємо в balance_ledger
        con.execute("""
            INSERT INTO balance_ledger (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, amount, balance_before, balance_after, reason or 'transferable_add', details, int(time.time())))
        
        con.commit()

def move_to_transferable(from_user_id: int, amount: float, reason: str = None):
    """Переміщує кошти з main_balance до transferable_balance"""
    with _db() as con:
        import time
        # Перевіряємо чи достатньо коштів
        row = con.execute("SELECT COALESCE(balance, 0.0) FROM users WHERE user_id = ?", (from_user_id,)).fetchone()
        main_balance = float(row[0]) if row else 0.0
        
        if main_balance < amount:
            return False, "Недостатньо коштів у основному балансі"
        
        # Отримуємо transferable_balance
        row = con.execute("SELECT COALESCE(transferable_balance, 0.0) FROM users WHERE user_id = ?", (from_user_id,)).fetchone()
        transferable_before = float(row[0]) if row else 0.0
        transferable_after = transferable_before + amount
        
        # Виконуємо переміщення
        con.execute("""
            UPDATE users 
            SET balance = balance - ?,
                transferable_balance = COALESCE(transferable_balance, 0.0) + ?
            WHERE user_id = ?
        """, (amount, amount, from_user_id))
        
        # Логуємо
        con.execute("""
            INSERT INTO balance_ledger (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_user_id, -amount, main_balance, main_balance - amount, reason or 'move_to_transferable', f'Moved {amount} to transferable', int(time.time())))
        
        con.commit()
        return True, None

def get_p2p_settings() -> dict:
    """Повертає налаштування P2P-переводів"""
    with _db() as con:
        row = con.execute("""
            SELECT min_amount, max_amount, fee_percent, fee_fixed, daily_limit, 
                   daily_transactions_limit, cooldown_seconds, auto_approve_enabled, auto_approve_threshold
            FROM p2p_settings
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
        
        if row:
            return {
                'min_amount': float(row[0]),
                'max_amount': float(row[1]),
                'fee_percent': float(row[2]),
                'fee_fixed': float(row[3]),
                'daily_limit': float(row[4]),
                'daily_transactions_limit': int(row[5]),
                'cooldown_seconds': int(row[6]),
                'auto_approve_enabled': bool(row[7]),
                'auto_approve_threshold': float(row[8])
            }
        
        # Значення за замовчуванням
        return {
            'min_amount': 10.0,
            'max_amount': 10000.0,
            'fee_percent': 2.0,
            'fee_fixed': 0.0,
            'daily_limit': 50000.0,
            'daily_transactions_limit': 50,
            'cooldown_seconds': 60,
            'auto_approve_enabled': False,
            'auto_approve_threshold': 100.0
        }

def get_p2p_daily_stats(user_id: int, date: str = None) -> dict:
    """Повертає статистику P2P-переводів за день"""
    if date is None:
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
    
    with _db() as con:
        row = con.execute("""
            SELECT transactions_count, total_sent, total_received, total_fees_paid
            FROM p2p_daily_stats
            WHERE user_id = ? AND date = ?
        """, (user_id, date)).fetchone()
        
        if row:
            return {
                'transactions_count': int(row[0]),
                'total_sent': float(row[1]),
                'total_received': float(row[2]),
                'total_fees_paid': float(row[3])
            }
        return {
            'transactions_count': 0,
            'total_sent': 0.0,
            'total_received': 0.0,
            'total_fees_paid': 0.0
        }

def check_p2p_cooldown(user_id: int) -> tuple:
    """Перевіряє чи минув кулдаун для переводу
    Повертає (can_transfer, seconds_left)
    """
    settings = get_p2p_settings()
    cooldown = settings['cooldown_seconds']
    
    with _db() as con:
        row = con.execute("""
            SELECT MAX(created_at) 
            FROM p2p_transactions
            WHERE from_user_id = ? AND status IN ('pending', 'completed')
        """, (user_id,)).fetchone()
        
        if not row or not row[0]:
            return True, 0
        
        import time
        last_transaction_time = row[0]
        elapsed = int(time.time()) - last_transaction_time
        
        if elapsed >= cooldown:
            return True, 0
        else:
            return False, cooldown - elapsed

def calculate_p2p_fee(amount: float) -> float:
    """Розраховує комісію за переказ"""
    settings = get_p2p_settings()
    fee_percent = settings['fee_percent']
    fee_fixed = settings['fee_fixed']
    
    fee = (amount * fee_percent / 100) + fee_fixed
    return round(fee, 2)

def validate_p2p_transfer(from_user_id: int, to_user_id: int, amount: float) -> tuple:
    """Валідація переводу
    Повертає (is_valid, error_message)
    """
    if from_user_id == to_user_id:
        return False, "Не можна переводити собі"
    
    settings = get_p2p_settings()
    
    # Перевірка мінімальної та максимальної суми
    if amount < settings['min_amount']:
        return False, f"Мінімальна сума переказу: {settings['min_amount']}₴"
    
    if amount > settings['max_amount']:
        return False, f"Максимальна сума переказу: {settings['max_amount']}₴"
    
    # Перевірка кулдауну
    can_transfer, seconds_left = check_p2p_cooldown(from_user_id)
    if not can_transfer:
        return False, f"Зачекайте {seconds_left} секунд перед наступним переказом"
    
    # Перевірка балансу
    balances = get_user_balances(from_user_id)
    fee = calculate_p2p_fee(amount)
    total_needed = amount + fee
    
    if balances['transferable_balance'] < total_needed:
        return False, f"Недостатньо коштів. Потрібно: {total_needed}₴ (сума: {amount}₴ + комісія: {fee}₴)"
    
    # Перевірка денних лімітів
    stats = get_p2p_daily_stats(from_user_id)
    if stats['transactions_count'] >= settings['daily_transactions_limit']:
        return False, f"Досягнуто ліміт транзакцій за день: {settings['daily_transactions_limit']}"
    
    if stats['total_sent'] + amount > settings['daily_limit']:
        return False, f"Досягнуто ліміт переказів за день: {settings['daily_limit']}₴"
    
    # Перевірка чи отримувач існує
    to_user = get_user(to_user_id)
    if not to_user:
        return False, "Отримувача не знайдено"
    
    return True, None

def create_p2p_transaction(from_user_id: int, to_user_id: int, amount: float) -> int:
    """Створює P2P транзакцію"""
    import time
    
    fee = calculate_p2p_fee(amount)
    total_needed = amount + fee
    
    # Валідація
    is_valid, error = validate_p2p_transfer(from_user_id, to_user_id, amount)
    if not is_valid:
        raise ValueError(error)
    
    with _db() as con:
        # Блокуємо кошти (переміщуємо з transferable_balance до locked_balance)
        row = con.execute("""
            SELECT COALESCE(transferable_balance, 0.0), COALESCE(locked_balance, 0.0)
            FROM users WHERE user_id = ?
        """, (from_user_id,)).fetchone()
        
        transferable_before = float(row[0]) if row else 0.0
        locked_before = float(row[1]) if row else 0.0
        
        # Перевірка балансу
        if transferable_before < total_needed:
            raise ValueError(f"Недостатньо коштів: потрібно {total_needed}₴")
        
        # Блокуємо кошти
        con.execute("""
            UPDATE users
            SET transferable_balance = transferable_balance - ?,
                locked_balance = COALESCE(locked_balance, 0.0) + ?
            WHERE user_id = ?
        """, (total_needed, total_needed, from_user_id))
        
        # Створюємо транзакцію
        now = int(time.time())
        con.execute("""
            INSERT INTO p2p_transactions 
            (from_user_id, to_user_id, amount, fee, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (from_user_id, to_user_id, amount, fee, now, now))
        
        transaction_id = con.lastrowid
        
        # Логуємо зміну балансу
        con.execute("""
            INSERT INTO balance_ledger 
            (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_user_id, -total_needed, transferable_before, transferable_before - total_needed, 
              'p2p_lock', f'P2P transfer #{transaction_id} locked', now))
        
        # Оновлюємо статистику
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
        con.execute("""
            INSERT INTO p2p_daily_stats (user_id, date, transactions_count, total_sent, total_fees_paid)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                transactions_count = transactions_count + 1,
                total_sent = total_sent + ?,
                total_fees_paid = total_fees_paid + ?
        """, (from_user_id, date, amount, fee, amount, fee))
        
        # Логуємо створення транзакції
        con.execute("""
            INSERT INTO p2p_transaction_logs (transaction_id, action, performed_by, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (transaction_id, 'created', from_user_id, f'Created transfer of {amount}₴', now))
        
        con.commit()
        
        # Перевірка чи потрібне автоматичне підтвердження
        settings = get_p2p_settings()
        if settings['auto_approve_enabled'] and amount <= settings['auto_approve_threshold']:
            approve_p2p_transaction(transaction_id, processed_by=None)
        
        return transaction_id

def approve_p2p_transaction(transaction_id: int, processed_by: int = None):
    """Підтверджує P2P транзакцію"""
    import time
    
    with _db() as con:
        # Отримуємо транзакцію
        row = con.execute("""
            SELECT from_user_id, to_user_id, amount, fee, status
            FROM p2p_transactions
            WHERE id = ?
        """, (transaction_id,)).fetchone()
        
        if not row:
            raise ValueError("Транзакцію не знайдено")
        
        from_user_id, to_user_id, amount, fee, status = row
        
        if status != 'pending':
            raise ValueError(f"Транзакція вже оброблена (статус: {status})")
        
        now = int(time.time())
        
        # Забираємо з locked_balance відправника (вже заблоковано)
        con.execute("""
            UPDATE users
            SET locked_balance = locked_balance - ?
            WHERE user_id = ?
        """, (amount + fee, from_user_id))
        
        # Зачисляємо отримувачу (до main_balance, можна змінити на transferable_balance)
        # Отримуємо поточний баланс отримувача
        to_user_row = con.execute("SELECT COALESCE(balance, 0.0) FROM users WHERE user_id = ?", (to_user_id,)).fetchone()
        to_balance_before = float(to_user_row[0]) if to_user_row else 0.0
        
        con.execute("""
            UPDATE users
            SET balance = COALESCE(balance, 0.0) + ?
            WHERE user_id = ?
        """, (amount, to_user_id))
        
        # Оновлюємо статус транзакції
        con.execute("""
            UPDATE p2p_transactions
            SET status = 'completed',
                processed_at = ?,
                processed_by = ?,
                updated_at = ?
            WHERE id = ?
        """, (now, processed_by, now, transaction_id))
        
        # Логуємо зміни балансів
        # Для відправника (зняття з locked)
        con.execute("""
            INSERT INTO balance_ledger 
            (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_user_id, -(amount + fee), amount + fee, 0, 'p2p_complete', 
              f'P2P transfer #{transaction_id} completed', now))
        
        # Для отримувача (нарахування)
        con.execute("""
            INSERT INTO balance_ledger 
            (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (to_user_id, amount, to_balance_before, to_balance_before + amount, 
              'p2p_receive', f'Received P2P transfer #{transaction_id}', now))
        
        # Оновлюємо статистику отримувача
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
        con.execute("""
            INSERT INTO p2p_daily_stats (user_id, date, total_received)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, date) DO UPDATE SET
                total_received = total_received + ?
        """, (to_user_id, date, amount, amount))
        
        # Логуємо підтвердження
        con.execute("""
            INSERT INTO p2p_transaction_logs (transaction_id, action, performed_by, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (transaction_id, 'approved', processed_by or 0, f'Approved by admin {processed_by}', now))
        
        con.commit()

def reject_p2p_transaction(transaction_id: int, rejection_reason: str, processed_by: int):
    """Відхиляє P2P транзакцію"""
    import time
    
    with _db() as con:
        # Отримуємо транзакцію
        row = con.execute("""
            SELECT from_user_id, to_user_id, amount, fee, status
            FROM p2p_transactions
            WHERE id = ?
        """, (transaction_id,)).fetchone()
        
        if not row:
            raise ValueError("Транзакцію не знайдено")
        
        from_user_id, to_user_id, amount, fee, status = row
        
        if status != 'pending':
            raise ValueError(f"Транзакція вже оброблена (статус: {status})")
        
        now = int(time.time())
        total_to_return = amount + fee
        
        # Повертаємо кошти відправнику (з locked_balance назад до transferable_balance)
        row = con.execute("""
            SELECT COALESCE(locked_balance, 0.0), COALESCE(transferable_balance, 0.0)
            FROM users WHERE user_id = ?
        """, (from_user_id,)).fetchone()
        
        locked_before = float(row[0]) if row else 0.0
        transferable_before = float(row[1]) if row else 0.0
        
        con.execute("""
            UPDATE users
            SET locked_balance = locked_balance - ?,
                transferable_balance = COALESCE(transferable_balance, 0.0) + ?
            WHERE user_id = ?
        """, (total_to_return, total_to_return, from_user_id))
        
        # Оновлюємо статус транзакції
        con.execute("""
            UPDATE p2p_transactions
            SET status = 'rejected',
                processed_at = ?,
                processed_by = ?,
                rejection_reason = ?,
                updated_at = ?
            WHERE id = ?
        """, (now, processed_by, rejection_reason, now, transaction_id))
        
        # Логуємо повернення коштів
        con.execute("""
            INSERT INTO balance_ledger 
            (user_id, delta, balance_before, balance_after, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_user_id, total_to_return, transferable_before, transferable_before + total_to_return,
              'p2p_reject', f'P2P transfer #{transaction_id} rejected, funds returned', now))
        
        # Виправляємо статистику (зменшуємо, бо транзакція відхилена)
        from datetime import datetime
        date = datetime.now().strftime('%Y-%m-%d')
        con.execute("""
            UPDATE p2p_daily_stats
            SET transactions_count = transactions_count - 1,
                total_sent = total_sent - ?,
                total_fees_paid = total_fees_paid - ?
            WHERE user_id = ? AND date = ?
        """, (amount, fee, from_user_id, date))
        
        # Логуємо відхилення
        con.execute("""
            INSERT INTO p2p_transaction_logs (transaction_id, action, performed_by, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (transaction_id, 'rejected', processed_by, f'Rejected: {rejection_reason}', now))
        
        con.commit()

def get_p2p_transaction(transaction_id: int) -> dict:
    """Повертає інформацію про P2P транзакцію"""
    with _db() as con:
        row = con.execute("""
            SELECT id, from_user_id, to_user_id, amount, fee, status, 
                   created_at, updated_at, processed_at, processed_by, rejection_reason
            FROM p2p_transactions
            WHERE id = ?
        """, (transaction_id,)).fetchone()
        
        if not row:
            return None
        
        return {
            'id': row[0],
            'from_user_id': row[1],
            'to_user_id': row[2],
            'amount': float(row[3]),
            'fee': float(row[4]),
            'status': row[5],
            'created_at': row[6],
            'updated_at': row[7],
            'processed_at': row[8],
            'processed_by': row[9],
            'rejection_reason': row[10]
        }

def get_pending_p2p_transactions(limit: int = 50) -> list:
    """Повертає список pending транзакцій"""
    with _db() as con:
        rows = con.execute("""
            SELECT id, from_user_id, to_user_id, amount, fee, created_at
            FROM p2p_transactions
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [
            {
                'id': row[0],
                'from_user_id': row[1],
                'to_user_id': row[2],
                'amount': float(row[3]),
                'fee': float(row[4]),
                'created_at': row[5]
            }
            for row in rows
        ]

def get_user_p2p_transactions(user_id: int, limit: int = 50) -> list:
    """Повертає історію P2P транзакцій користувача"""
    with _db() as con:
        rows = con.execute("""
            SELECT id, from_user_id, to_user_id, amount, fee, status, created_at, processed_at
            FROM p2p_transactions
            WHERE from_user_id = ? OR to_user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, user_id, limit)).fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                'id': row[0],
                'from_user_id': row[1],
                'to_user_id': row[2],
                'amount': float(row[3]),
                'fee': float(row[4]),
                'status': row[5],
                'created_at': row[6],
                'processed_at': row[7],
                'is_sent': row[1] == user_id,
                'is_received': row[2] == user_id
            })
        
        return transactions