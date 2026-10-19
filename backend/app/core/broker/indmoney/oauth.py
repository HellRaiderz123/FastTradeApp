"""
INDMoney / INDstocks auth handler.

Flow:
  .env holds INDMONEY_MOBILE + INDMONEY_PIN (static, never changes).
  At login time the user supplies:
    - mtp   : Mobile Transaction Password (changes per session)
    - totp  : 6-digit authenticator code

  POST /user/login  →  access_token stored in DB
  client.py reads token from DB first, falls back to INDMONEY_ACCESS_TOKEN in .env.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.db.models_indmoney import INDMoneySession
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("INDMONEY_BASE_URL", "https://api.indstocks.com").rstrip("/")
_TIMEOUT = int(os.getenv("INDMONEY_HTTP_TIMEOUT_SECONDS", "15"))


def login(db: Session, mtp: str, totp: str) -> str:
    """
    Authenticate with INDstocks using mobile+pin+mtp+totp.
    Stores the returned access_token in DB and returns it.

    Raises RuntimeError on auth failure.
    """
    mobile = os.getenv("INDMONEY_MOBILE", "")
    pin = os.getenv("INDMONEY_PIN", "")

    if not mobile or not pin:
        raise RuntimeError("INDMONEY_MOBILE and INDMONEY_PIN must be set in .env")

    payload = {
        "mobileNumber": mobile,
        "pin": pin,
        "mtp": mtp,
        "totp": totp,
    }

    resp = requests.post(
        f"{_BASE_URL}/user/login",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=_TIMEOUT,
    )

    if resp.status_code >= 400:
        raise RuntimeError(f"INDMoney login failed ({resp.status_code}): {resp.text[:400]}")

    body = resp.json()

    # Support both flat and nested response shapes
    token = (
        body.get("accessToken")
        or body.get("access_token")
        or (body.get("data") or {}).get("accessToken")
        or (body.get("data") or {}).get("access_token")
    )
    client_id = (
        body.get("clientID")
        or body.get("client_id")
        or (body.get("data") or {}).get("clientID")
        or (body.get("data") or {}).get("client_id")
    )

    if not token:
        raise RuntimeError(f"INDMoney login: no access token in response: {body}")

    _store_token(db, token, client_id=client_id)
    logger.info("INDMoney login successful, token stored (client_id=%s)", client_id)
    return token


def _store_token(db: Session, token: str, client_id: Optional[str] = None) -> INDMoneySession:
    # Deactivate all existing sessions
    db.query(INDMoneySession).filter(INDMoneySession.is_active == 1).update({"is_active": 0})

    existing = db.query(INDMoneySession).filter(INDMoneySession.access_token == token).first()
    expires_at = now_ist() + timedelta(days=1)

    if existing:
        existing.is_active = 1
        existing.expires_at = expires_at
        if client_id:
            existing.client_id = client_id
        session = existing
    else:
        session = INDMoneySession(
            access_token=token,
            client_id=client_id,
            expires_at=expires_at,
            is_active=1,
        )
        db.add(session)

    db.commit()
    db.refresh(session)
    return session


def get_active_session(db: Session) -> Optional[INDMoneySession]:
    session = (
        db.query(INDMoneySession)
        .filter(INDMoneySession.is_active == 1)
        .order_by(INDMoneySession.created_at.desc())
        .first()
    )
    if session and session.expires_at and now_ist() > session.expires_at:
        session.is_active = 0
        db.commit()
        return None
    return session


def get_access_token(db: Session) -> Optional[str]:
    """DB-first, .env fallback."""
    session = get_active_session(db)
    if session:
        return session.access_token
    return os.getenv("INDMONEY_ACCESS_TOKEN", "") or None
