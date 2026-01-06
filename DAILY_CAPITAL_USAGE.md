# Daily Capital Tracking - Usage Examples

## API Endpoints

### 1. Get Portfolio Growth History
**Endpoint:** `GET /account/daily-capital?days=30`

**Example - Using curl:**
```bash
curl -X GET "http://localhost:8000/account/daily-capital?days=30"
```

**Example - Using Python:**
```python
import requests

response = requests.get('http://localhost:8000/account/daily-capital?days=30')
data = response.json()

for record in data:
    print(f"{record['date']}: ₹{record['closing_capital']:,.0f} (PnL: ₹{record['daily_pnl']:,.0f})")
```

**Example - Using JavaScript:**
```typescript
const response = await accountAPI.getDailyCapital(30);
const history = response.data;

history.forEach(day => {
  console.log(`${day.date}: ₹${day.closing_capital.toLocaleString()} (${day.daily_return_pct}%)`);
});
```

### 2. Record Capital for a Day
**Endpoint:** `POST /account/daily-capital`

**Example - Using curl:**
```bash
# Record capital for today
curl -X POST "http://localhost:8000/account/daily-capital" \
  -H "Content-Type: application/json" \
  -d '{"capital": 505000}'

# Record capital for a specific date
curl -X POST "http://localhost:8000/account/daily-capital" \
  -H "Content-Type: application/json" \
  -d '{"capital": 505000, "date": "2026-01-06"}'
```

**Example - Using Python:**
```python
import requests

response = requests.post(
    'http://localhost:8000/account/daily-capital',
    json={
        'capital': 505000,
        'date': '2026-01-06'
    }
)

print(response.json())
# Output: {"success": true, "message": "Capital recorded for 2026-01-06"}
```

**Example - Using JavaScript:**
```typescript
const response = await accountAPI.recordDailyCapital(505000, '2026-01-06');
console.log(response.data);
```

### 3. Get Account Profile (Auto-updates Capital)
**Endpoint:** `GET /account/profile`

**Automatically:**
- Creates today's capital record if not exists
- Updates closing capital with current balance
- Calculates daily P&L and return %

```bash
curl -X GET "http://localhost:8000/account/profile"
```

## Real-World Scenarios

### Scenario 1: Track Portfolio Growth Over 30 Days
```python
import requests
from datetime import datetime

# Get 30-day history
response = requests.get('http://localhost:8000/account/daily-capital?days=30')
history = response.json()

print("Portfolio Growth - Last 30 Days")
print("=" * 60)
print(f"{'Date':<12} {'Opening':<15} {'Closing':<15} {'Daily P&L':<12}")
print("-" * 60)

total_pnl = 0
for day in history:
    opening = day['opening_capital']
    closing = day['closing_capital']
    daily_pnl = day['daily_pnl']
    total_pnl += daily_pnl
    
    print(f"{day['date']:<12} ₹{opening:>13,.0f} ₹{closing:>13,.0f} ₹{daily_pnl:>10,.0f}")

print("-" * 60)
print(f"Total Growth: ₹{total_pnl:,.0f}")
print(f"Return %: {(total_pnl / history[0]['opening_capital'] * 100):.2f}%")
```

### Scenario 2: Create Dashboard Widget
```typescript
// React component for daily capital summary
import { accountAPI } from '../lib/api';

export function CapitalSummary() {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    async function fetchData() {
      const response = await accountAPI.getDailyCapital(7);
      const history = response.data;
      
      const firstDay = history[0];
      const lastDay = history[history.length - 1];
      const totalGain = lastDay.closing_capital - firstDay.opening_capital;
      const returnPct = (totalGain / firstDay.opening_capital) * 100;
      
      setSummary({
        startCapital: firstDay.opening_capital,
        currentCapital: lastDay.closing_capital,
        totalGain,
        returnPct,
        days: history.length
      });
    }
    
    fetchData();
  }, []);

  if (!summary) return <div>Loading...</div>;

  return (
    <div className="card">
      <h3>7-Day Performance</h3>
      <p>Capital: ₹{summary.currentCapital.toLocaleString()}</p>
      <p>Gain: ₹{summary.totalGain.toLocaleString()} ({summary.returnPct.toFixed(2)}%)</p>
    </div>
  );
}
```

