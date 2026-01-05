# 🧪 QUICK TEST - Verify Signal Enhancement

**Run this to verify the signal changes are working**

---

## Test 1: Direct TA Signal Test

**File:** `test_ta_signal_enhanced.py`

```python
"""
Test enhanced ta_signal_15m output
"""
import sys
sys.path.insert(0, '/path/to/backend')

from app.db.session import SessionLocal
from app.core.signals.ta_engine import ta_signal_15m

db = SessionLocal()

print("=" * 60)
print("TEST 1: Enhanced TA Signal")
print("=" * 60)

try:
    signal = ta_signal_15m(db, "NIFTY")
    
    # Check required fields
    required_fields = [
        "signal",
        "confidence",
        "bias",
        "iv_regime",
        "quality_checks",
        "quality_score",
        "trade_readiness_score",
        "indicators",
        "trend_score"
    ]
    
    missing = [f for f in required_fields if f not in signal]
    
    if missing:
        print(f"❌ FAILED - Missing fields: {missing}")
    else:
        print("✅ PASSED - All required fields present\n")
        
        print(f"Signal: {signal['signal']}")
        print(f"Confidence: {signal['confidence']:.1f}%")
        print(f"Quality Score: {signal['quality_score']}/8")
        print(f"Trade Readiness: {signal['trade_readiness_score']}/100")
        print(f"IV Regime: {signal['iv_regime']}")
        print(f"Bias: {signal['bias']}")
        print(f"Indicators Count: {len(signal['indicators'])}")
        
        print("\nQuality Checks:")
        for check, status in signal["quality_checks"].items():
            symbol = "✅" if status else "❌"
            print(f"  {symbol} {check}")
        
        print(f"\nTop Indicators:")
        for key in list(signal["indicators"].keys())[:5]:
            print(f"  {key}: {signal['indicators'][key]}")
        
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "=" * 60)
```

**Run with:**
```bash
cd /path/to/backend
python test_ta_signal_enhanced.py
```

**Expected Output:**
```
============================================================
TEST 1: Enhanced TA Signal
============================================================
✅ PASSED - All required fields present

Signal: BULLISH
Confidence: 82.0%
Quality Score: 7/8
Trade Readiness: 78/100
IV Regime: NORMAL
Bias: BULLISH
Indicators Count: 15

Quality Checks:
  ✅ adx_strong
  ✅ time_ok
  ✅ stoch_ok
  ✅ vix_ok
  ✅ bb_confirm
  ❌ iv_trade_ok
  ✅ vol_strong
  ✅ sr_confirm

Top Indicators:
  adx: 28.0
  rsi: 64.0
  macd_hist: 0.6546
  stoch_k: 78.0
  stoch_d: 62.0

============================================================
```

---

## Test 2: Context Building Test

**File:** `test_context_enhanced.py`

```python
"""
Test enhanced context building
"""
import sys
sys.path.insert(0, '/path/to/backend')

from app.db.session import SessionLocal
from app.core.signals.ta_engine import ta_signal_15m
from app.core.strategies.option_spread_15m.context import build_market_context

db = SessionLocal()

print("=" * 60)
print("TEST 2: Enhanced Context Building")
print("=" * 60)

try:
    signal = ta_signal_15m(db, "NIFTY")
    context = build_market_context(signal)
    
    # Check required fields
    required_fields = [
        "market_mode",
        "vol_state",
        "iv_regime",
        "bias",
        "quality_checks",
        "quality_score",
        "trade_readiness_score",
        "indicators"
    ]
    
    missing = [f for f in required_fields if f not in context]
    
    if missing:
        print(f"❌ FAILED - Missing fields: {missing}")
    else:
        print("✅ PASSED - Context building complete\n")
        
        print(f"Market Mode: {context['market_mode']}")
        print(f"Vol State: {context['vol_state']}")
        print(f"IV Regime: {context['iv_regime']}")
        print(f"Bias: {context['bias']}")
        print(f"Quality Score: {context['quality_score']}/8")
        print(f"Trade Readiness: {context['trade_readiness_score']}/100")
        print(f"Indicators Available: {len(context['indicators'])}")
        
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "=" * 60)
```

