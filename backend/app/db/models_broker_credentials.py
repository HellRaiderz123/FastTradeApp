from sqlalchemy import Column, Integer, String, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class BrokerCredentials(Base):
    """
    Stores broker API credentials encrypted at rest.
    One row per broker (ZERODHA, INDMONEY, …).
    Sensitive fields (api_key, api_secret, access_token) are Fernet-encrypted
    by broker_credentials_repo before insert and decrypted on read.
    """
    __tablename__ = "broker_credentials"

    id           = Column(Integer, primary_key=True, index=True)
    broker       = Column(String, unique=True, index=True, nullable=False)  # ZERODHA | INDMONEY
    api_key      = Column(String, nullable=True)   # encrypted
    api_secret   = Column(String, nullable=True)   # encrypted
    access_token = Column(String, nullable=True)   # encrypted
    active_broker = Column(String, nullable=True)  # currently selected broker name
    execution_mode = Column(String, nullable=True) # LIVE | PAPER_TRADING | DRY_RUN

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
