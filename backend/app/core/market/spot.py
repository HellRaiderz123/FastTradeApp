import logging
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

def get_spot(underlying: str) -> float:
    """
    Get live spot price from Zerodha.
    Falls back to latest candle close if API unavailable.
    """
    try:
        kite = get_kite_client()
        token = get_index_token(underlying)
        data = kite.ltp([token])
        spot = data[token]["last_price"]
        logger.info(f"✅ Got live spot from Zerodha: {underlying} = {spot}")
        return spot
    except Exception as e:
        logger.warning(f"⚠️  Zerodha API failed ({e}), falling back to latest candle")
        # Fallback: use latest candle close price
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
