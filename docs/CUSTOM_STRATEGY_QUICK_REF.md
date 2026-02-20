# 🎯 Custom Strategy Builder - Quick Reference

## Strike Positioning Modes

### ABSOLUTE (Fixed Strikes)
```json
{
  "strike_type": "ABSOLUTE",
  "strike": 51000
}
```
✅ Use for: One-off trades, specific price levels

### RELATIVE (ATM-based) ⭐ RECOMMENDED
```json
{
  "strike_type": "RELATIVE",
  "strike_offset": 100
}
```
✅ Use for: Algo strategies, backtesting, production

---

## Common Offset Values

### Calls (CE)
- `strike_offset: 0` → ATM (At-The-Money)
- `strike_offset: 100` → 100 points OTM
- `strike_offset: 200` → 200 points OTM
- `strike_offset: -100` → 100 points ITM

### Puts (PE)
- `strike_offset: 0` → ATM (At-The-Money)
- `strike_offset: -100` → 100 points OTM
- `strike_offset: -200` → 200 points OTM
- `strike_offset: 100` → 100 points ITM

---

## Strategy Templates

### Bear Call Spread (Collect Premium)
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 0, "quantity": 15},
    {"side": "BUY", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 100, "quantity": 15}
  ]
}
```

### Bull Put Spread (Collect Premium)
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": 0, "quantity": 15},
    {"side": "BUY", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -100, "quantity": 15}
  ]
}
```

### Iron Condor (Defined Risk Both Sides)
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 200, "quantity": 50},
    {"side": "BUY", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 300, "quantity": 50},
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -200, "quantity": 50},
    {"side": "BUY", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -300, "quantity": 50}
  ]
}
```

### Short Straddle (High Premium, High Risk)
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 0, "quantity": 50},
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": 0, "quantity": 50}
  ]
}
```

### Short Strangle (Safer than Straddle)
```json
{
  "expiry": "2026-01-15",
  "legs": [
    {"side": "SELL", "option_type": "CE", "strike_type": "RELATIVE", "strike_offset": 100, "quantity": 50},
    {"side": "SELL", "option_type": "PE", "strike_type": "RELATIVE", "strike_offset": -100, "quantity": 50}
  ]
}
```

---

## API Request Example

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
            "option_type": "CE",
            "strike_type": "RELATIVE",
            "strike_offset": 0,
            "quantity": 15
          },
          {
            "side": "BUY",
            "option_type": "CE",
            "strike_type": "RELATIVE",
            "strike_offset": 100,
            "quantity": 15
          }
        ]
      }
    }
  }'
```

---

## Testing

```bash
cd D:\FastTradeApp\backend
python test_custom_strategy_relative.py
```

---

## Pro Tips

✅ **For Production:** Always use `RELATIVE` positioning
✅ **For Backtesting:** Use `RELATIVE` to test across multiple dates
✅ **For Learning:** Start with `ABSOLUTE` to understand strikes
✅ **Iron Condor:** Use ±200/±300 offsets for standard width
✅ **Strangle:** 100 points OTM on both sides is common

---

## Backward Compatibility

Old format without `strike_type` still works (defaults to ABSOLUTE):

```json
{"side": "SELL", "option_type": "CE", "strike": 51000, "quantity": 15}
```

Equals:

```json
{"side": "SELL", "option_type": "CE", "strike_type": "ABSOLUTE", "strike": 51000, "quantity": 15}
```

---

**Full Documentation:** [CUSTOM_STRATEGY_RELATIVE_GUIDE.md](CUSTOM_STRATEGY_RELATIVE_GUIDE.md)
