# Quick Reference: All 10 Strategies

## Strategy Cheat Sheet

| # | Strategy | Legs | Bias | Risk | When to Use | Min Confidence | Min Quality |
|---|----------|------|------|------|-------------|----------------|-------------|
| 1 | **Bull Put Spread** | 2 | Bullish | Limited | Range + Bullish bias | 60% | 4/8 |
| 2 | **Bear Call Spread** | 2 | Bearish | Limited | Range + Bearish bias | 60% | 4/8 |
| 3 | **Iron Condor** | 4 | Neutral | Limited | Range + High IV | 70% | 5/8 |
| 4 | **Short Straddle** 🔴 | 2 | Neutral | **Unlimited** | Range + Very High IV | **80%** | 6/8 |
| 5 | **Short Strangle** 🔴 | 2 | Neutral | **Unlimited** | Range + High IV | **75%** | 6/8 |
| 6 | **Long Straddle** 🟢 | 2 | Neutral | Limited | Low IV + Big move expected | 70% | 5/8 |
| 7 | **Long Strangle** 🟢 | 2 | Neutral | Limited | Low IV + Breakout expected | 70% | 5/8 |
| 8 | **Butterfly Spread** 🟣 | 4 | Neutral | Limited | Range + Low vol expected | 60% | 5/8 |
| 9 | **Call Ratio Backspread** 🟢 | 3 | Bullish | Limited | Strong uptrend + ADX≥20 | **75%** | 6/8 |
| 10 | **Put Ratio Backspread** 🟢 | 3 | Bearish | Limited | Strong downtrend + ADX≥20 | **75%** | 6/8 |

🔴 = Unlimited risk (use with extreme caution)  
🟢 = Unlimited profit potential  
🟣 = Low volatility play  

---

## Strike Construction

### **Simple Spreads** (Bull Put, Bear Call)
```
Bull Put:
  Short: ATM - offset (e.g., 24000 - 100 = 23900)
  Long:  Short - width (e.g., 23900 - 100 = 23800)

Bear Call:
  Short: ATM + offset (e.g., 24000 + 100 = 24100)
  Long:  Short + width (e.g., 24100 + 100 = 24200)
```

### **Iron Condor** (4 legs)
```
Put Side:
  Short Put: ATM - offset (e.g., 23900)
  Long Put:  Short - width (e.g., 23800)

Call Side:
  Short Call: ATM + offset (e.g., 24100)
  Long Call:  Short + width (e.g., 24200)
```

### **Straddle** (ATM both sides)
```
Short Straddle:
  Sell Call: ATM (e.g., 24000 CE)
  Sell Put:  ATM (e.g., 24000 PE)

Long Straddle:
  Buy Call: ATM (e.g., 24000 CE)
  Buy Put:  ATM (e.g., 24000 PE)
```

### **Strangle** (OTM both sides)
```
Short Strangle:
  Sell Call: ATM + step (e.g., 24050 CE)
  Sell Put:  ATM - step (e.g., 23950 PE)

Long Strangle:
  Buy Call: ATM + step (e.g., 24050 CE)
  Buy Put:  ATM - step (e.g., 23950 PE)
```

### **Butterfly** (Buy-Sell 2x-Buy)
```
Call Butterfly:
  Buy 1:  ATM - width (e.g., 23900 CE) x1
  Sell 2: ATM (e.g., 24000 CE) x2
  Buy 1:  ATM + width (e.g., 24100 CE) x1

Width = 100 (NIFTY) or 200 (BANKNIFTY)
```

### **Ratio Backspreads** (Sell 1, Buy 2)
```
Call Ratio Backspread:
  Sell 1: ATM - step (slight ITM, e.g., 23950 CE) x1
  Buy 1:  ATM + step (OTM, e.g., 24050 CE) x1
  Buy 1:  ATM + 2*step (far OTM, e.g., 24100 CE) x1

Put Ratio Backspread:
  Sell 1: ATM + step (slight ITM, e.g., 24050 PE) x1
  Buy 1:  ATM - step (OTM, e.g., 23950 PE) x1
  Buy 1:  ATM - 2*step (far OTM, e.g., 23900 PE) x1
```

---

## Risk Comparison

| Strategy | Max Loss | Max Profit | Breakevens |
|----------|----------|------------|------------|
| Bull Put | Spread width - Premium | Premium received | Short - Premium |
| Bear Call | Spread width - Premium | Premium received | Short + Premium |
| Iron Condor | Larger wing - Premium | Premium received | 2 points |
| Short Straddle | **Unlimited** | Premium received | ATM ± Premium |
| Short Strangle | **Unlimited** | Premium received | Strikes ± Premium |
| Long Straddle | Premium paid | **Unlimited** | ATM ± Premium |
| Long Strangle | Premium paid | **Unlimited** | Strikes ± Premium |
| Butterfly | Premium paid | Spread width - Premium | 2 points |
| Call Ratio Backspread | Limited (between strikes) | **Unlimited upside** | 2 points |
| Put Ratio Backspread | Limited (between strikes) | **Unlimited downside** | 2 points |

---

## Market Regime → Strategy Map

### 📈 **Strong Uptrend** (ADX ≥ 20, Bullish)
- Best: **Call Ratio Backspread** (unlimited upside, low/normal IV)
- Fallback: **Bull Put Spread** (safer, lower confidence)

### 📉 **Strong Downtrend** (ADX ≥ 20, Bearish)
- Best: **Put Ratio Backspread** (unlimited downside, low/normal IV)
- Fallback: **Bear Call Spread** (safer, lower confidence)

