import pumpFunDataStream
import sqlite3
import os
from datetime import datetime
import time

swap_count = 0
last_report = time.time()
REPORT_INTERVAL = 10  # seconds

def on_swap(sig, slot, timestamp, mint, user, is_buy, sol_amount, token_amount, v_sol_reserves, v_token_reserves, r_sol_reserves, r_token_reserves):
    global db, swap_count, last_report
    db.execute("""
        INSERT INTO swaps (sig, slot, timestamp, mint, user, is_buy, sol_amount, token_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(sig), int(slot), float(timestamp), str(mint), str(user), bool(is_buy), float(sol_amount), float(token_amount)))
    db.commit()
    
    swap_count += 1
    now = time.time()
    if now - last_report >= REPORT_INTERVAL:
        cursor = db.execute("""
            SELECT 
                COUNT(DISTINCT user) as traders,
                COUNT(DISTINCT mint) as tokens,
                SUM(CASE WHEN is_buy = 1 THEN sol_amount ELSE 0 END) / 1e9 as sol_bought,
                SUM(CASE WHEN is_buy = 0 THEN sol_amount ELSE 0 END) / 1e9 as sol_sold
            FROM swaps
        """)
        traders, tokens, sol_bought, sol_sold = cursor.fetchone()
        filesize = os.path.getsize(db_path) / (1024 * 1024)  # MB
        print(f"Swaps: {swap_count} | Traders: {traders} | Tokens: {tokens} | SOL Buy: {sol_bought:.2f} | SOL Sell: {sol_sold:.2f} | Size: {filesize:.1f}MB")
        last_report = now

try:
    now = datetime.now().strftime("%Y-%m-%d")
    db_path = f"{now}.db"
    db = sqlite3.connect(db_path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS swaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sig TEXT NOT NULL,
            slot INTEGER NOT NULL,
            timestamp REAL NOT NULL,
            mint TEXT NOT NULL,
            user TEXT NOT NULL,
            is_buy BOOLEAN NOT NULL,
            sol_amount REAL NOT NULL,
            token_amount REAL NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_swaps_mint ON swaps(mint)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_swaps_user ON swaps(user)")
    db.commit()
    pumpFunDataStream.run(None, on_swap)
except KeyboardInterrupt:
    print("\nShutting down...")
    db.close()
except Exception as e:
    print(f"Error: {e}")
    if 'db' in globals():
        db.close()
