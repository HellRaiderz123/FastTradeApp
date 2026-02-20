# Rate Limiter Monitoring Guide

## Quick Test Commands

### 1. Check Current Rate Limiter Status

```bash
curl -s http://localhost:8000/health/rate-limiter | jq .
```

**Response shows:**
- `tokens_available`: How many API calls you can make right now
- `wait_time_seconds`: How long before next token refills
- `cache`: How many items cached (hits = no API call needed)

Example output:
```json
{
  "status": "ok",
  "timestamp": "2026-02-07T23:30:00",
  "rate_limiter": {
    "tokens_available": 2.8,
    "max_tokens": 3,
    "wait_time_seconds": 0.067,
    "requests_per_second": 3,
    "window_seconds": 1
  },
  "cache": {
    "total_items": 6,
    "active_items": 5,
    "expired_items": 1
  },
  "message": "Rate limiter active: 3 requests/second max"
}
```

**What this means:**
- ✅ **tokens_available: 2.8** - Can make 2 more calls right now
- ✅ **wait_time_seconds: 0.067** - 67ms until next token refills
- ✅ **active_items: 5** - 5 quotes cached, reducing API calls

---

### 2. Check Cache Performance

```bash
curl -s http://localhost:8000/health/cache-stats | jq .
```

**Response shows cache hit ratio:**
```json
{
  "status": "ok",
  "timestamp": "2026-02-07T23:30:00",
  "cache": {
    "total_items": 8,
    "active_items": 6,
    "expired_items": 2,
    "ttl_seconds": 2
  }
}
```

**Interpretation:**
- 8 items have been cached total
- 6 are still valid (not expired)
- 2 have expired and will be refreshed on next request
- Each item cached for 2 seconds

---

## Real-Time Monitoring

### Start monitoring every 2 seconds:

```bash
watch -n 2 "curl -s http://localhost:8000/health/rate-limiter | jq '.rate_limiter | {tokens: .tokens_available, wait_ms: (.wait_time_seconds * 1000 | floor), cache: .cache_items}'"
```

Or with Python:

```python
import requests
import time
import json

while True:
    response = requests.get('http://localhost:8000/health/rate-limiter').json()
    rl = response['rate_limiter']
    cache = response['cache']
    
    print(f"\r[{time.strftime('%H:%M:%S')}] "
          f"Tokens: {rl['tokens_available']:.1f} | "
          f"Wait: {rl['wait_time_seconds']*1000:.0f}ms | "
          f"Cache: {cache['active_items']}/{cache['total_items']} items", 
          end='', flush=True)
    
    time.sleep(2)
```

Output:
```
[23:30:00] Tokens: 2.8 | Wait: 67ms | Cache: 5/6 items
[23:30:02] Tokens: 2.9 | Wait: 33ms | Cache: 4/6 items
[23:30:04] Tokens: 3.0 | Wait: 0ms | Cache: 3/6 items
```

---

## Understanding Token Flow

### Scenario: Switching Universe

**Timeline:**
```
T=0ms:    Start with 3 tokens (full bucket)
T=100ms:  Request 1 (HDFCBANK) → Cost 1 token → 2 tokens left
T=200ms:  Request 2 (ICICIBANK) → Cost 1 token → 1 token left
T=300ms:  Request 3 (SBIN) → Cost 1 token → 0 tokens left
T=400ms:  Request 4 (KOTAKBANK) → BLOCKED! Must wait
          (Rate limiter sleeps for ~600ms)
T=1000ms: Tokens refill → 3 tokens available
T=1000ms: Request 4 finally executes
T=1100ms: Display all 4 prices
```

**But with caching:**
```
T=0ms:    Start with 3 tokens
T=100ms:  Request 1 (HDFCBANK) → Cache miss → API call → Cache hit expires in 2s
T=200ms:  Request 1 again → Cache hit! (No API call needed!)
T=300ms:  Request 2 (ICICIBANK) → Cache hit!
T=400ms:  Request 3 (SBIN) → Cache hit!
Result: Only 1 API call instead of 4! 🎉
```

---

## Test the Rate Limiter

### Simulate heavy load:

```bash
# Make 10 rapid requests (will be rate-limited)
for i in {1..10}; do
  echo "Request $i..."
  curl -s http://localhost:8000/health/rate-limiter | jq '.rate_limiter.tokens_available'
  sleep 0.1
done
```

Expected output (rate limiter should queue requests):
```
Request 1...
2.95
Request 2...
1.95  
Request 3...
0.95
Request 4...
3.05  ← Refilled after ~0.3 seconds
Request 5...
2.05
Request 6...
1.05
Request 7...
...
```

---

## Monitoring in Dashboard

If you have a dashboard, you can poll `/health/rate-limiter` periodically:

```typescript
// Dashboard.tsx
useEffect(() => {
  const fetchStatus = async () => {
    const response = await fetch('/health/rate-limiter');
    const data = await response.json();
    
    setMetrics({
      tokensAvailable: data.rate_limiter.tokens_available,
      waitTime: data.rate_limiter.wait_time_seconds,
      cacheHitRatio: data.cache.active_items / data.cache.total_items
    });
  };
  
  const interval = setInterval(fetchStatus, 1000);
  return () => clearInterval(interval);
}, []);
```

---

## Troubleshooting

### Problem: "Too many requests" error still appearing?

**Check:**
```bash
# 1. Verify rate limiter is active
curl -s http://localhost:8000/health/rate-limiter

# 2. Check tokens available
jq '.rate_limiter.tokens_available' 

# 3. If tokens are very low, wait for refill
# (Should go back to 3 within 1 second)
```

### Problem: Cache not being used?

```bash
# Check cache stats
curl -s http://localhost:8000/health/cache-stats | jq '.cache'

# If active_items is always 0:
# - Cache TTL might be too short (default: 2s)
# - Check if quotes are being requested within 2-second window
```

### Problem: Need to clear cache?

```bash
# Clear all cached responses
curl -X POST http://localhost:8000/health/cache-clear
```

Response:
```json
{
  "status": "ok",
  "message": "Cache cleared successfully"
}
```

---

## Key Metrics to Watch

| Metric | Target | Status |
|--------|--------|--------|
| **tokens_available** | 1-3 | ✅ OK (0-1 means rate limited) |
| **wait_time_seconds** | 0 | ✅ OK (>0.1 means reqs queued) |
| **cache active_items** | >50% of total | ✅ OK (no cache = more API calls) |
| **total API calls/sec** | ~3 | ✅ OK (should never exceed) |

---

## API Endpoints for Monitoring

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health/rate-limiter` | GET | Current rate limiter status |
| `/health/cache-stats` | GET | Detailed cache statistics |
| `/health/cache-clear` | POST | Clear all cached responses |
| `/health/` | GET | Basic health check |
| `/health/full` | GET | Comprehensive health status |

---

## Expected Behavior

### After implementation is correctly deployed:

**Before:**
```
ERROR: Too many requests zerodha has 3req/sec limit
Status: ❌ Frequent errors
```

**After:**
```
✅ Rate limiter active: 3 requests/second max
Tokens available: 2.8
Wait time: 0.067 seconds
Cache active items: 5/6
Status: ✅ Smooth operation, no errors
```

---

You're now protected against Zerodha rate limit errors! 🚀
