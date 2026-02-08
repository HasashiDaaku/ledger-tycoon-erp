
import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger_tycoon.db")

def migrate():
    print(f"Migrating database at: {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(companies)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "strategy_memory" in columns:
            print("Column 'strategy_memory' already exists.")
        else:
            print("Adding 'strategy_memory' column...")
            cursor.execute("ALTER TABLE companies ADD COLUMN strategy_memory JSON DEFAULT '{}'")
            conn.commit()
            print("Migration successful.")
            
        conn.close()
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
