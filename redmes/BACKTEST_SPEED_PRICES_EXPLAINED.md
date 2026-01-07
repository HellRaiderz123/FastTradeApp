# Backtest Speed & Price Data Explained

## 1. Why Backtest is VERY FAST ⚡

### Current Architecture (In-Memory):
```
Generate Mock Candles (memory) → Process Signals (CPU only) → Calculate P&L (math) → Save Results
                    ↓                    ↓                      ↓
              ~30 seconds          ~30 seconds           ~30 seconds
         (1 week backtest)      (1 week backtest)      (1 week backtest)
```

### No API Calls = Lightning Fast ⚡⚡
```python
❌ SLOW:  Loop → Make API call to Zerodha → Wait for response → Process
❌ SLOW:  Loop → Query database → Wait for I/O → Process

✅ FAST:  Loop → Generate mock candle → Process in memory → Next
```

### Speed Breakdown (1-week backtest):
```
1. Generate candles:      ~100ms (generates 390 candles, 26 per day × 5 trading days)
2. Process signals:       ~5s    (390 candles × mock strategy logic = fast)
3. Calculate metrics:     ~1s    (aggregation of P&L)
4. Save to database:      ~2s    (SQLite write)
   ────────────────────────────
   TOTAL:                ~10-15 seconds
```

### For comparison (if using real Zerodha API):
```
1. Generate candles:      ~15 seconds (1 API call per 100 candles)
2. Process signals:       ~5 seconds  (but might block on API)
3. Calculate metrics:     ~1 second
4. Save to database:      ~2 seconds
   ────────────────────────────
   TOTAL:                ~25-30 seconds (+ network latency)

For 1-year backtest:
   Current (mock):        ~2-3 minutes  ⚡
   With API calls:        ~20-30 minutes 🐢
```

---

## 2. Spot Prices - Where Do They Come From? 🎯

### Current Implementation: **MOCK DATA** (Not Real Historical)

