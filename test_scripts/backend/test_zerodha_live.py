"""
Test Zerodha APIs with real credentials
"""
import os
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load credentials
zerodha_key = os.getenv("ZERODHA_API_KEY")
zerodha_token = os.getenv("ZERODHA_ACCESS_TOKEN")

if not zerodha_key or not zerodha_token:
    logger.error("❌ Zerodha credentials not found in environment")
    sys.exit(1)

logger.info(f"✅ Credentials loaded: API Key={zerodha_key[:8]}...., Token={zerodha_token[:8]}...")

# Test 1: Spot price
logger.info("\n=== TEST 1: SPOT PRICE ===")
try:
    from app.services.market_data import get_spot
    spot = get_spot("NIFTY")
    logger.info(f"✅ NIFTY Spot: {spot}")
except Exception as e:
    logger.error(f"❌ Error getting spot: {e}")

# Test 2: Option chain
logger.info("\n=== TEST 2: OPTION CHAIN ===")
try:
    from app.services.market_data import get_option_chain
    chain = get_option_chain("NIFTY")
    logger.info(f"✅ Got {len(chain)} option strikes from Zerodha")
    if not chain.empty:
        logger.info(f"   Sample: {chain.head(3).to_dict('records')}")
except Exception as e:
    logger.error(f"❌ Error getting option chain: {e}")

# Test 3: Enrich with LTP
logger.info("\n=== TEST 3: OPTION LTP ENRICHMENT ===")
try:
    from app.services.market_data import get_option_chain, enrich_chain_with_live_oi
    chain = get_option_chain("NIFTY")
    if not chain.empty:
        chain = enrich_chain_with_live_oi(chain)
        logger.info(f"✅ Enriched chain with LTP")
        logger.info(f"   Sample with LTP:")
        for idx, row in chain.head(3).iterrows():
            logger.info(f"   {row['tradingsymbol']}: LTP={row.get('ltp', 0)}")
except Exception as e:
    logger.error(f"❌ Error enriching chain: {e}")

# Test 4: Run full signal engine
logger.info("\n=== TEST 4: FULL SIGNAL ENGINE ===")
try:
    from app.core.signals.signals import generate_signal
    from app.db.session import SessionLocal
    
    db = SessionLocal()
    try:
        signal = generate_signal(db=db, symbol="NIFTY")
        
        if signal is None:
            logger.error("❌ Signal is None!")
        else:
            logger.info(f"✅ Signal generated!")
            logger.info(f"   Signal type: {signal}")
            logger.info(f"   Keys: {signal.keys() if isinstance(signal, dict) else 'Not a dict'}")
            if isinstance(signal, dict):
                logger.info(f"   Strategy/Signal: {signal.get('signal')}")
                logger.info(f"   Confidence: {signal.get('confidence')}")
                logger.info(f"   Indicators: {signal.get('indicators')}")
    finally:
        db.close()
except Exception as e:
    logger.error(f"❌ Error running signal engine: {e}")
    import traceback
    traceback.print_exc()

logger.info("\n✅ ALL TESTS COMPLETE")
