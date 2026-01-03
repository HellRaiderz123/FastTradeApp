from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey
from datetime import datetime, timedelta

from app.db.session import Base
from sqlalchemy import Float

class ExecutionIntent(Base):
    __tablename__ = "execution_intents"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, nullable=False)  # strategy_runs.id

    intent_id = Column(String, unique=True, index=True)
    strategy = Column(String)
    underlying = Column(String)

    ticket = Column(JSON)

    status = Column(String, default="CONFIRMED")
    expires_at = Column(DateTime)

    executed = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    status = Column(String, default="CONFIRMED")  
    executed = Column(Boolean, default=False)

    avg_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)

    execution_result = Column(JSON, nullable=True)