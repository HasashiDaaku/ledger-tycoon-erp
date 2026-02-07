import sqlite3

conn = sqlite3.connect('ledger_tycoon.db')
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='companies'")
result = cursor.fetchone()

if result:
    print("Companies table schema:")
    print(result[0])
else:
    print("Companies table not found")

conn.close()
