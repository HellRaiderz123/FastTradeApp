from sqlalchemy import Column, Integer, String, DateTime
from app.db.session import Base
from app.core.utils.time import now_ist


class UserSettings(Base):
    __tablename__ = "user_settings"

    id               = Column(Integer, primary_key=True, index=True)
    # LLM config
    llm_provider     = Column(String, default="groq")
    llm_api_key      = Column(String, nullable=True)
    llm_base_url     = Column(String, nullable=True)
    llm_model        = Column(String, default="llama-3.1-8b-instant")
    # News
    newsdata_api_key = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
