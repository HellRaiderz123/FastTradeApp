import sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

tables = [
    'alert_rules', 'auto_trader_config', 'auto_trader_log',
    'backtest_results', 'backtest_trades', 'bill_reminders',
    'brokerage_config', 'budgets', 'candles_15m', 'candles_1h',
    'candles_1m', 'candles_5m', 'candles_daily', 'condition_strategies',
    'condition_strategy_backtests', 'currency_exchanges', 'daily_capital',
    'execution_intents', 'expense_forecasts', 'finance_transactions',
    'market_data', 'notifications', 'option_historical_candles',
    'recurring_transactions', 'risk_limits', 'savings_goals',
    'scanner_signal_history', 'signal_outcomes', 'strategy_configs',
    'strategy_runs', 'symbols', 'system_control', 'trade_costs',
    'twitter_accounts', 'twitter_alerts', 'twitter_sentiment',
    'twitter_symbol_sentiment', 'vix_historic', 'watchlist_alerts',
    'watchlists', 'zerodha_sessions',
]

print(f"{'TABLE':<45} {'MAX_ID':>8}  {'SEQ_BEFORE':>12}  {'SEQ_AFTER':>10}")
print("-" * 80)

for t in tables:
    try:
        max_id = db.execute(text(f'SELECT COALESCE(MAX(id), 0) FROM "{t}"')).scalar() or 0
        seq = f"{t}_id_seq"
        try:
            seq_before = db.execute(text(f"SELECT last_value FROM {seq}")).scalar()
        except Exception:
            seq_before = "no_seq"
            print(f"{t:<45} {'N/A':>8}  {'no sequence':>12}")
            db.rollback()
            continue
        new_val = db.execute(text(f"SELECT setval('{seq}', GREATEST({max_id}, 1), true)")).scalar()
        status = "FIXED" if seq_before < max_id else "ok"
        print(f"{t:<45} {max_id:>8}  {seq_before:>12}  {new_val:>10}  {status}")
    except Exception as e:
        print(f"{t:<45} ERROR: {str(e)[:60]}")
        db.rollback()

db.commit()
db.close()
print("\nAll sequences fixed.")
