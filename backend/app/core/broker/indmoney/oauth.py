"""
INDMoney / INDstocks auth handler.

Correct flow (per INDstocks API docs, verified from OpenAlgo):
  Endpoint : POST /generate/token
  Header   : x-api-key: <client_id>   (NOT Authorization)
  Body     : { "mpin": "...", "totp": "..." }
  Response : { "data": { "token": "..." } }

  client_id comes from INDMONEY_CLIENT_ID env var or supplied at login time.
  Token expires after 24 hours. Only one TOTP token is live at a time.

  POST /indmoney/login  ->  token stored in DB
  client.py reads token from DB first, falls back to INDMONEY_ACCESS_TOKEN in .env.
"""

import logging
import os
from datetime import timedelta
from typing import Optional

import requests
from sqlalchemy.orm import Session

from app.db.models_indmoney import INDMoneySession
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("INDMONEY_BASE_URL", "https://api.indstocks.com").rstrip("/")
_TIMEOUT = int(os.getenv("INDMONEY_HTTP_TIMEOUT_SECONDS", "30"))


def login(db: Session, client_id: str, mpin: str, totp: str) -> str:
    """
    Authenticate with INDstocks via POST /generate/token.

    Args:
        client_id : Client ID from INDstocks access-tokens page (sent as x-api-key header)
        mpin      : Account MPIN
        totp      : Current 6-digit TOTP code from authenticator app

    Returns the access token and stores it in DB.
    Raises RuntimeError on failure.

    NOTE: Rate limited to 1 call/60s. 5 wrong TOTPs in 15 min locks the endpoint.
    Never retry automatically.
    """
    client_id = (client_id or "").strip()
    mpin = (mpin or "").strip()
    totp = (str(totp) if totp is not None else "").strip()  # preserve leading zeros

    if not client_id or not mpin or not totp:
        raise RuntimeError("client_id, mpin and totp are all required")

    resp = requests.post(
        f"{_BASE_URL}/generate/token",
        json={"mpin": mpin, "totp": totp},
        headers={
            "x-api-key": client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        timeout=_TIMEOUT,
    )

    if resp.status_code >= 400:
        try:
            body = resp.json()
            msg = body.get("message") or body.get("error") or resp.text[:300]
        except Exception:
            msg = resp.text[:300]
        raise RuntimeError(f"INDMoney login failed ({resp.status_code}): {msg}")

    body = resp.json()
    data = body.get("data") or {}
    token = (
        data.get("token")
        or data.get("access_token")
        or body.get("token")
        or body.get("access_token")
    )

    if not token:
        raise RuntimeError(f"INDMoney login: no token in response: {body}")

    _store_token(db, token, client_id=client_id)
    logger.info("INDMoney login successful, token stored (client_id=%s)", client_id)
    return token


def _store_token(db: Session, token: str, client_id: Optional[str] = None) -> INDMoneySession:
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
