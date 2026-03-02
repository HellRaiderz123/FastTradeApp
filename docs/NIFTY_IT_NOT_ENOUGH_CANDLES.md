# NIFTY_IT "Not Enough Candles" Error - Explanation & Solution

## The Error

```
Insufficient quality score (1/8 - minimum 3 required)
Reason: Not enough candles
```

For NIFTY_IT, the system rejects all strategy suggestions because it doesn't have enough market data.

---

## Why This Happens

### The Root Cause: Missing Candle Data

Your system currently has:
- ✅ **NIFTY** - 325 candles (Feb 11-27, 2026)
- ✅ **BANKNIFTY** - 325 candles (Feb 11-27, 2026)
- ✅ **FINNIFTY** - 325 candles (Feb 11-27, 2026)
- ❌ **NIFTY_IT** - 0 candles (NO DATA)

### The Signal Generation Process

```
Generate Signal (for NIFTY_IT)
    ↓
Fetch 15-min candles from database
    ↓ (Need >= 100 candles)
❌ Found 0 candles → "Not enough candles" error
    ↓
Return NO_TRADE signal with quality_score = 1/8
```

### Why 100 Candles Are Required

1. **Technical Indicators Need Historical Context**
   - RSI (Relative Strength Index) - needs ~14 periods
   - ADX (Average Directional Index) - needs ~14 periods
   - Moving averages (SMA/EMA) - needs 50+ periods
   - Stochastic - needs historical highs/lows

2. **Signal Reliability**
   - Fewer candles = less reliable patterns
   - 100 candles = approximately 4 trading days of 15-min data
   - This provides enough context for meaningful analysis

3. **Quality Scoring** (lines 35-47 in ta_engine.py)
   ```python
   if len(df) < 100:
       quality_score = 0  # Not enough data
       confidence = 0
       return NO_TRADE
   ```

---

## How Many Candles Do You Need?

### Candle Math
- **15-minute candles per day**: ~26 (6.5 trading hours × 4 candles/hour)
- **To get 100 candles**: Need 100 ÷ 26 = **~3.8 trading days**
- **To get 300 candles**: Need 300 ÷ 26 = **~11-12 trading days**

### Current Gaps
- NIFTY_IT currently has: **0 candles** (need 100+)
- To reach 100: Need **~4 days** of continuous tracking
- To reach 325 (like NIFTY): Need **~12-13 days** of tracking

---

## Solution

### Option 1: Automatically Load Historical Data (RECOMMENDED)

Run this one-time script to populate NIFTY_IT candles:

```bash
python load_nifty_it_candles.py --days 30
```

This will:
1. ✅ Fetch last 30 days of NIFTY_IT data from Zerodha
2. ✅ Store ~780 candles in your database (30 × 26)
3. ✅ Enable signal generation immediately
4. ✅ NIFTY_IT will show valid trade signals

**Output:**
```
1️⃣ Current NIFTY_IT candles in DB: 0
2️⃣ Fetching last 30 days of NIFTY_IT data from Zerodha...
   This will add ~780 candles (26 per trading day)
3️⃣ Verifying...
   Total NIFTY_IT candles now: 780
   ✅ SUCCESS! NIFTY_IT now has 780 candles
   ✅ You can now generate signals for NIFTY_IT
```

---

### Option 2: Wait for Data to Accumulate

If you've recently added NIFTY_IT to your tracking list and wait for live market data to accumulate:
- Day 1: 0 candles → NO_TRADE
- Day 2: 26 candles → NO_TRADE
- Day 3: 52 candles → NO_TRADE
- Day 4: 78 candles → NO_TRADE
- **Day 5: 104 candles → ✅ SIGNAL GENERATED**

---

### Option 3: Lower the Minimum Threshold

If you want to allow signals with fewer candles, modify `ta_engine.py` line 35:

**Before:**
```python
if len(df) < 100:
    return NO_TRADE  # Require 100 candles
```

**After:**
```python
if len(df) < 50:  # Lower threshold
    return NO_TRADE
```

⚠️ **Warning**: This may produce less reliable signals with insufficient data.

---

## Understanding the Error Message

The error message structure:

