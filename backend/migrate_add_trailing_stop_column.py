#!/usr/bin/env python
"""
Migration: Add max_unrealized_pnl column for trailing stop tracking.

This tracks the highest profit level reached, enabling trailing stop functionality.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.session import SessionLocal

def migrate():
    """Add max_unrealized_pnl column to execution_intents."""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM pragma_table_info('execution_intents') 
            WHERE name='max_unrealized_pnl'
        """))
        row = result.fetchone()
        
        if row and row[0] > 0:
            print("✅ Column 'max_unrealized_pnl' already exists. Skipping migration.")
            return
        
        # Add the column
        print("📝 Adding 'max_unrealized_pnl' column to execution_intents...")
        db.execute(text("""
            ALTER TABLE execution_intents 
            ADD COLUMN max_unrealized_pnl FLOAT
        """))
        db.commit()
        
        print("✅ Migration complete! Column 'max_unrealized_pnl' added successfully.")
        print("   This tracks the highest profit level for trailing stop functionality.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
