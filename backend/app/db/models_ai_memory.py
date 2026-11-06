from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from app.db.session import Base


class AIConversationMemory(Base):
    """Persists AI chat conversation turns per user across sessions."""
    __tablename__ = "ai_conversation_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(128), nullable=False, index=True)
    role = Column(String(16), nullable=False)   # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_ai_memory_user_created", "user_id", "created_at"),
    )
