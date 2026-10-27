"""
AI Usage Log — one row per LLM API call made anywhere in FastTradeApp.

Captures: caller context, model used, prompt/response text, token counts,
latency, and any error. All LLM calls flow through llm_service._do_chat_completion
so a single hook there covers trading_agents, ai_chat, simple_ai, and future callers.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from app.db.session import Base
from app.core.utils.time import now_ist


class AIUsageLog(Base):
    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True)

    # Which caller / agent triggered this call
    caller      = Column(String(80), nullable=True, index=True)   # e.g. TechnicalAnalyst, ai_chat, simple_ai
    model       = Column(String(120), nullable=True, index=True)  # actual model used

    # Request
    system_prompt = Column(Text, nullable=True)
    user_prompt   = Column(Text, nullable=True)   # last user message (or full prompt for call_llm)

    # Response
    response_text = Column(Text, nullable=True)
    finish_reason = Column(String(30), nullable=True)  # stop | length | tool_calls | error

    # Token usage (from API response when available)
    prompt_tokens     = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens      = Column(Integer, nullable=True)

    # Performance
    latency_ms = Column(Float, nullable=True)

    # Error (if call failed)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), index=True, default=now_ist)

    __table_args__ = (
        Index("ix_ai_usage_logs_caller_created", "caller", "created_at"),
    )
