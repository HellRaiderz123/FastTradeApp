# Zerodha API Failure Troubleshooting

## Issue
```
WARNING | app.services.market_data | ⚠️  Zerodha API failed (256265), falling back to latest candle
```

## Root Causes (Most Common)

### 1. **Access Token Expired** ⚠️ MOST LIKELY
- Zerodha access tokens expire after inactivity (~4 hours or after session timeout)
- **Solution**: Re-authenticate with Zerodha using your login credentials to get a new access token

### 2. **Wrong Token Format** ✅ FIXED
- The LTP API response uses integer keys, not strings
- Code was trying to access `data["256265"]` instead of `data[256265]`
- **Fixed in**: `app/services/market_data.py` - Updated to handle both integer and string keys

### 3. **Missing or Invalid Credentials**
- Check `.env` file for:
  - `ZERODHA_API_KEY` (should be: `el4pv3dwria188j9`)
  - `ZERODHA_ACCESS_TOKEN` (your login-based token)

### 4. **Network/Connectivity Issues**
- Check internet connection
- Zerodha API might be temporarily unavailable
- Firewall or proxy blocking API calls

### 5. **Market Hours**
- Zerodha LTP data may not be available during pre-market or post-market hours
- Try during 9:15 AM - 3:30 PM IST (market hours)

## What Changed

### Code Improvement in `get_spot()`
**Before** (problematic):
```python
token_key = str(token)  # Converts to string "256265"
data = kite.ltp([token])
spot = data[token_key].get("last_price")  # Key not found → AttributeError on None
```

**After** (robust):
```python
# Try both integer and string keys
if token not in data and str(token) not in data:
    raise KeyError(f"Token {token} not in response")

price_data = data.get(token) or data.get(str(token))
spot = price_data.get("last_price")
```

## How to Fix

### Option 1: Re-authenticate (Recommended)
1. Go to [Zerodha Kite login](https://kite.zerodha.com/)
2. Login with your credentials
3. Get new access token (usually visible in browser or settings)
4. Update `ZERODHA_ACCESS_TOKEN` in `.env`
5. Restart the server

### Option 2: Check Credentials
```bash
# Verify credentials are set
cat .env | grep ZERODHA
```

Should show:
```
ZERODHA_API_KEY=el4pv3dwria188j9
ZERODHA_ACCESS_TOKEN=<your-token>
```

### Option 3: Run Diagnostic
```bash
cd backend
python diagnose_zerodha.py
```

This will test:
- ✅ Kite client initialization
- ✅ Token retrieval
- ✅ LTP API response format
- ✅ Instruments loading

## Fallback Mechanism

If Zerodha API fails, the system automatically falls back to:
1. Latest candle close price from database
2. Cached data from previous candles
3. Error if no fallback data available

This ensures the strategy doesn't completely fail, but uses slightly stale data.

## Monitoring

If failures continue, check these logs:
- `app.services.market_data` - Spot price retrieval
- `app.core.broker.zerodha.client` - API connection
- `app.core.broker.zerodha.instruments` - Instruments loading
