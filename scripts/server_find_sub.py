import sqlite3

DB = "/opt/SmartKamaVPN/Database/smartkamavpn.db"
LOOKUP_ID = 30548

conn = sqlite3.connect(DB)
cur = conn.cursor()

queries = [
    ("users", "SELECT id, telegram_id, username FROM users WHERE id=? OR telegram_id=?"),
    (
        "non_order_subscriptions",
        "SELECT id, telegram_id, uuid, server_id FROM non_order_subscriptions WHERE id=? OR telegram_id=?",
    ),
    ("orders", "SELECT id, telegram_id, plan_id, user_name FROM orders WHERE id=? OR telegram_id=?"),
    (
        "order_subscriptions",
        "SELECT id, order_id, uuid, server_id FROM order_subscriptions WHERE id=? OR order_id=?",
    ),
]

for title, sql in queries:
    rows = cur.execute(sql, (LOOKUP_ID, LOOKUP_ID)).fetchall()
    if rows:
        print(f"[{title}]")
        for row in rows:
            print(row)

conn.close()
