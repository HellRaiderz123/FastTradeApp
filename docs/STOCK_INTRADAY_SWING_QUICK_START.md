# Quick Start: Stock Intraday/Swing Trading

## 🚀 What Changed

1. **"Create Strategy" button now works** - Opens a form to create new strategies
2. **Intraday/Swing toggle added** - Switch between 15-minute and daily timeframes
3. **Daily candles support** - New database table for swing trading data

---

## ⚡ Immediate Actions Required

### 1. Run Database Migration (REQUIRED)

```bash
cd backend
python migrate_daily_candles.py
```

This creates the `candles_daily` table needed for swing trading.

### 2. Test the "Create Strategy" Fix

1. Open your app
2. Click any stock (e.g., SBIN) to open Stock Detail Modal
3. Go to **Strategies** tab
4. Click **"Create"** button
5. Fill in the form:
   - Name: "Test Strategy"
   - Type: "Momentum"
   - Description: (optional)
6. Click **"Create Strategy"**
7. ✅ Should see new strategy appear in the list

### 3. Test Intraday/Swing Toggle

**Intraday Mode (Default):**
- Toggle should show **"Intraday (15m)"** highlighted in blue
- Strategies list shows: "Momentum 15m", "Trend Following 15m", etc.
- Trade suggestions use 15-minute candles

**Swing Mode:**
- Click **"Swing (Daily)"** button
- Strategies list updates to show: "Momentum Daily", "Trend Following Daily", etc.
- Trade suggestions will show "Insufficient daily candle data" initially (until you populate the table)

---

## 📊 Populate Daily Candles (Optional - For Swing Trading)

Daily candles table is empty initially. To use swing trading:

### Option A: Manual Fetch Script (Quick Test)
Create `backend/fetch_daily_candles.py`:

```python
from app.db.session import SessionLocal
from app.db.models_candles import CandleDaily
from kiteconnect import KiteConnect
import datetime

db = SessionLocal()
kite = KiteConnect(api_key="YOUR_API_KEY")
kite.set_access_token("YOUR_ACCESS_TOKEN")

symbols = ["SBIN", "RELIANCE", "TCS", "INFY"]
from_date = datetime.date.today() - datetime.timedelta(days=365)
to_date = datetime.date.today()

for symbol in symbols:
    print(f"Fetching {symbol}...")
    data = kite.historical_data(
        instrument_token=get_token(symbol),  # Need to map symbol to token
        from_date=from_date,
        to_date=to_date,
        interval="day"
    )
    
    for candle in data:
        db_candle = CandleDaily(
            symbol=symbol,
            date=candle['date'].date(),
            open=candle['open'],
            high=candle['high'],
            low=candle['low'],
            close=candle['close'],
            volume=candle['volume']
        )
        db.merge(db_candle)
    
    db.commit()
    print(f"✅ {symbol}: {len(data)} candles")

db.close()
```

### Option B: Wait for Production Cron Job
- Daily candles will be fetched automatically after market close (3:30 PM IST)
- Once data is available, swing strategies will work automatically

---

## 🧪 Testing Workflow

### Test Create Strategy
```
1. Open app → Stock Detail Modal (SBIN)
2. Strategies tab → Click "Create"
3. Fill form → Click "Create Strategy"
4. ✅ Strategy appears in list
5. Click "Execute" → Should run successfully
```

### Test Intraday Trading
```
1. Toggle: "Intraday (15m)" (default)
2. Verify strategies show "_15m" suffix
3. Trade suggestions show prices, entry, stop, target
4. Execute strategy → Should use 15-minute candles
```

### Test Swing Trading (After Daily Candles Populated)
```
1. Toggle: "Swing (Daily)"
2. Verify strategies show "_daily" suffix
3. If table empty: "Insufficient daily candle data"
4. After fetch: Trade suggestions use EMA 50/200, wider stops
5. Execute strategy → Should use daily candles
```

---

## 🔍 Verification Commands

