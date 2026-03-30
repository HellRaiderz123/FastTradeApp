import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def _is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() == "true"


def _secret_key() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if not secret:
        logger.warning("AUTH_SECRET_KEY is not set; using insecure fallback key for development")
        return "dev-insecure-auth-secret-change-me"
    return secret


def _token_expiry_minutes() -> int:
    try:
        return int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "480"))
    except Exception:
        return 480


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _sign(payload_b64: str) -> str:
    digest = hmac.new(
        _secret_key().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def create_access_token(username: str) -> Dict[str, Any]:
    expires_in = _token_expiry_minutes() * 60
    now_ts = int(datetime.now(tz=timezone.utc).timestamp())
    payload = {
        "sub": username,
        "iat": now_ts,
        "exp": now_ts + expires_in,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    token = f"{payload_b64}.{_sign(payload_b64)}"
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Invalid token format")

        payload_b64, signature = parts
        expected = _sign(payload_b64)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid token signature")

        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))

        exp = int(payload.get("exp", 0))
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        if now_ts >= exp:
            raise ValueError("Token expired")

        sub = payload.get("sub")
        if not sub or not isinstance(sub, str):
            raise ValueError("Invalid token subject")

        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def _expected_username() -> str:
    return os.getenv("AUTH_USERNAME", "admin")


def _expected_password() -> str:
    return os.getenv("AUTH_PASSWORD", "admin123")


def verify_login_credentials(username: str, password: str) -> bool:
    expected_u = _expected_username()
    expected_p = _expected_password()
    return hmac.compare_digest(username, expected_u) and hmac.compare_digest(password, expected_p)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Dict[str, Any]:
    if not _is_auth_enabled():
        return {"username": "anonymous", "auth_enabled": False}

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_access_token(credentials.credentials)
    return {
        "username": payload["sub"],
        "auth_enabled": True,
        "exp": payload.get("exp"),
    }


def require_authenticated_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return current_user


def authenticate_websocket(websocket: WebSocket) -> Dict[str, Any]:
    """
    Authenticate a WebSocket connection using bearer token from either:
    1) Authorization header: Bearer <token>
    2) Query param: ?token=<token>
    """
    if not _is_auth_enabled():
        return {"username": "anonymous", "auth_enabled": False}

    token = None

    auth_header = websocket.headers.get("authorization", "")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        token = websocket.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_access_token(token)
    return {
        "username": payload["sub"],
        "auth_enabled": True,
        "exp": payload.get("exp"),
    }
