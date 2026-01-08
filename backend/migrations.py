#!/usr/bin/env python
"""
Simple migration script to add trailing_sl_pct column to execution_intents table.
Run this once to update the database schema.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.db.session import engine

def migrate_add_trailing_sl_pct():
    """Add trailing_sl_pct column to execution_intents if it doesn't exist."""
    with engine.connect() as conn:
        # Check if column exists
        try:
            conn.execute(text("SELECT trailing_sl_pct FROM execution_intents LIMIT 1"))
            print("✓ trailing_sl_pct column already exists")
            return True
        except Exception:
            pass
        
        # Column doesn't exist, add it
        try:
            conn.execute(text("""
                ALTER TABLE execution_intents 
                ADD COLUMN trailing_sl_pct FLOAT NULL
            """))
            conn.commit()
            print("✓ Added trailing_sl_pct column to execution_intents")
            return True
        except Exception as e:
            print(f"✗ Failed to add column: {e}")
            return False

if __name__ == "__main__":
    print("Running migrations...")
    success = migrate_add_trailing_sl_pct()
    if success:
        print("✓ All migrations completed successfully")
        sys.exit(0)
    else:
        print("✗ Migration failed")
        sys.exit(1)
