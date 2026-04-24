"""
Zerodha OAuth handler — manages login flow and token persistence in DB.

Flow:
1. User clicks "Login with Zerodha" button
2. Frontend opens login_url (GET /zerodha/login-url)
3. User logs in on Zerodha, gets request_token
4. Browser redirected to callback_url with request_token
5. Backend exchanges for access_token, stores in DB
6. Frontend redirected to success page with token status
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from kiteconnect import KiteConnect
from sqlalchemy.orm import Session

from app.db.models_zerodha import ZerodhaSession
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


def activate_access_token(
    db: Session,
    access_token: str,
    user_id: Optional[str] = None,
    ttl: Optional[timedelta] = None,
) -> Optional[ZerodhaSession]:
    """Mark a Zerodha access token as the active DB session."""
    if not access_token:
        return None

    session_ttl = ttl or timedelta(days=1)
    expires_at = now_ist() + session_ttl

    db.query(ZerodhaSession).filter(ZerodhaSession.is_active == 1).update({"is_active": 0})

    existing = db.query(ZerodhaSession).filter(ZerodhaSession.access_token == access_token).first()
    if existing:
        existing.is_active = 1
        existing.expires_at = expires_at
        if user_id:
            existing.user_id = user_id
        session = existing
    else:
        session = ZerodhaSession(
            access_token=access_token,
            user_id=user_id,
            expires_at=expires_at,
            is_active=1,
        )
        db.add(session)

    db.commit()
    db.refresh(session)
    return session


def get_login_url(callback_url: str) -> str:
    """Generate Zerodha OAuth login URL."""
    api_key = os.getenv("ZERODHA_API_KEY")
    if not api_key:
        raise ValueError("ZERODHA_API_KEY not configured")
    
    kite = KiteConnect(api_key=api_key)
    return kite.login_url()


def exchange_request_token_for_access_token(
    db: Session,
    request_token: str,
) -> Optional[str]:
    """
    Exchange Zerodha request token for access token.
    Stores the access token in DB.
    
    Returns:
        access_token if successful, else None
    """
    try:
        api_key = os.getenv("ZERODHA_API_KEY")
        api_secret = os.getenv("ZERODHA_API_SECRET")
        
        if not api_key or not api_secret:
            logger.error("Zerodha API key or secret not configured")
            return None
        
        kite = KiteConnect(api_key=api_key)
        session_data = kite.generate_session(request_token, api_secret=api_secret)
        
        access_token = session_data.get("access_token")
        user_id = session_data.get("user_id")
        
        if not access_token:
            logger.error("Failed to generate access token from request token")
            return None
        
        activate_access_token(
            db,
            access_token,
            user_id=user_id,
            ttl=timedelta(days=60),
        )
        
        logger.info(f"✅ Zerodha session created for user {user_id}")
        return access_token
        
    except Exception as e:
        logger.error(f"❌ Error exchanging request token: {e}")
        db.rollback()
        return None


def get_active_session(db: Session) -> Optional[ZerodhaSession]:
    """Get the currently active Zerodha session from DB."""
    session = (
        db.query(ZerodhaSession)
        .filter(ZerodhaSession.is_active == 1)
        .order_by(ZerodhaSession.created_at.desc())
        .first()
    )
    
    if session and session.expires_at and now_ist() > session.expires_at:
        # Token expired
        session.is_active = 0
        db.commit()
        return None
    
    return session


def get_access_token_for_client(db: Session) -> Optional[str]:
    """
    Get access token from DB, fallback to .env
    
    Priority:
    1. Active DB session
    2. .env ZERODHA_ACCESS_TOKEN
    3. None
    """
    # Try DB first
    session = get_active_session(db)
    if session:
        return session.access_token
    
    # Fallback to .env
    return os.getenv("ZERODHA_ACCESS_TOKEN")
