import sqlite3, pathlib
DB_FILE = pathlib.Path(__file__).with_name("tg.db")

def get_min_withdraw():
    with sqlite3.connect(DB_FILE) as con:
        row = con.execute("SELECT value FROM settings WHERE key = 'min_withdraw'").fetchone()
        return float(row[0]) if row else 50.0  # дефолт 50 грн

def set_min_withdraw(amount):
    with sqlite3.connect(DB_FILE) as con:
        con.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('min_withdraw', ?)", (str(amount),))
        con.commit()
