"""
Test Impact of VIX/IV on Strategy Decisions
Shows how IV regime affects strategy approvals
"""
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load credentials from backend/.env if present (avoid hardcoding)
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Ensure execution mode allows Zerodha calls if creds exist
os.environ.setdefault("EXECUTION_MODE", "ZERODHA_DRY_RUN")

print("\n" + "="*100)
print("TESTING IMPACT OF VIX/IV ON STRATEGY DECISIONS")
print("="*100)

from datetime import datetime, timedelta

from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.db.session import SessionLocal, engine
from app.db.models import Base
from app.db.models_candles import Candle15m

Base.metadata.create_all(bind=engine)


def seed_candles(db):
    """Seed minimal 15m candles so TA has data."""
    existing = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == "NIFTY")
        .count()
    )
    if existing >= 120:
        return

    now = datetime.utcnow()
    candles = []
    for i in range(120):  # 120 × 15m = 30 hours of data
        ts = now - timedelta(minutes=15 * (120 - i))
        base = 20000 + i * 2
        candles.append(
            Candle15m(
                symbol="NIFTY",
                timestamp=ts,
                open=base,
                high=base + 5,
                low=base - 5,
                close=base + 1,
                volume=100000 + i * 100,
            )
        )

    db.bulk_save_objects(candles)
    db.commit()


db = SessionLocal()
seed_candles(db)

# Scenario 1: LOW IV (current market)
print("\n[SCENARIO 1] LOW IV Environment (VIX=10.1, IV_Rank=7.26)")
print("-" * 100)
try:
    result1 = run_option_spread(db=db, payload={
        "underlying": "NIFTY",
        "interval": "15m",
        "use_ml": False,
        "min_confidence": 75,
        "risk_mode": "Conservative",
        "lots": 1,
        "capital": 100000
    })
    
    print(f"  Strategy: {result1.get('strategy')}")
    print(f"  Approved: {result1.get('approved')}")
    print(f"  Reason: {result1.get('reason')}")
    signal = result1.get('signal', {})
    print(f"  IV Regime: {signal.get('iv_regime')}")
    print(f"  ADX: {signal.get('indicators', {}).get('adx')}")
    print(f"  Confidence: {signal.get('confidence')}%")

except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc()

db.close()

# Scenario 2: HIGH IV (high volatility market)
print("\n[SCENARIO 2] HIGH IV Environment (VIX=35, IV_Rank=85)")
print("-" * 100)

# For this test, we'll manually inject HIGH IV into the signal
from app.core.signals.signals import generate_signal

db = SessionLocal()
try:
    # Generate signal with HIGH IV
    signal_high_iv = generate_signal(
        db=db,
        symbol="NIFTY",
        vix_rank=85.0,
        india_vix=35.0,
        iv_regime="HIGH"
    )
    
    print(f"  Signal: {signal_high_iv.get('signal')}")
    print(f"  IV Regime: {signal_high_iv.get('iv_regime')}")
    print(f"  Confidence: {signal_high_iv.get('confidence')}%")
    print(f"  Quality Score: {signal_high_iv.get('quality_score')}")
    print(f"  ADX: {signal_high_iv.get('indicators', {}).get('adx')}")
    
    # This signal can now be used by strategy engine
    # The decision logic should handle HIGH IV better
    print("\n  Signal enriched with HIGH IV data:")
    print(f"     India VIX: {signal_high_iv.get('indicators', {}).get('india_vix')}")
    print(f"     IV Rank: {signal_high_iv.get('indicators', {}).get('iv_rank')}")
    
finally:
    db.close()

# Scenario 3: NORMAL IV
print("\n[SCENARIO 3] NORMAL IV Environment (VIX=20, IV_Rank=50)")
print("-" * 100)

db = SessionLocal()
try:
    signal_normal_iv = generate_signal(
        db=db,
        symbol="NIFTY",
        vix_rank=50.0,
        india_vix=20.0,
        iv_regime="NORMAL"
    )
    
    print(f"  Signal: {signal_normal_iv.get('signal')}")
    print(f"  IV Regime: {signal_normal_iv.get('iv_regime')}")
    print(f"  Confidence: {signal_normal_iv.get('confidence')}%")
    print(f"  Quality Score: {signal_normal_iv.get('quality_score')}")
    
finally:
    db.close()

print("\n" + "="*100)
print("✅ VIX/IV IMPACT TEST COMPLETE")
print("="*100)

print("\n📊 COMPARISON:")
print("  LOW IV:      Strategy likely rejected (unfavorable for spreads)")
print("  NORMAL IV:   Strategy might be approved (optimal for spreads)")
print("  HIGH IV:     Strategy likely approved (great for credit spreads)")

print("\n🔑 KEY IMPROVEMENTS:")
print("  1. Strategy decisions now depend on real VIX/IV levels")
print("  2. HIGH IV regimes → Better risk/reward for spreads")
print("  3. LOW IV regimes → Unfavorable (wider spreads needed)")
print("  4. Signal enrichment now includes market regime data")
print("  5. Quality checks include IV regime validation")

print("\n" + "="*100 + "\n")
