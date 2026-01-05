"""
signals.py
-----------
Orchestrates signal generation from multiple sources:
1. TA engine (real indicators)
2. ML model (optional)
3. External data (IV, VIX APIs)

Merges them into comprehensive market signal.
"""

from sqlalchemy.orm import Session
from typing import Dict, Optional
import logging

from app.core.signals.ta_engine import ta_signal_15m
from app.core.signals.ml_engine import ml_signal
from app.core.signals.signal_enricher import (
    enrich_signal_with_iv,
    merge_signals,
    parse_ml_app_response,
)
from app.core.market.vix_iv_api import (
    get_vix_iv_data_cached,
    determine_iv_regime,
)

logger = logging.getLogger(__name__)


def generate_signal(
    db: Session,
    symbol: str,
    use_ml: bool = False,
    iv_rank: Optional[float] = None,
    india_vix: Optional[float] = None,
    iv_regime: Optional[str] = None,
    ml_app_response: Optional[Dict] = None,
) -> Dict:
    """
    COMPREHENSIVE signal generation.
    
    Args:
        db: Database session
        symbol: NIFTY, BANKNIFTY, etc.
        use_ml: Enable ML model
        iv_rank: IV Rank (0-100) from external API
        india_vix: India VIX value from external API
        iv_regime: Force IV regime (LOW/NORMAL/HIGH)
        ml_app_response: Response from external ML app
    
    Returns:
        Comprehensive signal with all data:
        {
            signal, confidence, bias, iv_regime,
            quality_checks, quality_score, trade_readiness_score,
            indicators: {adx, rsi, macd, stoch, vix, iv_rank, ...},
            trend_score
        }
    """
    
    # ================================================
    # STEP 1: TA Signal from candles
    # ================================================
    ta_sig = ta_signal_15m(db, symbol)
    
    # ================================================
    # STEP 2: Fetch VIX/IV data if not provided
    # ================================================
    # If caller didn't provide VIX/IV, fetch from APIs
    if not iv_rank or not india_vix:
        logger.info("📊 Fetching live VIX/IV data from APIs...")
        try:
            vix_iv_data = get_vix_iv_data_cached()
            
            if not iv_rank:
                iv_rank = vix_iv_data.get("iv_rank")
                logger.info(f"   ✅ IV Rank: {iv_rank} (from {vix_iv_data.get('iv_source')})")
            
            if not india_vix:
                india_vix = vix_iv_data.get("india_vix")
                logger.info(f"   ✅ India VIX: {india_vix} (from {vix_iv_data.get('vix_source')})")
        
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch VIX/IV data: {e} - using defaults")
    
    # ================================================
    # STEP 3: Determine IV regime if not provided
    # ================================================
    if not iv_regime and iv_rank is not None and india_vix is not None:
        iv_regime = determine_iv_regime(india_vix, iv_rank)
        logger.info(f"   ✅ IV Regime: {iv_regime}")
    
    # ================================================
    # STEP 4: Enrich with external IV/VIX data
    # ================================================
    if iv_rank or india_vix or iv_regime:
        ta_sig = enrich_signal_with_iv(
            ta_sig,
            iv_rank=iv_rank,
            india_vix=india_vix,
            iv_regime=iv_regime,
        )
    
    # ================================================
    # STEP 5: ML Model (optional override)
    # ================================================
    final_sig = ta_sig
    
    if use_ml:
        # Option A: Use internal ML (placeholder)
        ml = ml_signal(symbol)
        if ml.get("confidence", 0) > ta_sig.get("confidence", 0):
            final_sig = merge_signals(ta_sig, ml_signal=ml)
    
    elif ml_app_response:
        # Option B: Use external ML app response
        ml = parse_ml_app_response(ml_app_response)
        if ml.get("confidence", 0) > ta_sig.get("confidence", 0):
            final_sig = merge_signals(ta_sig, ml_signal=ml)
    
    return final_sig
