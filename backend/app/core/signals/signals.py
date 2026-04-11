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

from datetime import datetime, time as dt_time

from sqlalchemy.orm import Session
from typing import Dict, Optional, Union
import logging
import pandas as pd

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
from app.core.market.expiry import get_weekly_expiry_for_date
from app.core.indicators.greeks import GreeksCalculator
from app.core.indicators.put_call_ratio import OptionChainAnalysis
from app.core.utils.time import now_ist
from app.services.market_data import enrich_chain_with_live_oi, get_option_chain, get_spot
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

_OPTION_CHAIN_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_option_chain_analytics(chain_df: pd.DataFrame, spot: float) -> Dict:
    """Build lightweight option-chain analytics from the live chain dataframe."""
    if chain_df is None or getattr(chain_df, "empty", True):
        return {}

    try:
        df = chain_df.copy()
        df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
        df["oi"] = pd.to_numeric(df["oi"], errors="coerce") if "oi" in df.columns else 0.0
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce") if "volume" in df.columns else 0.0
        df["oi"] = df["oi"].fillna(0.0)
        df["volume"] = df["volume"].fillna(0.0)

        df = df[df["instrument_type"].isin(["CE", "PE"]) & df["strike"].notna()]
        if df.empty or float(df["oi"].sum()) <= 0:
            return {}

        grouped = (
            df.groupby(["strike", "instrument_type"], as_index=False)[["oi", "volume"]]
            .sum()
            .sort_values("strike")
        )

        chain_payload = {"data": []}
        for strike, strike_df in grouped.groupby("strike"):
            call_row = strike_df[strike_df["instrument_type"] == "CE"]
            put_row = strike_df[strike_df["instrument_type"] == "PE"]
            chain_payload["data"].append(
                {
                    "strike": float(strike),
                    "call_oi": _safe_float(call_row["oi"].iloc[0]) if not call_row.empty else 0.0,
                    "put_oi": _safe_float(put_row["oi"].iloc[0]) if not put_row.empty else 0.0,
                }
            )

        analyzer = OptionChainAnalysis()
        analytics = analyzer.analyze_chain(chain_payload, spot)
        sentiment = analyzer.get_sentiment_score(
            pcr=_safe_float(analytics.get("pcr")),
            spot=spot,
            support=_safe_float(analytics.get("support_level")),
            resistance=_safe_float(analytics.get("resistance_level")),
        )
        analytics.update(sentiment)
        return analytics
    except Exception as e:
        logger.warning("⚠️ Option chain analytics build failed: %s", e)
        return {}


def _estimate_contract_volatility(iv_regime: str, moneyness: float, days_to_expiry: int) -> float:
    """Estimate a reasonable IV input for delta approximation when live Greeks are absent."""
    base_iv = {
        "LOW": 0.15,
        "NORMAL": 0.19,
        "HIGH": 0.26,
    }.get(str(iv_regime or "NORMAL").upper(), 0.19)

    skew = min(abs(float(moneyness) - 1.0) * 0.8, 0.12)
    front_week_boost = 0.04 if days_to_expiry <= 2 else 0.0
    return max(0.10, min(0.65, base_iv + skew + front_week_boost))


def _target_delta_for_entry(days_to_expiry: int, confidence: float) -> float:
    """Prefer higher-delta contracts for weekly long buys to reduce theta bleed."""
    if days_to_expiry <= 1:
        return 0.55
    if confidence >= 85:
        return 0.50
    if confidence >= 80:
        return 0.45
    return 0.40


