from sqlalchemy import text
from app.db.session import engine
from app.db.models import Base
from app.db.models_intent import ExecutionIntent
from app.db.models_control import SystemControl
from app.db.models_candles import Candle15m
from app.db.models_signal_outcome import SignalOutcome
from app.db.models_zerodha import ZerodhaSession
from app.core.scalp.scalp_paper_trader import ScalpTrade


_MIGRATIONS = [
    "ALTER TABLE execution_intents ADD COLUMN IF NOT EXISTS execution_mode VARCHAR;",
    "ALTER TABLE risk_limits ADD COLUMN IF NOT EXISTS per_trade_risk_pct FLOAT DEFAULT 2.0;",
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
