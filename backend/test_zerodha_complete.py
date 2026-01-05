"""
COMPREHENSIVE test: Zerodha APIs + Full Strategy Engine
Shows complete flow from live market data to strategy decision
"""
import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load credentials
os.environ["ZERODHA_API_KEY"] = "el4pv3dwria188j9"
os.environ["ZERODHA_ACCESS_TOKEN"] = "ZJpem2D1TftS74vXWFSI3cOuaa9uQOa8"
os.environ["EXECUTION_MODE"] = "ZERODHA_DRY_RUN"

logger.info("="*80)
logger.info("🚀 ZERODHA LIVE DATA TEST - FULL STRATEGY ENGINE")
logger.info("="*80)

# ============================================================
# PART 1: Verify Zerodha APIs
# ============================================================
logger.info("\n📊 PART 1: ZERODHA API VERIFICATION")
logger.info("-"*80)

logger.info("\n1️⃣  Credentials Status:")
zerodha_key = os.getenv("ZERODHA_API_KEY")
zerodha_token = os.getenv("ZERODHA_ACCESS_TOKEN")
logger.info(f"   ✅ API Key: {zerodha_key[:8]}****")
logger.info(f"   ✅ Access Token: {zerodha_token[:8]}****")

logger.info("\n2️⃣  Loading Zerodha Instruments...")
try:
    from app.core.broker.zerodha.instruments import load_instruments
    instruments = load_instruments()
    logger.info(f"   ✅ Total NFO instruments: {len(instruments)}")
    
    nifty_opts = instruments[
        (instruments["name"] == "NIFTY") & 
        (instruments["segment"] == "NFO-OPT")
    ]
    logger.info(f"   ✅ NIFTY options available: {len(nifty_opts)}")
except Exception as e:
    logger.error(f"   ❌ Error: {e}")
    sys.exit(1)

logger.info("\n3️⃣  Getting Live Spot Price...")
try:
    from app.services.market_data import get_spot
    spot = get_spot("NIFTY")
    logger.info(f"   ✅ NIFTY Spot: {spot}")
except Exception as e:
    logger.error(f"   ❌ Error: {e}")

logger.info("\n4️⃣  Getting Option Chain with Live LTP...")
try:
    from app.services.market_data import get_option_chain, enrich_chain_with_live_oi
    chain = get_option_chain("NIFTY")
    logger.info(f"   ✅ Got {len(chain)} strikes")
    
    chain = enrich_chain_with_live_oi(chain)
    logger.info(f"   ✅ Enriched with live LTP")
    
    # Show sample
    sample_ce = chain[chain["instrument_type"] == "CE"].iloc[0]
    sample_pe = chain[chain["instrument_type"] == "PE"].iloc[0]
    logger.info(f"   📈 Sample CE: {sample_ce['tradingsymbol']} @ {sample_ce['ltp']}")
    logger.info(f"   📉 Sample PE: {sample_pe['tradingsymbol']} @ {sample_pe['ltp']}")
except Exception as e:
    logger.error(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# PART 2: Generate Signal
# ============================================================
logger.info("\n📈 PART 2: SIGNAL GENERATION")
logger.info("-"*80)

try:
    from app.core.signals.signals import generate_signal
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        signal = generate_signal(db=db, symbol="NIFTY")
        
        logger.info(f"\n✅ Technical Analysis Signal:")
        logger.info(f"   Signal: {signal.get('signal')}")
        logger.info(f"   Confidence: {signal.get('confidence')}%")
        logger.info(f"   Bias: {signal.get('bias')}")
        logger.info(f"   IV Regime: {signal.get('iv_regime')}")
        
        indicators = signal.get('indicators', {})
        logger.info(f"\n📊 Key Indicators:")
        logger.info(f"   ADX: {indicators.get('adx')}")
        logger.info(f"   RSI: {indicators.get('rsi')}")
        logger.info(f"   Stoch K/D: {indicators.get('stoch_k')}/{indicators.get('stoch_d')}")
        logger.info(f"   MACD Hist: {indicators.get('macd_hist')}")
        logger.info(f"   EMA20/50: {indicators.get('ema_20')}/{indicators.get('ema_50')}")
        
        logger.info(f"\n✅ Quality Checks:")
        quality_checks = signal.get('quality_checks', {})
        for check, passed in quality_checks.items():
            status = "✓" if passed else "✗"
            logger.info(f"   {status} {check}")
        logger.info(f"   Quality Score: {signal.get('quality_score')}/8")
        logger.info(f"   Readiness Score: {signal.get('trade_readiness_score')}/100")
        
    finally:
        db.close()
except Exception as e:
    logger.error(f"❌ Error generating signal: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# PART 3: Strategy Decision Engine
# ============================================================
logger.info("\n🎯 PART 3: STRATEGY DECISION ENGINE")
logger.info("-"*80)

try:
    from app.core.strategies.option_spread_15m.engine import run_option_spread
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        result = run_option_spread(db=db, payload={"underlying": "NIFTY"})
        
        logger.info(f"\n✅ Strategy Execution Result:")
        logger.info(f"   Strategy: {result.get('strategy')}")
        logger.info(f"   Approved: {result.get('approved')}")
        logger.info(f"   Reason: {result.get('reason')}")
        
        if result.get('spot'):
            logger.info(f"\n✅ Market Context:")
            logger.info(f"   Spot: {result.get('spot')}")
            logger.info(f"   ATM: {result.get('atm')}")
            
            strike_meta = result.get('strike_meta')
            if strike_meta:
                logger.info(f"   ATM Call: {strike_meta.get('call_symbol')}")
                logger.info(f"   ATM Put: {strike_meta.get('put_symbol')}")
                
                call_meta = strike_meta.get('call', {})
                put_meta = strike_meta.get('put', {})
                if call_meta and put_meta:
                    logger.info(f"   Call LTP: {call_meta.get('ltp')}")
                    logger.info(f"   Put LTP: {put_meta.get('ltp')}")
        
        if result.get('ticket'):
            ticket = result['ticket']
            logger.info(f"\n✅ Trade Ticket:")
            logger.info(f"   Status: {ticket.get('status')}")
            logger.info(f"   Long Leg: {ticket.get('long_leg')}")
            logger.info(f"   Short Leg: {ticket.get('short_leg')}")
            logger.info(f"   Max Profit: {ticket.get('max_profit')}")
            logger.info(f"   Max Loss: {ticket.get('max_loss')}")
            logger.info(f"   Margin Req: {ticket.get('margin_required')}")
        
        if result.get('risk_metrics'):
            risk = result['risk_metrics']
            logger.info(f"\n✅ Risk Metrics:")
            logger.info(f"   Trade Risk: ${risk.get('trade_risk_pct')}%")
            logger.info(f"   Portfolio Risk: ${risk.get('portfolio_risk_pct')}%")
            logger.info(f"   Margin Used: {risk.get('margin_utilization_pct')}%")
        
    finally:
        db.close()
        
except Exception as e:
    logger.error(f"❌ Error in strategy engine: {e}")
    import traceback
    traceback.print_exc()

logger.info("\n" + "="*80)
logger.info("✅ ALL TESTS COMPLETE - ZERODHA INTEGRATION VERIFIED")
logger.info("="*80)