### 📊 **Range + High IV** (VIX > 20)
- Best: **Short Straddle** (max premium, extreme confidence ≥80%)
- Good: **Short Strangle** (high premium, confidence ≥75%)
- Safe: **Iron Condor** (defined risk, confidence ≥70%)

### 📊 **Range + Low IV** (VIX < 15)
- Neutral: **Butterfly Spread** (low vol expected)
- Bullish: **Bull Put Spread**
- Bearish: **Bear Call Spread**

### ⚡ **Expecting Volatility Spike** (Low IV currently)
- Uncertain direction: **Long Strangle** (cheaper than straddle)
- Strong move expected: **Long Straddle** (ATM for max sensitivity)
- Directional + breakout: **Ratio Backspread**

---

## Lot Sizes & Strike Steps

| Underlying | Lot Size | Strike Step | Weekly Expiry |
|------------|----------|-------------|---------------|
| **NIFTY** | 65 | 50 | Tuesday |
| **BANKNIFTY** | 15 | 100 | Wednesday |
| **FINNIFTY** | 40 | 50 | Tuesday |

### Example Trade Sizing
```
NIFTY Bull Put Spread (23900/23800):
- Sell 1 lot 23900 PE: 65 qty
- Buy 1 lot 23800 PE: 65 qty
- Max loss: (23900-23800) * 65 = ₹6,500
- Premium (est): ₹20 * 65 = ₹1,300
- Net risk: ₹5,200

BANKNIFTY Iron Condor (49000/48800 Put, 49400/49600 Call):
- Sell 49000 PE + 49400 CE: 15 qty each
- Buy 48800 PE + 49600 CE: 15 qty each
- Max loss: (200 * 15) = ₹3,000
- Premium (est): ₹50 * 15 * 2 = ₹1,500
- Net risk: ₹1,500
```

---

## Testing Checklist

Before using each new strategy in live trading:

### Paper Trading Tests
- [ ] Verify strike calculations for NIFTY
- [ ] Verify strike calculations for BANKNIFTY
- [ ] Verify strike calculations for FINNIFTY
- [ ] Test during high volatility (VIX > 20)
- [ ] Test during low volatility (VIX < 15)
- [ ] Test on weekly expiry day
- [ ] Test risk limit enforcement

### Strategy-Specific Tests
- [ ] **Short Straddle/Strangle**: Verify unlimited risk warnings
- [ ] **Ratio Backspreads**: Verify ADX ≥ 20 requirement
- [ ] **Butterfly**: Verify 4-leg ticket construction
- [ ] **Long Straddle/Strangle**: Verify debit spread handling
- [ ] All strategies: Verify symbol generation (NIFTY24JAN24000CE format)

### API Tests
```bash
# Test suggestions endpoint
curl -X POST http://localhost:8000/api/suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "underlyings": ["NIFTY", "BANKNIFTY", "FINNIFTY"],
    "capital": 100000,
    "lots": 1
  }'

# Should return array with multiple strategy suggestions
# Check for new strategy types in response
```

---

## Safety Guidelines

### ⚠️ **Unlimited Risk Strategies** (Short Straddle, Short Strangle)
1. **Never** use in live trading until you have 3+ months of limited-risk strategy experience
2. **Always** paper trade for minimum 2 weeks first
3. **Start** with 1 lot only
4. **Monitor** positions every 15 minutes
5. **Exit** immediately if price moves 5% against you
6. **Use** stop-loss orders (not just alerts)

### ✅ **Recommended Path for Beginners**
1. **Week 1-2**: Bull Put & Bear Call spreads only
2. **Week 3-4**: Add Iron Condor
3. **Week 5-6**: Add Butterfly & Ratio Backspreads  
4. **Month 2**: Add Long Straddle/Strangle (defined risk)
5. **Month 3+**: Consider Short Straddle/Strangle (with extreme caution)

### 💰 **Position Sizing**
- **Conservative**: Risk 1-2% of capital per trade
- **Moderate**: Risk 3-5% of capital per trade
- **Never exceed**: 10% of capital in one position

---

## Quick Commands

### Check Backend Status
```powershell
# Navigate to backend
cd d:\FastTradeApp\backend

# Check for syntax errors
python -m py_compile app/core/strategies/option_spread_15m/engine.py
python -m py_compile app/core/strategies/option_spread_15m/decision.py
python -m py_compile app/core/strategies/option_spread_15m/risk.py

# Start backend server
uvicorn app.main:app --reload
```

### View Logs
```powershell
# Watch real-time logs
Get-Content backend/logs/fastapi.log -Wait -Tail 50
```

### Test Strategy Engine
```powershell
# Run unit tests (when created)
pytest backend/tests/test_strategy_engine.py -v
```

---

## Support & Resources

- **Decision Logic**: [decision.py](../backend/app/core/strategies/option_spread_15m/decision.py)
- **Risk Checks**: [risk.py](../backend/app/core/strategies/option_spread_15m/risk.py)
- **Strike Calculations**: [strikes.py](../backend/app/core/strategies/option_spread_15m/strikes.py)
- **Ticket Building**: [engine.py](../backend/app/core/strategies/option_spread_15m/engine.py)
- **Production Roadmap**: [PRODUCTION_TRADING_ENHANCEMENTS.md](../PRODUCTION_TRADING_ENHANCEMENTS.md)

---

## Color Legend (Terminal UI)

When displayed in StrategyManager:
- 🟢 **Green**: Approved strategies with good quality scores
- 🟡 **Yellow**: Moderate quality or risk
- 🔴 **Red**: High risk or rejected strategies
- 🔵 **Blue**: Information/neutral status

---

*Last Updated: January 2024*  
*Version: 2.0 (10 Strategies)*
