#!/usr/bin/env python
"""
Migration: Add margin_required column to execution_intents table.

This tracks the margin blocked by the broker (Zerodha) for each position.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from app.db.session import SessionLocal, engine

def migrate():
    """Add margin_required column to execution_intents."""
    db = SessionLocal()
    try:
        # Check if column already exists
        result = db.execute(text("""
            SELECT COUNT(*) as count 
            FROM pragma_table_info('execution_intents') 
            WHERE name='margin_required'
        """))
        row = result.fetchone()
        
        if row and row[0] > 0:
            print("✅ Column 'margin_required' already exists. Skipping migration.")
            return
        
        # Add the column
        print("📝 Adding 'margin_required' column to execution_intents...")
        db.execute(text("""
            ALTER TABLE execution_intents 
            ADD COLUMN margin_required FLOAT
        """))
        db.commit()
        
        print("✅ Migration complete! Column 'margin_required' added successfully.")
        print("   This will store the margin blocked by Zerodha for each position.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
