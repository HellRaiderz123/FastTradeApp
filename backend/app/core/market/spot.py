import logging
from app.core.market.provider import fetch_spot as _provider_fetch_spot
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

def get_spot(underlying: str) -> float:
    """
    Get live spot price via the active market data provider.
    Falls back to latest candle close if API unavailable.
    """
    try:
        price = _provider_fetch_spot(underlying)
        if price and price > 0:
            logger.info("Got live spot for %s = %s", underlying, price)
            return price
    except Exception as e:
        logger.warning("Provider spot fetch failed (%s), falling back to candle: %s", underlying, e)
    return get_spot_fallback(underlying)

def get_spot_fallback(underlying: str) -> float:
    """Get spot from latest 15m candle as fallback"""
    db = SessionLocal()
    try:
        latest = (
            db.query(Candle15m)
            .filter(Candle15m.symbol == underlying.upper())
            .order_by(Candle15m.timestamp.desc())
            .first()
        )
        
        if latest:
            logger.info(f"✅ Using latest candle close as spot: {underlying} = {latest.close}")
            return latest.close
        else:
            logger.error(f"❌ No candle data found for {underlying}")
            raise RuntimeError(f"No spot data available for {underlying}")
    finally:
        db.close()
