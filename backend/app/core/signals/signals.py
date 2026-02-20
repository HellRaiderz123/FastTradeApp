"""
signals.py
-----------
Orchestrates signal generation from multiple sources:
1. TA engine (real indicators)
2. ML model (optional)
3. External data (India VIX, VIX Rank)
4. Asset-specific enrichers (stocks, options, futures, indices)

Merges them into a comprehensive market signal using the new multi-asset Signal architecture.
"""

from sqlalchemy.orm import Session
from typing import Dict, Optional, Union
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
from app.core.signals.base import (
    Signal,
    SignalFactory,
    SignalStrength,
    MarketBias,
    IVRegime,
    AssetType,
)
from app.core.signals.enrichers import (
    StockEnricher,
    OptionEnricher,
    FutureEnricher,
    IndexEnricher,
)

logger = logging.getLogger(__name__)


def _initialize_signal_factory():
    """Register asset-specific enrichers with the signal factory"""
    try:
        SignalFactory.register_enricher(AssetType.STOCK, StockEnricher())
        SignalFactory.register_enricher(AssetType.OPTION, OptionEnricher())
        SignalFactory.register_enricher(AssetType.FUTURE, FutureEnricher())
        SignalFactory.register_enricher(AssetType.INDEX, IndexEnricher())
        logger.info("✅ Signal enrichers registered successfully")
    except Exception as e:
        logger.warning(f"⚠️ Failed to register enrichers: {e}")


# Initialize on module import
_initialize_signal_factory()


def generate_signal_multi_asset(
    db: Session,
    symbol: str,
    asset_type: AssetType = AssetType.OPTION,
    use_ml: bool = False,
    india_vix: Optional[float] = None,
    vix_rank: Optional[float] = None,
    iv_regime: Optional[str] = None,
    ml_app_response: Optional[Dict] = None,
) -> Signal:
    """
    Generate signal for ANY asset type (stock, option, future, index).
    
    Returns: Signal object (multi-asset capable)
    
    Args:
        db: Database session
        symbol: Trading symbol
        asset_type: AssetType enum (STOCK, OPTION, FUTURE, INDEX)
        use_ml: Whether to use ML signals
        india_vix: Current India VIX (optional)
        vix_rank: VIX percentile (optional)
        iv_regime: IV regime (optional, will be determined if not provided)
        ml_app_response: ML model response dict (optional)
    """
    logger.info(f"🔍 Generating {asset_type.value} signal for {symbol}")
    
    # =====================================================
    # STEP 1: Generate base TA signal
    # =====================================================
    ta_sig = ta_signal_15m(db, symbol)
    
    # Convert old dict format to new Signal format
    signal_strength = _map_signal_strength(ta_sig.get("signal", "NO_TRADE"))
    bias = _map_market_bias(ta_sig.get("bias", "NEUTRAL"))
    
    # =====================================================
    # STEP 2: Fetch VIX data if missing
    # =====================================================
    if india_vix is None or vix_rank is None:
        try:
            vix_data = get_vix_iv_data_cached()
            if india_vix is None:
                india_vix = vix_data.get("india_vix")
            if vix_rank is None:
                vix_rank = vix_data.get("vix_rank")
            logger.info(f"   ✅ VIX data fetched: VIX={india_vix}, Rank={vix_rank}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to fetch VIX data: {e}")
    
    # =====================================================
    # STEP 3: Determine IV regime
    # =====================================================
    if iv_regime is None and india_vix is not None:
        iv_regime_str = determine_iv_regime(india_vix=india_vix, vix_rank=vix_rank)
        iv_regime = IVRegime(iv_regime_str) if iv_regime_str else IVRegime.NORMAL
    elif isinstance(iv_regime, str):
        iv_regime = IVRegime(iv_regime) if iv_regime in [e.value for e in IVRegime] else IVRegime.NORMAL
    else:
        iv_regime = IVRegime.NORMAL
    
    # =====================================================
    # STEP 4: Create base Signal using factory
    # =====================================================
    signal = SignalFactory.create_signal(
        asset_type=asset_type,
        symbol=symbol,
        signal_strength=signal_strength,
        confidence=ta_sig.get("confidence", 50),
        bias=bias,
        reasoning=ta_sig.get("reason", ""),
        indicators=ta_sig.get("indicators", {}),
        context={
            "india_vix": india_vix,
            "vix_rank": vix_rank,
            "iv_regime": iv_regime.value,
        },
        quality_checks=ta_sig.get("quality_checks", {}),
        quality_score=ta_sig.get("quality_score", 0),
        trade_readiness_score=ta_sig.get("trade_readiness_score", 0),
        iv_regime=iv_regime,
    )
    
    # =====================================================
    # STEP 5: ML Override (optional)
    # =====================================================
    if use_ml:
        try:
            ml = ml_signal(symbol)
            if ml.get("confidence", 0) > signal.confidence:
                signal.signal = _map_signal_strength(ml.get("signal", "NO_TRADE"))
                signal.confidence = ml.get("confidence", signal.confidence)
                signal.bias = _map_market_bias(ml.get("bias", signal.bias.value))
                logger.info(f"   🤖 ML signal applied: {signal.signal.value} (confidence: {signal.confidence})")
        except Exception as e:
            logger.warning(f"⚠️ ML signal failed: {e}")
    
    elif ml_app_response:
        try:
            ml = parse_ml_app_response(ml_app_response)
            if ml.get("confidence", 0) > signal.confidence:
                signal.signal = _map_signal_strength(ml.get("signal", "NO_TRADE"))
                signal.confidence = ml.get("confidence", signal.confidence)
                signal.bias = _map_market_bias(ml.get("bias", signal.bias.value))
                logger.info(f"   🤖 ML app response applied: {signal.signal.value}")
        except Exception as e:
            logger.warning(f"⚠️ ML app response parsing failed: {e}")
    
    logger.info(f"✅ Signal generated: {signal.signal.value} (confidence: {signal.confidence}%, quality: {signal.quality_score})")
    return signal


