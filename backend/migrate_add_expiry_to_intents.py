"""
Migration script to add expiry column to execution_intents table.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "trading.db")

def migrate():
    """Add expiry column to execution_intents table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(execution_intents)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "expiry" in columns:
            print("✅ Column 'expiry' already exists in execution_intents table")
            return
        
        # Add the column
        cursor.execute("""
            ALTER TABLE execution_intents 
            ADD COLUMN expiry TEXT
        """)
        
        conn.commit()
        print("✅ Successfully added 'expiry' column to execution_intents table")
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
