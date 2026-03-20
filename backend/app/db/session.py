from pathlib import Path
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Use an absolute path so the DB location doesn't depend on process CWD.
_default_db_path = Path(__file__).resolve().parents[2] / "trading.db"

# Use in-memory DB for tests
_is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
_is_testing_env = os.getenv("FASTTRADE_TESTING", "0") == "1"

if _is_pytest or _is_testing_env:
    DATABASE_URL = "sqlite:///:memory:"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path.as_posix()}")

_is_postgres = DATABASE_URL.startswith("postgresql")
_is_sqlite = DATABASE_URL.startswith("sqlite")

# Build engine kwargs based on DB type
_engine_kwargs = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {
        "check_same_thread": False,
        "timeout": 30,
    }
elif _is_postgres:
    # Connection pool tuning for Postgres (Neon serverless works best with these)
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True       # detect stale connections
    _engine_kwargs["pool_recycle"] = 300         # recycle every 5 min (Neon idle timeout)
    _engine_kwargs["connect_args"] = {
        "sslmode": "require",
        "options": "-c timezone=Asia/Kolkata",
    }

engine = create_engine(DATABASE_URL, **_engine_kwargs)

# SQLite-only: enable WAL mode for concurrent reads
if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
