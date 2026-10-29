import logging
import os
from sqlalchemy.orm import Session
from app.db.models_user_settings import UserSettings

logger = logging.getLogger(__name__)


def get_user_settings(db: Session) -> UserSettings | None:
    return db.query(UserSettings).first()


def upsert_user_settings(db: Session, **kwargs) -> UserSettings:
    row = db.query(UserSettings).first()
    if row is None:
        row = UserSettings(**kwargs)
        db.add(row)
    else:
        for k, v in kwargs.items():
            if v is not None:
                setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def seed_user_settings_from_env(db: Session) -> None:
    """Seed LLM + newsdata keys from env on first boot. Safe to re-run."""
    if db.query(UserSettings).first():
        return  # already seeded

    llm_api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("NVIDIA_API_KEY")
        or ""
    )
    row = UserSettings(
        llm_provider=os.getenv("LLM_PROVIDER", "groq"),
        llm_api_key=llm_api_key or None,
        llm_base_url=os.getenv("LLM_BASE_URL") or None,
        llm_model=os.getenv("LLM_MODEL", "llama-3.1-8b-instant"),
        newsdata_api_key=os.getenv("NEWSDATA_API_KEY") or None,
    )
    db.add(row)
    db.commit()
    logger.info("✅ user_settings seeded from env")
