import sqlite3

conn = sqlite3.connect('ledger_tycoon.db')

# Check for indexes on companies table
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='companies'")
indexes = cursor.fetchall()

print(f"Found {len(indexes)} indexes on companies table:")
for idx in indexes:
    if idx[0]:  # Some indexes might be NULL (auto-created)
        print(idx[0])

conn.close()