```json
{
  "signal": "NO_TRADE",
  "reason": "Insufficient quality score (1/8 - minimum 3 required)",
  "quality_score": 1,
  "trade_readiness_score": 0,
  "indicators": {},
  "signal_diagnosis": {
    "problem": "Not enough candles",
    "candles_found": 0,
    "candles_needed": 100
  }
}
```

### Quality Score Breakdown

| Component | NIFTY_IT | Status |
|-----------|----------|--------|
| **Data Freshness** | Missing | ❌ |
| **Trend Indicators** | Can't compute (need 100 candles) | ❌ |
| **Momentum Indicators** | Can't compute (RSI, MACD) | ❌ |
| **Volatility Measures** | Can't compute (Bollinger Bands) | ❌ |
| **Volume Confirmation** | N/A | N/A |
| **Overall Quality** | 1/8 | ❌ FAIL |

**Minimum Required**: 3/8 to even consider trading

---

## Technical Deep Dive

### Where the Data Comes From

```python
# ta_engine.py (line 242-250)
def ta_signal_15m(db: Session, symbol: str) -> Dict:
    candles = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)  # ← Looks for NIFTY_IT
        .order_by(Candle15m.timestamp.desc())
        .limit(300)
        .all()
    )
    
    if len(candles) < 100:  # ← Requires 100
        return NO_TRADE  # ← Returns this for NIFTY_IT
```

### How Data Gets Populated

```python
# candles.py
def fetch_15m_candles(db: Session, symbol: str, days: int = 15):
    """Fetch historical data from Zerodha for any symbol"""
    kite = get_kite_client()
    
    # Works for: NIFTY, BANKNIFTY, FINNIFTY, NIFTY_IT, etc.
    token = get_index_token(symbol)
    
    candles = kite.historical_data(
        instrument_token=token,
        from_date=from_dt,
        to_date=to_dt,
        interval="15minute",  # ← 15-min candles
    )
    
    # Stores in database
    for c in candles:
        db.add(Candle15m(...))
    db.commit()
```

---

## Verification

After loading NIFTY_IT candles, verify it works:

```bash
# Check candle count
python -c "
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

db = SessionLocal()
count = db.query(Candle15m).filter(Candle15m.symbol == 'NIFTY_IT').count()
print(f'NIFTY_IT candles: {count}')
db.close()
"

# Generate a signal
python -c "
from app.db.session import SessionLocal
from app.core.signals.signals import generate_signal

db = SessionLocal()
sig = generate_signal(db, 'NIFTY_IT')
print(f'Signal: {sig[\"signal\"]}')
print(f'Quality: {sig[\"quality_score\"]}/8')
db.close()
"
```

---

## FAQ

**Q: Do other symbols have the same problem?**  
A: No, only NIFTY_IT. NIFTY, BANKNIFTY, FINNIFTY have sufficient historical data.

**Q: Will new data be fetched automatically going forward?**  
A: Data accumulates from live market feeds. Each new 15-min candle is stored.

**Q: Can I delete NIFTY_IT candles and reload them?**  
A: Yes, but it's not necessary. The `fetch_15m_candles` function skips duplicates.

**Q: What if Zerodha API fails?**  
A: The error will be caught and logged. System won't crash, but data won't load.

**Q: Do I need to do this for other instruments?**  
A: Only if you add new symbols to track. Common indices (NIFTY, BANKNIFTY) are pre-populated.

---

## Summary

| Item | Details |
|------|---------|
| **Issue** | NIFTY_IT has 0 candles; needs 100+ for signals |
| **Why** | Data hasn't been fetched/cached yet |
| **Impact** | All signals for NIFTY_IT return "NO_TRADE" |
| **Solution** | Run `python load_nifty_it_candles.py --days 30` |
| **Time to Fix** | 1 minute (automatic fetch from Zerodha) |
| **Ongoing** | Candles accumulate automatically going forward |

---

## Resources

- **TA Engine**: `backend/app/core/signals/ta_engine.py` (quality scoring, indicator calculation)
- **Candle Fetching**: `backend/app/core/market/candles.py` (Zerodha API integration)
- **Loader Script**: `load_nifty_it_candles.py` (automatic historical data load)
- **Diagnostic Script**: `test_candle_diagnostic.py` (check available data)

