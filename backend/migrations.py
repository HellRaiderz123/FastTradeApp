#!/usr/bin/env python
"""
Simple migration script to keep the SQLite schema in sync.
- Adds trailing_sl_pct column to execution_intents (legacy)
- Creates risk_limits table for DB-backed risk settings
"""
import sys
import os
import json
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


def migrate_create_risk_limits_table():
    """Create risk_limits table and seed a default row if missing."""
    default_iv_limits = {
        "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 4.0},
        "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 2.0},
        "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0},
    }

    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS risk_limits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        max_portfolio_loss_pct FLOAT DEFAULT 3.0,
                        max_trades_per_day INTEGER DEFAULT 3,
                        iv_regime_limits JSON,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            conn.commit()
        except Exception as e:
            print(f"✗ Failed to create risk_limits table: {e}")
            return False

        try:
            existing = conn.execute(text("SELECT COUNT(*) FROM risk_limits")).scalar()
            if existing == 0:
                conn.execute(
                    text(
                        """
                        INSERT INTO risk_limits (max_portfolio_loss_pct, max_trades_per_day, iv_regime_limits)
                        VALUES (:max_loss, :max_trades, :iv_limits)
                        """
                    ),
                    {
                        "max_loss": 3.0,
                        "max_trades": 3,
                        "iv_limits": json.dumps(default_iv_limits),
                    },
                )
                conn.commit()
                print("✓ Seeded default risk_limits row")
            else:
                print("✓ risk_limits table already populated")
            return True
        except Exception as e:
            print(f"✗ Failed to seed risk_limits table: {e}")
            return False

if __name__ == "__main__":
    print("Running migrations...")
    success = True
    success = migrate_add_trailing_sl_pct() and success
    success = migrate_create_risk_limits_table() and success
    if success:
        print("✓ All migrations completed successfully")
        sys.exit(0)
    else:
        print("✗ Migration failed")
        sys.exit(1)