def _select_direct_option_contract(
    chain_df: Optional[pd.DataFrame],
    *,
    spot: float,
    expiry_date,
    option_type: str,
    iv_regime: str,
    confidence: float,
    asof_dt: datetime,
) -> Optional[Dict]:
    """Pick a liquid weekly option contract near a target delta for direct CE/PE buying."""
    if chain_df is None or getattr(chain_df, "empty", True) or spot <= 0:
        return None

    df = chain_df.copy()
    for col in ["strike", "oi", "volume", "bid", "ask", "ltp"]:
        if col not in df.columns:
            df[col] = 0.0
    if "instrument_type" not in df.columns:
        df["instrument_type"] = ""

    df["instrument_type"] = df["instrument_type"].astype(str).str.upper()
    df = df[df["instrument_type"] == str(option_type or "").upper()].copy()
    if df.empty:
        return None

    df["strike"] = pd.to_numeric(df["strike"], errors="coerce")
    for col in ["oi", "volume", "bid", "ask", "ltp"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    df = df[df["strike"].notna()]
    if df.empty:
        return None

    days_to_expiry = max((expiry_date - asof_dt.date()).days, 0)
    target_delta = _target_delta_for_entry(days_to_expiry, confidence)
    min_oi = 500.0 if days_to_expiry <= 1 else 1500.0
    min_volume = 100.0 if days_to_expiry <= 1 else 1000.0
    max_spread_pct = 2.5 if days_to_expiry <= 1 else 2.0

    candidates = []
    for _, row in df.iterrows():
        strike = _safe_float(row.get("strike"), default=0.0)
        if strike <= 0:
            continue

        bid = _safe_float(row.get("bid"), default=0.0)
        ask = _safe_float(row.get("ask"), default=0.0)
        ltp = _safe_float(row.get("ltp"), default=0.0)
        mid = (bid + ask) / 2 if bid > 0 and ask > 0 else ltp
        spread_pct = ((ask - bid) / mid * 100.0) if bid > 0 and ask > 0 and mid > 0 else 999.0

        moneyness = strike / max(spot, 1.0)
        est_vol = _estimate_contract_volatility(iv_regime, moneyness, days_to_expiry)
        greeks = GreeksCalculator(
            spot=spot,
            strike=strike,
            expiry=expiry_date,
            volatility=est_vol,
            option_type=option_type,
        ).calculate_all()
        approx_delta = abs(_safe_float(greeks.get("delta"), default=0.0))

        oi = _safe_float(row.get("oi"), default=0.0)
        volume = _safe_float(row.get("volume"), default=0.0)
        spread_ok = spread_pct <= max_spread_pct
        delta_ok = 0.25 <= approx_delta <= 0.70
        liquidity_ok = oi >= min_oi and volume >= min_volume and spread_ok and delta_ok

        score = (
            abs(approx_delta - target_delta) * 100.0
            + spread_pct * 2.5
            + (0.0 if liquidity_ok else 25.0)
            + (0.0 if ltp >= 30 else 8.0)
        )

        candidates.append(
            {
                "tradingsymbol": str(row.get("tradingsymbol") or ""),
                "strike": int(round(strike)),
                "option_type": option_type,
                "ltp": round(ltp or mid, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "spread_pct": round(spread_pct, 2),
                "oi": int(round(oi)),
                "volume": int(round(volume)),
                "approx_delta": round(approx_delta, 4),
                "target_delta": round(target_delta, 4),
                "delta_ok": delta_ok,
                "spread_ok": spread_ok,
                "liquidity_ok": liquidity_ok,
                "score": round(score, 4),
            }
        )

    if not candidates:
        return None

    liquid_candidates = [c for c in candidates if c["liquidity_ok"]]
    ranked = liquid_candidates or candidates
    return min(ranked, key=lambda row: row["score"])


def _apply_option_context_to_signal(signal: Dict, analytics: Dict) -> Dict:
    """Adjust directional signal using option-chain OI/PCR confirmation."""
    if not analytics:
        return signal

    enriched = signal.copy()
    indicators = (enriched.get("indicators") or {}).copy()
    quality_checks = (enriched.get("quality_checks") or {}).copy()
    existing_ctx = enriched.get("context")
    context = existing_ctx.copy() if isinstance(existing_ctx, dict) else {}

    pcr = analytics.get("pcr")
    support = analytics.get("support_level")
    resistance = analytics.get("resistance_level")
    spot = analytics.get("spot_price")
    sentiment = str(analytics.get("sentiment") or "Neutral")
    total_score = int(_safe_float(analytics.get("total_score")))

    indicators.update({
        "option_pcr": round(_safe_float(pcr), 4) if pcr is not None else None,
        "oi_support": support,
        "oi_resistance": resistance,
        "oi_sentiment_score": total_score,
    })
    context["option_chain"] = {
        "pcr": pcr,
        "support": support,
        "resistance": resistance,
        "sentiment": sentiment,
        "sentiment_score": total_score,
    }

    bias = str(enriched.get("bias") or "NEUTRAL").upper()
    confidence = _safe_float(enriched.get("confidence"))
    confirm = True
    adjustment = 0

    near_support = bool(support and spot and support > 0 and abs(spot - support) / support <= 0.0035)
    near_resistance = bool(resistance and spot and resistance > 0 and abs(resistance - spot) / resistance <= 0.0035)

    if bias == "BULLISH":
        if sentiment == "Bullish":
            adjustment += 4
        elif sentiment == "Bearish":
            adjustment -= 8
            confirm = False
        if near_resistance:
            adjustment -= 5
            confirm = False
    elif bias == "BEARISH":
        if sentiment == "Bearish":
            adjustment += 4
        elif sentiment == "Bullish":
            adjustment -= 8
            confirm = False
        if near_support:
            adjustment -= 5
            confirm = False

    quality_checks["oi_data_ok"] = True
    quality_checks["oi_bias_confirm"] = confirm

    if adjustment > 0:
        enriched["reason"] = f"{enriched.get('reason', '')} | OI/PCR confirmation".strip()
    elif adjustment < 0:
        enriched["reason"] = f"{enriched.get('reason', '')} | OI/PCR conflict".strip()

    enriched["confidence"] = max(0.0, min(100.0, confidence + adjustment))
    enriched["indicators"] = indicators
    enriched["quality_checks"] = quality_checks
    enriched["quality_score"] = sum(1 for v in quality_checks.values() if v)
    enriched["context"] = context
    return enriched


def _enrich_signal_with_option_context(signal: Dict, symbol: str) -> Dict:
    """Add live option-chain confirmation for index underlyings used in options trading."""
    normalized = str(symbol or "").upper().strip()
    if normalized not in _OPTION_CHAIN_UNDERLYINGS:
        return signal

    try:
        diagnostics = signal.get("diagnostics") if isinstance(signal.get("diagnostics"), dict) else {}
        spot = _safe_float(diagnostics.get("last_close"), default=0.0)
        if spot <= 0:
            spot = _safe_float(get_spot(normalized), default=0.0)
        if spot <= 0:
            return signal

        chain = get_option_chain(normalized)
        chain = enrich_chain_with_live_oi(chain)
        analytics = _build_option_chain_analytics(chain, spot)
        if not analytics:
            return signal

        analytics.setdefault("spot_price", spot)
        return _apply_option_context_to_signal(signal, analytics)
    except Exception as e:
        logger.warning("⚠️ Failed to enrich signal with option chain context for %s: %s", normalized, e)
        return signal


def _apply_weekly_option_entry_filter(
    signal: Dict,
    symbol: str,
    *,
    asof_dt: Optional[datetime] = None,
    chain_df: Optional[pd.DataFrame] = None,
    spot: Optional[float] = None,
) -> Dict:
    """Gate direct CE/PE entries using weekly-expiry timing, liquidity, and IV-risk quality."""
    normalized = str(symbol or "").upper().strip()
    if normalized not in _OPTION_CHAIN_UNDERLYINGS:
        return signal

    enriched = signal.copy()
    indicators = (enriched.get("indicators") or {}).copy()
    quality_checks = (enriched.get("quality_checks") or {}).copy()
    existing_ctx = enriched.get("context")
    context = existing_ctx.copy() if isinstance(existing_ctx, dict) else {}

    asof_dt = asof_dt or now_ist()
    current_time = dt_time(asof_dt.hour, asof_dt.minute, asof_dt.second)

    try:
        expiry_date = get_weekly_expiry_for_date(normalized, asof_dt.date())
    except Exception:
        expiry_date = asof_dt.date()

    days_to_expiry = max((expiry_date - asof_dt.date()).days, 0)
    is_expiry_day = days_to_expiry == 0

    bias = str(enriched.get("bias") or "NEUTRAL").upper()
    confidence = _safe_float(enriched.get("confidence"), default=0.0)
    readiness = int(_safe_float(enriched.get("trade_readiness_score"), default=0.0))
    quality_score = int(enriched.get("quality_score", 0) or 0)
    adx = _safe_float(indicators.get("adx"), default=0.0)
    rsi = _safe_float(indicators.get("rsi"), default=50.0)
    iv_regime = str(enriched.get("iv_regime") or context.get("iv_regime") or "NORMAL").upper()
    vix_rank = _safe_float(context.get("vix_rank"), default=0.0)
    oi_confirm = bool(quality_checks.get("oi_bias_confirm", True))

    effective_spot = _safe_float(spot, default=0.0)
    if effective_spot <= 0:
        diagnostics = enriched.get("diagnostics") if isinstance(enriched.get("diagnostics"), dict) else {}
        effective_spot = _safe_float(diagnostics.get("last_close"), default=0.0)
    if effective_spot <= 0:
        effective_spot = _safe_float(get_spot(normalized), default=0.0)

    selected_contract = None
    liquidity_ok = True
    spread_ok = True
    delta_contract_ok = True

    if bias in {"BULLISH", "BEARISH"}:
        option_type = "CE" if bias == "BULLISH" else "PE"
        if chain_df is None:
            chain_df = enrich_chain_with_live_oi(get_option_chain(normalized))
        selected_contract = _select_direct_option_contract(
            chain_df,
            spot=effective_spot,
            expiry_date=expiry_date,
            option_type=option_type,
            iv_regime=iv_regime,
            confidence=confidence,
            asof_dt=asof_dt,
        )
        if selected_contract:
            liquidity_ok = bool(selected_contract.get("liquidity_ok"))
            spread_ok = bool(selected_contract.get("spread_ok"))
            delta_contract_ok = bool(selected_contract.get("delta_ok"))
        else:
            liquidity_ok = False
            spread_ok = False
            delta_contract_ok = False

    entry_window_ok = dt_time(9, 20) <= current_time <= dt_time(14, 45)
    expiry_entry_ok = (not is_expiry_day) or (current_time <= dt_time(12, 15))

    if is_expiry_day and current_time <= dt_time(12, 15):
        min_confidence = 82.0
        min_readiness = 65
        min_adx = 25.0
    else:
        min_confidence = 75.0
        min_readiness = 55
        min_adx = 22.0

    iv_crush_safe = not (iv_regime == "HIGH" and (vix_rank >= 80 or days_to_expiry <= 2) and confidence < 85.0)
    base_gate_ok = all([
        entry_window_ok,
        expiry_entry_ok,
        oi_confirm,
        iv_crush_safe,
        confidence >= min_confidence,
        readiness >= min_readiness,
        quality_score >= 4,
        adx >= min_adx,
        liquidity_ok,
        spread_ok,
        delta_contract_ok,
    ])

    bullish_entry_ok = base_gate_ok and bias == "BULLISH" and 52.0 <= rsi <= 68.0
    bearish_entry_ok = base_gate_ok and bias == "BEARISH" and 32.0 <= rsi <= 48.0

    blocked_reasons = []
    if not entry_window_ok:
        blocked_reasons.append("outside preferred intraday entry window")
    if not expiry_entry_ok:
        blocked_reasons.append("expiry-day theta risk")
    if not oi_confirm:
        blocked_reasons.append("option-chain confirmation missing")
    if not iv_crush_safe:
        blocked_reasons.append("IV too high / crush risk for direct option buying")
    if not liquidity_ok or not spread_ok:
        blocked_reasons.append("poor liquidity or wide bid-ask spread")
    if not delta_contract_ok:
        blocked_reasons.append("no contract near the target delta")
    if confidence < min_confidence or readiness < min_readiness or adx < min_adx or quality_score < 4:
        blocked_reasons.append("directional momentum not strong enough")
    if bias == "BULLISH" and not (52.0 <= rsi <= 68.0):
        blocked_reasons.append("RSI not in clean CE entry zone")
    if bias == "BEARISH" and not (32.0 <= rsi <= 48.0):
        blocked_reasons.append("RSI not in clean PE entry zone")

    recommendation = "NO_TRADE"
    entry_type = "WAIT"
    if bullish_entry_ok:
        recommendation = "BUY_CE"
        entry_type = "OPTION_BUY"
    elif bearish_entry_ok:
        recommendation = "BUY_PE"
        entry_type = "OPTION_BUY"
    elif bias in {"BULLISH", "BEARISH"}:
        entry_type = "SPREAD_PREFERRED"

    quality_checks["entry_window_ok"] = entry_window_ok
    quality_checks["expiry_entry_ok"] = expiry_entry_ok
    quality_checks["liquidity_ok"] = liquidity_ok
    quality_checks["spread_ok"] = spread_ok
    quality_checks["iv_crush_safe"] = iv_crush_safe
    quality_checks["directional_entry_ok"] = recommendation in {"BUY_CE", "BUY_PE"}

    context["options_entry"] = {
        "recommendation": recommendation,
        "entry_type": entry_type,
        "days_to_expiry": days_to_expiry,
        "is_expiry_day": is_expiry_day,
        "expiry_date": expiry_date.isoformat() if hasattr(expiry_date, "isoformat") else str(expiry_date),
        "selected_contract": selected_contract,
        "blocked_reasons": blocked_reasons,
    }

    reason = str(enriched.get("reason") or "").strip()
    if recommendation == "BUY_CE" and "Direct BUY_CE allowed" not in reason:
        enriched["reason"] = f"{reason} | Direct BUY_CE allowed".strip(" |")
    elif recommendation == "BUY_PE" and "Direct BUY_PE allowed" not in reason:
        enriched["reason"] = f"{reason} | Direct BUY_PE allowed".strip(" |")
    elif blocked_reasons:
        gate_reason = blocked_reasons[0]
        if gate_reason not in reason:
            enriched["reason"] = f"{reason} | Entry gate: {gate_reason}".strip(" |")

    enriched["recommendation"] = recommendation
    enriched["quality_checks"] = quality_checks
    enriched["quality_score"] = sum(1 for v in quality_checks.values() if v)
    enriched["context"] = context
    return enriched


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
    # Guard: context may be a string
    existing_ctx = ta_sig.get("context")
    if not isinstance(existing_ctx, dict):
        existing_ctx = {}
    existing_ctx.update({
        "india_vix": india_vix,
        "vix_rank": vix_rank,
        "iv_regime": iv_regime,
    })
    ta_sig["context"] = existing_ctx
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
    ta_sig = _enrich_signal_with_option_context(ta_sig, symbol)

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
    # Guard: context may be a string (e.g. from DB JSON deserialization)
    existing_ctx = final_sig.get("context")
    if not isinstance(existing_ctx, dict):
        existing_ctx = {}
    existing_ctx.update({
        "india_vix": india_vix,
        "vix_rank": vix_rank,
        "iv_regime": iv_regime,
    })
    final_sig["context"] = existing_ctx
    final_sig = _apply_weekly_option_entry_filter(final_sig, symbol)

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