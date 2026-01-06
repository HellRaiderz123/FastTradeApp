# 🔌 API ENDPOINT ENHANCEMENTS FOR COMPREHENSIVE SIGNALS

**Purpose:** Shows how to call the enhanced signal system with all data

---

## 1️⃣ Basic Signal (TA Only)

```bash
POST /strategy/option-spread/15m/run

{
  "underlying": "NIFTY",
  "capital": 100000,
  "lots": 1,
  "use_ml": false
}
```

**Response (with comprehensive signal):**
```json
{
  "run_id": 42,
  "strategy": "BULL_PUT",
  "approved": true,
  "reason": "Trending bullish (conf=82%, quality=7/8)",
  "signal": {
    "signal": "BULLISH",
    "confidence": 82,
    "reason": "EMA trend up + RSI > 50 + ADX strong",
    "bias": "BULLISH",
    "iv_regime": "NORMAL",
    "quality_score": 7,
    "trade_readiness_score": 78,
    "quality_checks": {
      "adx_strong": true,
      "time_ok": true,
      "stoch_ok": true,
      "vix_ok": true,
      "bb_confirm": true,
      "iv_trade_ok": true,
      "vol_strong": true,
      "sr_confirm": true
    },
    "indicators": {
      "adx": 28,
      "rsi": 64,
      "macd_hist": 0.6546,
      "stoch_k": 78,
      "stoch_d": 62,
      "sma_20": 26342.50,
      "sma_50": 26300.00,
      "ema_20": 26350.25,
      "ema_50": 26320.75,
      "bb_upper": 26400.50,
      "bb_middle": 26350.25,
      "bb_lower": 26300.00,
      "volatility_pct": 0.12,
      "volume_ratio": 1.8,
      "india_vix": 10.1,
      "iv_rank": 7.26
    },
    "trend_score": 95
  },
  "context": {
    "market_mode": "TRENDING",
    "vol_state": "NORMAL",
    "iv_regime": "NORMAL",
    "bias": "BULLISH",
    "quality_score": 7,
    "trade_readiness_score": 78,
    "trend_score": 95
  },
  "risk_metrics": {
    "strike_dist_pct": 0.6,
    "max_loss": 5000,
    "risk_pct_capital": 5.0
  },
  "ticket": {
    "strategy": "BULL_PUT",
    "underlying": "NIFTY",
    "lot_size": 50,
    "lots": 1,
    "legs": [
      {
        "side": "SELL",
        "strike": 22300,
        "type": "PE"
      },
      {
        "side": "BUY",
        "strike": 22200,
        "type": "PE"
      }
    ]
  },
  "spot": 22350,
  "atm": 22350,
  "strike_meta": {
    "step": 50,
    "width": 100,
    "short_offset": 50
  }
}
```

---

## 2️⃣ Signal with IV Data Enrichment

```bash
POST /strategy/option-spread/15m/run

{
  "underlying": "NIFTY",
  "capital": 100000,
  "lots": 1,
  "use_ml": false,
  "iv_rank": 7.26,
  "india_vix": 10.1,
  "iv_regime": "LOW"
}
```

**Response:**
```json
{
  "run_id": 43,
  "strategy": "NO_TRADE",
  "approved": false,
  "reason": "Range market with low IV → Unfavorable for spreads",
  "signal": {
    "signal": "BULLISH",
    "confidence": 82,
    "bias": "BULLISH",
    "iv_regime": "LOW",      ← Updated!
    "quality_score": 6,      ← Adjusted with IV data
    "quality_checks": {
      "adx_strong": true,
      "time_ok": true,
      "stoch_ok": true,
      "vix_ok": true,
      "bb_confirm": true,
      "iv_trade_ok": false,  ← Changed to false in LOW IV
      "vol_strong": true,
      "sr_confirm": true
    },
    "trade_readiness_score": 68,  ← Reduced due to LOW IV
    "indicators": {
      "adx": 28,
      "india_vix": 10.1,     ← Added!
      "iv_rank": 7.26,       ← Added!
      ...rest of indicators...
    }
  }
}
```

---

## 3️⃣ Full Integration with ML App Response

**Endpoint to add (NEW):**
```python
# In app/api/routes/strategy.py or new file

@router.post("/strategy/option-spread/15m/run/with-ml")
def run_option_spread_with_ml(
    payload: OptionSpreadRequest,
    ml_app_response: MLAppSignal = Body(...),
    db: Session = Depends(get_db)
):
    """
    Runs strategy with full ML app signal integration.
    """
    result = run_option_spread(
        db=db,
        payload=payload.dict(),
        ml_app_response=ml_app_response.dict()
    )
    return result
```

**Request:**
```bash
POST /strategy/option-spread/15m/run/with-ml

{
  "payload": {
    "underlying": "NIFTY",
    "capital": 100000,
    "lots": 1
  },
  "ml_app_response": {
    "signal": "BUY_CE",
    "confidence": 85.0,
    "quality_checks": {
      "adx_strong": true,
      "time_ok": true,
      "stoch_ok": true,
      "vix_ok": true,
      "bb_confirm": true,
      "iv_trade_ok": false,
      "vol_strong": true,
      "sr_confirm": true
    },
    "quality_score": 7,
    "trade_readiness_score": 75,
    "iv_regime": "LOW",
    "iv_rank": 7.26,
    "india_vix": 10.1,
    "indicators": {
      "adx": 26,
      "rsi": 64,
      "macd_hist": 0.6546,
      "stoch_k": 78,
      "trend_score": 95
    }
  }
}
```

