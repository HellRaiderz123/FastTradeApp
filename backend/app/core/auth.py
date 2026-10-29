import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# python-jose JWT
# ---------------------------------------------------------------------------
try:
    from jose import JWTError, jwt as _jwt

    def _create_token(data: dict, expires_delta: timedelta) -> str:
        payload = data.copy()
        payload["exp"] = datetime.now(tz=timezone.utc) + expires_delta
        return _jwt.encode(payload, _secret_key(), algorithm="HS256")

    def _decode_token(token: str) -> dict:
        try:
            return _jwt.decode(token, _secret_key(), algorithms=["HS256"])
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc

    JOSE_AVAILABLE = True

except ImportError:
    # Fallback to existing custom JWT so nothing breaks if jose not installed yet
    import base64, hashlib, hmac, json
    logger.warning("python-jose not installed — using legacy JWT. Run: pip install python-jose[cryptography]")
    JOSE_AVAILABLE = False

    def _b64url_encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def _b64url_decode(raw: str) -> bytes:
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

    def _sign(payload_b64: str) -> str:
        digest = hmac.new(_secret_key().encode(), payload_b64.encode(), hashlib.sha256).digest()
        return _b64url_encode(digest)

    def _create_token(data: dict, expires_delta: timedelta) -> str:
        payload = data.copy()
        payload["exp"] = int((datetime.now(tz=timezone.utc) + expires_delta).timestamp())
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
        return f"{payload_b64}.{_sign(payload_b64)}"

    def _decode_token(token: str) -> dict:
        parts = token.split(".")
        if len(parts) != 2:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")
        payload_b64, sig = parts
        if not hmac.compare_digest(sig, _sign(payload_b64)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")
        payload = json.loads(_b64url_decode(payload_b64).decode())
        if int(datetime.now(tz=timezone.utc).timestamp()) >= int(payload.get("exp", 0)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        return payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "true").strip().lower() == "true"


def _secret_key() -> str:
    secret = os.getenv("AUTH_SECRET_KEY", "")
    if not secret:
        logger.warning("AUTH_SECRET_KEY not set — using insecure dev fallback")
        return "dev-insecure-auth-secret-change-me"
    return secret


def _access_token_minutes() -> int:
    try:
        return int(os.getenv("AUTH_TOKEN_EXPIRE_MINUTES", "480"))
    except Exception:
        return 480


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_access_token(username: str, user_id: int | None = None, role: str = "user") -> Dict[str, Any]:
    expires_in = _access_token_minutes() * 60
    token = _create_token(
        {"sub": username, "user_id": user_id, "role": role},
        timedelta(seconds=expires_in),
    )
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


def decode_access_token(token: str) -> Dict[str, Any]:
    return _decode_token(token)


def verify_login_credentials(username: str, password: str) -> bool:
    """
    Legacy env-based check — used only as fallback if DB is unavailable.
    Primary path is authenticate_user() in user_repo.
    """
    import hmac as _hmac
    expected_u = os.getenv("AUTH_USERNAME", "admin")
    expected_p = os.getenv("AUTH_PASSWORD", "")
    return _hmac.compare_digest(username, expected_u) and _hmac.compare_digest(password, expected_p)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Dict[str, Any]:
    if not _is_auth_enabled():
        return {"username": "anonymous", "user_id": None, "role": "admin", "auth_enabled": False}

    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif request is not None:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    payload = decode_access_token(token)
    return {
        "username": payload.get("sub"),
        "user_id": payload.get("user_id"),
        "role": payload.get("role", "user"),
        "auth_enabled": True,
        "exp": payload.get("exp"),
    }


def require_authenticated_user(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    return current_user


def require_admin(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def authenticate_websocket(websocket: WebSocket) -> Dict[str, Any]:
    if not _is_auth_enabled():
        return {"username": "anonymous", "user_id": None, "role": "admin", "auth_enabled": False}

    token = None
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    payload = decode_access_token(token)
    return {
        "username": payload.get("sub"),
        "user_id": payload.get("user_id"),
        "role": payload.get("role", "user"),
        "auth_enabled": True,
        "exp": payload.get("exp"),
    }
