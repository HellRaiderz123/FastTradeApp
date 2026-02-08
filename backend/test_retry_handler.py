"""
Test script to verify retry handler functionality
Run with: python backend/test_retry_handler.py
"""

import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.retry_handler import (
    retry_with_backoff,
    is_transient_error,
    retry_on_transient_error
)

logger = logging.getLogger("test_retry_handler")


def test_transient_error_detection():
    """Test transient error detection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Transient Error Detection")
    logger.info("="*60)
    
    # Should detect as transient
    transient_errors = [
        Exception("503 Service Unavailable"),
        Exception("502 Bad Gateway"),
        TimeoutError("Connection timeout"),
        Exception("Connection refused"),
        Exception("temporarily unavailable"),
    ]
    
    for error in transient_errors:
        result = is_transient_error(error)
        status = "✅" if result else "❌"
        logger.info(f"{status} {str(error)}: is_transient={result}")
        assert result, f"Should detect '{error}' as transient"
    
    # Should NOT detect as transient
    permanent_errors = [
        Exception("404 Not Found"),
        Exception("401 Unauthorized"),
        Exception("Invalid symbol"),
    ]
    
    for error in permanent_errors:
        result = is_transient_error(error)
        status = "✅" if not result else "❌"
        logger.info(f"{status} {str(error)}: is_transient={result}")
        assert not result, f"Should NOT detect '{error}' as transient"
    
    logger.info("✅ All transient error detection tests passed!")


def test_retry_with_successful_attempt():
    """Test retry logic when function succeeds"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Successful Call (No Retries Needed)")
    logger.info("="*60)
    
    attempt_count = 0
    
    def successful_call():
        nonlocal attempt_count
        attempt_count += 1
        logger.info(f"Attempt {attempt_count}: Success!")
        return {"data": "success"}
    
    start_time = time.time()
    result = retry_with_backoff(successful_call, max_retries=3)
    elapsed = time.time() - start_time
    
    assert attempt_count == 1, f"Should only attempt once, got {attempt_count}"
    assert result == {"data": "success"}, f"Wrong result: {result}"
    assert elapsed < 0.5, f"Should be fast, took {elapsed:.2f}s"
    
    logger.info(f"✅ Success! Time: {elapsed:.2f}s, Attempts: {attempt_count}")


def test_retry_with_transient_failure_then_success():
    """Test retry logic when function fails then succeeds"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Transient Failure Then Success (2 Retries)")
    logger.info("="*60)
    
    attempt_count = 0
    
    def flaky_call():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            logger.info(f"Attempt {attempt_count}: 503 Service Unavailable")
            raise Exception("503 Service Unavailable")
        logger.info(f"Attempt {attempt_count}: Success!")
        return {"data": "recovered"}
    
    start_time = time.time()
    result = retry_with_backoff(
        flaky_call,
        max_retries=3,
        base_delay=0.1,  # Fast testing
        max_delay=0.5
    )
    elapsed = time.time() - start_time
    
    assert attempt_count == 3, f"Should attempt 3 times, got {attempt_count}"
    assert result == {"data": "recovered"}, f"Wrong result: {result}"
    assert elapsed >= 0.2, f"Should include delays, took {elapsed:.2f}s"  # At least 2 delays
    
    logger.info(f"✅ Success! Time: {elapsed:.2f}s, Attempts: {attempt_count}")


def test_retry_with_all_failures():
    """Test retry logic when all attempts fail"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: All Retries Fail (Max Retries Exceeded)")
    logger.info("="*60)
    
    attempt_count = 0
    
    def always_fails_call():
        nonlocal attempt_count
        attempt_count += 1
        logger.info(f"Attempt {attempt_count}: 503 Service Unavailable")
        raise Exception("503 Service Unavailable")
    
    start_time = time.time()
    result = retry_with_backoff(
        always_fails_call,
        max_retries=2,
        base_delay=0.1,  # Fast testing
        max_delay=0.5
    )
    elapsed = time.time() - start_time
    
    assert attempt_count == 3, f"Should attempt 3 times, got {attempt_count}"
    assert result is None, f"Should return None on all failures, got {result}"
    assert elapsed >= 0.2, f"Should include delays, took {elapsed:.2f}s"
    
    logger.info(f"✅ Correctly handled failure! Time: {elapsed:.2f}s, Attempts: {attempt_count}")


def test_decorator_syntax():
    """Test decorator syntax"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Decorator Syntax")
    logger.info("="*60)
    
    call_count = 0
    
    @retry_on_transient_error(max_retries=2, base_delay=0.1)
    def decorated_call():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            logger.info(f"Attempt {call_count}: Transient error")
            raise Exception("503 Service Unavailable")
        logger.info(f"Attempt {call_count}: Success!")
        return {"status": "ok"}
    
    result = decorated_call()
    
    assert call_count == 2, f"Should retry once and succeed, got {call_count} attempts"
    assert result == {"status": "ok"}, f"Wrong result: {result}"
    
    logger.info(f"✅ Decorator works! Attempts: {call_count}")


def test_permanent_error_raises_immediately():
    """Test that permanent errors raise immediately without retrying"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Permanent Error Raises Immediately")
    logger.info("="*60)
    
    attempt_count = 0
    
    def auth_error_call():
        nonlocal attempt_count
        attempt_count += 1
        logger.info(f"Attempt {attempt_count}: 401 Unauthorized")
        raise Exception("401 Unauthorized (permanent)")
    
    start_time = time.time()
    try:
        result = retry_with_backoff(
            auth_error_call,
            max_retries=3,
            base_delay=0.1
        )
        assert False, "Should have raised exception"
    except Exception as e:
        assert "401" in str(e), f"Wrong exception: {e}"
    
    elapsed = time.time() - start_time
    
    assert attempt_count == 1, f"Should not retry permanent errors, got {attempt_count} attempts"
    assert elapsed < 0.1, f"Should fail immediately, took {elapsed:.2f}s"
    
    logger.info(f"✅ Correct! Failed immediately without retrying. Attempts: {attempt_count}")


def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("RETRY HANDLER TEST SUITE")
    logger.info("="*60)
    
    try:
        test_transient_error_detection()
        test_retry_with_successful_attempt()
        test_retry_with_transient_failure_then_success()
        test_retry_with_all_failures()
        test_decorator_syntax()
        test_permanent_error_raises_immediately()
        
        logger.info("\n" + "="*60)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("="*60)
        return 0
    
    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit(main())
