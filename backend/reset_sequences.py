"""
One-time script to reset Postgres sequences after data migration.
Run this once: python reset_sequences.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.db.session import engine
from sqlalchemy import text

TABLES = [
    "candles_1m",
    "candles_5m",
    "candles_15m",
    "candles_1h",
    "candles_daily",
    "option_historical_candles",
    "alert_rules",
    "auto_trader_config",
    "auto_trader_log",
    "backtest_results",
    "backtest_trades",
    "bill_reminders",
    "brokerage_config",
    "budgets",
    "daily_capital",
    "execution_intents",
    "expense_forecasts",
    "finance_transactions",
    "market_data",
    "notifications",
    "recurring_transactions",
    "risk_limits",
    "savings_goals",
    "scanner_signal_history",
    "signal_outcomes",
    "strategy_configs",
    "strategy_runs",
    "symbols",
    "system_control",
    "trade_costs",
    "twitter_accounts",
    "twitter_alerts",
    "twitter_sentiment",
    "twitter_symbol_sentiment",
    "vix_historic",
    "watchlist_alerts",
    "watchlists",
    "zerodha_sessions",
]

def reset_sequences():
    with engine.connect() as conn:
        for table in TABLES:
            try:
                # Check if table exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
                ), {"t": table})
                if not result.scalar():
                    print(f"  SKIP  {table} (table not found)")
                    continue

                # Reset sequence to max(id) + 1
                conn.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 0) + 1,
                        false
                    )
                """))
                conn.commit()

                # Show new sequence value
                result = conn.execute(text(f"SELECT MAX(id) FROM {table}"))
                max_id = result.scalar() or 0
                print(f"  OK    {table} → next id will be {max_id + 1}")

            except Exception as e:
                print(f"  ERROR {table}: {e}")
                conn.rollback()

if __name__ == "__main__":
    print("Resetting Postgres sequences...\n")
    reset_sequences()
    print("\nDone. Duplicate key errors should be gone now.")