def _map_signal_strength(signal_str: str) -> SignalStrength:
    """Map string signal to SignalStrength enum.
    
    Handles both canonical (BUY/SELL) and TA engine (BULLISH/BEARISH/RANGE) formats.
    """
    mapping = {
        "BUY": SignalStrength.BUY,
        "SELL": SignalStrength.SELL,
        "HOLD": SignalStrength.HOLD,
        "NO_TRADE": SignalStrength.NO_TRADE,
        # TA engine returns these — map them correctly
        "BULLISH": SignalStrength.BUY,
        "BEARISH": SignalStrength.SELL,
        "RANGE": SignalStrength.HOLD,
    }
    return mapping.get(signal_str, SignalStrength.NO_TRADE)


def _map_market_bias(bias_str: str) -> MarketBias:
    """Map string bias to MarketBias enum"""
    mapping = {
        "BULLISH": MarketBias.BULLISH,
        "BEARISH": MarketBias.BEARISH,
        "NEUTRAL": MarketBias.NEUTRAL,
    }
    return mapping.get(bias_str, MarketBias.NEUTRAL)


def generate_signal_from_candles(
    candles: list[dict],
    india_vix: Optional[float] = 15.0,
    vix_rank: Optional[float] = 50.0,
    iv_regime: Optional[str] = "NORMAL",
) -> Dict:
    """DB-free signal generation for backtests.

    Uses in-memory candles instead of querying the database.
    ~100x faster than generate_signal() because it skips:
    - DB writes (save candles)
    - DB reads (query 300 candles back)
    - VIX API calls (uses provided values)
    """
    from app.core.signals.ta_engine import ta_signal_15m_from_candles

    ta_sig = ta_signal_15m_from_candles(candles)

    # Determine IV regime if not provided
    if iv_regime is None and india_vix is not None:
        iv_regime = determine_iv_regime(india_vix=india_vix, vix_rank=vix_rank)
    if iv_regime is None:
        iv_regime = "NORMAL"

    ta_sig = enrich_signal_with_iv(
        ta_sig,
        india_vix=india_vix,
        vix_rank=vix_rank,
        iv_regime=iv_regime,
    )
    ta_sig.setdefault("context", {})
    ta_sig["context"].update({
        "india_vix": india_vix,
        "vix_rank": vix_rank,
        "iv_regime": iv_regime,
    })
    return ta_sig


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

def signal_to_dict(signal: Signal) -> Dict:
    """
    Convert Signal object to dict format for backward compatibility.
    
    Useful for APIs and systems expecting the old dict-based signal format.
    """
    return {
        "asset_type": signal.asset_type.value,
        "symbol": signal.symbol,
        "timestamp": signal.timestamp.isoformat(),
        "signal": signal.signal.value,
        "confidence": signal.confidence,
        "bias": signal.bias.value,
        "reasoning": signal.reasoning,
        "iv_regime": signal.iv_regime.value if signal.iv_regime else None,
        "india_vix": signal.india_vix,
        "vix_rank": signal.vix_rank,
        "indicators": signal.indicators,
        "context": signal.context,
        "quality_checks": signal.quality_checks,
        "quality_score": signal.quality_score,
        "trade_readiness_score": signal.trade_readiness_score,
    }


def dict_to_signal(data: Dict) -> Signal:
    """
    Convert dict to Signal object for systems using old dict format.
    """
    asset_type_str = data.get("asset_type", "OPTION")
    asset_type = AssetType(asset_type_str) if asset_type_str in [e.value for e in AssetType] else AssetType.OPTION
    
    signal_str = data.get("signal", "NO_TRADE")
    signal_strength = _map_signal_strength(signal_str)
    
    bias_str = data.get("bias", "NEUTRAL")
    market_bias = _map_market_bias(bias_str)
    
    iv_regime_str = data.get("iv_regime", "NORMAL")
    iv_regime = IVRegime(iv_regime_str) if iv_regime_str in [e.value for e in IVRegime] else IVRegime.NORMAL
    
    return Signal(
        asset_type=asset_type,
        symbol=data.get("symbol", ""),
        timestamp=data.get("timestamp", __import__("datetime").datetime.utcnow()),
        signal=signal_strength,
        confidence=data.get("confidence", 50),
        bias=market_bias,
        reasoning=data.get("reasoning", ""),
        iv_regime=iv_regime,
        india_vix=data.get("india_vix"),
        vix_rank=data.get("vix_rank"),
        indicators=data.get("indicators", {}),
        context=data.get("context", {}),
        quality_checks=data.get("quality_checks", {}),
        quality_score=data.get("quality_score", 0),
        trade_readiness_score=data.get("trade_readiness_score", 0),
    )