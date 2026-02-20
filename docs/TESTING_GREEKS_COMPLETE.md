# Complete Testing Guide for StrategyBuilder & Greeks API

## What Just Changed ✅

1. **New Backend Endpoint**: `/greeks/calculate` - Calculates Greeks for multi-leg strategies
2. **Updated Frontend**: StrategyBuilder now calls Greeks API
3. **New Route**: `/strategies/builder` - UI for building strategies
4. **Added Integrations**: Frontend api.ts now includes `greeksAPI`

---

## Quick Start (5 minutes)

### Step 1: Start Backend
```powershell
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 2: Start Frontend (in another terminal)
```powershell
cd d:\FastTradeApp\web
npm start
```

**Expected:** Browser opens at `http://localhost:3000`

### Step 3: Test Greeks API Directly
```powershell
cd d:\FastTradeApp
python test_greeks_api.py
```

**Expected Output:**
```
✅ SUCCESS!

📊 Greeks Summary:
  Delta (Δ):  0.5736  [Directional exposure]
  Gamma (Γ):  0.000261  [Delta acceleration]
  Theta (Θ):  -11.70     [Daily decay]
  Vega (ν):   29.33     [IV sensitivity]
  Rho (ρ):    11.73     [Rate sensitivity]
  Premium:    125.50
```

If you see "Connection Error", the backend is not running.

---

## Full Testing Workflow

### Test 1: Verify Route Works

**Action:**
1. Go to: `http://localhost:3000/strategies/builder`

**Expected:**
- Dark gray UI loads
- Left panel: "Add Leg" button
- Middle panel: Empty chart area
- Right panel: Greeks display area (will be empty/0 until legs added)

**If you see 404:**
- Hard refresh: `Ctrl + Shift + R`
- Check browser console (F12)
- Verify `grep_search` shows route in App.tsx

---

### Test 2: Add Legs (UI Interaction)

**Action:**
1. Click **"+ Add Leg"** button
2. You should see a new row with:
   - Type dropdown (BUY/SELL)
   - Option Type (CE/PE)
   - Strike input (number)
   - Quantity input (number)
   - Delete button (X)

**Expected:**
- Leg appears instantly
- Default: BUY, CE, strike=26150, qty=1
- No API calls yet

**If nothing happens:**
- Check browser console for JavaScript errors (F12 → Console)
- Verify StrategyBuilder.tsx imported correctly in App.tsx

---

### Test 3: Calculate Greeks (API Call)

**Action:**
1. Add 1 leg (BUY CALL at 26000 strike)
2. Leave default: 
   - Type: BUY
   - Option Type: CE
   - Strike: 26000
   - Quantity: 1
3. Click **"Calculate Greeks"** button

**Expected (in Browser Network Tab - F12):**
1. Open DevTools: `F12`
2. Go to **Network** tab
3. Click "Calculate Greeks"
4. Look for POST request to `http://localhost:8000/greeks/calculate`

**Request should show:**
```json
{
  "legs": [
    {
      "type": "BUY",
      "option_type": "CE",
      "strike": 26000,
      "spot": 26150,
      "expiry_days": 7,
      "volatility": 20,
      "quantity": 1
    }
  ],
  "spot": 26150,
  "rate": 5.0
}
```

**Response should show (200 OK):**
```json
{
  "delta": 0.5736,
  "gamma": 0.000261,
  "theta": -11.70,
  "vega": 29.33,
  "rho": 11.73,
  "premium": 125.50,
  "legs_details": [
    {
      "strike": 26000,
      "type": "BUY",
      "option_type": "CE",
      "quantity": 1,
      "delta": 0.5736,
      "gamma": 0.000261,
      "theta": -11.70,
      "vega": 29.33,
      "rho": 11.73,
      "premium": 125.50
    }
  ]
}
```

**Expected UI Result:**
- Right panel shows Greeks values
- Payoff diagram updates in middle panel

**If API call doesn't happen:**
- Check backend logs for errors
- Verify backend running on port 8000
- Check browser console for errors
- Try manual test with PowerShell below

---

### Test 4: Multi-Leg Strategy (Call Spread)

**Action:**
1. Add first leg: BUY CE 26000
2. Add second leg: SELL CE 26200
3. Click "Calculate Greeks"

**Expected:**
- Both legs appear in list
- Greeks show combined values (delta should be lower than single call)
- Payoff diagram shows diagonal line capped at top

**Network Tab Should Show:**
```json
{
  "legs": [
    { "type": "BUY", "option_type": "CE", "strike": 26000, ... },
    { "type": "SELL", "option_type": "CE", "strike": 26200, ... }
  ]
}
```

---

### Test 5: Greeks Display

**Action:**
1. After clicking "Calculate Greeks", check right panel

**Expected to see:**
- Delta: ~0.57 (positive = bullish)
- Gamma: ~0.00026 (positive = long premium)
- Theta: ~-11.70 (negative = time decay loss for longs)
- Vega: ~29.33 (positive = IV increase helps)
- Rho: ~11.73 (positive = rate increase helps)
- Premium: cost of strategy

**Understanding the Greeks:**
- ✅ Delta > 0: Bullish position
- ✅ Gamma > 0: Benefits from large moves
- ✅ Theta < 0: Time decay works against you
- ✅ Vega > 0: IV increases help you
- ✅ Rho > 0: Interest rate increases help

---

### Test 6: Payoff Diagram