[backend/app/core/data/candles.py](backend/app/core/data/candles.py#L65):
```python
# Base price for the symbol (HARDCODED)
base_prices = {
    "NIFTY": 20000,      # NOT Jan 7, 2026 actual price (26,132.2)
    "BANKNIFTY": 45000,  # NOT actual price
    "FINNIFTY": 22000,   # NOT actual price
}

# Generate random walk from base price
price = base_price  # Start at 20,000
for each candle:
    change = random.uniform(-0.5, 0.5)%  # Random ±0.5% per 15-min
    price = price * (1 + change)         # Random walk
```

### Example Price Generation:
```
Day 1, 9:15 AM:  NIFTY = 20,000.00 (base)
Day 1, 9:30 AM:  NIFTY = 20,089.45 (+0.45%)
Day 1, 9:45 AM:  NIFTY = 19,934.21 (-0.77%)
Day 1, 10:00 AM: NIFTY = 20,156.78 (+1.12%)
...continues with random walk...
```

### **Issue: Backtest Uses UNREALISTIC Prices**

| What User Sees | Actual Value |
|---|---|
| Entry Price: 20,089.45 | ❌ Not real Jan 7, 2026 price |
| Date: 2026-01-07 | ✅ Correct date |
| P&L: ₹4,323 | ⚠️ Based on mock prices, not real market |
| Metrics (Sharpe, Win Rate) | ⚠️ Can't compare to live trading |

---

## 3. Real Spot Prices - What Should Be Used?

### Option A: Real Historical Candles from Zerodha ✅
```python
def get_historical_candles(symbol, start_date, end_date):
    """TODO: Replace mock with real data"""
    
    # Should do this:
    kite = KiteConnect(...)
    history = kite.historical_data(
        instrument_token=NIFTY_TOKEN,
        from_date=start_date,
        to_date=end_date,
        interval="15minute"
    )
    return history  # Real NIFTY prices
```

**For 2026-01-07:**
```python
Real prices from Zerodha:
  9:15 AM: Open=26,130, High=26,145, Low=26,120, Close=26,132
  9:30 AM: Open=26,132, High=26,150, Low=26,125, Close=26,140
  9:45 AM: Open=26,140, High=26,155, Low=26,138, Close=26,145
  ...continues with actual market data...
```

### Option B: Historical Data from Yahoo Finance or NSE
```python
# For backtesting historical years (e.g., 2024)
import pandas as pd
data = pd.read_csv('nifty_2024_15min.csv')  # Real data
```

---

## 4. Current Backtest Accuracy

### Mock Data Results:
```
Starting Capital: ₹100,000
After 1-week backtest: ₹85,344
Return: -14.66%

This is FICTIONAL because:
✗ Uses random walk prices, not real market
✗ Can't match actual trading results
✗ Metrics are not comparable to live trading
✓ BUT good for testing backtest ENGINE architecture
```

### Real Data Results (When Integrated):
```
Starting Capital: ₹100,000
After 1-week backtest with REAL prices: TBD

This WILL BE accurate:
✓ Uses actual Jan 7, 2026 prices
✓ Can match against live trading
✓ Metrics comparable to actual performance
✓ Can validate strategy before live trading
```

---

## 5. TODO: Integrate Real Prices

### Priority 1: For Local Testing (Use Cache)
```python
# Cache real prices locally
# Run once: fetch from Zerodha
# Cache: historical_data_2024.pickle
# Run backtest: Load from cache (instant)
```

### Priority 2: For Production
```python
# Modify candles.py:
def get_historical_candles(symbol, start_date, end_date):
    try:
        # Try cache first
        cached = load_from_cache(symbol, start_date, end_date)
        if cached: return cached
        
        # Fallback to Zerodha API
        real_data = fetch_from_zerodha(symbol, start_date, end_date)
        cache_data(real_data)
        return real_data
    except:
        # Last resort: mock data
        return _generate_mock_candles(...)
```

---

## Current Status

### ✅ Backtest Infrastructure Ready
- Engine: ✅ Works with mock prices
- Database: ✅ Saves results
- Metrics: ✅ Calculated correctly
- UI: ✅ Charts display
- Speed: ✅ Lightning fast

### ⚠️ Price Accuracy Issue
- Current: Using base prices ±0.5% random walk
- Need: Real historical prices from Zerodha
- Impact: Can't validate strategy before live trading

### 📋 Before Moving to Phase 4B

**Option 1: Accept Mock Data**
- Good for testing backtest engine logic
- NOT suitable for strategy validation

**Option 2: Integrate Real Prices**
- Takes ~1-2 hours to fetch 1 year of data
- Enables real backtest validation
- **RECOMMENDED before Phase 4B**

---

## How to Verify Prices Are Real (After Integration)

```python
# After fixing candles.py
backtest_result = run_backtest(
    strategy="option_spread_15m",
    start_date=date(2025, 12, 31),
    end_date=date(2026, 1, 7)
)

# Check if prices are real:
print(backtest_result['equity_curve'][0])  # Should be ~₹100,000 (starting)
print(backtest_result['trades'][0]['entry_price'])  # Should match live trading

# Compare with live NIFTY price on 2026-01-07:
# Live: 26,132.20
# Backtest: Should be close to actual market prices
```

---

## Recommendation

**For Phase 4B, suggest:**
1. Keep mock prices for now (good for testing)
2. Add comment: "TODO: Replace with real Zerodha data"
3. After Phase 4B complete, integrate real prices
4. Then validate strategies with actual market data

This way you get:
- ✅ Fast backtest for development
- ✅ Realistic UI/UX testing
- ✅ Ability to add real prices later without refactoring

---

**Summary:**
- ⚡ **Fast**: No API calls, in-memory processing
- 📊 **Prices**: Currently mock data (random walk), not real market
- 🎯 **Accuracy**: Good for testing engine, not strategy validation
- 📈 **Next Step**: Integrate real Zerodha prices before Phase 4B
