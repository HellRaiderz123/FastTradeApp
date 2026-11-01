"""
Async Database Session Module

Provides async SQLAlchemy session support for FastAPI async routes.
Falls back gracefully to sync sessions when async driver is unavailable.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# Check if async support is available
_ASYNC_AVAILABLE = False
_async_engine = None
_AsyncSessionLocal = None

try:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    _ASYNC_AVAILABLE = True
except ImportError:
    logger.info("Async SQLAlchemy not available, using sync sessions only")


def _get_async_database_url() -> Optional[str]:
    """
    Convert DATABASE_URL to async format if possible.
    
    - sqlite:/// -> sqlite+aiosqlite:///
    - postgresql:// -> postgresql+asyncpg://
    """
    from app.db.session import DATABASE_URL
    
    if DATABASE_URL.startswith("sqlite:///"):
        # Check if aiosqlite is available
        try:
            import aiosqlite  # noqa: F401
            return DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
        except ImportError:
            logger.debug("aiosqlite not installed, async SQLite not available")
            return None
    
    elif DATABASE_URL.startswith("postgresql://"):
        # Check if asyncpg is available
        try:
            import asyncpg  # noqa: F401
            return DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        except ImportError:
            logger.debug("asyncpg not installed, async PostgreSQL not available")
            return None
    
    elif DATABASE_URL.startswith("postgresql+asyncpg://"):
        return DATABASE_URL
    
    elif DATABASE_URL.startswith("sqlite+aiosqlite://"):
        return DATABASE_URL
    
    return None


def _init_async_engine():
    """Initialize async engine if available."""
    global _async_engine, _AsyncSessionLocal
    
    if not _ASYNC_AVAILABLE:
        return
    
    async_url = _get_async_database_url()
    if not async_url:
        logger.info("Async database URL not available, using sync sessions")
        return
    
    try:
        _async_engine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True,
        )
        
        _AsyncSessionLocal = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info("✅ Async database engine initialized: %s", async_url.split("@")[-1] if "@" in async_url else async_url[:50])
    except Exception as e:
        logger.warning("Failed to initialize async engine: %s", e)
        _async_engine = None
        _AsyncSessionLocal = None


# Initialize on module load
_init_async_engine()


def is_async_available() -> bool:
    """Check if async database sessions are available."""
    return _AsyncSessionLocal is not None


@asynccontextmanager
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Usage:
        async with get_async_db() as db:
            result = await db.execute(select(Model))
    
    Raises:
        RuntimeError: If async sessions are not available
    """
    if _AsyncSessionLocal is None:
        raise RuntimeError(
            "Async database sessions not available. "
            "Install aiosqlite (for SQLite) or asyncpg (for PostgreSQL)."
        )
    
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_async_db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_async_db_dependency)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    if _AsyncSessionLocal is None:
        # Fall back to sync session wrapped in async
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            yield db  # type: ignore
        finally:
            db.close()
        return
    
    async with _AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


class AsyncDBContext:
    """
    Helper class for running async DB operations from sync code.
    
    Usage:
        async def my_async_query(db):
            result = await db.execute(select(Model))
            return result.scalars().all()
        
        # From sync code:
        result = AsyncDBContext.run(my_async_query)
    """
    
    @staticmethod
    def run(coro_func, *args, **kwargs):
        """
        Run an async function that takes a db session as first argument.
        
        Args:
            coro_func: Async function that accepts db session as first arg
            *args, **kwargs: Additional arguments to pass to the function
        
        Returns:
            Result of the async function
        """
        import asyncio
        
        async def _run():
            async with get_async_db() as db:
                return await coro_func(db, *args, **kwargs)
        
        # Get or create event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run())
                return future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            return asyncio.run(_run())


# Convenience function for hybrid sync/async code
def get_db_session():
    """
    Get a database session (sync).
    
    For new async code, prefer get_async_db() or get_async_db_dependency().
    This function exists for backward compatibility.
    """
    from app.db.session import SessionLocal
    return SessionLocal()
