# 🔑 ZERODHA CREDENTIALS SETUP

## Why This Matters
Your backend **cannot fetch fresh candle data** without Zerodha API credentials. Currently the database has 6-day-old candles, which is why ADX and RSI are showing old values.

---

## Step 1: Get Your Zerodha Credentials

### 1.1 Get API Key
- Go to: https://kite.zerodha.com/account/profile/preferences/api
- Copy your **API key** (starts with `abc123`)

### 1.2 Generate Access Token
- Go to: https://kite.zerodha.com/connect/login
- Login with your Zerodha account
- You'll get an **Access Token** (unique per session)

**Note:** Access token expires after 1 day. You need to regenerate it daily, OR use a token generation script.

---

## Step 2: Set Environment Variables

### On Windows (PowerShell)
```powershell
# Set environment variables
[System.Environment]::SetEnvironmentVariable("ZERODHA_API_KEY", "your_api_key", "User")
[System.Environment]::SetEnvironmentVariable("ZERODHA_ACCESS_TOKEN", "your_access_token", "User")

# Close and reopen terminal for changes to take effect
```

### On Windows (.env file - EASIER)
Create file: `backend/.env`
```
ZERODHA_API_KEY=your_api_key_here
ZERODHA_ACCESS_TOKEN=your_access_token_here
```

---

## Step 3: Verify Setup

Run this to check if credentials are loaded:
```bash
cd backend
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('ZERODHA_API_KEY')
token = os.getenv('ZERODHA_ACCESS_TOKEN')
print(f'API Key: {api_key}')
print(f'Access Token: {token}')
"
```

Expected output:
```
API Key: abc123xyz...
Access Token: def456uvw...
```

---

## Step 4: Refresh Candles

Run the refresh script:
```bash
cd backend
python refresh_candles.py
```

Expected output:
```
🔄 REFRESHING 15-MINUTE CANDLE DATA
Current candles in DB: 483
Latest candle: 2026-01-05 11:00:00

📥 Fetching latest 15 days of candles from Zerodha...
✅ Refresh complete!

Total candles in DB now: 1250
Added: 767 new candles
Latest candle now: 2026-01-05 15:30:00
```

---

## Step 5: Test Signal Generation

After refresh, test signal:
```bash
python test_indicator_debug.py
```

Expected output:
```
ADX: ~26 (now matches your chart!)
RSI: ~64 (now matches your chart!)
```

---

## Step 6: Restart Backend

The candle scheduler will now run automatically:
```bash
# In terminal 1
cd backend
python -m uvicorn app.main:app --reload
```

Monitor logs:
```
🟢 Candle scheduler started
⏱️ Running 15m candle update
✅ 15m candles updated
```

---

## Troubleshooting

### Error: "Zerodha API key or access token missing"
- ✅ Check `.env` file exists in `backend/` folder
- ✅ Restart terminal/IDE after setting environment variables
- ✅ Verify file is named `.env` (not `.env.txt`)

### Error: "Invalid API key"
- ✅ Check API key is correct (copy-paste from Zerodha)
- ✅ Check for leading/trailing spaces in `.env`

### Error: "Access token expired"
- ✅ Access tokens expire after 1 day
- ✅ Get a fresh token from https://kite.zerodha.com/connect/login
- ✅ Update `.env` with new token

### Candles still not updating?
- ✅ Check scheduler is running: `⏱️ Running 15m candle update` in logs
- ✅ Check market hours: scheduler only works during market hours (9:15 AM - 3:30 PM IST)
- ✅ Check internet connection (needed for Zerodha API)

---

## What Happens After Setup

1. **Scheduler starts** when backend starts
2. **Every 15 minutes** it fetches latest candles from Zerodha
3. **Indicators update automatically** with fresh data
4. **Signals now reflect current market state**
5. **Trade decisions become accurate**

---

## File Locations

| File | Purpose |
|------|---------|
| `backend/.env` | Store credentials (create this) |
| `backend/app/core/market/scheduler.py` | Candle update scheduler |
| `backend/app/core/market/candles.py` | Fetches candles from Zerodha |
| `backend/app/core/signals/ta_engine.py` | Calculates indicators |
| `backend/refresh_candles.py` | Manual refresh script |

---

## Quick Checklist

- [ ] Get API key from Zerodha
- [ ] Get access token from Zerodha  
- [ ] Create `backend/.env` with credentials
- [ ] Restart terminal/IDE
- [ ] Run `python refresh_candles.py` (verify success)
- [ ] Run `python test_indicator_debug.py` (verify ADX ~26, RSI ~64)
- [ ] Restart backend
- [ ] Monitor logs for scheduler messages

---

## After This is Done

Your backend will have:
✅ Fresh 15m candles every 15 minutes  
✅ Accurate ADX, RSI, and all other indicators  
✅ Correct signal generation matching your chart  
✅ Proper trade decision logic  

**Let me know once you've set this up!**