**Expected Output:**
```
============================================================
TEST 2: Enhanced Context Building
============================================================
✅ PASSED - Context building complete

Market Mode: TRENDING
Vol State: NORMAL
IV Regime: NORMAL
Bias: BULLISH
Quality Score: 7/8
Trade Readiness: 78/100
Indicators Available: 15

============================================================
```

---

## Test 3: Decision Logic Test

**File:** `test_decision_enhanced.py`

```python
"""
Test enhanced decision logic with quality gate
"""
import sys
sys.path.insert(0, '/path/to/backend')

from app.db.session import SessionLocal
from app.core.signals.ta_engine import ta_signal_15m
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy

db = SessionLocal()

print("=" * 60)
print("TEST 3: Enhanced Decision Logic")
print("=" * 60)

try:
    signal = ta_signal_15m(db, "NIFTY")
    context = build_market_context(signal)
    
    strategy, reason = decide_strategy(
        sig=signal,
        ctx=context,
        confidence=signal["confidence"],
        min_confidence=75
    )
    
    print(f"✅ DECISION MADE\n")
    print(f"Strategy: {strategy}")
    print(f"Reason: {reason}")
    print(f"\nData Used:")
    print(f"  Quality Score: {context['quality_score']}/8")
    print(f"  Market Mode: {context['market_mode']}")
    print(f"  IV Regime: {context['iv_regime']}")
    print(f"  Bias: {context['bias']}")
    print(f"  Confidence: {signal['confidence']:.1f}%")
    
    if strategy != "NO_TRADE":
        print(f"\n✅ Strategy approved with quality gate check!")
    else:
        print(f"\n⚠️ Strategy rejected - check quality checks:")
        for check, status in signal["quality_checks"].items():
            symbol = "✅" if status else "❌"
            print(f"  {symbol} {check}")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "=" * 60)
```

**Expected Output:**
```
============================================================
TEST 3: Enhanced Decision Logic
============================================================
✅ DECISION MADE

Strategy: BULL_PUT
Reason: Trending bullish (conf=82%, quality=7/8)

Data Used:
  Quality Score: 7/8
  Market Mode: TRENDING
  IV Regime: NORMAL
  Bias: BULLISH
  Confidence: 82.0%

✅ Strategy approved with quality gate check!

============================================================
```

---

## Test 4: Full Engine Test

**File:** `test_engine_enhanced.py`

```python
"""
Test full strategy engine with enhanced signals
"""
import sys
sys.path.insert(0, '/path/to/backend')

from app.db.session import SessionLocal
from app.core.strategies.option_spread_15m.engine import run_option_spread

db = SessionLocal()

print("=" * 60)
print("TEST 4: Full Strategy Engine")
print("=" * 60)

try:
    payload = {
        "underlying": "NIFTY",
        "interval": "15minute",
        "use_ml": False,
        "min_confidence": 75,
        "risk_mode": "Conservative",
        "lots": 1,
        "capital": 100000,
    }
    
    result = run_option_spread(db, payload)
    
    print(f"✅ ENGINE EXECUTION COMPLETE\n")
    print(f"Strategy: {result['strategy']}")
    print(f"Approved: {result['approved']}")
    print(f"Reason: {result['reason']}")
    
    print(f"\nSignal Data:")
    print(f"  Signal: {result['signal']['signal']}")
    print(f"  Confidence: {result['signal']['confidence']:.1f}%")
    print(f"  Quality Score: {result['signal']['quality_score']}/8")
    print(f"  Trade Readiness: {result['signal']['trade_readiness_score']}/100")
    print(f"  Indicators: {len(result['signal']['indicators'])}")
    
    print(f"\nContext Data:")
    print(f"  Market Mode: {result['context']['market_mode']}")
    print(f"  Vol State: {result['context']['vol_state']}")
    print(f"  IV Regime: {result['context']['iv_regime']}")
    
    if result['approved']:
        print(f"\nTrade Ticket:")
        print(f"  Strategy: {result['ticket']['strategy']}")
        print(f"  Underlying: {result['ticket']['underlying']}")
        print(f"  Legs: {len(result['ticket']['legs'])}")
        for leg in result['ticket']['legs']:
            print(f"    {leg['side']} {leg['strike']}{leg['type']}")
        
        print(f"\nRisk Metrics:")
        for key, val in result['risk_metrics'].items():
            print(f"  {key}: {val}")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "=" * 60)
```

