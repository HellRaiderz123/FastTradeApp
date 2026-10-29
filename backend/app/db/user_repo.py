import logging
import os
from sqlalchemy.orm import Session
from app.db.models_user import User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing — use passlib bcrypt (already pulled in by many deps)
# Falls back to hashlib sha256 if passlib not available
# ---------------------------------------------------------------------------
try:
    from passlib.context import CryptContext
    _pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(plain: str) -> str:
        return _pwd_ctx.hash(plain)

    def verify_password(plain: str, hashed: str) -> bool:
        return _pwd_ctx.verify(plain, hashed)

except ImportError:
    import hashlib, hmac as _hmac
    logger.warning("passlib not installed — using sha256 fallback (install passlib[bcrypt])")

    def hash_password(plain: str) -> str:  # type: ignore[misc]
        return hashlib.sha256(plain.encode()).hexdigest()

    def verify_password(plain: str, hashed: str) -> bool:  # type: ignore[misc]
        return _hmac.compare_digest(hashlib.sha256(plain.encode()).hexdigest(), hashed)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username, User.is_active == True).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active == True).first()


def get_all_users(db: Session) -> list[User]:
    return db.query(User).filter(User.is_active == True).all()


def create_user(
    db: Session,
    username: str,
    password: str,
    email: str | None = None,
    role: str = "user",
) -> User:
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def update_user_password(db: Session, user_id: int, new_password: str) -> bool:
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    user.password_hash = hash_password(new_password)
    db.commit()
    return True


def update_user_preferences(
    db: Session,
    user_id: int,
    active_broker: str | None = None,
    execution_mode: str | None = None,
) -> User | None:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    if active_broker is not None:
        user.active_broker = active_broker
    if execution_mode is not None:
        user.execution_mode = execution_mode
    db.commit()
    db.refresh(user)
    return user


def seed_admin_from_env(db: Session) -> None:
    """
    On first boot, create the admin user from AUTH_USERNAME / AUTH_PASSWORD env vars.
    Safe to call on every startup — skips if user already exists.
    """
    username = os.getenv("AUTH_USERNAME", "admin")
    password = os.getenv("AUTH_PASSWORD", "")
    if not password:
        logger.warning("AUTH_PASSWORD not set — skipping admin seed")
        return

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return  # already seeded

    active_broker  = os.getenv("ACTIVE_BROKER", "ZERODHA")
    execution_mode = os.getenv("EXECUTION_MODE", "PAPER_TRADING")

    user = User(
        username=username,
        password_hash=hash_password(password),
        role="admin",
        active_broker=active_broker,
        execution_mode=execution_mode,
    )
    db.add(user)
    db.commit()
    logger.info("✅ Admin user '%s' seeded from env", username)
