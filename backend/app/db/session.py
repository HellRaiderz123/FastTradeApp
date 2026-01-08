from pathlib import Path
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use an absolute path so the DB location doesn't depend on process CWD.
# Default location: backend/trading.db
_default_db_path = Path(__file__).resolve().parents[2] / "trading.db"

# Use in-memory DB for tests to avoid persistent state/uniques across runs
_is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
_is_testing_env = os.getenv("FASTTRADE_TESTING", "0") == "1"
if _is_pytest or _is_testing_env:
    DATABASE_URL = "sqlite:///:memory:"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path.as_posix()}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()
