"""Persistent storage for Alexa memory plus request/response analytics."""

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

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


class AlexaInteractionLog(Base):
    __tablename__ = "alexa_interaction_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    locale = Column(String, nullable=False, default="en-US", index=True)
    request_type = Column(String, nullable=False, index=True)
    intent_name = Column(String, nullable=True, index=True)
    question = Column(Text, nullable=True)
    spoken_response = Column(Text, nullable=True)
    request_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True, index=True)
    application_id = Column(String, nullable=True, index=True)
    response_status_code = Column(Integer, nullable=False, default=200)
    latency_ms = Column(Float, nullable=True)
    used_fasttrade_context = Column(Boolean, nullable=False, default=False)
    is_alert_request = Column(Boolean, nullable=False, default=False)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_ist, index=True)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "locale": self.locale,
            "request_type": self.request_type,
            "intent_name": self.intent_name,
            "question": self.question,
            "spoken_response": self.spoken_response,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "application_id": self.application_id,
            "response_status_code": self.response_status_code,
            "latency_ms": self.latency_ms,
            "used_fasttrade_context": bool(self.used_fasttrade_context),
            "is_alert_request": bool(self.is_alert_request),
            "success": bool(self.success),
            "error_message": self.error_message,
            "request_payload": self.request_payload,
            "response_payload": self.response_payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
