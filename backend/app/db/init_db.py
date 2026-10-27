from sqlalchemy import text
from app.db.session import engine
from app.db.models import Base
from app.db.models_intent import ExecutionIntent
from app.db.models_control import SystemControl
from app.db.models_candles import Candle15m
from app.db.models_signal_outcome import SignalOutcome
from app.db.models_zerodha import ZerodhaSession
from app.db.models_indmoney import INDMoneySession
from app.db.models_instruments import IndstocksInstrument  # noqa: F401 — registers table
from app.core.scalp.scalp_paper_trader import ScalpTrade
from app.db.models_ai_log import AIUsageLog  # noqa: F401 — registers table


_MIGRATIONS = [
    "ALTER TABLE execution_intents ADD COLUMN IF NOT EXISTS execution_mode VARCHAR;",
    "ALTER TABLE risk_limits ADD COLUMN IF NOT EXISTS per_trade_risk_pct FLOAT DEFAULT 2.0;",
    "ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS merchant VARCHAR;",
    "ALTER TABLE indmoney_sessions ADD COLUMN IF NOT EXISTS mobile VARCHAR;",
    # Phase 1.3: Time-series composite indexes for performance
    "CREATE INDEX IF NOT EXISTS idx_candle_5m_symbol_ts ON candle_5m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_15m_symbol_ts ON candle_15m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_1h_symbol_ts ON candle_1h (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_daily_symbol_date ON candle_daily (symbol, date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_date ON ai_decisions (symbol, analysed_at DESC);",
]


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for stmt in _MIGRATIONS:
            conn.execute(text(stmt))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("✅ Database tables created")
