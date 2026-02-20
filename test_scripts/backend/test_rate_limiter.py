"""
Test rate limiter implementation
Run: python -m pytest backend/test_rate_limiter.py -v
"""

import time
import pytest
from app.core.rate_limiter import RateLimiter, RequestCache, ZerodhaRateLimiter


class TestRateLimiter:
    """Test token bucket rate limiter"""
    
    def test_basic_acquire(self):
        """Test basic token acquisition"""
        limiter = RateLimiter(max_requests=3, window_seconds=1.0)
        
        # Should succeed for first 3 requests
        assert limiter.acquire(block=False) is True
        assert limiter.acquire(block=False) is True
        assert limiter.acquire(block=False) is True
        
        # 4th request should be blocked
        assert limiter.acquire(block=False) is False
    
    def test_token_refill(self):
        """Test token refilling over time"""
        limiter = RateLimiter(max_requests=1, window_seconds=1.0)
        
        # Consume token
        assert limiter.acquire(block=False) is True
        assert limiter.acquire(block=False) is False
        
        # Wait for refill
        time.sleep(1.1)
        
        # Token should be available again
        assert limiter.acquire(block=False) is True
    
    def test_blocking_acquire(self):
        """Test blocking acquire with sleep"""
        limiter = RateLimiter(max_requests=2, window_seconds=1.0)
        
        # Use up tokens
        limiter.acquire(block=False)
        limiter.acquire(block=False)
        
        # This should block and wait
        start = time.time()
        limiter.acquire(block=True)  # Will wait ~0.5s
        elapsed = time.time() - start
        
        # Should have waited at least 0.4 seconds
        assert elapsed >= 0.4
    
    def test_cost_parameter(self):
        """Test acquiring multiple tokens at once"""
        limiter = RateLimiter(max_requests=3, window_seconds=1.0)
        
        # Acquire 3 tokens at once
        assert limiter.acquire(cost=3, block=False) is True
        
        # Next request should be blocked
        assert limiter.acquire(cost=1, block=False) is False
    
    def test_get_wait_time(self):
        """Test wait time calculation"""
        limiter = RateLimiter(max_requests=1, window_seconds=1.0)
        
        # Use token
        limiter.acquire(block=False)
        
        # Wait time should be > 0
        wait_time = limiter.get_wait_time()
        assert wait_time > 0
        assert wait_time <= 1.0


class TestRequestCache:
    """Test response caching"""
    
    def test_cache_hit(self):
        """Test cache hit"""
        cache = RequestCache(ttl_seconds=10)
        
        cache.set("key1", {"data": "value1"})
        
        result = cache.get("key1")
        assert result == {"data": "value1"}
    
    def test_cache_miss(self):
        """Test cache miss on non-existent key"""
        cache = RequestCache(ttl_seconds=10)
        
        result = cache.get("nonexistent")
        assert result is None
    
    def test_cache_expiry(self):
        """Test cache expiration"""
        cache = RequestCache(ttl_seconds=1)
        
        cache.set("key1", {"data": "value1"})
        
        # Should be cached
        assert cache.get("key1") is not None
        
        # Wait for expiry
        time.sleep(1.1)
        
        # Should be expired
        assert cache.get("key1") is None
    
    def test_cache_stats(self):
        """Test cache statistics"""
        cache = RequestCache(ttl_seconds=10)
        
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        
        stats = cache.get_stats()
        assert stats["total_items"] == 2
        assert stats["active_items"] == 2


class TestZerodhaRateLimiter:
    """Test Zerodha-specific rate limiter"""
    
    def test_initialization(self):
        """Test initialization"""
        limiter = ZerodhaRateLimiter()
        
        assert limiter.global_limiter is not None
        assert limiter.cache is not None
    
    def test_acquire_for_quote(self):
        """Test quote acquisition"""
        limiter = ZerodhaRateLimiter()
        
        # First 3 should succeed
        assert limiter.acquire_for_quote() is True
        assert limiter.acquire_for_quote() is True
        assert limiter.acquire_for_quote() is True
        
        # 4th should be blocked
        assert limiter.acquire_for_quote() is False
    
    def test_cache_operations(self):
        """Test cache get/set"""
        limiter = ZerodhaRateLimiter()
        
        limiter.set_cache("test_key", {"price": 100}, ttl=5)
        result = limiter.get_cache("test_key")
        
        assert result == {"price": 100}
    
    def test_get_wait_time(self):
        """Test wait time calculation"""
        limiter = ZerodhaRateLimiter()
        
        # Use all tokens
        limiter.acquire_for_quote()
        limiter.acquire_for_quote()
        limiter.acquire_for_quote()
        
        # Next request should have positive wait time
        wait_time = limiter.get_wait_time()
        assert wait_time > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
