from pathlib import Path
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool, StaticPool

# Use an absolute path so the DB location doesn't depend on process CWD.
_default_db_path = Path(__file__).resolve().parents[2] / "trading.db"

# Use in-memory DB for tests
_is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
_is_testing_env = os.getenv("FASTTRADE_TESTING", "0") == "1"

if _is_pytest or _is_testing_env:
    DATABASE_URL = "sqlite:///:memory:"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path.as_posix()}")

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    if ":memory:" in DATABASE_URL:
        # In-memory SQLite: must share a single connection across threads
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # File-based SQLite: NullPool — each session gets its own connection,
        # no pool contention between background threads.
        # WAL mode allows concurrent readers + one writer without blocking.
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False, "timeout": 30},
            poolclass=NullPool,
        )
else:
    # PostgreSQL / other: use default QueuePool with generous limits
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=40,
        pool_timeout=30,
        pool_pre_ping=True,
    )

# SQLite WAL mode pragma (applied on every new connection)
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")  # 10s busy wait instead of immediate error
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