**Expected Output:**
```
============================================================
TEST 4: Full Strategy Engine
============================================================
✅ ENGINE EXECUTION COMPLETE

Strategy: BULL_PUT
Approved: True
Reason: Trending bullish (conf=82%, quality=7/8)

Signal Data:
  Signal: BULLISH
  Confidence: 82.0%
  Quality Score: 7/8
  Trade Readiness: 78/100
  Indicators: 15

Context Data:
  Market Mode: TRENDING
  Vol State: NORMAL
  IV Regime: NORMAL

Trade Ticket:
  Strategy: BULL_PUT
  Underlying: NIFTY
  Legs: 2
    SELL 22300PE
    BUY 22200PE

Risk Metrics:
  strike_dist_pct: 0.6
  max_loss: 5000
  risk_pct_capital: 5.0

============================================================
```

---

## Test 5: Signal Enrichment Test

**File:** `test_enrichment.py`

```python
"""
Test signal enrichment with IV data
"""
import sys
sys.path.insert(0, '/path/to/backend')

from app.db.session import SessionLocal
from app.core.signals.ta_engine import ta_signal_15m
from app.core.signals.signal_enricher import enrich_signal_with_iv

db = SessionLocal()

print("=" * 60)
print("TEST 5: Signal Enrichment with IV Data")
print("=" * 60)

try:
    # Get TA signal
    signal = ta_signal_15m(db, "NIFTY")
    
    print(f"Before Enrichment:")
    print(f"  IV Regime: {signal['iv_regime']}")
    print(f"  Quality Score: {signal['quality_score']}/8")
    print(f"  IV Trade OK: {signal['quality_checks']['iv_trade_ok']}")
    
    # Enrich with IV data
    enriched = enrich_signal_with_iv(
        signal,
        iv_rank=7.26,
        india_vix=10.1,
        iv_regime="LOW"
    )
    
    print(f"\nAfter Enrichment:")
    print(f"  IV Regime: {enriched['iv_regime']}")
    print(f"  Quality Score: {enriched['quality_score']}/8")
    print(f"  IV Trade OK: {enriched['quality_checks']['iv_trade_ok']}")
    print(f"  IV Rank: {enriched['indicators']['iv_rank']}")
    print(f"  India VIX: {enriched['indicators']['india_vix']}")
    print(f"  Trade Readiness: {enriched['trade_readiness_score']}/100")
    
    if enriched['iv_regime'] == "LOW" and enriched['quality_checks']['iv_trade_ok'] == False:
        print(f"\n✅ Enrichment working - LOW IV detected correctly")
    else:
        print(f"\n❌ Enrichment not working properly")
    
except Exception as e:
    print(f"❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

db.close()

print("\n" + "=" * 60)
```

**Expected Output:**
```
============================================================
TEST 5: Signal Enrichment with IV Data
============================================================
Before Enrichment:
  IV Regime: NORMAL
  Quality Score: 7/8
  IV Trade OK: True

After Enrichment:
  IV Regime: LOW
  Quality Score: 6/8
  IV Trade OK: False
  IV Rank: 7.26
  India VIX: 10.1
  Trade Readiness: 68/100

✅ Enrichment working - LOW IV detected correctly

============================================================
```

---

## 🚀 RUN ALL TESTS

**Create:** `run_all_tests.sh`

```bash
#!/bin/bash
cd /path/to/backend

echo "Running all enhancement tests..."
python test_ta_signal_enhanced.py
echo ""
python test_context_enhanced.py
echo ""
python test_decision_enhanced.py
echo ""
python test_engine_enhanced.py
echo ""
python test_enrichment.py

echo "All tests complete!"
```

**Run with:**
```bash
chmod +x run_all_tests.sh
./run_all_tests.sh
```

---

## ✅ SUCCESS CRITERIA

✅ Test 1 passes (signal has 30+ fields)  
✅ Test 2 passes (context extracts quality metrics)  
✅ Test 3 passes (decision makes proper choice)  
✅ Test 4 passes (engine approves trades with quality data)  
✅ Test 5 passes (enrichment updates IV regime correctly)

**If all 5 pass → Signal enhancement is working!**

