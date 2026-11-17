"""
sl_reflection_engine.py
-----------------------
Post-mortem engine triggered after an SL hit.

Reuses existing FastTrade infrastructure:
  - NseFilingAnalysis  → news/filing context near SL time
  - vix_iv_api         → VIX at entry time (from SignalOutcome.context_json)
  - ta_engine          → re-evaluate TA quality at entry
  - signal_diagnostics → failure pattern aggregation
  - llm_service        → optional human-readable reflection text
  - SignalOutcome       → entry indicators snapshot
"""

import json
import logging
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _check_news_context(db: Session, symbol: str, sl_time) -> dict:
    """Look for a filing/news event within ±4 hours of the SL hit."""
    try:
        from app.db.models_filing_analysis import NseFilingAnalysis
        from datetime import datetime

        window_start = sl_time - timedelta(hours=4)
        window_end = sl_time + timedelta(hours=1)

        row = (
            db.query(NseFilingAnalysis)
            .filter(
                NseFilingAnalysis.symbol == symbol.upper(),
                NseFilingAnalysis.analysed_at >= window_start,
                NseFilingAnalysis.analysed_at <= window_end,
            )
            .order_by(NseFilingAnalysis.analysed_at.desc())
            .first()
        )
        if row:
            return {
                "found": True,
                "sentiment": row.sentiment,
                "tags": row.signal_tags or "",
                "headline": row.headline,
                "score": _safe_float(row.sentiment_score),
            }
    except Exception as e:
        logger.debug("News context check failed: %s", e)
    return {"found": False, "sentiment": None, "tags": "", "headline": None, "score": 0.0}


