# IMMEDIATE TEST - Copy & Paste Commands

## Start Here: 3-Step Testing

### Step 1: Backend (Copy-Paste)
```powershell
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Wait for output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

---

### Step 2: In NEW Terminal - Test Greeks API Directly
```powershell
cd d:\FastTradeApp
python test_greeks_api.py
```

**Expected Output:**
```
============================================================
Testing Greeks API Endpoint
============================================================

📍 Endpoint: POST http://localhost:8000/greeks/calculate

Status Code: 200
✅ SUCCESS!

📊 Greeks Summary:
  Delta (Δ):  0.5736  [Directional exposure]
  Gamma (Γ):  0.000261  [Delta acceleration]
  Theta (Θ):  -11.70     [Daily decay]
  Vega (ν):   29.33     [IV sensitivity]
  Rho (ρ):    11.73     [Rate sensitivity]
  Premium:    125.50

============================================================
Test 2: Multi-leg strategy (Call Spread)
============================================================
✅ SUCCESS!
```

**If it fails**, the issue is backend. Check logs in Step 1 terminal.

---

### Step 3: Frontend & UI Test
```powershell
cd d:\FastTradeApp\web
npm start
```

Wait for:
```
Compiled successfully!
```

Browser opens to `http://localhost:3000`

---

## Now Test StrategyBuilder in Browser

### Quick UI Test (2 minutes)

1. **Navigate to builder**
   - Manual: Type in address bar: `http://localhost:3000/strategies/builder`
   - Or: Click "Strategies" → Look for "Open Builder" button

2. **Add first leg**
   - Click **"+ Add Leg"** button
   - New leg appears below
   - Default values: BUY, CE, strike=26150, qty=1

3. **Calculate Greeks**
   - Keep defaults
   - Click **"Calculate Greeks"** button
   - Look at **right panel** - should show values:
     - Delta: 0.5736
     - Gamma: 0.000261
     - Theta: -11.70
     - Vega: 29.33
     - Rho: 11.73

4. **Verify Network Call (F12)**
   - Press `F12` (open DevTools)
   - Click **Network** tab
   - Click "Calculate Greeks" again
   - Should see POST request to `/greeks/calculate`
   - Status should be **200 OK**

---

## If Greeks Show 0 or undefined

### Debug Step 1: Check Backend is Running
```powershell
# In backend terminal, look for:
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

If not there, go back to Step 1.

### Debug Step 2: Check Frontend Console
- Press F12
- Click **Console** tab
- Click "Calculate Greeks"
- Look for red errors

**Common Error #1: greeksAPI is undefined**
- Check: `web/src/lib/api.ts` has `export const greeksAPI`

**Common Error #2: Cannot POST**
- Backend not running (see Debug Step 1)

**Common Error #3: 404 Not Found**
- Backend route not registered in `backend/app/main.py`

### Debug Step 3: Manual PowerShell Test
```powershell
# Test the endpoint directly
$body = @{
    legs = @(@{
        type = "BUY"
        option_type = "CE"
        strike = 26000
        spot = 26150
        expiry_days = 7
        volatility = 20
        quantity = 1
    })
    spot = 26150
    rate = 5.0
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/greeks/calculate" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$response | ConvertTo-Json | Write-Host
```

**Expected Response:**
```json
{
  "delta": 0.5736,
  "gamma": 0.000261,
  "theta": -11.70,
  "vega": 29.33,
  "rho": 11.73,
  "premium": 125.50,
  "legs_details": [...]
}
```

If this doesn't work, backend endpoint is broken.

---

## Complete Testing Flow (Full 15 minutes)

### ✅ Pre-test Verification
```powershell
# Verify files exist
Test-Path d:\FastTradeApp\backend\app\api\routes\greeks.py
Test-Path d:\FastTradeApp\test_greeks_api.py
Test-Path d:\FastTradeApp\GREEKS_API_IMPLEMENTATION.md
Test-Path d:\FastTradeApp\TESTING_GREEKS_COMPLETE.md
```

All should show: `True`

### ✅ Terminal 1: Start Backend
```powershell
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Wait 5 seconds for startup.

### ✅ Terminal 2: Test API
```powershell
cd d:\FastTradeApp
python test_greeks_api.py
```

Should see:
```
✅ SUCCESS!
✅ SUCCESS!
✓ All tests completed!
```

### ✅ Terminal 3: Start Frontend
```powershell
cd d:\FastTradeApp\web
npm start
```

Wait for browser to open.

### ✅ Browser: Test UI
1. Go to `http://localhost:3000/strategies/builder`
2. Click "+ Add Leg"
3. Click "Calculate Greeks"
4. Open F12 → Network → See POST to `/greeks/calculate`
5. See Greeks values in right panel

---

## What Each Test Tells You

| Test | What It Checks | If Fails |
|------|----------------|----------|
| `python test_greeks_api.py` | Backend API endpoint | Backend route not registered or Greeks calculator broken |
| UI page loads | Frontend route | StrategyBuilder.tsx not imported in App.tsx |
| "Add Leg" button | React state | JavaScript error in component |
| "Calculate Greeks" button | API call | greeksAPI not exported from api.ts |
| Network POST shows | CORS + API | Backend route missing or CORS issues |
| Greeks values appear | API response | Backend calculation error |

---

## Success Criteria ✅

You'll know everything works when:

1. ✅ `python test_greeks_api.py` shows "SUCCESS" twice
2. ✅ Can navigate to `http://localhost:3000/strategies/builder`
3. ✅ Add leg, click "Calculate Greeks", see network request
4. ✅ Request returns 200 OK
5. ✅ Greeks values display (not 0 or undefined)
6. ✅ Multi-leg shows aggregated Greeks

---

## Copy-Paste Troubleshooting Commands

### Check backend route registered
```powershell
Select-String -Path "d:\FastTradeApp\backend\app\main.py" -Pattern "greeks"
```

Should show 2 lines (import + include_router)

### Check frontend API export
```powershell
Select-String -Path "d:\FastTradeApp\web\src\lib\api.ts" -Pattern "greeksAPI"
```

Should show 1 line with `export const greeksAPI`

### Check App.tsx route
```powershell
Select-String -Path "d:\FastTradeApp\web\src\App.tsx" -Pattern "strategies/builder"
```

Should show 1 line with route definition

### Test network connectivity
```powershell
Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Detailed
```

Should show: `TcpTestSucceeded : True`

---

## Immediate Actions

**RIGHT NOW, DO THIS:**

1. Copy-paste Step 1 into PowerShell terminal
2. Wait 5 seconds
3. Open new terminal, copy-paste Step 2
4. See "SUCCESS" output
5. Open new terminal, copy-paste Step 3
6. Open browser to `http://localhost:3000/strategies/builder`
7. Click "+ Add Leg"
8. Click "Calculate Greeks"
9. Open F12, look at Network tab
10. Report back what you see!

---

## Report Template (For Issues)

If something doesn't work, run this and tell me output:

```powershell
# Show if files exist
"--- Files ---"
Test-Path d:\FastTradeApp\backend\app\api\routes\greeks.py
Test-Path d:\FastTradeApp\web\src\lib\api.ts
Test-Path d:\FastTradeApp\web\src\pages\StrategyBuilder.tsx

# Show backend route
"--- Backend Routes ---"
Select-String -Path "d:\FastTradeApp\backend\app\main.py" -Pattern "greeks"

# Show frontend API
"--- Frontend API ---"
Select-String -Path "d:\FastTradeApp\web\src\lib\api.ts" -Pattern "greeksAPI"

# Test backend port
"--- Backend Connectivity ---"
Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet
```

---

