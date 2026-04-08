import sqlite3

con = sqlite3.connect('tg.db')
cur = con.cursor()
cur.execute("DROP TABLE IF EXISTS tx;")
cur.execute("""
CREATE TABLE tx (
    tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    comment TEXT,
    status TEXT DEFAULT 'pending'
);
""")
con.commit()
cols = list(cur.execute('PRAGMA table_info(tx);'))
for col in cols:
    print(col)
con.close()
