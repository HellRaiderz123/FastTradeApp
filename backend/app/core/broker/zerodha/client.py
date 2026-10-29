import os
from kiteconnect import KiteConnect
import logging
from app.db.session import SessionLocal
from app.core.broker.zerodha.oauth import get_access_token_for_client

_kite = None

logger = logging.getLogger("connect")
logger.setLevel(logging.INFO)


def get_kite_client() -> KiteConnect:
    global _kite

    api_key = os.getenv("ZERODHA_API_KEY")

    # Always fetch the current token from DB — never use a cached client
    # because Zerodha tokens expire daily and the singleton would stay stale.
    db = SessionLocal()
    try:
        access_token = get_access_token_for_client(db)
    except Exception as e:
        logger.warning(f"Failed to get token from DB, using .env: {e}")
        access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
    finally:
        db.close()

    if not api_key or not access_token:
        _kite = None
        raise RuntimeError("Zerodha API key or access token missing")

    # Reuse cached client only if the token hasn't changed
    if _kite and _kite.access_token == access_token:
        return _kite

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    _kite = kite
    return kite
