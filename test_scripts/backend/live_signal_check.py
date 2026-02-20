"""
Live signal check with current market data
"""
from pathlib import Path
from dotenv import load_dotenv
import os

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)
os.environ.setdefault("EXECUTION_MODE", "ZERODHA_DRY_RUN")

from app.db.session import SessionLocal, Base, engine
from app.db.models_candles import Candle15m
from app.core.strategies.option_spread_15m.engine import run_option_spread
from app.services.market_data import get_spot
from app.core.market.candles import fetch_15m_candles

print("=" * 80)
print("LIVE SIGNAL & DECISION CHECK")
print("=" * 80)

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Fetch fresh candles if table is empty
candle_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY").count()
if candle_count < 100:
    print(f"\n⚠️  Only {candle_count} candles found, fetching fresh data...")
    try:
        fetch_15m_candles(db, "NIFTY", days=15)
        candle_count = db.query(Candle15m).filter(Candle15m.symbol == "NIFTY").count()
        print(f"✅ Fetched candles, now have {candle_count} bars")
    except Exception as e:
        print(f"⚠️  Could not fetch candles: {e}")
else:
    print(f"\n✅ Found {candle_count} NIFTY candles in DB")

try:
    # Get live spot
    spot = get_spot("NIFTY")
    print(f"\n📊 Live Spot: NIFTY = {spot}")
    
    # Run strategy with current settings
    print("\n🔄 Running option_spread_15m strategy...")
    result = run_option_spread(db=db, payload={
        "underlying": "NIFTY",
        "interval": "15minute",
        "use_ml": False,
        "min_confidence": 75,
        "risk_mode": "Conservative",
        "lots": 1,
        "capital": 100000
    })
    
    print("\n" + "=" * 80)
    print("DECISION RESULT")
    print("=" * 80)
    
    print(f"\nStrategy:  {result.get('strategy')}")
    print(f"Approved:  {result.get('approved')}")
    print(f"Reason:    {result.get('reason')}")
    
    # Signal details
    sig = result.get('signal', {})
    print("\n📡 Signal:")
    print(f"   Bias:       {sig.get('bias')}")
    print(f"   Confidence: {sig.get('confidence')}%")
    print(f"   Quality:    {sig.get('quality_score')}/8")
    
    # Context
    ctx = result.get('context', {})
    print("\n🌐 Context:")
    print(f"   Market Mode: {ctx.get('market_mode')}")
    print(f"   IV Regime:   {ctx.get('iv_regime')}")
    
    # IV data
    context_data = sig.get('context', {})
    print(f"   India VIX:   {context_data.get('india_vix')}")
    print(f"   VIX Rank:    {context_data.get('vix_rank')}")
    
    # Key indicators
    indicators = sig.get('indicators', {})
    print("\n📈 Key Indicators:")
    print(f"   ADX:  {indicators.get('adx', 0):.2f}")
    print(f"   RSI:  {indicators.get('rsi', 0):.2f}")
    print(f"   MACD: {indicators.get('macd', 0):.2f}")
    
    # Quality checks
    quality_checks = sig.get('quality_checks', {})
    print("\n✅ Quality Checks:")
    for check, passed in quality_checks.items():
        status = "✓" if passed else "✗"
        print(f"   {status} {check}")
    
    # Strike info if available
    if result.get('strike_meta'):
        print("\n🎯 Strike Selection:")
        meta = result['strike_meta']
        print(f"   ATM:    {meta.get('atm')}")
        print(f"   Offset: {meta.get('offset')}")
        print(f"   Width:  {meta.get('width')}")
    
    # What would make this trade?
    print("\n" + "=" * 80)
    print("WHAT'S NEEDED FOR TRADE APPROVAL?")
    print("=" * 80)
    
    current_quality = sig.get('quality_score', 0)
    current_conf = sig.get('confidence', 0)
    iv_regime = ctx.get('iv_regime', 'UNKNOWN')
    
    # Calculate threshold
    if iv_regime == "LOW":
        threshold = max(55, 75 - 10)
    elif iv_regime == "NORMAL":
        threshold = max(60, 75 - 5)
    else:
        threshold = 75
    
    print(f"\n✓ Quality Score: {current_quality}/8 (needs ≥4) {'PASS' if current_quality >= 4 else 'FAIL'}")
    print(f"✓ Confidence: {current_conf}% (needs ≥{threshold}% for {iv_regime} IV) {'PASS' if current_conf >= threshold else 'FAIL'}")
    print(f"✓ Clear Bias: {sig.get('bias')} {'PASS' if sig.get('bias') in ['BULLISH', 'BEARISH'] else 'FAIL'}")
    
    if result.get('approved'):
        print("\n🎉 TRADE APPROVED!")
        if result.get('ticket'):
            print("\nTicket would execute:")
            for leg in result['ticket']['legs']:
                print(f"   {leg['side']} {leg['type']} {leg['strike']}")
    else:
        print("\n⚠️ TRADE NOT APPROVED")
        print(f"\nReason: {result.get('reason')}")
        
        # Suggestions
        if current_quality < 4:
            print("\n💡 Improve quality by ensuring:")
            print("   - Fresh candle data (at least 100 bars)")
            print("   - Clear trend/momentum alignment")
        
        if current_conf < threshold:
            print(f"\n💡 Confidence needs to reach {threshold}%:")
            print("   - Wait for clearer market setup")
            print("   - Ensure indicators align (ADX>25, clear RSI/MACD)")

finally:
    db.close()

print("\n" + "=" * 80)
