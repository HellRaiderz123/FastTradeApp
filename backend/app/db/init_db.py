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
from app.db.models_watchlist import Watchlist, WatchlistAlert  # noqa: F401
from app.db.models_trade_costs import TradeCost, BrokerageConfig  # noqa: F401
from app.db.models_nse import NseSnapshot  # noqa: F401
from app.db.models_twitter import TwitterSentiment  # noqa: F401
from app.db.models_fundamentals import FundamentalsCache  # noqa: F401
from app.db.models_finance import FinanceTransaction  # noqa: F401
from app.db.models_condition_strategy import ConditionStrategy  # noqa: F401
from app.db.models_scanner_signal import ScannerSignalHistory  # noqa: F401
from app.db.models_stock_holding import StockHolding  # noqa: F401
from app.db.models_risk import RiskLimitConfig  # noqa: F401
from app.db.models_notification import Notification  # noqa: F401
from app.db.models_alexa import AlexaMemory, AlexaInteractionLog  # noqa: F401
from app.db.models_ai_decisions import AIDecision  # noqa: F401
from app.db.models_auto_trader import AutoTraderConfig, AutoTraderLog  # noqa: F401
from app.db.models_signal_outcome import SignalOutcome  # noqa: F401 (already imported, safe)
from app.db.models_indmoney import INDMoneySession  # noqa: F401 (already imported, safe)

_MIGRATIONS_COMMON = [
    "ALTER TABLE execution_intents ADD COLUMN execution_mode VARCHAR;",
    "ALTER TABLE risk_limits ADD COLUMN per_trade_risk_pct FLOAT DEFAULT 2.0;",
    "ALTER TABLE finance_transactions ADD COLUMN merchant VARCHAR;",
    "ALTER TABLE indmoney_sessions ADD COLUMN mobile VARCHAR;",
    "CREATE INDEX IF NOT EXISTS idx_candle_5m_symbol_ts ON candle_5m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_15m_symbol_ts ON candle_15m (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_1h_symbol_ts ON candle_1h (symbol, timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_candle_daily_symbol_date ON candle_daily (symbol, date DESC);",
    "CREATE INDEX IF NOT EXISTS idx_ai_decisions_symbol_date ON ai_decisions (symbol, analysed_at DESC);",
]


def init_db():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for stmt in _MIGRATIONS_COMMON:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass  # ignore errors on already-applied migrations
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("\u2705 Database tables created")
