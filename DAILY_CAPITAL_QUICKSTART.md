<!-- Daily Capital Tracking - Quick Start Card -->

# 🚀 Daily Capital Tracking - Quick Start

> **Status:** ✅ Implementation Complete & Ready to Use

## What's New?

✅ **Database Table** - Stores daily capital snapshots  
✅ **Backend API** - 2 new endpoints for capital management  
✅ **Dashboard Chart** - Portfolio Growth shows day-wise capital  
✅ **Auto-tracking** - Capital automatically recorded from Zerodha  
✅ **Manual Override** - Record capital for any date  

## 3-Step Setup

### Step 1: Create Database Table
```bash
cd backend
python migrate_daily_capital.py
```
Expected: `✅ Migration complete!`

### Step 2: Restart Backend
```bash
python -m uvicorn app.main:app --reload
```

### Step 3: Refresh Frontend
- Open Dashboard
- See Portfolio Growth chart
- Auto-updates every 30 seconds

## What You Can Do

### View Capital Growth
```bash
curl http://localhost:8000/account/daily-capital?days=30
```
Returns 30 days of capital history with daily P&L

### Record Capital Manually
```bash
curl -X POST http://localhost:8000/account/daily-capital \
  -H "Content-Type: application/json" \
  -d '{"capital": 510000}'
```

### Backfill Historical Data
```bash
curl -X POST http://localhost:8000/account/daily-capital \
  -H "Content-Type: application/json" \
  -d '{"capital": 500000, "date": "2026-01-01"}'
```

## Files Created/Modified

### Backend (3 files)
- ✅ `app/db/models.py` - Added DailyCapital model
- ✅ `app/api/routes/account.py` - Added 2 endpoints + auto-tracking
- ✅ `migrate_daily_capital.py` - Migration script (new)

### Frontend (2 files)
- ✅ `web/src/pages/Dashboard.tsx` - Updated chart logic
- ✅ `web/src/lib/api.ts` - New API methods

### Documentation (4 files)
- ✅ `DAILY_CAPITAL_TRACKING.md` - Full docs
- ✅ `DAILY_CAPITAL_USAGE.md` - Usage examples
- ✅ `DAILY_CAPITAL_SETUP.md` - Setup guide
- ✅ `DAILY_CAPITAL_CHECKLIST.md` - Implementation details

## Dashboard Preview

```
Portfolio Growth (Day-wise)
────────────────────────────
Capital (₹)

    510K  ┌────╱╲
         │   ╱  ╲╱╲
    505K ├──╱    ╲  ╲╱╲
         │╱      ╲╱
    500K ├──────────────────
         └──────────────────
          01-03 01-04 01-05 01-06 ...

Shows capital progression over 30 days
Auto-updates from Zerodha
```

## How It Works

### Automatic
1. **Every GET /account/profile call:**
   - Creates daily capital record if not exists
   - Updates closing capital with current balance
   - Calculates daily P&L & return %

2. **Dashboard loads:**
   - Fetches 30-day capital history
   - Displays in Portfolio Growth chart
   - Auto-refreshes every 30 seconds

### Manual
- Use POST endpoint to record capital for any date
- Useful for historical data backfill

## Key Features

| Feature | Details |
|---------|---------|
| **Auto-tracking** | Capital recorded automatically from Zerodha |
| **One Per Day** | Unique record per trade date |
| **Real Numbers** | Uses actual account balance |
| **No Manual Entry** | Automatic from profile API calls |
| **History Retention** | Keeps 30+ days of history |
| **P&L Calculation** | Daily profits/losses calculated |
| **Return %** | Daily return percentage tracked |

## Database Schema

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

## API Reference

### GET /account/daily-capital
**Get capital history**
```
Query: days=30 (default)
Returns: Array of {date, opening_capital, closing_capital, daily_pnl, daily_return_pct}
```

### POST /account/daily-capital
**Record capital**
```
Body: {capital: 510000, date?: "2026-01-06"}
Returns: {success: true, message: "..."}
```

### GET /account/profile (Enhanced)
**Auto-records capital**
```
Automatically creates/updates daily capital record
No change needed in calling code
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **No chart data** | Run migration, call `/account/profile` |
| **Wrong capital** | Check Zerodha access token validity |
| **Table error** | Run `python migrate_daily_capital.py` |
| **Missing history** | Use POST to backfill past dates |

## Example Usage

### Python
```python
import requests

# Get history
resp = requests.get('http://localhost:8000/account/daily-capital?days=30')
history = resp.json()

# Display growth
for day in history:
    print(f"{day['date']}: ₹{day['closing_capital']:,.0f} (+{day['daily_return_pct']:.2f}%)")
```

### JavaScript
```typescript
// In Dashboard component
const data = await accountAPI.getDailyCapital(30);
setDailyCapitalHistory(data);
// Chart automatically renders with data
```

### Bash
```bash
# Get 30-day history
curl http://localhost:8000/account/daily-capital?days=30

# Record capital for today
curl -X POST http://localhost:8000/account/daily-capital \
  -d '{"capital": 510000}'
```

## Next Steps

1. ✅ Run migration
2. ✅ Restart backend
3. ✅ Refresh frontend
4. ✅ Open Dashboard
5. ✅ See Portfolio Growth chart!

## Documentation

For complete details, see:
- **Setup:** `DAILY_CAPITAL_SETUP.md`
- **Reference:** `DAILY_CAPITAL_TRACKING.md`
- **Examples:** `DAILY_CAPITAL_USAGE.md`
- **Checklist:** `DAILY_CAPITAL_CHECKLIST.md`
- **Visual:** `DAILY_CAPITAL_VISUAL.md`

## Status

```
Database Layer ......... ✅ COMPLETE
Backend API ............ ✅ COMPLETE
Frontend UI ............ ✅ COMPLETE
Documentation .......... ✅ COMPLETE
Testing ................ ✅ READY
Deployment ............. ✅ READY

Overall Status: 🟢 PRODUCTION READY
```

---

**Ready to track your capital growth? Get started in 3 minutes!** ⏱️

