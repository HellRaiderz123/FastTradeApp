"""
Migration: add final_pnl column to execution_intents table.
Run once: python migrate_add_final_pnl.py
"""
from app.db.session import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE execution_intents ADD COLUMN final_pnl FLOAT"))
        conn.commit()
        print("[OK] Added final_pnl column")
    except Exception as e:
        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
            print("[SKIP] final_pnl column already exists, skipping")
        else:
            raise
