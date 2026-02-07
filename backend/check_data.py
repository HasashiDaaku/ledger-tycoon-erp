import sqlite3

conn = sqlite3.connect('ledger_tycoon.db')

# Check companies
cursor = conn.execute("SELECT * FROM companies")
companies = cursor.fetchall()

print(f"Found {len(companies)} companies:")
for company in companies:
    print(f"  ID: {company[0]}, Name: {company[1]}, IsPlayer: {company[2]}, Cash: {company[3]}")

conn.close()
