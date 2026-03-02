"""
Feature #17 — Signal-Level Backtest Engine
Replays ML signals on historical candle data and scores each signal hit/miss.
Unlike the strategy-level backtest, this tests the *signal* itself.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.core.ml.config import StockMLConfig
from app.core.ml.dataset import _load_candles_df
from app.core.ml.feature_builder import FEATURE_COLUMNS, build_features_from_df

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SignalEvent:
    """One signal emitted by a model at a point in time."""
    idx: int                   # row index in feature df
    timestamp: Any
    signal: str                # BULLISH / BEARISH / NO_TRADE
    confidence: int
    prob_up: float
    # Outcome (filled later)
    forward_return: Optional[float] = None
    forward_max_gain: Optional[float] = None
    forward_max_drawdown: Optional[float] = None
    hit: Optional[bool] = None


@dataclass
class SignalBacktestResult:
    """Aggregate results of a signal-level backtest."""
    symbol: str
    timeframe: str
    horizon: int
    total_signals: int = 0
    bullish_signals: int = 0
    bearish_signals: int = 0
    no_trade_signals: int = 0
    bullish_hits: int = 0
    bearish_hits: int = 0
    bullish_accuracy: float = 0.0
    bearish_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    avg_forward_return_bullish: float = 0.0
    avg_forward_return_bearish: float = 0.0
    profit_factor: Optional[float] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    daily_returns: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------


def run_signal_backtest(
    db: Session,
    symbol: str,
    config: StockMLConfig,
    *,
    model_type: str = "single",
    threshold_bullish: float = 0.55,
    threshold_bearish: float = 0.45,
    horizon: int = 5,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Replay model predictions on historical data:
    1. Build features for entire history
    2. Run model on each row
    3. Score each signal against forward return
    """
    # Load model
    if model_type == "ensemble":
        from app.core.ml.ensemble import load_ensemble
        model = load_ensemble(config)
    else:
        from app.core.ml.model_registry import load_model
        model = load_model(config)

    if model is None:
        return {"error": f"Model ({model_type}) not trained"}

    # Load candles
    raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
    if raw.empty or len(raw) < 100:
        return {"error": f"Insufficient data for {symbol} (need 100+ candles)"}

    features = build_features_from_df(raw, config)
    if features.empty or len(features) < 50:
        return {"error": f"Could not build features for {symbol}"}

    # Optionally filter by date range
    if "timestamp" in features.columns:
        if start_date:
            features = features[features["timestamp"] >= pd.Timestamp(start_date)]
        if end_date:
            features = features[features["timestamp"] <= pd.Timestamp(end_date)]

    # We need at least horizon extra rows after each signal to evaluate
    eval_end = len(features) - horizon
    if eval_end < 10:
        return {"error": f"Not enough rows to evaluate with horizon={horizon}"}

    # Run predictions on each row (sliding window)
    events: List[SignalEvent] = []

    for i in range(0, eval_end):
        row = features.iloc[i : i + 1]
        x = row[FEATURE_COLUMNS]

        try:
            prob_up = float(model.predict_proba(x)[0][1])
        except Exception:
            continue

        # Derive signal
        if prob_up >= threshold_bullish:
            sig = "BULLISH"
        elif prob_up <= threshold_bearish:
            sig = "BEARISH"
        else:
            sig = "NO_TRADE"

        confidence = int(max(prob_up, 1 - prob_up) * 100)

        # Forward return
        close_now = float(features.iloc[i]["close"]) if "close" in features.columns else None
        close_future = float(features.iloc[i + horizon]["close"]) if close_now else None

        if close_now and close_future and close_now > 0:
            forward_ret = (close_future - close_now) / close_now

            # Max gain and max drawdown over horizon window
            window = features.iloc[i + 1: i + horizon + 1]
            if "high" in window.columns and "low" in window.columns:
                max_gain = (float(window["high"].max()) - close_now) / close_now
                max_dd = (float(window["low"].min()) - close_now) / close_now
            else:
                max_gain = forward_ret
                max_dd = forward_ret
        else:
            forward_ret = None
            max_gain = None
            max_dd = None

        # Determine hit/miss
        hit = None
        if forward_ret is not None and sig != "NO_TRADE":
            if sig == "BULLISH":
                hit = forward_ret > 0
            else:
                hit = forward_ret < 0

        ts = features.iloc[i].get("timestamp", i)

        events.append(SignalEvent(
            idx=i,
            timestamp=str(ts),
            signal=sig,
            confidence=confidence,
            prob_up=round(prob_up, 4),
            forward_return=round(forward_ret, 6) if forward_ret is not None else None,
            forward_max_gain=round(max_gain, 6) if max_gain is not None else None,
            forward_max_drawdown=round(max_dd, 6) if max_dd is not None else None,
            hit=hit,
        ))

    # --- Aggregate results -------------------------------------------------
    bullish_events = [e for e in events if e.signal == "BULLISH"]
    bearish_events = [e for e in events if e.signal == "BEARISH"]
    no_trade = [e for e in events if e.signal == "NO_TRADE"]

    bullish_hits = sum(1 for e in bullish_events if e.hit is True)
    bearish_hits = sum(1 for e in bearish_events if e.hit is True)

    bullish_acc = (bullish_hits / len(bullish_events) * 100) if bullish_events else 0
    bearish_acc = (bearish_hits / len(bearish_events) * 100) if bearish_events else 0

    total_actionable = len(bullish_events) + len(bearish_events)
    total_hits = bullish_hits + bearish_hits
    overall_acc = (total_hits / total_actionable * 100) if total_actionable else 0

    avg_ret_bullish = float(np.mean([e.forward_return for e in bullish_events if e.forward_return is not None])) if bullish_events else 0
    avg_ret_bearish = float(np.mean([e.forward_return for e in bearish_events if e.forward_return is not None])) if bearish_events else 0

    # Profit factor: gross gain / gross loss from actionable signals
    gains = sum(e.forward_return for e in events if e.signal != "NO_TRADE" and e.forward_return and e.forward_return > 0)
    losses = abs(sum(e.forward_return for e in events if e.signal != "NO_TRADE" and e.forward_return and e.forward_return < 0))
    pf = round(gains / losses, 2) if losses > 0 else None

    # Simulated equity curve (start at 100k, invest per signal)
    equity = 100000.0
    equity_curve = [equity]
    for e in events:
        if e.signal == "NO_TRADE" or e.forward_return is None:
            equity_curve.append(equity)
            continue
        # BULLISH = long, BEARISH = short
        direction = 1 if e.signal == "BULLISH" else -1
        pnl = direction * e.forward_return * equity * 0.1  # 10% position sizing
        equity += pnl
        equity_curve.append(round(equity, 2))

    # Confidence buckets
    conf_buckets: Dict[str, Dict] = {}
    for bucket_name, lo, hi in [("50-60", 50, 60), ("60-70", 60, 70), ("70-80", 70, 80), ("80-90", 80, 90), ("90-100", 90, 101)]:
        bucket_events = [e for e in events if e.signal != "NO_TRADE" and lo <= e.confidence < hi]
        bucket_hits = sum(1 for e in bucket_events if e.hit is True)
        conf_buckets[bucket_name] = {
            "count": len(bucket_events),
            "hits": bucket_hits,
            "accuracy": round(bucket_hits / len(bucket_events) * 100, 1) if bucket_events else 0,
        }

    return {
        "symbol": symbol,
        "timeframe": config.timeframe,
        "horizon": horizon,
        "model_type": model_type,
        "total_signals": len(events),
        "bullish_signals": len(bullish_events),
        "bearish_signals": len(bearish_events),
        "no_trade_signals": len(no_trade),
        "bullish_hits": bullish_hits,
        "bearish_hits": bearish_hits,
        "bullish_accuracy": round(bullish_acc, 2),
        "bearish_accuracy": round(bearish_acc, 2),
        "overall_accuracy": round(overall_acc, 2),
        "avg_forward_return_bullish": round(avg_ret_bullish * 100, 3),
        "avg_forward_return_bearish": round(avg_ret_bearish * 100, 3),
        "profit_factor": pf,
        "confidence_buckets": conf_buckets,
        "equity_curve": equity_curve[-100:],  # last 100 points
        "events": [
            {
                "timestamp": e.timestamp,
                "signal": e.signal,
                "confidence": e.confidence,
                "prob_up": e.prob_up,
                "forward_return_pct": round(e.forward_return * 100, 3) if e.forward_return is not None else None,
                "hit": e.hit,
            }
            for e in events[-200:]  # last 200 events
        ],
    }


