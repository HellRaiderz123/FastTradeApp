# Daily Capital Tracking System

## Overview
This system tracks your daily capital growth to display portfolio growth trends on the Dashboard.

## What's New

### 1. **Database Table: `daily_capital`**
Stores daily capital snapshots (one record per day).

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `trade_date` | Date | Trading date (unique) |
| `opening_capital` | Float | Capital at start of day |
| `closing_capital` | Float | Capital at end of day |
| `daily_pnl` | Float | Profit/Loss for the day |
| `daily_return_pct` | Float | Return percentage (PnL / opening × 100) |
| `source` | String | Data source (zerodha, manual) |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last update timestamp |

### 2. **Backend API Endpoints**

#### **GET `/account/daily-capital`**
Get daily capital history for chart.

**Query Parameters:**
- `days`: Number of days to retrieve (default: 30)

**Response:**
```json
[
  {
    "date": "2026-01-05",
    "opening_capital": 500000,
    "closing_capital": 502500,
    "daily_pnl": 2500,
    "daily_return_pct": 0.5
  },
  {
    "date": "2026-01-06",
    "opening_capital": 502500,
    "closing_capital": 505000,
    "daily_pnl": 2500,
    "daily_return_pct": 0.497
  }
]
```

#### **POST `/account/daily-capital`**
Record or update daily capital.

**Request Body:**
```json
{
  "capital": 505000,
  "date": "2026-01-06"  // optional, defaults to today
}
```

**Response:**
```json
{
  "success": true,
  "message": "Capital recorded for 2026-01-06"
}
```

### 3. **Automatic Capital Tracking**
When you call `GET /account/profile`:
- Opens a daily capital record with opening capital
- Updates closing capital with current balance
- Calculates daily P&L and return %

No additional API calls needed - happens automatically!

### 4. **Frontend Updates**

#### **Dashboard.tsx**
Portfolio Growth chart now:
- ✅ Fetches daily capital history
- ✅ Displays day-by-day capital progression
- ✅ Shows trends over 30 days (configurable)
- ✅ Falls back to trade data if no history

#### **api.ts**
New API client methods:
```typescript
accountAPI.getDailyCapital(days)    // Get history
accountAPI.recordDailyCapital(amount, date)  // Record capital
```

## Setup Instructions

### 1. **Create the Table**
```bash
cd backend
python migrate_daily_capital.py
```

**Output:**
```
✅ Migration complete! Table 'daily_capital' created successfully
```

### 2. **Restart Backend**
```bash
# Restart your uvicorn server
python -m uvicorn app.main:app --reload
```

### 3. **Rebuild Frontend**
```bash
cd web
npm run build
# or for dev
npm run dev
```

## How It Works

### **Daily Flow**
1. **9:15 AM (Market Open)**
   - Call `GET /account/profile`
   - System creates daily capital record with opening balance
   - Chart starts tracking from this point

2. **Throughout the Day**
   - Your capital changes (profits/losses)
   - Each profile call updates closing capital
   - Daily P&L and return % calculated automatically

3. **End of Day (3:30 PM)**
   - Final closing capital recorded
   - Ready for next day

### **Chart Display**
Dashboard shows:
```
Portfolio Growth Chart
├── X-axis: Dates (last 30 days)
├── Y-axis: Capital amount
├── Area chart: Capital progression
└── Tooltip: Shows daily P&L on hover
```

## Example Data

**Day 1 (2026-01-05):**
- Opening: ₹500,000
- Closing: ₹502,500
- P&L: +₹2,500 (+0.5%)

**Day 2 (2026-01-06):**
- Opening: ₹502,500
- Closing: ₹505,000
- P&L: +₹2,500 (+0.497%)

**Cumulative in Chart:** Linear growth from ₹500K → ₹505K over 2 days

## API Integration Points

### **Automatic (Built-in)**
```
GET /account/profile → Automatically updates daily capital
```

### **Manual (Optional)**
```
POST /account/daily-capital → Manually set capital for a day
```

### **Retrieval**
```
GET /account/daily-capital?days=30 → Fetch history for chart
```

## Customization

### **Change History Window**
In `Dashboard.tsx`:
```tsx
const response = await accountAPI.getDailyCapital(60);  // 60 days instead of 30
```

### **Change Chart Update Frequency**
In `Dashboard.tsx`:
```tsx
const interval = setInterval(() => {
  fetchDailyCapitalHistory();
}, 10000);  // 10 seconds instead of 30
```

### **Manually Record Capital**
```bash
curl -X POST http://localhost:8000/account/daily-capital \
  -H "Content-Type: application/json" \
  -d '{"capital": 510000, "date": "2026-01-10"}'
```

## Troubleshooting

### **Chart Shows No Data**
1. Check if table exists: `python migrate_daily_capital.py`
2. Call `GET /account/profile` to create first day's record
3. Refresh dashboard

### **Wrong Capital Values**
- Daily capital is updated from Zerodha account balance
- Verify Zerodha credentials are valid
- Check if access token is expired

### **Missing Historical Data**
- System only tracks from first call onwards
- Historical data cannot be auto-backfilled
- Manually record past days with `POST /account/daily-capital`

## Files Modified/Created

✅ **Backend:**
- `app/db/models.py` - Added DailyCapital model
- `app/api/routes/account.py` - Added 2 new endpoints
- `migrate_daily_capital.py` - Migration script

✅ **Frontend:**
- `web/src/pages/Dashboard.tsx` - Updated chart logic
- `web/src/lib/api.ts` - Added new API methods

## Next Steps

1. Run migration script
2. Restart backend
3. Refresh frontend
4. Call `/account/profile` to create first day's record
5. Watch portfolio growth chart populate!
