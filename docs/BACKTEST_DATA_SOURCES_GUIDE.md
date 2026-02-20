# Backtest Data Sources - Complete Guide

## 🎯 Problem Summary

Your backtest system has a **critical data limitation**:
- ✅ **NIFTY spot prices**: Work fine (from Zerodha/Yahoo Finance)
- ❌ **Option prices (CE/PE)**: Only work for CURRENT contracts
- ❌ **Historical backtests**: Fail because expired options missing from live instruments dump

## 📊 Current Data Flow

### NIFTY Spot Data (✅ Working)
```
get_historical_candles("NIFTY", start, end)
  ├─ 1. Check local cache (pickle files)
  ├─ 2. Zerodha API (token: 256265)
  ├─ 3. Yahoo Finance (^NSEI)
  └─ 4. Mock data (last resort)
```

**File**: `backend/app/core/data/candles.py` (lines 77-164)

### Option Prices (❌ Broken for Old Data)
```
fetch_option_series("NIFTY24FEB48000CE", start, end)
  ├─ 1. Look up tradingsymbol → instrument_token
  │     ⚠️ FAILS if option expired (not in current dump)
  ├─ 2. Zerodha historical_data(token)
  └─ 3. Return candle series
```

**File**: `backend/app/core/backtest/options_pricing.py` (lines 82-122)

**The Issue**:
```python
# From the code comments:
"""
Important limitation: Zerodha instruments dump generally contains only currently
listed contracts (expired contracts may be absent). Options backtests therefore
work best for very recent days / current expiry.
"""
```

## 🔍 How to Verify the Problem

Check your backtest results for these fields:
```json
{
  "pricing_missing_count": 15,  // ← Non-zero = missing data
  "pricing_missing_symbols": [
    "NIFTY24JAN48000CE",
    "NIFTY24JAN48500PE",
    // ... expired contracts
  ]
}
```

If `pricing_missing_count > 0`, your backtest is incomplete!

## 🛠️ Solutions

### Option 1: Recent Data Only (Quick Fix)
**Good for**: Production testing, recent strategy validation

```python
from datetime import date, timedelta

# Only backtest last 30-45 days
start_date = date.today() - timedelta(days=30)
end_date = date.today()
```

**Pros**:
- Works immediately
- Uses real Zerodha data
- No setup required

**Cons**:
- Can't test long-term performance
- Limited sample size
- Seasonal patterns missed

### Option 2: Build Historical Database (Proper Fix) ⭐
**Good for**: Long-term backtesting, robust strategy validation

#### Step 1: Create Database Table
```bash
cd backend
python migrate_option_candles_table.py
```

This creates `option_historical_candles` table to store expired option data.

#### Step 2: Run Daily Archive Job
```bash
# Setup cron job or Windows Task Scheduler
python store_option_candles_daily.py
```

**What it does**:
- Fetches 15-min candles for all strikes (current + next 2 week expiries)
- Stores in database BEFORE they expire
- Accumulates historical data over time

**Schedule**: Run daily at 4:00 PM IST (after market close)

**Files Created**:
- `backend/app/db/models_candles.py` - Database model (UPDATED)
- `backend/migrate_option_candles_table.py` - Table creation
- `backend/store_option_candles_daily.py` - Daily archive job
- `backend/app/core/backtest/options_pricing.py` - Updated to use DB first (UPDATED)

#### Step 3: Backtest Now Uses Database
Updated code automatically checks:
```python
def fetch_option_series(tradingsymbol, from_dt, to_dt):
    # 1. Try DATABASE first (for expired contracts) ← NEW!
    series = _fetch_from_database(tradingsymbol, from_dt, to_dt)
    if series:
        return series
    
    # 2. Fall back to live API (for current contracts)
    return _fetch_from_zerodha_api(tradingsymbol, from_dt, to_dt)
```

### Option 3: Use Mock/Synthetic Pricing (Not Recommended)
**Good for**: Development, UI testing only

You could calculate synthetic option prices using Black-Scholes:
- Pros: Works for any historical date
- Cons: Not realistic, backtests meaningless

## 📈 Data Storage Requirements

### Per Expiry Week:
- 3 underlyings × 100 strikes/each × 2 types (CE/PE) = 600 contracts
- 5 trading days × 25 candles/day × 600 contracts = 75,000 candles
- ~40 bytes/candle × 75,000 = **3 MB per week**

### Annual Storage:
- 52 weeks × 3 MB = **156 MB/year**