def run_multi_symbol_signal_backtest(
    db: Session,
    symbols: List[str],
    config: StockMLConfig,
    **kwargs,
) -> Dict[str, Any]:
    """Run signal backtest across multiple symbols and aggregate."""
    results: List[Dict] = []
    for sym in symbols:
        try:
            r = run_signal_backtest(db, sym, config, **kwargs)
            if "error" not in r:
                results.append(r)
        except Exception as exc:
            logger.warning(f"Signal backtest failed for {sym}: {exc}")

    if not results:
        return {"error": "No valid results"}

    # Aggregate
    total_signals = sum(r["total_signals"] for r in results)
    total_bullish = sum(r["bullish_signals"] for r in results)
    total_bearish = sum(r["bearish_signals"] for r in results)
    total_hits = sum(r["bullish_hits"] + r["bearish_hits"] for r in results)
    total_actionable = total_bullish + total_bearish

    return {
        "symbols_tested": len(results),
        "total_signals": total_signals,
        "bullish_signals": total_bullish,
        "bearish_signals": total_bearish,
        "overall_accuracy": round(total_hits / total_actionable * 100, 2) if total_actionable else 0,
        "avg_bullish_accuracy": round(float(np.mean([r["bullish_accuracy"] for r in results])), 2),
        "avg_bearish_accuracy": round(float(np.mean([r["bearish_accuracy"] for r in results])), 2),
        "per_symbol": [
            {
                "symbol": r["symbol"],
                "total_signals": r["total_signals"],
                "overall_accuracy": r["overall_accuracy"],
                "bullish_accuracy": r["bullish_accuracy"],
                "bearish_accuracy": r["bearish_accuracy"],
                "profit_factor": r["profit_factor"],
            }
            for r in results
        ],
    }
