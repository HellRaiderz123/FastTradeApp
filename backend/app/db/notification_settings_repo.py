import logging
import os
from sqlalchemy.orm import Session
from app.db.models_notification_settings import NotificationSettings

logger = logging.getLogger(__name__)

# Reuse the same Fernet helper from broker_credentials_repo
try:
    from app.db.broker_credentials_repo import _encrypt, _decrypt, _safe_decrypt
except ImportError:
    def _encrypt(v: str) -> str: return v      # type: ignore[misc]
    def _decrypt(v: str) -> str: return v      # type: ignore[misc]
    def _safe_decrypt(v: str | None) -> str:   # type: ignore[misc]
        return v or ""


def get_notification_settings(db: Session) -> NotificationSettings | None:
    return db.query(NotificationSettings).first()


def get_notification_config(db: Session) -> dict:
    """Return fully decrypted notification config dict."""
    row = db.query(NotificationSettings).first()
    if not row:
        return {
            "gmail_user": os.getenv("GMAIL_USER", ""),
            "gmail_app_password": os.getenv("GMAIL_APP_PASSWORD", ""),
            "alert_email": os.getenv("ALERT_EMAIL", ""),
            "gmail_enabled": os.getenv("NOTIFY_GMAIL_ENABLED", "true").lower() in ("1", "true", "yes"),
            "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
            "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        }
    return {
        "gmail_user":         _safe_decrypt(row.gmail_user),
        "gmail_app_password": _safe_decrypt(row.gmail_app_password),
        "alert_email":        row.alert_email or "",
        "gmail_enabled":      row.gmail_enabled if row.gmail_enabled is not None else True,
        "telegram_bot_token": _safe_decrypt(row.telegram_bot_token),
        "telegram_chat_id":   row.telegram_chat_id or "",
    }


def upsert_notification_settings(db: Session, **kwargs) -> NotificationSettings:
    row = db.query(NotificationSettings).first()
    if row is None:
        row = NotificationSettings()
        db.add(row)
    # Encrypt sensitive fields
    for field in ("gmail_user", "gmail_app_password", "telegram_bot_token"):
        if field in kwargs and kwargs[field] is not None:
            kwargs[field] = _encrypt(kwargs[field]) if kwargs[field] else None
    for k, v in kwargs.items():
        if v is not None or k == "gmail_enabled":
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


def seed_notification_settings_from_env(db: Session) -> None:
    """Seed notification settings from env on first boot. Safe to re-run."""
    if db.query(NotificationSettings).first():
        return

    gmail_user     = os.getenv("GMAIL_USER", "")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "")
    alert_email    = os.getenv("ALERT_EMAIL", "")
    gmail_enabled  = os.getenv("NOTIFY_GMAIL_ENABLED", "true").lower() in ("1", "true", "yes")
    tg_token       = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_chat_id     = os.getenv("TELEGRAM_CHAT_ID", "")

    if not any([gmail_user, gmail_password, tg_token]):
        return  # nothing to seed

    row = NotificationSettings(
        gmail_user=_encrypt(gmail_user) if gmail_user else None,
        gmail_app_password=_encrypt(gmail_password) if gmail_password else None,
        alert_email=alert_email or None,
        gmail_enabled=gmail_enabled,
        telegram_bot_token=_encrypt(tg_token) if tg_token else None,
        telegram_chat_id=tg_chat_id or None,
    )
    db.add(row)
    db.commit()
    logger.info("✅ Notification settings seeded from env")
