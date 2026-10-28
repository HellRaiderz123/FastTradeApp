from sqlalchemy import text
from app.db.session import engine, Base, DATABASE_URL
from app.db.models import Base  # noqa: F811 — same Base, just ensures all models are imported
from app.db.models_intent import ExecutionIntent
from app.db.models_control import SystemControl
from app.db.models_candles import Candle15m
from app.db.models_signal_outcome import SignalOutcome
from app.db.models_zerodha import ZerodhaSession
from app.db.models_indmoney import INDMoneySession
from app.db.models_instruments import IndstocksInstrument  # noqa: F401 — registers table
from app.core.scalp.scalp_paper_trader import ScalpTrade
from app.db.models_ai_log import AIUsageLog  # noqa: F401 — registers table
from app.db.models_fii_dii import FiiDiiDaily  # noqa: F401 — registers table

_is_postgres = DATABASE_URL.startswith("postgresql")

_MIGRATIONS_COMMON = [
    "ALTER TABLE execution_intents ADD COLUMN IF NOT EXISTS execution_mode VARCHAR;",
    "ALTER TABLE risk_limits ADD COLUMN IF NOT EXISTS per_trade_risk_pct FLOAT DEFAULT 2.0;",
    "ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS merchant VARCHAR;",
    "ALTER TABLE indmoney_sessions ADD COLUMN IF NOT EXISTS mobile VARCHAR;",
    "CREATE INDEX IF NOT EXISTS idx_candle_5m_symbol_ts ON candle_5m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_15m_symbol_ts ON candle_15m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_1h_symbol_ts ON candle_1h (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_daily_symbol_date ON candle_daily (symbol, date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_date ON ai_decisions (symbol, analysed_at DESC);",
]

# Postgres-only: fii_dii_daily was added after initial DB creation so needs explicit migration
_MIGRATIONS_POSTGRES = [
    """
    CREATE TABLE IF NOT EXISTS fii_dii_daily (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL UNIQUE,
        fii_buy FLOAT, fii_sell FLOAT, fii_net FLOAT,
        dii_buy FLOAT, dii_sell FLOAT, dii_net FLOAT,
        fii_idx_fut_long INTEGER, fii_idx_fut_short INTEGER, fii_idx_fut_net INTEGER,
        fii_stk_fut_long INTEGER, fii_stk_fut_short INTEGER, fii_stk_fut_net INTEGER,
        fii_idx_call_long INTEGER, fii_idx_call_short INTEGER, fii_idx_call_net INTEGER,
        fii_idx_put_long INTEGER, fii_idx_put_short INTEGER, fii_idx_put_net INTEGER,
        dii_idx_fut_long INTEGER, dii_idx_fut_short INTEGER, dii_idx_fut_net INTEGER,
        pcr FLOAT, sentiment_score FLOAT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_fii_dii_daily_date ON fii_dii_daily (date);",
]


def init_db():
    Base.metadata.create_all(bind=engine)
    migrations = _MIGRATIONS_COMMON + (_MIGRATIONS_POSTGRES if _is_postgres else [])
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # ignore errors on already-applied migrations
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("\u2705 Database tables created")
