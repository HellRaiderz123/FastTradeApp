# Testing StrategyBuilder Component & Greeks API

## Step 1: Verify Backend is Running

```bash
# Terminal 1 - Backend
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

## Step 2: Verify Frontend is Running

```bash
# Terminal 2 - Frontend
cd d:\FastTradeApp\web
npm start
```

**Expected Output:**
```
Compiled successfully!
```

The app should open at `http://localhost:3000`

## Step 3: Navigate to StrategyBuilder

**Option A: Direct URL**
```
http://localhost:3000/strategies/builder
```

**Option B: Via UI**
1. Click "Strategies" in sidebar
2. Look for "New Strategy" or "Open Builder" button
3. Click to navigate to builder

**Expected:** Dark gray page with:
- Left panel: Add Leg button + leg list
- Middle panel: Payoff diagram area
- Right panel: Greeks display + Save button

## Step 4: Test Add Leg Functionality

1. Click **"+ Add Leg"** button
2. A new leg should appear below with:
   - Type dropdown: BUY / SELL (default: BUY)
   - Option Type: CE / PE
   - Strike input
   - Quantity input
   - Delete button (X)

**Expected:** Leg appears instantly in the list

## Step 5: Test Greeks API Call

1. **Open Browser DevTools** (F12)
2. Go to **Network** tab
3. Click "**Calculate Greeks**" button
4. **Watch Network tab** for POST request to:
   - `http://localhost:8000/greeks/calculate`
   
**Expected Response (200 OK):**
```json
{
  "delta": 0.5736,
  "gamma": 0.000261,
  "theta": -11.70,
  "vega": 29.33,
  "rho": 11.73,
  "premium": 125.50
}
```

**If you DON'T see the request:**
- Check browser console for errors (F12 → Console tab)
- Verify backend is running on port 8000
- Check if URL in api.ts is correct (should be `http://localhost:8000`)

## Step 6: Test Payoff Diagram

1. Add at least 2 legs (e.g., BUY CALL + SELL CALL)
2. Click "**Calculate Greeks**"
3. **Middle panel** should show:
   - SVG chart with diagonal payoff line
   - X-axis: Spot prices
   - Y-axis: P&L values
   - Max profit / Max loss at top

**Expected:** Chart updates when you add/modify legs

## Step 7: Test Strategy Save

1. Add 2-3 legs with different strikes/types
2. Enter Strategy Name (e.g., "Call Spread")
3. Click **"Save Strategy"**
4. **Watch Network tab** for:
   - POST request to `http://localhost:8000/strategies`
   - Response should show: `{ id, name, created_at, ... }`

**Expected:** Strategy saves successfully

## Step 8: Verify API Exists (Manual Test)

Run this in PowerShell to test Greeks endpoint directly:

```powershell
$body = @{
    legs = @(
        @{
            type = "BUY"
            strike = 26000
            spot = 26150
            expiry_days = 7
            volatility = 20.5
            quantity = 1
            side = "call"
        }
    )
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "http://localhost:8000/greeks/calculate" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body

$response | ConvertTo-Json
```

**Expected Output:**
```json
{
  "delta": 0.5736,
  "gamma": 0.000261,
  "theta": -11.70,
  "vega": 29.33,
  "rho": 11.73,
  "premium": 125.50
}
```

---

## Troubleshooting

### Issue: "Cannot GET /strategies/builder"
- ✅ Check route was added to App.tsx
- ✅ Verify app compiled without errors
- ✅ Try hard refresh (Ctrl + Shift + R)

### Issue: No API calls in Network tab
- ✅ Check if "Calculate Greeks" button is actually being clicked
- ✅ Open Console (F12) and look for JavaScript errors
- ✅ Verify backend URL in `web/src/lib/api.ts`
- ✅ Check if backend `/greeks/calculate` endpoint exists

### Issue: Greeks show null/undefined
- ✅ Backend returned error - check backend logs
- ✅ API endpoint not implemented - verify `app/core/greeks.py` has `/greeks/calculate` endpoint
- ✅ Network error - check CORS headers in response

### Issue: Payoff diagram is blank
- ✅ SVG might be rendering outside viewport
- ✅ Check browser console for rendering errors
- ✅ Verify calculatePayoff() function logic

---

## What Should Work NOW

✅ Navigate to `/strategies/builder`
✅ Add/remove legs
✅ Click Calculate Greeks (if endpoint exists)
✅ See Greeks values (Delta, Gamma, Theta, Vega, Rho)
✅ See payoff diagram
✅ Save strategy

## What Might Be Missing

❓ Backend `/greeks/calculate` endpoint
❓ API integration in frontend
❓ Some accessibility warnings (non-critical)

