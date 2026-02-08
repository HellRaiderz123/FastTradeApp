"""
Retry handler for transient API errors (503, timeouts, connection errors)
Implements exponential backoff with jitter for Zerodha API calls
"""

import logging
import time
import random
from typing import Optional, Callable, Any, TypeVar
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Define transient error types
TRANSIENT_ERROR_MESSAGES = [
    "503",  # Service unavailable
    "timeout",  # Connection timeout
    "Connection refused",
    "Connection reset",
    "temporarily unavailable",
    "service unavailable",
    "502",  # Bad gateway
    "504",  # Gateway timeout
]


def is_transient_error(exception: Exception) -> bool:
    """
    Check if an exception represents a transient error that should retry
    
    Returns:
        True if the error is transient (503, timeout, connection error, etc.)
        False if the error is permanent (auth error, 404, etc.)
    """
    error_str = str(exception).lower()
    
    # Check for known transient error patterns
    for pattern in TRANSIENT_ERROR_MESSAGES:
        if pattern.lower() in error_str:
            return True
    
    # Check for specific exception types
    exception_type = type(exception).__name__
    transient_types = [
        "ConnectionError",
        "TimeoutError",
        "ReadTimeoutError",
        "ConnectTimeoutError",
        "Timeout",
        "ClientOSError",
        "ServerTimeoutError",
    ]
    
    return exception_type in transient_types


def retry_on_transient_error(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0
):
    """
    Decorator for retrying API calls on transient errors with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (in seconds)
        max_delay: Maximum delay between retries (in seconds)
        backoff_factor: Multiplier for exponential backoff
    
    Returns:
        Decorated function that retries on transient errors
    
    Example:
        @retry_on_transient_error(max_retries=3, base_delay=1.0)
        def fetch_quotes(symbols):
            return kite.quote(symbols)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Optional[T]:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # If it's not a transient error, raise immediately
                    if not is_transient_error(e):
                        logger.warning(f"Non-transient error in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__} "
                            f"after {attempt + 1} attempts. Last error: {e}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay * (backoff_factor ** attempt),
                        max_delay
                    )
                    # Add jitter (±10% of delay)
                    jitter = delay * (0.1 * random.random() * 2 - 0.1)
                    actual_delay = delay + jitter
                    
                    logger.warning(
                        f"Transient error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {actual_delay:.2f}s..."
                    )
                    
                    time.sleep(actual_delay)
            
            # If we get here, all retries failed
            logger.error(f"All retries failed for {func.__name__}. Returning None.")
            return None
        
        return wrapper
    return decorator


async def retry_on_transient_error_async(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0
):
    """
    Decorator for async functions to retry on transient errors with exponential backoff
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Optional[Any]:
            import asyncio
            
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # If it's not a transient error, raise immediately
                    if not is_transient_error(e):
                        logger.warning(f"Non-transient error in {func.__name__}: {e}")
                        raise
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__} "
                            f"after {attempt + 1} attempts. Last error: {e}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff + jitter
                    delay = min(
                        base_delay * (backoff_factor ** attempt),
                        max_delay
                    )
                    # Add jitter (±10% of delay)
                    jitter = delay * (0.1 * random.random() * 2 - 0.1)
                    actual_delay = delay + jitter
                    
                    logger.warning(
                        f"Transient error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {actual_delay:.2f}s..."
                    )
                    
                    await asyncio.sleep(actual_delay)
            
            # If we get here, all retries failed
            logger.error(f"All retries failed for {func.__name__}. Returning None.")
            return None
        
        return wrapper
    
    return decorator


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0
) -> Optional[Any]:
    """
    Call a function with retry logic for transient errors
    
    Args:
        func: Function to call
        max_retries: Maximum attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        backoff_factor: Exponential backoff multiplier
    
    Returns:
        Result of function call or None if all retries fail
    
    Example:
        result = retry_with_backoff(
            lambda: kite.quote(['NFO:NIFTY26000CE']),
            max_retries=3
        )
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            if not is_transient_error(e):
                logger.warning(f"Non-transient error: {e}")
                raise
            
            if attempt >= max_retries:
                logger.error(f"Max retries exceeded. Last error: {e}")
                break
            
            delay = min(
                base_delay * (backoff_factor ** attempt),
                max_delay
            )
            jitter = delay * (0.1 * random.random() * 2 - 0.1)
            actual_delay = delay + jitter
            
            logger.warning(
                f"Transient error (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {actual_delay:.2f}s..."
            )
            
            time.sleep(actual_delay)
    
    return None
