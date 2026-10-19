from sqlalchemy import Column, Integer, String, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class INDMoneySession(Base):
    __tablename__ = "indmoney_sessions"

    id = Column(Integer, primary_key=True)
    access_token = Column(String, nullable=False, unique=True, index=True)
    client_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Integer, default=1)  # 1 = active, 0 = revoked/expired
