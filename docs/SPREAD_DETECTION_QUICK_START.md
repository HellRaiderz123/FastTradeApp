# 🚀 Spread Detection - Quick Start

## What It Does
When you open the **Positions** page, you'll now see a new section called **"🎯 Spread Intelligence"** that automatically analyzes your open trades and:

1. ✅ **Groups related options into spreads** (Bull Call, Iron Condor, etc.)
2. ⚠️ **Shows incomplete spreads** with missing protective legs
3. 🚨 **Alerts on naked positions** (unlimited risk) in RED

---

## How to Use It

### 1. Open the Positions Page
Navigate to `/positions` in your app

### 2. View Your Spread Analysis
Below your "Open Positions" list, you'll see:

```
🎯 SPREAD INTELLIGENCE

Summary Cards:
  ✅ Grouped Spreads: 3
  ⚠️ Incomplete Spreads: 1  
  🚨 Naked Positions: 2
  🔴 Critical Alerts: 2

[Detailed Analysis Below]
```

### 3. Check for Warnings

#### 🟢 Green Section: Properly Hedged Spreads
```
✅ 📈 Bull Call Spread
   NIFTY • Week 1 • Confidence: 95%
   Max Profit: ₹10,000
   
   [Click to expand and see all legs]
```

**Action**: Keep monitoring, spread is healthy

#### 🟡 Yellow Section: Incomplete Spreads  
```
⚠️ SELL 25000 PE is missing its hedge
   Affected: Position ID xyz
   Consider adding: BUY 24900 PE (or lower)
```

**Action**: Add the missing leg to complete the spread

#### 🔴 Red Section: Naked Positions (HIGH RISK!)
```
🚨 NAKED SELL 25000 PE 
   Unhedged position - Unlimited loss potential!
   
   [Hedge Button]
```

**Action**: 
- ❌ DO NOT ignore this!
- ✅ Either add a protective BUY leg
- ✅ Or close the position immediately
- ✅ Set a strict stop loss

---

## Understanding the Summary

### "Grouped Spreads" (Green)
Count of properly detected spreads where all legs are paired correctly.
- ✅ Each leg has its corresponding hedge
- ✅ Max profit and loss are calculable
- ✅ Risk is known and limited

### "Incomplete Spreads" (Yellow)
Positions that look like spreads but are missing legs.
- ⚠️ Unlikely intentional (most spreads need pairs)
- ⚠️ Unbalanced risk exposure
- ✅ Can be fixed by adding missing leg

### "Naked Positions" (Red)
Completely unhedged positions.
- 🚨 If SELL: Unlimited downside loss!
- 🚨 If BUY: Significant downside at 0
- ⚠️ These are NOT spreads
- ⚠️ Require immediate hedging

### "Critical Alerts" (Red Count)
Number of CRITICAL level warnings (usually naked sells).
- 🚨 If > 0: Requires immediate action
- ✅ Add protective legs or close

---

## Spread Types Detected

| Spread | Pattern | Max Risk |
|--------|---------|----------|
| **Bull Call** | BUY lower CE + SELL higher CE | Known (premium paid) |
| **Bear Call** | SELL higher CE + BUY higher CE | Known |
| **Bull Put** | SELL higher PE + BUY lower PE | Known |
| **Bear Put** | BUY higher PE + SELL lower PE | Known |
| **Iron Condor** | Bull Put + Bear Call (4 legs) | Known |
| **Straddle** | BUY/SELL same strike CE+PE | Known/Unlimited |
| **Strangle** | BUY/SELL diff strikes CE+PE | Known/Unlimited |

---

## Step-by-Step Example

### Scenario: You Executed "BULL_CALL_SPREAD"

#### Before Spread Detection
```
Open Positions:

Position 1: BUY 20000 CE (NIFTY)
  Entry: ₹250
  Current P&L: ₹100
  
Position 2: SELL 20100 CE (NIFTY)
  Entry: -₹150
  Current P&L: -₹50

Risk: ???
Max Profit: ???
Max Loss: ???
```

#### After Spread Detection
```
🎯 SPREAD INTELLIGENCE

Summary:
  ✅ Grouped Spreads: 1
  ⚠️ Incomplete: 0
  🚨 Naked: 0
  
Properly Grouped Spreads:
  ✅ 📈 Bull Call Spread
     NIFTY • Weekly • Confidence: 95%
     
     Legs:
       BUY 20000 CE (Qty: 1)
       SELL 20100 CE (Qty: 1)
     
     Max Profit: ₹10,000 (width - premium paid)
     Max Loss: ₹5,000 (premium paid)
     Breakeven: ₹20,250

✅ Spread is properly hedged! No warnings.
```

**Benefit**: Now you see the spread's max profit/loss at a glance!

---

## Common Issues & Fixes

### Issue: "Two positions not grouping into spread"

**Reasons**:
- ❌ Different expirations (e.g., weekly vs monthly)
- ❌ Different underlyings (e.g., NIFTY vs BANKNIFTY)
- ❌ Strike pattern doesn't match known spreads

**Fix**: Verify expiry and underlying are exactly the same

---

### Issue: "CRITICAL warning for position I didn't mean to hedge"

**Reason**: 
- Position is a naked sell (only one leg, not paired)

**Options**:
1. Add a protective BUY leg to pair it
2. Close the position if it was accidental
3. Check if you meant to create a spread instead

---

### Issue: "Spread shows wrong confidence %"

**Meaning**:
- 95% = Perfect 2-leg pattern match
- 90% = Pattern matches but something unusual
- 85% = Possible but ambiguous

**Why it matters**:
- Lower confidence = more likely to be orphaned positions
- Higher confidence = definitely a spread

---

## Tips & Best Practices

### ✅ DO
- ✅ Check Spread Intelligence section daily
- ✅ Act on CRITICAL warnings within same day
- ✅ Verify spreads have both expected legs
- ✅ Monitor max loss limits quarterly

### ❌ DON'T
- ❌ Ignore RED warnings (naked positions)
- ❌ Assume incomplete spreads are intentional
- ❌ Leave naked sells overnight unmonitored
- ❌ Exceed max loss limits per spread

---

## FAQ

**Q: Why is my spread showing 85% confidence instead of 95%?**
A: Strike distance or quantity mismatch slightly unusual. Still a valid spread, just less typical.

**Q: Can I hedge a naked position automatically?**
A: Not yet, but "Hedge" button will be available soon. For now, manually add protective legs.

**Q: What if I have 10+ open positions?**
A: System handles 100+ positions efficiently. UI is still responsive.

**Q: How often does it update?**
A: Real-time via WebSocket when available, falls back to 30-second polling.

**Q: Can I disable warnings?**
A: Not recommended (why would you?), but settings coming soon.

---

## Next Steps

1. ✅ Open Positions page now
2. ✅ Look for new "Spread Intelligence" section
3. ✅ Check if any CRITICAL warnings appear
4. ✅ Review any incomplete spreads
5. ✅ Monitor max profit/loss limits

**That's it!** The system works automatically. Just monitor and act on warnings. 🎯

For detailed technical information, see [SPREAD_DETECTION_GUIDE.md](./SPREAD_DETECTION_GUIDE.md)
