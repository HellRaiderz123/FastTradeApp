# IV Rank System - Quick Reference Card

## Installation & Testing (5 minutes)

```bash
# 1️⃣ FIRST TIME ONLY - Create database tables
python -m app.db.init_db
# ✅ You should see: "✅ Database tables created"

# 2️⃣ Start the app (automatic initialization)
uvicorn app.main:app --reload
# ✅ You should see: "🟢 VIX daily scheduler started (3:45 PM IST)"

# 3️⃣ In another terminal - Run tests
python simple_test.py          # Quick health check
python test_iv_rank_integration.py  # Full integration test
```

---

## What Gets Auto-Setup When App Starts

| Component | What Happens | Status |
|-----------|-------------|--------|
| **Database** | VixHistoric table created | ✅ Auto |
| **VIX Data** | Initialized from Zerodha or defaults | ✅ Auto |
| **Candle Scheduler** | Runs every 5 minutes | ✅ Auto |
| **VIX Scheduler** | Runs daily at 3:45 PM IST | ✅ Auto |
| **API Integration** | IV Rank included in responses | ✅ Auto |

---

## Files Changed/Created

### Modified Files
- `app/main.py` - Added VIX initialization and scheduler
- `app/core/market/scheduler.py` - Added daily VIX update job
- `app/db/models.py` - Added VixHistoric table

### New Files
- `app/core/market/iv_rank_calculator.py` - IV Rank calculation logic
- `app/core/market/zerodha_historic_fetcher.py` - Data fetching
- `test_iv_rank_system.py` - Unit tests
- `test_iv_rank_integration.py` - Integration tests
- `simple_test.py` - Quick health check
- `IV_RANK_TESTING_GUIDE.py` - Detailed documentation
- `IV_RANK_SETUP.md` - Setup guide

---

## Testing Commands

```bash
# Health Check (30 seconds)
python simple_test.py

# Unit Tests (1 minute)
python test_iv_rank_system.py

# Integration Tests (2 minutes)
python test_iv_rank_integration.py

# Risk Limits Tests (1 minute)
python test_risk_limits.py

# TP/SL Calculator Tests (1 minute)
python test_tp_sl.py
```

---

## How IV Rank is Used

### In Signals (Automatic)
```
POST /strategy/decision
Response includes:
{
  "context": {
    "india_vix": 18.5,
    "iv_rank": 65.2,          ← IV Rank here!
    "iv_regime": "NORMAL",    ← Regime here!
    ...
  }
}
```

### In Risk Management (Automatic)
- IV regime determines risk limits
- HIGH IV → stricter limits
- LOW IV → relaxed limits

### In Strategy Quality (Automatic)
- Higher IV → better spreads
- IV regime affects approval probability

---

## Verification Checklist

```bash
✅ Database created
python -m app.db.init_db

✅ App starts without errors
uvicorn app.main:app --reload
# Should see: "🟢 VIX daily scheduler started"

✅ Tests pass
python simple_test.py
# Should see: "✅ API working"

✅ IV Rank in responses
curl -X POST http://localhost:8000/strategy/decision \
  -H "Content-Type: application/json" \
  -d '{"underlying":"NIFTY","spot_price":20500,"capital":100000}'
# Should see: "iv_rank": XX.XX

✅ Daily updates scheduled
# Check at 3:45 PM IST - logs should show VIX update
```

---

## Fallback Values (If No Zerodha Data)

| Metric | Fallback |
|--------|----------|
| India VIX | 10.1 |
| IV Rank | 7.26% |
| IV Regime | LOW |

These are used automatically until real Zerodha data is available.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "no such table: vix_historic" | `python -m app.db.init_db` |
| "No module named 'kiteconnect'" | Optional - system uses fallback |
| IV Rank always 7.26% | Normal - waiting for data initialization |
| Scheduler not running | Check app.main.py has `start_vix_scheduler()` |

---

## Daily Workflow

```
3:00 PM - Trading happens
3:30 PM - Market closes
3:45 PM - Automatic VIX update:
         ✅ Fetch current VIX from Zerodha
         ✅ Calculate IV Rank percentile
         ✅ Update database
         ✅ Ready for next day's signals
```

---

## Manual Operations (Advanced)

```python
# Get current IV Rank
from app.core.market.vix_iv_api import get_vix_iv_data_cached
data = get_vix_iv_data_cached()
print(data['iv_rank'])

# Update today's VIX
from app.core.market.zerodha_historic_fetcher import fetch_and_store_daily_vix
from app.db.session import SessionLocal
db = SessionLocal()
fetch_and_store_daily_vix(db)
db.close()

# Get statistics
from app.core.market.iv_rank_calculator import get_vix_historic_stats
stats = get_vix_historic_stats(db)
print(f"52w High: {stats['52w_high']}, Low: {stats['52w_low']}")
```

---

## 🎉 You're Ready!

The IV Rank system is fully integrated and operational.

**Start trading:**
```bash
uvicorn app.main:app --reload
```

**That's it!** Everything else happens automatically.
