"""Persistent storage for Alexa memory, reminders, and journal notes."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.utils.time import now_ist
from app.db.session import Base


class AlexaMemory(Base):
    __tablename__ = "alexa_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    memory_type = Column(String, nullable=False, index=True)  # note, reminder, journal
    content = Column(Text, nullable=False)
    locale = Column(String, nullable=False, default="en-US", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
