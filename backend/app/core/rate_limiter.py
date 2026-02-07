"""
Rate Limiter for Zerodha API (3 requests/second max)
Prevents hitting API limits by queuing and spacing out requests
"""

import asyncio
import time
import logging
from typing import Optional, Dict, Any, Callable
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for API calls
    Zerodha limit: 3 requests per second
    """
    
    def __init__(self, max_requests: int = 3, window_seconds: float = 1.0):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Token bucket: refill at fixed rate
        self.tokens = max_requests
        self.last_refill = time.time()
        
        # Per-endpoint tracking
        self.endpoint_calls: Dict[str, list] = defaultdict(list)
        self.endpoint_lock = asyncio.Lock()
        
        logger.info(f"RateLimiter initialized: {max_requests} req/{window_seconds}s")
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        
        if elapsed > 0:
            # Add tokens at rate: max_requests / window_seconds
            refill_rate = self.max_requests / self.window_seconds
            new_tokens = refill_rate * elapsed
            
            self.tokens = min(self.max_requests, self.tokens + new_tokens)
            self.last_refill = now
    
    def acquire(self, cost: int = 1, block: bool = True) -> bool:
        """
        Acquire tokens for a request
        
        Args:
            cost: Number of tokens to consume (default 1)
            block: Whether to sleep until tokens available
        
        Returns:
            True if acquired, False if blocked without waiting
        """
        self._refill_tokens()
        
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        
        if not block:
            return False
        
        # Calculate wait time
        tokens_needed = cost - self.tokens
        wait_time = tokens_needed / (self.max_requests / self.window_seconds)
        
        logger.debug(f"Rate limited: waiting {wait_time:.2f}s")
        time.sleep(wait_time)
        
        self._refill_tokens()
        self.tokens -= cost
        return True
    
    async def acquire_async(self, cost: int = 1) -> bool:
        """
        Async version of acquire
        
        Args:
            cost: Number of tokens to consume
        
        Returns:
            True if acquired
        """
        async with self.endpoint_lock:
            self._refill_tokens()
            
            if self.tokens >= cost:
                self.tokens -= cost
                return True
        
        # Calculate wait time
        tokens_needed = cost - self.tokens
        wait_time = tokens_needed / (self.max_requests / self.window_seconds)
        
        logger.debug(f"Rate limited (async): waiting {wait_time:.2f}s")
        await asyncio.sleep(wait_time)
        
        async with self.endpoint_lock:
            self._refill_tokens()
            self.tokens -= cost
            return True
    
    def get_wait_time(self) -> float:
        """Get current wait time if rate limited (in seconds)"""
        self._refill_tokens()
        
        if self.tokens >= 1:
            return 0
        
        tokens_needed = 1 - self.tokens
        wait_time = tokens_needed / (self.max_requests / self.window_seconds)
        return wait_time


class RequestCache:
    """
    Simple in-memory cache for API responses
    Reduces redundant API calls
    """
    
    def __init__(self, ttl_seconds: int = 2):
        """
        Initialize cache
        
        Args:
            ttl_seconds: Time-to-live for cached items
        """
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # key -> (data, expiry_time)
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self.cache:
            return None
        
        data, expiry_time = self.cache[key]
        
        if time.time() > expiry_time:
            del self.cache[key]
            return None
        
        logger.debug(f"Cache hit: {key}")
        return data
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """Set value in cache"""
        ttl = ttl or self.ttl_seconds
        expiry_time = time.time() + ttl
        self.cache[key] = (data, expiry_time)
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
    
    def clear(self):
        """Clear entire cache"""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = time.time()
        active_items = sum(1 for _, expiry in self.cache.values() if now < expiry)
        
        return {
            "total_items": len(self.cache),
            "active_items": active_items,
            "expired_items": len(self.cache) - active_items
        }


class ZerodhaRateLimiter:
    """
    Zerodha-specific rate limiter with per-method limits
    """
    
    def __init__(self):
        # Zerodha has 3 requests per second globally
        self.global_limiter = RateLimiter(max_requests=3, window_seconds=1.0)
        
        # Method-specific limiters (optional)
        self.quote_limiter = self.global_limiter
        self.bulk_quote_limiter = self.global_limiter
        self.option_chain_limiter = self.global_limiter
        
        # Response cache
        self.cache = RequestCache(ttl_seconds=2)
    
    def acquire_for_quote(self, cost: int = 1) -> bool:
        """Acquire tokens for a quote request"""
        return self.quote_limiter.acquire(cost=cost)
    
    async def acquire_for_quote_async(self, cost: int = 1) -> bool:
        """Async version"""
        return await self.quote_limiter.acquire_async(cost=cost)
    
    def get_cache(self, key: str) -> Optional[Any]:
        """Get cached response"""
        return self.cache.get(key)
    
    def set_cache(self, key: str, data: Any, ttl: int = 2):
        """Cache a response"""
        self.cache.set(key, data, ttl=ttl)
    
    def get_wait_time(self) -> float:
        """Get current wait time"""
        return self.global_limiter.get_wait_time()


# Global rate limiter instance
zerodha_limiter = ZerodhaRateLimiter()


def rate_limited(func: Callable) -> Callable:
    """
    Decorator for rate-limited functions
    Usage:
        @rate_limited
        def my_api_call():
            ...
    """
    def wrapper(*args, **kwargs):
        zerodha_limiter.acquire_for_quote()
        return func(*args, **kwargs)
    return wrapper