### Check Daily Candles Table Exists
```bash
cd backend
python -c "from app.db.session import engine; from sqlalchemy import inspect; print('candles_daily' in inspect(engine).get_table_names())"
```

Should print: `True`

### Check Daily Candles Count
```bash
python -c "from app.db.session import SessionLocal; from app.db.models_candles import CandleDaily; db = SessionLocal(); print(f'Daily candles: {db.query(CandleDaily).count()}'); db.close()"
```

Shows: `Daily candles: 0` (or count if populated)

### Check Registered Strategies
```python
from app.core.strategies.registry import StrategyRegistry
strategies = StrategyRegistry.list_strategies()
print("Registered strategies:")
for name in strategies:
    print(f"  - {name}")
```

Should show 6 strategies:
- stock_momentum_15m
- stock_trend_following_15m
- stock_mean_reversion_15m
- stock_momentum_daily
- stock_trend_following_daily
- stock_mean_reversion_daily

---

## 📱 UI Changes to Expect

### Strategies Tab - Before vs After

**BEFORE:**
```
┌─────────────────────────────────┐
│ Trading Strategies              │
│ Execute automated strategies    │
│                          [Create]│
└─────────────────────────────────┘
[Create button did nothing] ❌
```

**AFTER:**
```
┌─────────────────────────────────┐
│ Trading Strategies              │
│ Execute automated strategies    │
│                          [Create]│
├─────────────────────────────────┤
│ [Intraday (15m)] [Swing (Daily)]│ ← NEW TOGGLE
└─────────────────────────────────┘

[Click Create → Form opens] ✅

┌─────────────────────────────────┐
│ Create New Strategy        [X]  │
├─────────────────────────────────┤
│ Strategy Name:                  │
│ [________________]              │
│                                 │
│ Strategy Type:                  │
│ [Momentum         ▼]            │
│                                 │
│ Description (Optional):         │
│ [________________]              │
│                                 │
│ Note: Will create a 15-minute   │
│ timeframe strategy              │
│                                 │
│ [Create Strategy]  [Cancel]     │
└─────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### Issue: Create button still doesn't work
**Solution:**
```bash
# Clear browser cache
Ctrl + Shift + Delete → Clear cache

# Restart frontend dev server
cd web
npm run dev
```

### Issue: Toggle doesn't filter strategies
**Solution:**
```bash
# Restart backend to load new strategy registrations
cd backend
python -m uvicorn app.main:app --reload
```

### Issue: "Module ta_signal_daily_from_df not found"
**Cause:** Backend not restarted after code changes

**Solution:**
```bash
cd backend
# Kill existing Python process
taskkill /F /IM python.exe
# Restart
python -m uvicorn app.main:app --reload
```

### Issue: Swing mode shows "Insufficient data"
**Expected:** This is normal until you populate daily candles table

**Solution:** See "Populate Daily Candles" section above

---

## ✅ Success Criteria

After completing setup, you should be able to:

1. ✅ Click "Create" button and see form
2. ✅ Submit form and see new strategy in list
3. ✅ Toggle between Intraday and Swing modes
4. ✅ See different strategy lists based on toggle
5. ✅ Execute strategies successfully
6. ✅ (Optional) See swing trade suggestions after populating daily candles

---

## 📋 Summary of Changes

| Component | Change |
|-----------|--------|
| **Frontend** | Added timeframe toggle + create form |
| **Backend Models** | Added `CandleDaily` table |
| **TA Engine** | Added daily timeframe analysis (`EMA 50/200`) |
| **Strategies** | Registered 6 strategies (15m + daily) |
| **API Routes** | Added timeframe parameter to suggestions |
| **Migration** | Created database migration script |

---

## 🎯 Next Steps

1. **Immediate:** Run `migrate_daily_candles.py` ✅
2. **Test:** Create strategy button works ✅
3. **Test:** Intraday toggle filters correctly ✅
4. **Optional:** Fetch daily candles for swing trading
5. **Production:** Set up cron job for daily candle updates

---

**Questions?** Check full documentation: `STOCK_INTRADAY_SWING_IMPLEMENTATION.md`