### Scenario 3: Daily Backup of Capital
```python
# Automated task to record capital at end of day (3:30 PM IST)
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

def daily_backup():
    """Record capital snapshot at end of trading day"""
    try:
        # Get current capital from Zerodha
        profile_response = requests.get('http://localhost:8000/account/profile')
        current_capital = profile_response.json()['capital']
        
        # Record it
        response = requests.post(
            'http://localhost:8000/account/daily-capital',
            json={'capital': current_capital}
        )
        
        if response.json()['success']:
            print(f"✅ Daily backup recorded: ₹{current_capital:,.0f}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")

# Schedule at 3:30 PM IST
scheduler = BackgroundScheduler()
scheduler.add_job(
    daily_backup,
    'cron',
    hour=15,
    minute=30,
    timezone='Asia/Kolkata'
)
scheduler.start()
```

### Scenario 4: Compare Against Benchmark
```python
# Compare your portfolio growth against Nifty return
import requests

def compare_with_benchmark():
    # Get your capital history
    response = requests.get('http://localhost:8000/account/daily-capital?days=30')
    history = response.json()
    
    your_return = (
        (history[-1]['closing_capital'] - history[0]['opening_capital']) /
        history[0]['opening_capital'] * 100
    )
    
    # Nifty benchmark (fetch from separate endpoint)
    benchmark_return = 2.5  # hypothetical
    
    print(f"Your Return: {your_return:.2f}%")
    print(f"Nifty Return: {benchmark_return:.2f}%")
    print(f"Outperformance: {your_return - benchmark_return:.2f}%")
```

## Testing with Postman

### Collection Setup
```json
{
  "info": {
    "name": "Daily Capital API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Get Daily Capital History",
      "request": {
        "method": "GET",
        "url": {
          "raw": "http://localhost:8000/account/daily-capital?days=30",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["account", "daily-capital"],
          "query": [{"key": "days", "value": "30"}]
        }
      }
    },
    {
      "name": "Record Capital",
      "request": {
        "method": "POST",
        "url": "http://localhost:8000/account/daily-capital",
        "header": [{"key": "Content-Type", "value": "application/json"}],
        "body": {
          "mode": "raw",
          "raw": "{\"capital\": 505000, \"date\": \"2026-01-06\"}"
        }
      }
    }
  ]
}
```

## Database Queries

### View All Records
```sql
SELECT * FROM daily_capital ORDER BY trade_date DESC;
```

### Get Capital Growth
```sql
SELECT 
  trade_date,
  opening_capital,
  closing_capital,
  daily_pnl,
  daily_return_pct
FROM daily_capital
WHERE trade_date >= date('now', '-30 days')
ORDER BY trade_date;
```

### Calculate Total Return
```sql
SELECT 
  MIN(opening_capital) as start_capital,
  MAX(closing_capital) as current_capital,
  SUM(daily_pnl) as total_pnl,
  (SUM(daily_pnl) / MIN(opening_capital) * 100) as total_return_pct
FROM daily_capital;
```

## Troubleshooting

### Q: Chart shows no data
**A:** 
1. Run migration: `python migrate_daily_capital.py`
2. Call `GET /account/profile` to create first day's record
3. Refresh dashboard

### Q: Capital numbers seem wrong
**A:** 
- Capital comes from Zerodha live balance
- Verify access token is valid
- Check Zerodha account manually

### Q: Can I backfill historical data?
**A:** 
Yes, use POST endpoint with date parameter:
```bash
curl -X POST http://localhost:8000/account/daily-capital \
  -H "Content-Type: application/json" \
  -d '{"capital": 495000, "date": "2026-01-01"}'
```