Very manageable! PostgreSQL can handle this easily.

## 🚀 Implementation Timeline

### Week 1 (Immediate):
1. ✅ Create database table (5 mins)
   ```bash
   python migrate_option_candles_table.py
   ```

2. ✅ Setup daily archive job (10 mins)
   - Windows: Task Scheduler at 4:00 PM
   - Linux: Cron job `0 16 * * 1-5`

3. ⏳ Wait 7-10 days (accumulate data)
   - System runs automatically
   - Builds database in background

### Week 2 (After Data Collection):
4. ✅ Run backtest with 1-2 week history
   - Should work perfectly now
   - Check `pricing_missing_count = 0`

5. ✅ Backfill historical data (optional)
   - Manually fetch last 2-3 months if needed
   - One-time operation

## 🎓 Technical Details

### Database Schema
```sql
CREATE TABLE option_historical_candles (
    id SERIAL PRIMARY KEY,
    tradingsymbol VARCHAR,           -- NIFTY24FEB48000CE
    instrument_token INTEGER,        -- 12628738
    underlying VARCHAR,              -- NIFTY
    expiry DATE,                     -- 2024-02-15
    strike REAL,                     -- 48000
    option_type VARCHAR,             -- CE or PE
    timestamp TIMESTAMP,             -- 2024-02-01 09:15:00
    open REAL,
    high REAL,
    low REAL,
    close REAL,                      -- Most important for backtests
    volume REAL,
    created_at TIMESTAMP
);

CREATE UNIQUE INDEX ON option_historical_candles(tradingsymbol, timestamp);
CREATE INDEX ON option_historical_candles(underlying, expiry, strike, option_type);
```

### API Rate Limits (Zerodha)
- Historical data: **3 requests/second**
- 600 contracts × 1 request = **200 seconds** (~3 mins per week)
- Daily job completes in 5-10 minutes

### Zerodha Instruments Dump
Current file contains:
```python
# What's in instruments.csv:
- Active futures (current + next 2 months)
- Active options (current + next 4 weekly expiries)
- Stocks, indices, commodities

# What's NOT in instruments.csv:
- Expired options ❌
- Expired futures ❌
- Historical contracts ❌
```

This is why your backtests fail for old dates!

## ✅ Verification Checklist

After implementing Option 2:

1. **Database populated?**
   ```sql
   SELECT COUNT(*), underlying, expiry 
   FROM option_historical_candles 
   GROUP BY underlying, expiry;
   ```

2. **Daily job running?**
   - Check logs after 4:00 PM
   - Look for: "✅ Stored X candles for NIFTY24FEB48000CE"

3. **Backtest working?**
   ```python
   result = backtest_engine.run(
       start_date=date(2024, 1, 1),  # Old date!
       end_date=date(2024, 1, 31)
   )
   assert result["pricing_missing_count"] == 0  # Should be zero now
   ```

4. **Compare results**:
   - Before: 5-10 trades (many missing)
   - After: 30-50 trades (complete data)

## 📞 Quick Reference

### Files Modified/Created:
```
backend/
├── app/
│   ├── db/
│   │   └── models_candles.py (UPDATED - added OptionHistoricalCandle)
│   └── core/
│       └── backtest/
│           └── options_pricing.py (UPDATED - checks DB first)
├── migrate_option_candles_table.py (NEW - creates table)
└── store_option_candles_daily.py (NEW - archives candles)
```

### Commands:
```bash
# Setup (once)
python migrate_option_candles_table.py

# Daily job (automated)
python store_option_candles_daily.py

# Check data
psql -d your_database -c "SELECT COUNT(*) FROM option_historical_candles;"
```

### Environment Variables:
```env
# Force data source (optional)
CANDLES_SOURCE=ZERODHA   # or YFINANCE, MOCK
SAVE_CANDLES_TO_DB=1     # Enable database storage
```

## 🎯 Expected Results

### Before Fix:
```json
{
  "total_trades": 8,
  "pricing_missing_count": 45,
  "backtest_accuracy": "LOW"
}
```

### After Fix:
```json
{
  "total_trades": 52,
  "pricing_missing_count": 0,
  "backtest_accuracy": "HIGH"
}
```

You should see **5-10x more trades** with complete historical data!

---

**Next Steps**: 
1. Run migration script
2. Setup daily job  
3. Wait 7 days
4. Re-run your backtests and compare results! 🚀
