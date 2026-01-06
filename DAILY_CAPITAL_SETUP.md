# Daily Capital Tracking - Implementation Summary

## ✅ What Was Implemented

### 1. **Database Layer**
- ✅ New `DailyCapital` model in `app/db/models.py`
- ✅ Stores day-wise capital snapshots
- ✅ Tracks opening, closing capital and daily P&L
- ✅ Automatic daily return % calculation

### 2. **Backend API** (`app/api/routes/account.py`)

#### New Endpoints:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/account/daily-capital` | GET | Fetch capital history (last N days) |
| `/account/daily-capital` | POST | Record/update capital for a day |
| `/account/profile` | GET | Auto-updates daily capital |

#### Features:
- ✅ Automatic capital tracking on profile fetch
- ✅ Manual capital recording with date override
- ✅ Configurable history window (days)
- ✅ Daily P&L & return % calculation
- ✅ Error handling with fallbacks

### 3. **Frontend Updates** (`web/src/pages/Dashboard.tsx`)

#### Changes:
- ✅ New state for daily capital history
- ✅ Fetch 30-day capital history on load
- ✅ Portfolio Growth chart uses real data
- ✅ Auto-refresh every 30 seconds
- ✅ Fallback to mock data if unavailable

#### Chart Display:
```
Portfolio Growth (Line Chart)
├── X-axis: Dates (last 30 days)
├── Y-axis: Capital amount
├── Color: Green gradient
└── Shows daily capital progression
```

### 4. **API Client** (`web/src/lib/api.ts`)

#### New Methods:
```typescript
accountAPI.getDailyCapital(days)        // Get history
accountAPI.recordDailyCapital(capital)  // Record capital
```

## 📁 Files Modified/Created

### Backend
```
✅ app/db/models.py                    (Added DailyCapital model)
✅ app/api/routes/account.py           (Added 2 endpoints)
✅ migrate_daily_capital.py            (Migration script)
✅ setup_daily_capital.py              (Setup helper)
✅ diagnose_zerodha.py                 (Existing, from earlier)
```

### Frontend
```
✅ web/src/pages/Dashboard.tsx         (Updated chart logic)
✅ web/src/lib/api.ts                  (Added API methods)
```

### Documentation
```
✅ DAILY_CAPITAL_TRACKING.md           (Full documentation)
✅ DAILY_CAPITAL_USAGE.md              (Usage examples & scenarios)
✅ SETUP SUMMARY (this file)
```

## 🚀 Quick Setup (3 Steps)

### Step 1: Create Database Table
```bash
cd backend
python migrate_daily_capital.py
```

Expected output:
```
✅ Migration complete! Table 'daily_capital' created successfully
```

### Step 2: Restart Backend
```bash
# Kill existing process and restart
python -m uvicorn app.main:app --reload
```

### Step 3: Refresh Frontend
- Clear browser cache or reload page
- Dashboard will auto-fetch capital history

## 📊 How It Works

### Automatic Flow
```
1. Frontend calls GET /account/profile
   ↓
2. Backend creates/updates daily capital record
   ├── Creates new record for today (if not exists)
   ├── Updates closing capital with current balance
   ├── Calculates daily P&L
   └── Calculates daily return %
   ↓
3. Frontend calls GET /account/daily-capital?days=30
   ↓
4. Returns array of 30 days of capital data
   ↓
5. Dashboard renders Portfolio Growth chart
   ├── Shows capital progression
   ├── Displays daily changes
   └── Updates in real-time
```

## 💾 Database Schema

```sql
CREATE TABLE daily_capital (
    id INTEGER PRIMARY KEY,
    trade_date DATE UNIQUE,
    opening_capital FLOAT,
    closing_capital FLOAT,
    daily_pnl FLOAT DEFAULT 0.0,
    daily_return_pct FLOAT,
    source VARCHAR DEFAULT 'zerodha',
    created_at DATETIME,
    updated_at DATETIME
);
```

## 📈 Sample Data

```
Date        | Opening   | Closing   | Daily P&L | Return%
------------|-----------|-----------|-----------|----------
2026-01-03  | 500,000   | 501,500   | +1,500    | +0.30%
2026-01-04  | 501,500   | 503,000   | +1,500    | +0.30%
2026-01-05  | 503,000   | 505,000   | +2,000    | +0.40%
2026-01-06  | 505,000   | 507,500   | +2,500    | +0.50%
```

## 🎯 Key Features

### ✅ Automatic Capital Tracking
- Every `GET /account/profile` call updates capital
- No manual data entry needed
- Real data from Zerodha

### ✅ Portfolio Growth Chart
- Day-by-day capital visualization
- Shows trends over 30 days
- Interactive tooltips with P&L

### ✅ Flexible Storage
- One record per day
- Easy to query and aggregate
- Supports historical backfill

### ✅ Comprehensive Reporting
- Daily P&L tracking
- Return percentage calculation
- Cumulative growth view

## 🔌 API Usage Examples

### Get Capital History
```bash
curl "http://localhost:8000/account/daily-capital?days=30"
```

### Record Capital Manually
```bash
curl -X POST http://localhost:8000/account/daily-capital \
  -H "Content-Type: application/json" \
  -d '{"capital": 510000, "date": "2026-01-10"}'
```

### Backfill Historical Data
```bash
# Loop through past dates and record capital
for date in 2026-01-01 2026-01-02 2026-01-03; do
  curl -X POST http://localhost:8000/account/daily-capital \
    -H "Content-Type: application/json" \
    -d "{\"capital\": 500000, \"date\": \"$date\"}"
done
```

## 🔍 Verification Steps

### 1. Database Check
```bash
sqlite3 fastrade.db
sqlite> SELECT COUNT(*) FROM daily_capital;
```
Expected: Returns number of records

### 2. API Test
```bash
curl http://localhost:8000/account/daily-capital
```
Expected: Returns JSON array of capital records

### 3. Frontend Check
- Open Dashboard page
- Scroll to "Portfolio Growth" chart
- Should show area chart with capital progression

## ⚙️ Configuration

### Change History Window (days)
In `Dashboard.tsx`:
```tsx
const response = await accountAPI.getDailyCapital(60);  // 60 days
```

### Change Refresh Frequency
In `Dashboard.tsx`:
```tsx
const interval = setInterval(fetchDailyCapitalHistory, 15000);  // 15 seconds
```

### Add More Data Sources
In `account.py` POST handler:
```python
source_map = {
    "zerodha": "zerodha",
    "manual": "manual",
    "import": "imported",
    # Add more as needed
}
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| Table doesn't exist | Run `python migrate_daily_capital.py` |
| No chart data | Call `/account/profile` first to create record |
| Wrong capital values | Verify Zerodha access token is valid |
| Historical gaps | Use POST to backfill missing dates |

## 📚 Documentation Files

1. **DAILY_CAPITAL_TRACKING.md** - Complete system documentation
2. **DAILY_CAPITAL_USAGE.md** - Usage examples and code snippets
3. **This file** - Implementation summary

## ✨ What's Next

Optional enhancements:
- [ ] Add benchmark comparison (Nifty, Bank Nifty)
- [ ] Export capital history to CSV
- [ ] Add monthly/yearly aggregation
- [ ] Set capital growth targets
- [ ] Compare multiple strategies

## 🎉 Summary

You now have:
- ✅ Day-wise capital tracking table
- ✅ Automatic capital recording from Zerodha
- ✅ Portfolio Growth chart on Dashboard
- ✅ Manual recording capability
- ✅ Historical data retrieval
- ✅ Complete API documentation
- ✅ Ready-to-use examples

**Status: COMPLETE AND READY TO USE**
