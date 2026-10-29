import logging
import os
import base64
from sqlalchemy.orm import Session
from app.db.models_broker_credentials import BrokerCredentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fernet encryption — key derived from JWT_SECRET so no extra env var needed
# Falls back to identity (no encryption) if cryptography not installed
# ---------------------------------------------------------------------------
try:
    from cryptography.fernet import Fernet
    import hashlib

    def _fernet() -> Fernet:
        secret = os.getenv("JWT_SECRET", "dev-insecure-secret")
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)

    def _encrypt(value: str) -> str:
        return _fernet().encrypt(value.encode()).decode()

    def _decrypt(value: str) -> str:
        return _fernet().decrypt(value.encode()).decode()

except ImportError:
    logger.warning("cryptography not installed — broker credentials stored unencrypted")

    def _encrypt(value: str) -> str:  # type: ignore[misc]
        return value

    def _decrypt(value: str) -> str:  # type: ignore[misc]
        return value


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def _safe_decrypt(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _decrypt(value)
    except Exception:
        return value  # already plaintext (legacy row)


def get_broker_credentials(db: Session, broker: str) -> dict:
    """Return decrypted credentials dict for a broker. Empty strings if not set."""
    row = db.query(BrokerCredentials).filter(BrokerCredentials.broker == broker.upper()).first()
    if not row:
        return {"api_key": "", "api_secret": "", "access_token": ""}
    return {
        "api_key":      _safe_decrypt(row.api_key),
        "api_secret":   _safe_decrypt(row.api_secret),
        "access_token": _safe_decrypt(row.access_token),
    }


def get_active_broker_from_db(db: Session) -> str | None:
    """Return the stored active_broker value (from the settings row)."""
    row = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "_SETTINGS").first()
    return row.active_broker if row else None


def get_execution_mode_from_db(db: Session) -> str | None:
    row = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "_SETTINGS").first()
    return row.execution_mode if row else None


def upsert_broker_credentials(
    db: Session,
    broker: str,
    api_key: str | None = None,
    api_secret: str | None = None,
    access_token: str | None = None,
) -> BrokerCredentials:
    broker = broker.upper()
    row = db.query(BrokerCredentials).filter(BrokerCredentials.broker == broker).first()
    if row is None:
        row = BrokerCredentials(broker=broker)
        db.add(row)
    if api_key is not None:
        row.api_key = _encrypt(api_key) if api_key else None
    if api_secret is not None:
        row.api_secret = _encrypt(api_secret) if api_secret else None
    if access_token is not None:
        row.access_token = _encrypt(access_token) if access_token else None
    db.commit()
    db.refresh(row)
    return row


def upsert_app_settings(
    db: Session,
    active_broker: str | None = None,
    execution_mode: str | None = None,
) -> BrokerCredentials:
    """Store app-level settings (active broker, execution mode) in a sentinel row."""
    row = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "_SETTINGS").first()
    if row is None:
        row = BrokerCredentials(broker="_SETTINGS")
        db.add(row)
    if active_broker is not None:
        row.active_broker = active_broker
    if execution_mode is not None:
        row.execution_mode = execution_mode
    db.commit()
    db.refresh(row)
    return row


def seed_broker_credentials_from_env(db: Session) -> None:
    """Seed broker credentials from env on first boot. Safe to re-run."""
    # Zerodha
    zerodha_key    = os.getenv("ZERODHA_API_KEY", "")
    zerodha_secret = os.getenv("ZERODHA_API_SECRET", "")
    zerodha_token  = os.getenv("ZERODHA_ACCESS_TOKEN", "")
    existing = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "ZERODHA").first()
    if not existing and (zerodha_key or zerodha_secret or zerodha_token):
        upsert_broker_credentials(
            db, "ZERODHA",
            api_key=zerodha_key or None,
            api_secret=zerodha_secret or None,
            access_token=zerodha_token or None,
        )
        logger.info("✅ Zerodha credentials seeded from env")

    # INDMoney
    indmoney_token = os.getenv("INDMONEY_ACCESS_TOKEN", "")
    existing_ind = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "INDMONEY").first()
    if not existing_ind and indmoney_token:
        upsert_broker_credentials(db, "INDMONEY", access_token=indmoney_token)
        logger.info("✅ INDMoney credentials seeded from env")

    # App settings
    existing_settings = db.query(BrokerCredentials).filter(BrokerCredentials.broker == "_SETTINGS").first()
    if not existing_settings:
        upsert_app_settings(
            db,
            active_broker=os.getenv("ACTIVE_BROKER", "ZERODHA"),
            execution_mode=os.getenv("EXECUTION_MODE", "PAPER_TRADING"),
        )
        logger.info("✅ App settings (broker/mode) seeded from env")