**Response:**
```json
{
  "run_id": 44,
  "strategy": "BULL_PUT",
  "approved": true,
  "reason": "Trending bullish (conf=85%, quality=7/8)",
  "signal": {
    "signal": "BULLISH",        ← From ML app
    "confidence": 85,           ← From ML app (higher than TA)
    "bias": "BULLISH",
    "iv_regime": "LOW",         ← From ML app
    "quality_score": 7,         ← From ML app
    "quality_checks": {...},
    "ml_override": true         ← Indicates ML was used
  }
}
```

---

## 4️⃣ Pydantic Models to Add

```python
# app/api/schemas/signal.py

from pydantic import BaseModel
from typing import Optional, Dict, Any

class QualityChecks(BaseModel):
    adx_strong: bool
    time_ok: bool
    stoch_ok: bool
    vix_ok: bool
    bb_confirm: bool
    iv_trade_ok: bool
    vol_strong: bool
    sr_confirm: bool

class SignalIndicators(BaseModel):
    adx: float
    rsi: float
    macd_hist: float
    stoch_k: float
    stoch_d: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    volatility_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    india_vix: Optional[float] = None
    iv_rank: Optional[float] = None

class MLAppSignal(BaseModel):
    signal: str  # BUY_CE, BUY_PE, NO_TRADE
    confidence: float
    quality_checks: QualityChecks
    quality_score: int  # 0-8
    trade_readiness_score: int  # 0-100
    iv_regime: str  # LOW, NORMAL, HIGH
    iv_rank: float
    india_vix: float
    indicators: SignalIndicators
    trend_score: Optional[int] = None
    bias: Optional[str] = None

class TechnicalSignal(BaseModel):
    signal: str
    confidence: float
    reason: str
    bias: str
    iv_regime: str
    quality_checks: QualityChecks
    quality_score: int
    trade_readiness_score: int
    indicators: SignalIndicators
    trend_score: int
```

---

## 5️⃣ Updated Engine Function Signature

```python
# app/core/strategies/option_spread_15m/engine.py

def run_option_spread(
    db: Session, 
    payload: Dict[str, Any],
    iv_rank: Optional[float] = None,
    india_vix: Optional[float] = None,
    iv_regime: Optional[str] = None,
    ml_app_response: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Enhanced engine that accepts:
    - Basic payload (NIFTY, capital, lots)
    - Optional IV enrichment (iv_rank, india_vix, iv_regime)
    - Optional ML app full response
    """
    
    # Generate signal with all enhancements
    sig = generate_signal(
        db=db,
        symbol=payload["underlying"],
        use_ml=payload.get("use_ml", False),
        iv_rank=iv_rank,
        india_vix=india_vix,
        iv_regime=iv_regime,
        ml_app_response=ml_app_response,
    )
    
    # Rest of orchestration...
```

---

## 6️⃣ Complete Request/Response Flow

### Request Format
```json
{
  "underlying": "NIFTY",
  "capital": 100000,
  "lots": 1,
  "min_confidence": 75,
  "risk_mode": "Conservative",
  "use_ml": false,
  
  // Optional: IV data
  "iv_rank": 7.26,
  "india_vix": 10.1,
  "iv_regime": "LOW",
  
  // Optional: Full ML response
  "ml_app_response": {...}
}
```

### Response Format
```json
{
  "run_id": 42,
  "strategy": "BULL_PUT|BEAR_CALL|IRON_CONDOR|NO_TRADE",
  "approved": true|false,
  "reason": "Detailed reason",
  
  "signal": {
    "signal": "BULLISH|BEARISH|RANGE",
    "confidence": 85.0,
    "bias": "BULLISH|BEARISH|NEUTRAL",
    "iv_regime": "LOW|NORMAL|HIGH",
    "quality_score": 7,
    "trade_readiness_score": 75,
    "quality_checks": {...},
    "indicators": {...},
    "trend_score": 95
  },
  
  "context": {
    "market_mode": "TRENDING|RANGE",
    "vol_state": "HIGH|NORMAL|LOW",
    "iv_regime": "LOW|NORMAL|HIGH",
    "quality_score": 7,
    "trade_readiness_score": 75
  },
  
  "ticket": {
    "strategy": "BULL_PUT",
    "underlying": "NIFTY",
    "lots": 1,
    "legs": [...]
  },
  
  "risk_metrics": {
    "strike_dist_pct": 0.6,
    "max_loss": 5000,
    "risk_pct_capital": 5.0
  },
  
  "spot": 22350,
  "atm": 22350
}
```

---

## ✅ SUMMARY

| Component | Status | Now Includes |
|-----------|--------|--------------|
| Signal | ✅ Enhanced | 15+ indicators + quality + readiness |
| Context | ✅ Enhanced | Quality score + trade readiness |
| Decision | ✅ Enhanced | Quality gate + better logic |
| Integration | ✅ Ready | IV enrichment + ML app response |
| API | ✅ Ready | Full comprehensive responses |

**Your trading engine now has all the data from your ML app available for proper decision-making!**

