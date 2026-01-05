from app.db.session import engine
from app.db.models import Base
from app.db.models_intent import ExecutionIntent
from app.db.models_control import SystemControl
from app.db.models_candles import Candle15m


def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("✅ Database tables created")
