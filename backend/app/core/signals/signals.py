"""
signals.py
-----------
Orchestrates signal generation from multiple sources:
1. TA engine (real indicators)
2. ML model (optional)
3. External data (India VIX, VIX Rank)

Merges them into a comprehensive market signal.
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
    vix_rank: Optional[float] = None,     # 🔧 renamed (was iv_rank)
    india_vix: Optional[float] = None,
    iv_regime: Optional[str] = None,
    ml_app_response: Optional[Dict] = None,
) -> Dict:
    """
    COMPREHENSIVE signal generation.

    Returns:
        {
            signal, confidence, bias,
            iv_regime, india_vix, vix_rank,
            quality_checks, quality_score,
            trade_readiness_score,
            indicators: {...}
        }
    """

    # =====================================================
    # STEP 1: TA Signal
    # =====================================================
    ta_sig = ta_signal_15m(db, symbol)

    # =====================================================
    # STEP 2: Fetch VIX data if missing
    # =====================================================
    if india_vix is None or vix_rank is None:
        logger.info("📊 Fetching live VIX data from APIs...")

        try:
            vix_data = get_vix_iv_data_cached()

            if india_vix is None:
                india_vix = vix_data.get("india_vix")
                logger.info(
                    f"   ✅ India VIX: {india_vix} "
                    f"(from {vix_data.get('vix_source')})"
                )

            if vix_rank is None:
                vix_rank = vix_data.get("vix_rank")
                logger.info(
                    f"   ✅ VIX Rank: {vix_rank} "
                    f"(from {vix_data.get('vix_rank_source')})"
                )

        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch VIX data: {e}")

    # =====================================================
    # STEP 3: Determine IV regime (ALWAYS if missing)
    # =====================================================
    if iv_regime is None and india_vix is not None:
        iv_regime = determine_iv_regime(
            india_vix=india_vix,
            vix_rank=vix_rank,
        )
        logger.info(f"   🧠 IV Regime determined: {iv_regime}")

    # Absolute safety fallback (never return null)
    if iv_regime is None:
        iv_regime = "NORMAL"
        logger.warning("⚠️ IV regime unresolved — defaulting to NORMAL")

    # =====================================================
    # STEP 4: Enrich TA signal with VIX context
    # =====================================================
    ta_sig = enrich_signal_with_iv(
        ta_sig,
        india_vix=india_vix,
        vix_rank=vix_rank,
        iv_regime=iv_regime,
    )

    # =====================================================
    # STEP 5: ML Override (optional)
    # =====================================================
    final_sig = ta_sig

    if use_ml:
        ml = ml_signal(symbol)
        if ml.get("confidence", 0) > ta_sig.get("confidence", 0):
            final_sig = merge_signals(ta_sig, ml_signal=ml)

    elif ml_app_response:
        ml = parse_ml_app_response(ml_app_response)
        if ml.get("confidence", 0) > ta_sig.get("confidence", 0):
            final_sig = merge_signals(ta_sig, ml_signal=ml)

    # =====================================================
    # STEP 6: Ensure IV fields are present in response
    # =====================================================
    final_sig.setdefault("context", {})
    final_sig["context"].update({
        "india_vix": india_vix,
        "vix_rank": vix_rank,
        "iv_regime": iv_regime,
    })

    return final_sig