**Action:**
1. Add legs and calculate Greeks
2. Check middle panel

**Expected:**
- SVG chart showing payoff line
- X-axis: Spot prices (25900 - 26400)
- Y-axis: P&L values
- Line shows profit/loss at each spot price at expiration

**Example: BUY CALL 26000**
- Below 26000: Loss = premium paid
- Above 26000: Profit increases with spot
- Slope = 1:1 above strike

---

### Test 7: Spot Price Override

**Action:**
1. Add legs with spot price 26150
2. Scroll up to spot price input field
3. Change spot price to 26200
4. Click "Calculate Greeks"

**Expected:**
- Greeks recalculated for new spot price
- Payoff diagram updates
- Delta might change based on new ATM

---

### Test 8: Save Strategy

**Action:**
1. Add 2-3 legs
2. Calculate Greeks
3. Scroll down to "Save Strategy" button
4. Enter strategy name (e.g., "My Call Spread")
5. Click "Save"

**Expected:**
- Modal dialog appears (or success message)
- Network tab shows POST to `/strategies`
- Strategy saved with all legs

**Response should contain:**
```json
{
  "id": 1,
  "name": "My Call Spread",
  "strategy_type": "spread",
  "created_at": "2026-01-07T10:30:00"
}
```

---

## Troubleshooting

### Issue: "Cannot GET /strategies/builder"

**Cause:** Route not registered

**Fix:**
```bash
# Check App.tsx has the route:
grep -n "strategies/builder" d:\FastTradeApp\web\src\App.tsx
```

**Should output:**
```
43: <Route path="/strategies/builder" element={<StrategyBuilder />} />
```

**If missing:** Add manually to App.tsx Routes section

---

### Issue: No Network Request When Clicking "Calculate Greeks"

**Cause:** Button not working or function error

**Debug:**
1. Open DevTools: `F12`
2. Console tab
3. Click "Calculate Greeks"
4. Look for errors

**Common errors:**
- `TypeError: greeksAPI is undefined` → greeksAPI not imported
- `Cannot POST /greeks/calculate` → Backend route not registered
- `Connection refused` → Backend not running

---

### Issue: Network Request Returns 404 or 500

**Cause 1: Backend route not registered (404)**
```bash
# Check if greeks router imported in main.py:
grep "greeks" d:\FastTradeApp\backend\app\main.py
```

Should show:
```
from app.api.routes import greeks
app.include_router(greeks.router)
```

**Cause 2: Greeks calculation error (500)**

Check backend logs:
```powershell
# Look for error in terminal running uvicorn
# Should see: "Greeks calculation error: ..."
```

**Fix:** May need scipy/scipy issues:
```bash
cd backend
pip install --upgrade scipy numpy
```

---

### Issue: Greeks Values Show as 0 or null

**Cause:** API returned but with missing data

**Fix:**
1. Check backend logs
2. Verify leg data in Network tab request
3. Manually test with PowerShell:

```powershell
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

Invoke-RestMethod -Uri "http://localhost:8000/greeks/calculate" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json
```

---

### Issue: Payoff Diagram is Blank

**Cause:** SVG rendering or calculation issue

**Debug:**
1. Verify Greeks calculated successfully
2. Check browser console for errors
3. Inspect Network tab response

**Try:**
1. Add more legs to make calculation more obvious
2. Hard refresh page: `Ctrl + Shift + R`

---

## Complete Test Checklist ✅

- [ ] Backend starts without errors
- [ ] Frontend loads at localhost:3000
- [ ] Navigate to /strategies/builder works
- [ ] Add Leg button adds new leg to list
- [ ] Remove Leg button removes leg
- [ ] Update leg fields updates immediately
- [ ] Calculate Greeks button appears
- [ ] Greeks API returns 200 OK
- [ ] Greeks values display in UI
- [ ] Delta > 0 for BUY calls
- [ ] Delta < 0 for SELL calls
- [ ] Multi-leg Greeks aggregates correctly
- [ ] Payoff diagram renders
- [ ] Spot price changes update Greeks
- [ ] Save Strategy works
- [ ] Strategy appears in list after save

---

## Next Steps After Testing

Once all tests pass:

1. **Phase 5 Complete**: Strategy builder UI fully functional ✅
2. **Phase 5B**: Add strategy templates (presets)
3. **Phase 6**: Portfolio analytics (aggregate Greeks across positions)
4. **Live Trading**: Connect to execution engine

---

## Quick Command Reference

```bash
# Start backend
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --reload

# Start frontend
cd d:\FastTradeApp\web
npm start

# Test Greeks API
cd d:\FastTradeApp
python test_greeks_api.py

# Check route registered
grep "strategies/builder" d:\FastTradeApp\web\src\App.tsx

# Check backend route registered
grep "greeks" d:\FastTradeApp\backend\app\main.py
```

---

## Questions or Errors?

Check these files in order:

1. **Frontend route missing?** → [web/src/App.tsx](web/src/App.tsx#L43)
2. **greeksAPI not found?** → [web/src/lib/api.ts](web/src/lib/api.ts)
3. **Backend route missing?** → [backend/app/main.py](backend/app/main.py#L110)
4. **Greeks calculation error?** → Check backend logs + [backend/app/api/routes/greeks.py](backend/app/api/routes/greeks.py)
5. **StrategyBuilder not rendering?** → [web/src/pages/StrategyBuilder.tsx](web/src/pages/StrategyBuilder.tsx)

