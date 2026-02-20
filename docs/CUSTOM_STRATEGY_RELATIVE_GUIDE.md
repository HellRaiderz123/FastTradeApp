# 🎯 Custom Strategy Builder: Relative vs Absolute Strike Positioning

## Overview

The custom strategy builder now supports **two modes** for strike selection:
1. **ABSOLUTE** - Fixed strike values (legacy mode)
2. **RELATIVE** - Dynamic ATM-based positioning (algo mode) ✨

This enhancement brings professional algorithmic trading capabilities to your custom strategies.

---

## Strike Positioning Modes

### 1. ABSOLUTE Strike Positioning

**What it is:** Fixed, hard-coded strike values that never change.

**Use when:**
- Making specific one-off trades
- You have a strong view on a particular strike level
- Quick manual testing
- Learning options trading

**Example:**
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {
      "side": "SELL",
      "option_type": "CE",
      "strike_type": "ABSOLUTE",
      "strike": 51000,
      "quantity": 15
    },
    {
      "side": "BUY",
      "option_type": "CE",
      "strike_type": "ABSOLUTE",
      "strike": 51100,
      "quantity": 15
    }
  ]
}
```

**Result:** Always trades exactly 51000/51100 strikes, regardless of current market price.

---

### 2. RELATIVE Strike Positioning (ATM-based) ⭐

**What it is:** Dynamic strikes calculated as **ATM ± offset**.

**Use when:**
- Building systematic algo strategies
- Backtesting across different price levels
- Production deployment
- Multi-day strategies
- Professional algorithmic trading

**Example:**
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {
      "side": "SELL",
      "option_type": "CE",
      "strike_type": "RELATIVE",
      "strike_offset": 0,        // ATM + 0 = At-The-Money
      "quantity": 15
    },
    {
      "side": "BUY",
      "option_type": "CE",
      "strike_type": "RELATIVE",
      "strike_offset": 100,      // ATM + 100 = 100 points OTM
      "quantity": 15
    }
  ]
}
```

**Result:** If BANKNIFTY spot = 50,850:
- ATM = 50,900 (rounded to nearest 100)
- SELL 50,900 CE (ATM + 0)
- BUY 51,000 CE (ATM + 100)

If next day spot = 51,250:
- ATM = 51,200
- SELL 51,200 CE
- BUY 51,300 CE

**Same strategy logic, adapts to market!** 🎯

---

## Complete Strike Offset Guide

### Call Options (CE)

| Offset | Position | Description | Delta Range |
|--------|----------|-------------|-------------|
| `+300` | OTM | Far Out-of-Money | ~0.10-0.20 |
| `+200` | OTM | Moderately OTM | ~0.20-0.35 |
| `+100` | OTM | Slightly OTM | ~0.35-0.45 |
| `0` | **ATM** | **At-The-Money** | **~0.50** |
| `-100` | ITM | Slightly In-Money | ~0.55-0.65 |
| `-200` | ITM | Moderately ITM | ~0.65-0.80 |

### Put Options (PE)

| Offset | Position | Description | Delta Range |
|--------|----------|-------------|-------------|
| `-300` | OTM | Far Out-of-Money | ~-0.10 to -0.20 |
| `-200` | OTM | Moderately OTM | ~-0.20 to -0.35 |
| `-100` | OTM | Slightly OTM | ~-0.35 to -0.45 |
| `0` | **ATM** | **At-The-Money** | **~-0.50** |
| `+100` | ITM | Slightly In-Money | ~-0.55 to -0.65 |
| `+200` | ITM | Moderately ITM | ~-0.65 to -0.80 |

---

## Common Strategy Patterns

### 1. Bull Call Spread (Relative)
```json
{
  "legs": [
    {"side": "BUY", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 0},
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 100}
  ]
}
```
**Logic:** Buy ATM, Sell 100 OTM → Bullish limited risk

---

### 2. Bear Call Spread (Relative)
```json
{
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 0},
    {"side": "BUY", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 100}
  ]
}
```
**Logic:** Sell ATM, Buy 100 OTM → Bearish/neutral, collect premium

---

### 3. Bull Put Spread (Relative)
```json
{
  "legs": [
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": 0},
    {"side": "BUY", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -100}
  ]
}
```
**Logic:** Sell ATM Put, Buy 100 OTM Put → Bullish, collect premium

---

### 4. Iron Condor (Relative) - Professional Strategy
```json
{
  "legs": [
    // Call Spread (upper)
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 200},
    {"side": "BUY", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 300},
    
    // Put Spread (lower)
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -200},
    {"side": "BUY", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -300}
  ]
}
```
**Logic:** Profit from low volatility, defined risk both sides

---

### 5. Straddle (Relative)
```json
{
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 0},
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": 0}
  ]
}
```
**Logic:** Sell both ATM Call & Put → High premium, expects low volatility

---

### 6. Strangle (Relative)
```json
{
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 100},
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -100}
  ]
}
```
**Logic:** Sell OTM options → Lower risk than straddle, lower premium

---

## Mixed Positioning (Advanced)