def _check_ta_quality(db: Session, symbol: str) -> dict:
    """Re-run TA on the symbol to check if the setup was valid."""
    try:
        from app.core.signals.ta_engine import ta_signal_15m
        result = ta_signal_15m(db, symbol)
        indicators = result.get("indicators", {})
        return {
            "rsi": _safe_float(indicators.get("rsi")),
            "adx": _safe_float(indicators.get("adx")),
            "quality_score": result.get("quality_score", 0),
            "signal": result.get("signal", "UNKNOWN"),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        logger.debug("TA quality check failed: %s", e)
    return {"rsi": 0.0, "adx": 0.0, "quality_score": 0, "signal": "UNKNOWN", "reason": ""}


def _get_vix_at_entry(context_json: dict) -> Optional[float]:
    """Extract VIX from the stored context snapshot."""
    if not context_json:
        return None
    return (
        context_json.get("india_vix")
        or context_json.get("vix")
        or context_json.get("vix_value")
    )


def _compute_cause_weights(
    *,
    news: dict,
    ta: dict,
    entry_rsi: float,
    entry_adx: float,
    entry_vix: float,
    entry_iv_regime: str,
    strategy: str,
) -> dict:
    """
    Rule-based cause attribution. Returns weights summing to 1.0.
    """
    news_score = 0.0
    technical_score = 0.0
    macro_score = 0.0
    iv_score = 0.0
    timing_score = 0.0

    # ── News ──────────────────────────────────────────────────────────────────
    if news["found"]:
        tags = news["tags"].upper()
        if any(t in tags for t in ["REGULATORY_ACTION", "LOSS_REPORTED", "INSIDER_SELL"]):
            news_score = 0.7
        elif any(t in tags for t in ["MISS", "M&A"]):
            news_score = 0.5
        elif news["sentiment"] == "BEARISH":
            news_score = 0.4
        else:
            news_score = 0.2

    # ── Technical ─────────────────────────────────────────────────────────────
    # Overbought entry for a bullish strategy = technical miss
    if strategy in ("BULL_PUT", "LONG_CALL", "SCALP_CALL"):
        if entry_rsi > 70:
            technical_score += 0.4
        elif entry_rsi > 65:
            technical_score += 0.2
        if entry_adx < 20:
            technical_score += 0.2  # weak trend = bad entry
    elif strategy in ("BEAR_CALL", "LONG_PUT", "SCALP_PUT"):
        if entry_rsi < 30:
            technical_score += 0.4
        elif entry_rsi < 35:
            technical_score += 0.2
        if entry_adx < 20:
            technical_score += 0.2

    technical_score = min(technical_score, 0.6)

    # ── Macro ─────────────────────────────────────────────────────────────────
    if entry_vix and entry_vix > 18:
        macro_score = 0.5
    elif entry_vix and entry_vix > 15:
        macro_score = 0.3

    # ── IV regime ─────────────────────────────────────────────────────────────
    # Credit spreads (Bull Put / Bear Call) should NOT be entered in HIGH IV
    # because premium is inflated and reversals are violent
    if entry_iv_regime == "HIGH" and strategy in ("BULL_PUT", "BEAR_CALL", "IRON_CONDOR"):
        iv_score = 0.4
    elif entry_iv_regime == "LOW" and strategy in ("LONG_CALL", "LONG_PUT"):
        iv_score = 0.3  # buying options in low IV = overpaying for theta

    # ── Timing ────────────────────────────────────────────────────────────────
    # If none of the above are strong, attribute to timing/randomness
    total_so_far = news_score + technical_score + macro_score + iv_score
    if total_so_far < 0.3:
        timing_score = 0.4

    # ── Normalise ─────────────────────────────────────────────────────────────
    total = news_score + technical_score + macro_score + iv_score + timing_score
    if total == 0:
        timing_score = 1.0
        total = 1.0

    weights = {
        "news": round(news_score / total, 3),
        "technical": round(technical_score / total, 3),
        "macro": round(macro_score / total, 3),
        "iv": round(iv_score / total, 3),
        "timing": round(timing_score / total, 3),
    }

    primary = max(weights, key=weights.get)
    return {**weights, "primary_cause": primary.upper()}


def _generate_reflection_text(
    *,
    symbol: str,
    strategy: str,
    pnl: float,
    weights: dict,
    news: dict,
    entry_rsi: float,
    entry_vix: float,
    entry_iv_regime: str,
) -> str:
    """
    Generate a human-readable reflection. Uses LLM if available,
    falls back to rule-based template.
    """
    try:
        from app.services.llm_service import call_llm, is_available
        if is_available():
            prompt = (
                f"A {strategy} trade on {symbol} hit its stop-loss with PnL ₹{pnl:.0f}.\n"
                f"Root cause weights: news={weights['news']:.0%}, technical={weights['technical']:.0%}, "
                f"macro={weights['macro']:.0%}, iv_regime={weights['iv']:.0%}, timing={weights['timing']:.0%}.\n"
                f"Entry conditions: RSI={entry_rsi:.1f}, VIX={entry_vix:.1f}, IV regime={entry_iv_regime}.\n"
                f"News found: {news['found']} — {news.get('headline', 'N/A')}.\n\n"
                "Write a 2-sentence trading post-mortem explaining why this trade failed and "
                "what to watch for next time. Be specific and concise."
            )
            text = call_llm(prompt, max_tokens=120, temperature=0.3, caller="sl_reflection")
            if text:
                return text.strip()
    except Exception as e:
        logger.debug("LLM reflection failed, using rule-based: %s", e)

    # Rule-based fallback
    primary = weights.get("primary_cause", "TIMING")
    parts = []
    if primary == "NEWS":
        parts.append(f"A surprise filing/news event ({news.get('headline', 'unknown')[:60]}) drove the SL hit.")
    elif primary == "TECHNICAL":
        overbought = entry_rsi > 65
        parts.append(
            f"The entry had a {'overbought RSI of ' + str(round(entry_rsi, 1)) if overbought else 'weak ADX'}, "
            "indicating the setup was not technically sound."
        )
    elif primary == "MACRO":
        parts.append(f"Elevated VIX ({entry_vix:.1f}) created adverse macro conditions for this strategy.")
    elif primary == "IV":
        parts.append(f"The IV regime ({entry_iv_regime}) was unfavourable for a {strategy} — avoid this combination.")
    else:
        parts.append("No dominant single cause — likely market noise or timing mismatch.")

    parts.append(
        f"Next time: check news within 4h of entry, confirm RSI < 65 for bullish credit spreads, "
        f"and avoid {strategy} when VIX > 16."
    )
    return " ".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────────

def reflect_on_sl(
    db: Session,
    *,
    intent_id: str,
    symbol: str,
    strategy: str,
    pnl: float,
    sl_time,
    signal_json: Optional[dict] = None,
    context_json: Optional[dict] = None,
) -> Optional[dict]:
    """
    Full reflection pipeline for a single SL hit.
    Returns the reflection dict (also upserted into DB).
    """
    from app.db.models_sl_reflection import SLReflection

    # Avoid duplicate reflections
    existing = db.query(SLReflection).filter(SLReflection.intent_id == intent_id).first()
    if existing:
        logger.info("Reflection already exists for intent_id=%s", intent_id)
        return None

    signal_json = signal_json or {}
    context_json = context_json or {}

    # ── Gather evidence ───────────────────────────────────────────────────────
    news = _check_news_context(db, symbol, sl_time)
    ta = _check_ta_quality(db, symbol)

    entry_rsi = _safe_float(
        (signal_json.get("indicators") or {}).get("rsi")
        or context_json.get("entry_rsi")
    )
    entry_adx = _safe_float(
        (signal_json.get("indicators") or {}).get("adx")
        or context_json.get("entry_adx")
    )
    entry_vix = _safe_float(_get_vix_at_entry(context_json), default=13.0)
    entry_iv_regime = str(
        context_json.get("iv_regime") or signal_json.get("iv_regime") or "NORMAL"
    )
    entry_market_mode = str(context_json.get("market_mode") or "UNKNOWN")

    # ── Compute weights ───────────────────────────────────────────────────────
    weights = _compute_cause_weights(
        news=news,
        ta=ta,
        entry_rsi=entry_rsi,
        entry_adx=entry_adx,
        entry_vix=entry_vix,
        entry_iv_regime=entry_iv_regime,
        strategy=strategy,
    )

    # ── Generate reflection text ──────────────────────────────────────────────
    reflection_text = _generate_reflection_text(
        symbol=symbol,
        strategy=strategy,
        pnl=pnl,
        weights=weights,
        news=news,
        entry_rsi=entry_rsi,
        entry_vix=entry_vix,
        entry_iv_regime=entry_iv_regime,
    )

    evidence = {
        "news": news,
        "ta_at_reflection": ta,
        "entry_rsi": entry_rsi,
        "entry_adx": entry_adx,
        "entry_vix": entry_vix,
        "entry_iv_regime": entry_iv_regime,
    }

    row = SLReflection(
        intent_id=intent_id,
        symbol=symbol,
        strategy=strategy,
        pnl=pnl,
        news_weight=weights["news"],
        technical_weight=weights["technical"],
        macro_weight=weights["macro"],
        iv_weight=weights["iv"],
        timing_weight=weights["timing"],
        primary_cause=weights["primary_cause"],
        entry_rsi=entry_rsi,
        entry_adx=entry_adx,
        entry_vix=entry_vix,
        entry_iv_regime=entry_iv_regime,
        entry_market_mode=entry_market_mode,
        news_filing_found=1 if news["found"] else 0,
        news_sentiment=news["sentiment"],
        news_tags=news["tags"],
        reflection_text=reflection_text,
        evidence=evidence,
    )
    db.add(row)
    try:
        db.commit()
        logger.info(
            "SL reflection stored: intent=%s symbol=%s primary_cause=%s",
            intent_id, symbol, weights["primary_cause"],
        )
    except Exception as e:
        db.rollback()
        logger.error("Failed to store SL reflection: %s", e)
        return None

    return {
        "intent_id": intent_id,
        "symbol": symbol,
        "strategy": strategy,
        "pnl": pnl,
        "primary_cause": weights["primary_cause"],
        "weights": weights,
        "reflection_text": reflection_text,
        "evidence": evidence,
    }


def get_failure_patterns(db: Session, min_trades: int = 3) -> list[dict]:
    """
    Aggregate SL reflections into failure patterns.
    Returns patterns sorted by SL rate descending.
    """
    from app.db.models_sl_reflection import SLReflection
    from sqlalchemy import func

    rows = db.query(SLReflection).all()
    if not rows:
        return []

    # Group by (strategy, primary_cause)
    buckets: dict[str, dict] = {}
    for r in rows:
        key = f"{r.strategy}|{r.primary_cause}"
        if key not in buckets:
            buckets[key] = {
                "strategy": r.strategy,
                "primary_cause": r.primary_cause,
                "count": 0,
                "total_loss": 0.0,
                "avg_entry_rsi": [],
                "avg_entry_vix": [],
            }
        b = buckets[key]
        b["count"] += 1
        b["total_loss"] += abs(_safe_float(r.pnl))
        if r.entry_rsi:
            b["avg_entry_rsi"].append(r.entry_rsi)
        if r.entry_vix:
            b["avg_entry_vix"].append(r.entry_vix)

    patterns = []
    for key, b in buckets.items():
        if b["count"] < min_trades:
            continue
        patterns.append({
            "strategy": b["strategy"],
            "primary_cause": b["primary_cause"],
            "sl_count": b["count"],
            "avg_loss": round(b["total_loss"] / b["count"], 2),
            "avg_entry_rsi": round(sum(b["avg_entry_rsi"]) / len(b["avg_entry_rsi"]), 1) if b["avg_entry_rsi"] else None,
            "avg_entry_vix": round(sum(b["avg_entry_vix"]) / len(b["avg_entry_vix"]), 1) if b["avg_entry_vix"] else None,
        })

    patterns.sort(key=lambda x: x["sl_count"], reverse=True)
    return patterns
