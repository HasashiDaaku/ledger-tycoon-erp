import sqlite3

conn = sqlite3.connect('ledger_tycoon.db')

# Check products table schema
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='products'")
result = cursor.fetchone()

if result:
    print("Products table schema:")
    print(result[0])
else:
    print("Products table not found")

# Check for UNIQUE indexes
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='products' AND sql LIKE '%UNIQUE%'")
indexes = cursor.fetchall()

if indexes:
    print("\nUNIQUE indexes on products:")
    for idx in indexes:
        if idx[0]:
            print(idx[0])

conn.close()