You can **combine both modes** in a single strategy:

```json
{
  "legs": [
    {
      "side": "SELL",
      "option_type": "CE",
      "strike_type": "RELATIVE",  // Dynamic
      "strike_offset": 0
    },
    {
      "side": "BUY",
      "option_type": "CE",
      "strike_type": "ABSOLUTE",  // Fixed protection
      "strike": 52000
    }
  ]
}
```

**Use case:** Dynamic entry with fixed protection level.

---

## API Usage Examples

### Python API Call
```python
import requests

payload = {
    "strategy_id": 123,
    "additional_context": {
        "underlying": "NIFTY",
        "parameters": {
            "expiry": "2026-01-15",
            "legs": [
                {
                    "side": "SELL",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 100,
                    "quantity": 50
                },
                {
                    "side": "BUY",
                    "option_type": "CE",
                    "strike_type": "RELATIVE",
                    "strike_offset": 200,
                    "quantity": 50
                }
            ]
        }
    }
}

response = requests.post(
    "http://localhost:8000/strategies/run/single",
    json=payload
)
```

### cURL Request
```bash
curl -X POST http://localhost:8000/strategies/run/single \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": 123,
    "additional_context": {
      "underlying": "BANKNIFTY",
      "parameters": {
        "expiry": "2026-01-15",
        "legs": [
          {
            "side": "SELL",
            "option_type": "PE",
            "strike_type": "RELATIVE",
            "strike_offset": -100,
            "quantity": 15
          },
          {
            "side": "BUY",
            "option_type": "PE",
            "strike_type": "RELATIVE",
            "strike_offset": -200,
            "quantity": 15
          }
        ]
      }
    }
  }'
```

---

## Backward Compatibility

**Old strategies still work!** If you omit `strike_type`, it defaults to `ABSOLUTE`:

```json
{
  "side": "SELL",
  "option_type": "CE",
  "strike": 51000,        // No strike_type → defaults to ABSOLUTE
  "quantity": 15
}
```

This equals:

```json
{
  "side": "SELL",
  "option_type": "CE",
  "strike_type": "ABSOLUTE",
  "strike": 51000,
  "quantity": 15
}
```

---

## Testing

Run the comprehensive test suite:

```bash
cd D:\FastTradeApp\backend
python test_custom_strategy_relative.py
```

**Tests:**
1. ✅ Absolute strike positioning
2. ✅ Relative strike positioning
3. ✅ Mixed positioning
4. ✅ Iron Condor (4-leg)
5. ✅ Backward compatibility

---

## Comparison with Existing option_spread_15m

| Feature | option_spread_15m | option_spread_custom (NEW) |
|---------|-------------------|----------------------------|
| **Strike Mode** | Relative only | Both Absolute + Relative ✅ |
| **Flexibility** | Fixed strategy logic | User-defined legs ✅ |
| **Strategy Types** | Bull Put / Bear Call | Any combination ✅ |
| **Entry Signals** | ADX/RSI based | User-triggered ✅ |
| **Backtest Ready** | ✅ Yes | ✅ Yes (with relative) |
| **Production Ready** | ✅ Yes | ✅ Yes |

---

## Best Practices

### ✅ DO Use Relative Strikes For:
- Automated daily execution
- Backtesting across multiple dates
- Production algo strategies
- Strategies you want to scale

### ⚠️ Consider Absolute Strikes For:
- Learning and experimentation
- Specific market views
- One-off manual trades
- Testing specific price levels

---

## Technical Details

### ATM Calculation
- **NIFTY:** Rounds to nearest 50
- **BANKNIFTY:** Rounds to nearest 100
- **FINNIFTY:** Rounds to nearest 50

Example:
```python
spot = 50,875
atm = round(50875 / 100) * 100 = 50,900
```

### Strike Resolution Process
1. Extract legs from parameters
2. Check if any leg has `strike_type="RELATIVE"`
3. If yes:
   - Fetch current spot price
   - Calculate ATM
   - Resolve all relative strikes: `absolute_strike = ATM + strike_offset`
4. Build ticket with absolute strikes
5. Execute normally

---

## FAQ

**Q: Can I backtest relative strategies?**
✅ Yes! The engine resolves strikes at execution time using historical spot prices.

**Q: What happens if I mix absolute and relative?**
✅ Both work together. Absolute stays fixed, relative adapts to ATM.

**Q: Does this work with live trading?**
✅ Yes! Zerodha executor receives resolved absolute strikes.

**Q: Can I use negative offsets?**
✅ Yes! Negative offsets mean ITM for Calls, OTM for Puts.

**Q: Is the 15m strategy affected?**
❌ No! It continues to work independently with its own logic.

---

## Summary

🎯 **Relative positioning brings professional algo capabilities to custom strategies**

- ✅ Industry-standard approach (like Algobulls, Streak, Tradetron)
- ✅ Backtest across any time period
- ✅ Deploy once, runs forever
- ✅ Complete backward compatibility
- ✅ Flexible: choose what works for you

**Now you have the best of both worlds!** 🚀
