"""
Condition-based Strategy Scanner (Streak-like)
================================================
Lets users define entry/exit conditions using technical indicators,
save strategies, scan symbols for signals, and auto-execute trades
based on the current trading mode (Paper / DryRun / Live).

Endpoints:
  POST /condition-scanner/strategies         — create strategy
  GET  /condition-scanner/strategies         — list strategies
  GET  /condition-scanner/strategies/{id}    — get one
  PUT  /condition-scanner/strategies/{id}    — update
  DELETE /condition-scanner/strategies/{id}  — delete
  POST /condition-scanner/scan/{id}          — run scan now
  GET  /condition-scanner/prebuilt           — list pre-built templates
  POST /condition-scanner/prebuilt/{key}/install — install a pre-built
  GET  /condition-scanner/indicators         — available indicator list
  POST /condition-scanner/execute-signal     — execute a triggered signal
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, date as dt_date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.execution.mode import get_execution_mode, is_paper_mode, is_live_mode
from app.core.indicators.technical import TechnicalIndicators
from app.core.condition_strategy_lab import (
    expand_strategies_with_exit_variants,
    generate_candidate_strategies,
    generate_exit_param_combinations,
    score_backtest_summary,
    select_diverse_top,
    strategy_family,
)
from app.core.learning.scanner_signal_history import mark_signal_execution, record_scanner_signal
from app.core.utils.time import now_ist
from app.config.market_config import get_symbols
from app.db.models_candles import Candle1m, Candle5m, Candle15m, Candle1h, CandleDaily
from app.db.models_scanner_signal import ScannerSignalHistory
from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest
from app.db.session import SessionLocal
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/condition-scanner", tags=["condition-scanner"])

kite_service = KiteConnectService()

# ── DB dependency ───────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic schemas ────────────────────────────────────────────────────────

class Condition(BaseModel):
    """Single condition row:  If/And  INDICATOR(params) COMPARATOR VALUE"""
    indicator: str          # e.g. "TEMA", "Stochastic", "RSI", "ADX", "EMA", "SMA", "MACD", "BB"
    params: Dict[str, Any]  # e.g. {"source": "close", "period": 50, "offset": 0}
    comparator: str         # "crosses_above", "crosses_below", "higher_than", "lower_than"
    value: str              # target: a number ("20") or another indicator ref like "Close(0)"

class ExitConfig(BaseModel):
    sl_pct: float = 5.0
    tp_pct: float = 10.0
    tsl_pct: float = 0.0
    exit_mode: str = "percentage"  # percentage | points | pnl
    exit_conditions: List[Condition] = Field(default_factory=list)
    require_htf_confirm: bool = False
    htf_timeframe: Optional[str] = None  # Auto-resolve to the next higher timeframe when omitted
    use_atr_sizing: bool = False
    atr_period: int = 14
    atr_multiplier: float = 1.5
    risk_per_trade_pct: float = 1.0
    apply_slippage: bool = False
    slippage_pct: float = 0.1
    walk_forward_enabled: bool = False
    walk_forward_windows: int = 3
    walk_forward_train_pct: float = 67.0

class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    strategy_type: str = "Equity Swing"   # Equity Swing / Equity Intraday / Options Buying / Options Selling
    direction: str = "BUY"                # BUY / SELL
    timeframe: str = "1 Hour"             # 1 Min, 5 Min, 15 Min, 1 Hour, Day
    instruments: List[str] = []           # empty = scan universe
    universe: str = "NIFTY50"
    entry_conditions: List[Condition]
    exit_config: ExitConfig = ExitConfig()
    is_active: bool = True
    auto_scan_enabled: bool = False
    auto_amount: float = 10000.0  # ₹ amount per trade; qty = floor(amount / price)

class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    strategy_type: Optional[str] = None
    direction: Optional[str] = None
    timeframe: Optional[str] = None
    instruments: Optional[List[str]] = None
    universe: Optional[str] = None
    entry_conditions: Optional[List[Condition]] = None
    exit_config: Optional[ExitConfig] = None
    is_active: Optional[bool] = None
    auto_scan_enabled: Optional[bool] = None
    auto_amount: Optional[float] = None


# ── DB-backed strategy helpers ─────────────────────────────────────────────

def _get_strategy_or_404(db: Session, strategy_id: int) -> ConditionStrategy:
    row = db.query(ConditionStrategy).filter(ConditionStrategy.id == strategy_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return row

def _strategy_with_backtest(db: Session, row: ConditionStrategy) -> dict:
    """Serialize strategy dict, attaching last backtest result if available."""
    d = row.to_dict()
    if row.last_backtest_id:
        bt = db.query(ConditionStrategyBacktest).filter(
            ConditionStrategyBacktest.id == row.last_backtest_id
        ).first()
        if bt:
            d["last_backtest_result"] = bt.result_dict
    return d


def _get_discovery_leaderboard_snapshot() -> Dict[str, Any]:
    """Return the latest rolling discovery leaderboard persisted by the scheduler/manual discovery script."""
    try:
        from app.core.market.scheduler import _load_discovery_state

        state = _load_discovery_state()
    except Exception:
        return {
            "state_key": None,
            "last_run_at": None,
            "next_offset": 0,
            "total_pool": 0,
            "last_batch_start": 0,
            "last_batch_end": 0,
            "completed_cycle": False,
            "rolling_top_results": [],
        }

    batches = (state or {}).get("strategy_batches") or {}
    if not batches:
        return {
            "state_key": None,
            "last_run_at": None,
            "next_offset": 0,
            "total_pool": 0,
            "last_batch_start": 0,
            "last_batch_end": 0,
            "completed_cycle": False,
            "rolling_top_results": [],
        }

    state_key, row = max(
        batches.items(),
        key=lambda item: (
            str((item[1] or {}).get("last_run_at") or ""),
            int((item[1] or {}).get("last_batch_end", 0) or 0),
            int((item[1] or {}).get("pool_total", 0) or 0),
        ),
    )
    latest = dict(row or {})
    rolling = latest.get("rolling_top_results") or latest.get("top_results") or []
    return {
        "state_key": state_key,
        "last_run_at": latest.get("last_run_at"),
        "next_offset": int(latest.get("next_offset", 0) or 0),
        "total_pool": int(latest.get("pool_total", 0) or 0),
        "last_batch_start": int(latest.get("last_batch_start", 0) or 0),
        "last_batch_end": int(latest.get("last_batch_end", 0) or 0),
        "completed_cycle": bool(latest.get("completed_cycle", False)),
        "rolling_top_results": [
            {
                "rank": index,
                **dict(item or {}),
            }
            for index, item in enumerate(rolling[:5], start=1)
        ],
    }

# Legacy shim — used by condition_scanner_scheduler (will be updated separately)
def _load_strategies() -> List[dict]:
    db = SessionLocal()
    try:
        rows = db.query(ConditionStrategy).order_by(ConditionStrategy.id).all()
        return [r.to_dict() for r in rows]
    finally:
        db.close()

def _save_strategies(strategies: List[dict]):
    """No-op shim — DB writes happen inline now. Kept for scheduler compatibility."""
    pass

def _next_id(strategies: List[dict]) -> int:
    """Unused — DB auto-increments. Kept for discover endpoint compatibility."""
    if not strategies:
        return 1
    return max(s.get("id", 0) for s in strategies) + 1


def _serialize_signal_history(row: ScannerSignalHistory) -> Dict[str, Any]:
    return {
        "id": row.id,
        "strategy_id": row.strategy_id,
        "strategy_name": row.strategy_name,
        "symbol": row.symbol,
        "direction": row.direction,
        "timeframe": row.timeframe,
        "universe": row.universe,
        "source": row.source,
        "status": row.status,
        "signal_date": row.signal_date.isoformat() if row.signal_date else None,
        "first_seen_at": row.first_seen_at,
        "last_seen_at": row.last_seen_at,
        "executed_at": row.executed_at,
        "trigger_count": row.trigger_count,
        "auto_execute": row.auto_execute,
        "execution_mode": row.execution_mode,
        "quantity": row.quantity,
        "ltp": row.ltp,
        "change_percent": row.change_percent,
        "order_id": row.order_id,
        "indicators": row.indicators_json,
        "signal_payload": row.signal_payload,
        "execution_payload": row.execution_payload,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ── Indicator evaluation engine ─────────────────────────────────────────────

def _compute_indicator(
    indicator: str,
    params: Dict[str, Any],
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
) -> Optional[float]:
    """Compute a single indicator value from OHLCV data."""
    ind = indicator.upper()
    period = int(params.get("period", 14))

    if ind in ("SMA",):
        return TechnicalIndicators.calculate_sma(closes, period)

    elif ind in ("EMA",):
        return TechnicalIndicators.calculate_ema(closes, period)

    elif ind in ("TEMA",):
        # TEMA = 3*EMA1 - 3*EMA2 + EMA3
        return _calculate_tema(closes, period)

    elif ind in ("DEMA",):
        return _calculate_dema(closes, period)

    elif ind in ("WMA",):
        return _calculate_wma(closes, period)

    elif ind in ("RSI",):
        return TechnicalIndicators.calculate_rsi(closes, period)

    elif ind in ("ADX",):
        result = TechnicalIndicators.calculate_adx(highs, lows, closes, period)
        return result["adx"] if result else None

    elif ind in ("STOCHASTIC", "STOCH"):
        k_period = int(params.get("k_period", params.get("period", 14)))
        d_period = int(params.get("d_period", 3))
        smoothing = params.get("smoothing", "%k")
        result = TechnicalIndicators.calculate_stochastic(highs, lows, closes, k_period, d_period)
        if not result:
            return None
        return result["k"] if smoothing in ("%k", "k", "yes") else result["d"]

    elif ind in ("MACD",):
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        comp = params.get("component", "histogram")
        result = TechnicalIndicators.calculate_macd(closes, fast, slow, signal)
        if not result:
            return None
        return result.get(comp, result.get("histogram"))

    elif ind in ("BB", "BOLLINGER"):
        std_dev = float(params.get("std_dev", 2.0))
        band = params.get("band", "percent_b")  # upper/middle/lower/percent_b
        result = TechnicalIndicators.calculate_bollinger_bands(closes, period, std_dev)
        if not result:
            return None
        return result.get(band, result.get("percent_b"))

    elif ind in ("ATR",):
        return TechnicalIndicators.calculate_atr(highs, lows, closes, period)

    elif ind in ("CLOSE", "PRICE"):
        offset = int(params.get("offset", 0))
        idx = -1 - offset
        return closes[idx] if abs(idx) <= len(closes) else None

    elif ind in ("VOLUME", "VOL"):
        return float(volumes[-1]) if volumes else None

    elif ind in ("MOVING_AVERAGE", "MA"):
        ma_type = params.get("type", "sma").lower()
        if ma_type == "ema":
            return TechnicalIndicators.calculate_ema(closes, period)
        return TechnicalIndicators.calculate_sma(closes, period)

    elif ind in ("CCI",):
        return _calculate_cci(closes, highs, lows, period)

    elif ind in ("ROC",):
        if len(closes) < period + 1:
            return None
        prev = closes[-(period + 1)]
        return ((closes[-1] - prev) / prev) * 100 if prev != 0 else None

    elif ind in ("WILLIAMS_R", "WILLIAMSR", "WILLR"):
        return _calculate_williams_r(highs, lows, closes, period)

    elif ind in ("OBV",):
        return _calculate_obv(closes, volumes)

    elif ind in ("VWAP",):
        return _calculate_vwap(closes, highs, lows, volumes, period)

    elif ind in ("SUPERTREND",):
        multiplier = float(params.get("multiplier", 3.0))
        return _calculate_supertrend(closes, highs, lows, period, multiplier)

    else:
        logger.warning(f"Unknown indicator: {indicator}")
        return None


def _calculate_cci(closes: List[float], highs: List[float], lows: List[float], period: int) -> Optional[float]:
    """Commodity Channel Index."""
    if len(closes) < period:
        return None
    typical = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    window = typical[-period:]
    mean = sum(window) / period
    mad = sum(abs(x - mean) for x in window) / period
    return (typical[-1] - mean) / (0.015 * mad) if mad != 0 else 0.0


def _calculate_williams_r(highs: List[float], lows: List[float], closes: List[float], period: int) -> Optional[float]:
    """Williams %R."""
    if len(closes) < period:
        return None
    highest_high = max(highs[-period:])
    lowest_low = min(lows[-period:])
    if highest_high == lowest_low:
        return -50.0
    return ((highest_high - closes[-1]) / (highest_high - lowest_low)) * -100


def _calculate_obv(closes: List[float], volumes: List[float]) -> Optional[float]:
    """On-Balance Volume — returns last value in thousands."""
    if len(closes) < 2:
        return None
    obv = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            obv += volumes[i]
        elif closes[i] < closes[i - 1]:
            obv -= volumes[i]
    return obv / 1000.0


def _calculate_vwap(closes: List[float], highs: List[float], lows: List[float], volumes: List[float], period: int) -> Optional[float]:
    """Rolling VWAP over `period` bars."""
    if len(closes) < period:
        return None
    tp = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
    window_tp = tp[-period:]
    window_vol = volumes[-period:]
    total_vol = sum(window_vol)
    if total_vol == 0:
        return closes[-1]
    return sum(t * v for t, v in zip(window_tp, window_vol)) / total_vol


def _calculate_supertrend(closes: List[float], highs: List[float], lows: List[float], period: int, multiplier: float) -> Optional[float]:
    """
    Simplified Supertrend — returns +1 if price is above the lower band (bullish)
    or -1 if below (bearish). Use comparator 'higher_than 0' for buy signals.
    """
    if len(closes) < period + 1:
        return None
    atr = TechnicalIndicators.calculate_atr(highs, lows, closes, period)
    if atr is None:
        return None
    mid = (highs[-1] + lows[-1]) / 2
    lower = mid - multiplier * atr
    return 1.0 if closes[-1] > lower else -1.0


def _calculate_tema(prices: List[float], period: int) -> Optional[float]:
    """Triple Exponential Moving Average."""
    if len(prices) < period * 3:
        return None
    ema1_series = _ema_series(prices, period)
    if not ema1_series or len(ema1_series) < period:
        return None
    ema2_series = _ema_series(ema1_series, period)
    if not ema2_series or len(ema2_series) < period:
        return None
    ema3_series = _ema_series(ema2_series, period)
    if not ema3_series:
        return None
    return 3 * ema1_series[-1] - 3 * ema2_series[-1] + ema3_series[-1]


def _calculate_dema(prices: List[float], period: int) -> Optional[float]:
    """Double Exponential Moving Average."""
    if len(prices) < period * 2:
        return None
    ema1_series = _ema_series(prices, period)
    if not ema1_series or len(ema1_series) < period:
        return None
    ema2_series = _ema_series(ema1_series, period)
    if not ema2_series:
        return None
    return 2 * ema1_series[-1] - ema2_series[-1]


def _calculate_wma(prices: List[float], period: int) -> Optional[float]:
    """Weighted Moving Average."""
    if len(prices) < period:
        return None
    window = prices[-period:]
    weights = list(range(1, period + 1))
    return sum(p * w for p, w in zip(window, weights)) / sum(weights)


def _ema_series(prices: List[float], period: int) -> List[float]:
    """Return full EMA series."""
    if len(prices) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]
    for p in prices[period:]:
        ema.append(p * k + ema[-1] * (1 - k))
    return ema


def _compute_indicator_prev(
    indicator: str,
    params: Dict[str, Any],
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
) -> Optional[float]:
    """Same indicator on the previous bar (for crossover detection)."""
    if len(closes) < 2:
        return None
    return _compute_indicator(
        indicator, params,
        closes[:-1], highs[:-1], lows[:-1], volumes[:-1]
    )


def _resolve_value(
    value_str: str,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
) -> Optional[float]:
    """
    Resolve the right-hand side value.
    Could be a plain number ("20"), indicator ref ("Close(0)"), or indicator ("DEMA(26)", "EMA(50)").
    """
    v = value_str.strip()

    # Plain number
    try:
        return float(v)
    except ValueError:
        pass

    # Check if it's an indicator reference (e.g., "DEMA(26)", "EMA(50)", "TEMA(20)")
    if any(v.upper().startswith(ind) for ind in ("DEMA", "TEMA", "EMA", "SMA", "WMA", "RSI", "ADX", "MACD", "STOCH", "BB")):
        # Parse indicator name and period
        if "(" in v:
            parts = v.split("(")
            indicator_name = parts[0].strip().upper()
            period_str = parts[1].rstrip(")")
            try:
                period = int(period_str)
                # Recursively compute the indicator value
                return _compute_indicator(indicator_name, {"period": period}, closes, highs, lows, volumes)
            except (ValueError, IndexError):
                pass

    # Close(offset)
    if v.upper().startswith("CLOSE"):
        offset = 0
        if "(" in v:
            offset = int(v.split("(")[1].rstrip(")"))
        idx = -1 - offset
        return closes[idx] if abs(idx) <= len(closes) else None

    # Open/High/Low
    if v.upper().startswith("HIGH"):
        return highs[-1] if highs else None
    if v.upper().startswith("LOW"):
        return lows[-1] if lows else None

    return None


def _resolve_value_prev(
    value_str: str,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
) -> Optional[float]:
    if len(closes) < 2:
        return None
    return _resolve_value(value_str, closes[:-1], highs[:-1], lows[:-1], volumes[:-1])


def _required_history_bars(conditions: List[dict]) -> int:
    """Estimate the warm-up bars required to evaluate a strategy reliably."""
    required = 30
    for cond in conditions or []:
        indicator = str(cond.get("indicator", "")).upper()
        params = cond.get("params", {}) or {}
        period = int(params.get("period", 14) or 14)

        if indicator == "TEMA":
            required = max(required, period * 3 + 5)
        elif indicator == "DEMA":
            required = max(required, period * 2 + 5)
        elif indicator in ("STOCHASTIC", "STOCH"):
            k_period = int(params.get("k_period", period) or period)
            d_period = int(params.get("d_period", 3) or 3)
            required = max(required, k_period + d_period + 5)
        elif indicator == "MACD":
            slow = int(params.get("slow", 26) or 26)
            signal = int(params.get("signal", 9) or 9)
            required = max(required, slow + signal + 5)
        else:
            required = max(required, period + 5)

    return max(required, 30)


def _evaluate_condition(
    cond: dict,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
) -> bool:
    """Evaluate a single condition against OHLCV data."""
    indicator = cond["indicator"]
    params = cond.get("params", {})
    comparator = cond["comparator"]
    value_str = cond["value"]

    curr_val = _compute_indicator(indicator, params, closes, highs, lows, volumes)
    if curr_val is None:
        return False

    if comparator in ("crosses_above", "crosses_below"):
        prev_val = _compute_indicator_prev(indicator, params, closes, highs, lows, volumes)
        if prev_val is None:
            return False

        target_curr = _resolve_value(value_str, closes, highs, lows, volumes)
        target_prev = _resolve_value_prev(value_str, closes, highs, lows, volumes)
        if target_curr is None or target_prev is None:
            return False

        if comparator == "crosses_above":
            return prev_val <= target_prev and curr_val > target_curr
        else:
            return prev_val >= target_prev and curr_val < target_curr

    # Simple comparisons
    target = _resolve_value(value_str, closes, highs, lows, volumes)
    if target is None:
        return False

    if comparator == "higher_than":
        return curr_val > target
    elif comparator == "lower_than":
        return curr_val < target
    elif comparator == "equal_to":
        return abs(curr_val - target) < 0.01
    elif comparator == "above":
        return curr_val > target
    elif comparator == "below":
        return curr_val < target
    elif comparator == "between":
        # value_str expected as "lo,hi" e.g. "30,70"
        try:
            parts = value_str.split(",")
            lo, hi = float(parts[0]), float(parts[1])
            return lo <= curr_val <= hi
        except Exception:
            return False
    else:
        logger.warning(f"Unknown comparator: {comparator}")
        return False


def _scan_symbol(
    symbol: str,
    conditions: List[dict],
    db: Session,
    ltp: Optional[float] = None,
    volume: Optional[int] = None,
    timeframe: str = "Day",
    exit_config: Optional[Dict[str, Any]] = None,
    capital_base: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Scan a single symbol against entry conditions using the strategy timeframe.
    Returns match info or None.
    """
    exit_settings = dict(exit_config or {})
    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe, TIMEFRAME_CANDLE_MAP["Day"])
    CandleModel, date_attr, _table_label = candle_info
    date_col = getattr(CandleModel, date_attr)

    required_bars = _required_history_bars(conditions)
    default_limit = {
        "1 Min": 600,
        "5 Min": 600,
        "15 Min": 600,
        "1 Hour": 400,
        "Day": 250,
    }.get(timeframe, 250)
    limit_bars = max(default_limit, required_bars + 50)

    candles = (
        db.query(CandleModel)
        .filter(CandleModel.symbol == symbol)
        .order_by(desc(date_col))
        .limit(limit_bars)
        .all()
    )

    if len(candles) < required_bars:
        return None

    candles = candles[::-1]  # chronological
    closes, highs, lows, volumes = _build_price_series(candles, ltp=ltp, volume=volume)

    for cond in conditions:
        if not _evaluate_condition(cond, closes, highs, lows, volumes):
            return None

    htf_timeframe = None
    htf_confirmed = True
    if bool(exit_settings.get("require_htf_confirm")):
        htf_timeframe = _resolve_confirmation_timeframe(timeframe, exit_settings)
        if htf_timeframe:
            htf_info = TIMEFRAME_CANDLE_MAP.get(htf_timeframe)
            if not htf_info:
                return None
            HtfModel, htf_date_attr, _htf_table = htf_info
            htf_date_col = getattr(HtfModel, htf_date_attr)
            htf_default_limit = {
                "1 Min": 600,
                "5 Min": 600,
                "15 Min": 600,
                "1 Hour": 400,
                "Day": 250,
            }.get(htf_timeframe, 250)
            htf_limit = max(htf_default_limit, required_bars + 20)
            htf_candles = (
                db.query(HtfModel)
                .filter(HtfModel.symbol == symbol)
                .order_by(desc(htf_date_col))
                .limit(htf_limit)
                .all()
            )
            htf_candles = htf_candles[::-1]
            htf_confirmed = _conditions_match_on_candles(conditions, htf_candles)
        if not htf_confirmed:
            return None

    indicator_values = {}
    for cond in conditions:
        ind = cond["indicator"]
        val = _compute_indicator(ind, cond.get("params", {}), closes, highs, lows, volumes)
        if val is not None:
            indicator_values[ind] = round(val, 2)

    atr_period = max(int(exit_settings.get("atr_period", 14) or 14), 2)
    atr_value = TechnicalIndicators.calculate_atr(highs, lows, closes, atr_period) if len(closes) >= atr_period else None
    sizing = _recommended_position_size(
        entry_price=float(closes[-1]),
        available_capital=float(capital_base or 10000.0),
        position_size_pct=100.0,
        exit_config=exit_settings,
        atr_value=atr_value,
    )

    change_pct = 0.0
    if len(closes) >= 2 and closes[-2] != 0:
        change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100

    return {
        "symbol": symbol,
        "ltp": round(closes[-1], 2),
        "change_percent": round(change_pct, 2),
        "indicators": indicator_values,
        "conditions_met": len(conditions),
        "timeframe": timeframe,
        "timestamp": datetime.now().isoformat(),
        "htf_confirmed": htf_confirmed,
        "htf_timeframe": htf_timeframe,
        "atr": round(float(atr_value), 2) if atr_value is not None else None,
        "suggested_quantity": int(sizing["quantity"]),
        "capital_used": float(sizing["capital_used"]),
        "position_sizing": sizing["position_sizing"],
        "risk_amount": float(sizing["risk_amount"]),
    }


# ── Pre-built strategy templates ────────────────────────────────────────────

PREBUILT_STRATEGIES: Dict[str, dict] = {
    "volume_breakout": {
        "name": "Volume Breakout",
        "description": "Enters long when price is above its 20-bar close with RSI above 50, confirming genuine breakout interest backed by momentum.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "Day",
        "entry_conditions": [
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "50"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "25"},
            {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 12, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "gap_up_momentum": {
        "name": "Gap Up Momentum",
        "description": "Captures stocks with strong intraday momentum. RSI above 55 confirms momentum, MACD histogram positive ensures trend alignment, ADX above 20 confirms trend strength.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "15 Min",
        "entry_conditions": [
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "55"},
            {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "20"},
        ],
        "exit_config": {"sl_pct": 1.5, "tp_pct": 3, "tsl_pct": 0.5, "exit_mode": "percentage"},
    },
    "supertrend_buy": {
        "name": "Supertrend Bullish",
        "description": "Enters long when Supertrend is bullish (returns +1) with RSI above 50 and ADX above 20 confirming trend strength. A clean trend-following setup.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {"indicator": "Supertrend", "params": {"period": 10, "multiplier": 3.0}, "comparator": "higher_than", "value": "0"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "50"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "20"},
        ],
        "exit_config": {"sl_pct": 3, "tp_pct": 9, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
    "cci_oversold_reversal": {
        "name": "CCI Oversold Reversal",
        "description": "Buys when CCI crosses above -100 from oversold territory, signalling a mean-reversion bounce. EMA(50) below price confirms the broader uptrend.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "Day",
        "entry_conditions": [
            {"indicator": "CCI", "params": {"period": 20}, "comparator": "crosses_above", "value": "-100"},
            {"indicator": "EMA", "params": {"period": 50}, "comparator": "lower_than", "value": "Close(0)"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "35"},
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 10, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "williams_r_oversold": {
        "name": "Williams %R Oversold Bounce",
        "description": "Enters long when Williams %R crosses above -80 (leaving oversold zone) with price above EMA(20). Effective for short-term mean-reversion trades.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "15 Min",
        "entry_conditions": [
            {"indicator": "Williams_R", "params": {"period": 14}, "comparator": "crosses_above", "value": "-80"},
            {"indicator": "EMA", "params": {"period": 20}, "comparator": "lower_than", "value": "Close(0)"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "40"},
        ],
        "exit_config": {"sl_pct": 1.5, "tp_pct": 3.5, "tsl_pct": 0.5, "exit_mode": "percentage"},
    },
    "roc_momentum_burst": {
        "name": "ROC Momentum Burst",
        "description": "Captures stocks with strong price acceleration. Rate of Change above 5% over 10 days with RSI in the 50-70 zone indicates a momentum burst without being overbought.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "Day",
        "entry_conditions": [
            {"indicator": "ROC", "params": {"period": 10}, "comparator": "higher_than", "value": "5"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "50"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": "70"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "25"},
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 10, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "vwap_pullback_buy": {
        "name": "VWAP Pullback Buy",
        "description": "Buys when price is above VWAP and RSI is above 45 with positive MACD histogram. Ideal for intraday trend continuation after a brief pullback.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "5 Min",
        "entry_conditions": [
            {"indicator": "VWAP", "params": {"period": 20}, "comparator": "lower_than", "value": "Close(0)"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "45"},
            {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
        ],
        "exit_config": {"sl_pct": 1, "tp_pct": 2, "tsl_pct": 0.5, "exit_mode": "percentage"},
    },
    "bb_mean_reversion_sell": {
        "name": "Bollinger Band Mean Reversion Short",
        "description": "Short signal when price closes above the upper Bollinger Band (%B > 1) and RSI is overbought above 70. Expects a reversion back to the mean.",
        "strategy_type": "Equity Swing",
        "direction": "SELL",
        "timeframe": "Day",
        "entry_conditions": [
            {"indicator": "BB", "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"}, "comparator": "higher_than", "value": "1"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "70"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "lower_than", "value": "30"},
        ],
        "exit_config": {"sl_pct": 3, "tp_pct": 6, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
    "triple_ema_trend": {
        "name": "Triple EMA Trend Filter",
        "description": "Enters long only when EMA(9) > EMA(21) > EMA(50), confirming a strong multi-timeframe uptrend. ADX above 25 ensures the trend has sufficient strength.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {"indicator": "EMA", "params": {"period": 9}, "comparator": "higher_than", "value": "EMA(21)"},
            {"indicator": "EMA", "params": {"period": 21}, "comparator": "higher_than", "value": "EMA(50)"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "25"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "50"},
        ],
        "exit_config": {"sl_pct": 3, "tp_pct": 9, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
    "stoch_rsi_combo": {
        "name": "Stochastic + RSI Combo",
        "description": "Dual-oscillator confirmation: Stochastic %K crosses above 20 while RSI simultaneously crosses above 30. Both must fire together for a high-confidence entry.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "Day",
        "entry_conditions": [
            {"indicator": "Stochastic", "params": {"k_period": 14, "smoothing": "%k"}, "comparator": "crosses_above", "value": "20"},
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "crosses_above", "value": "30"},
            {"indicator": "EMA", "params": {"period": 50}, "comparator": "lower_than", "value": "Close(0)"},
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 10, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "intraday_opening_range": {
        "name": "Intraday Opening Range Breakout",
        "description": "Classic ORB: enters when RSI is above 55 and MACD histogram crosses above 0 with ADX confirming trend. Tight SL/TP for quick intraday moves.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "5 Min",
        "entry_conditions": [
            {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "55"},
            {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "crosses_above", "value": "0"},
            {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "20"},
        ],
        "exit_config": {"sl_pct": 0.8, "tp_pct": 1.6, "tsl_pct": 0.4, "exit_mode": "percentage"},
    },
    "tema_stochastic_rebound": {
        "name": "TEMA Stochastic Rebound",
        "description": "Takes a buy position when the closing price crosses above the 50-period TEMA, signaling a potential shift in trend. This is supported by the Stochastic %K crossing above 20, indicating early bullish momentum from oversold territory.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {
                "indicator": "TEMA",
                "params": {"source": "close", "period": 50, "offset": 0},
                "comparator": "crosses_below",
                "value": "Close(0)"
            },
            {
                "indicator": "Stochastic",
                "params": {"k_period": 14, "smoothing": "%k", "offset": 0},
                "comparator": "crosses_above",
                "value": "20"
            },
            {
                "indicator": "ADX",
                "params": {"period": 14, "offset": 0},
                "comparator": "higher_than",
                "value": "25"
            }
        ],
        "exit_config": {"sl_pct": 5, "tp_pct": 10, "tsl_pct": 0, "exit_mode": "percentage"},
    },
    "rsi_oversold_bounce": {
        "name": "RSI Oversold Bounce",
        "description": "Buys when RSI crosses above 30 from oversold territory with EMA(20) providing trend support. ADX above 20 confirms sufficient trend strength.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "Day",
        "entry_conditions": [
            {
                "indicator": "RSI",
                "params": {"period": 14, "offset": 0},
                "comparator": "crosses_above",
                "value": "30"
            },
            {
                "indicator": "EMA",
                "params": {"period": 20, "offset": 0},
                "comparator": "lower_than",
                "value": "Close(0)"
            },
            {
                "indicator": "ADX",
                "params": {"period": 14, "offset": 0},
                "comparator": "higher_than",
                "value": "20"
            }
        ],
        "exit_config": {"sl_pct": 3, "tp_pct": 8, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
    "macd_bullish_crossover": {
        "name": "MACD Bullish Crossover",
        "description": "Enters long when MACD histogram turns positive (MACD crosses above signal line) with RSI between 40-70 confirming bullish momentum without being overbought.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "15 Min",
        "entry_conditions": [
            {
                "indicator": "MACD",
                "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"},
                "comparator": "crosses_above",
                "value": "0"
            },
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "comparator": "higher_than",
                "value": "40"
            },
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "comparator": "lower_than",
                "value": "70"
            }
        ],
        "exit_config": {"sl_pct": 2, "tp_pct": 4, "tsl_pct": 1, "exit_mode": "percentage"},
    },
    "bollinger_squeeze_breakout": {
        "name": "Bollinger Squeeze Breakout",
        "description": "Detects low-volatility squeeze (bandwidth compression) followed by an upside breakout. When price closes above the upper Bollinger Band with ADX above 25, a strong trend move is likely.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {
                "indicator": "BB",
                "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"},
                "comparator": "higher_than",
                "value": "1"
            },
            {
                "indicator": "ADX",
                "params": {"period": 14},
                "comparator": "higher_than",
                "value": "25"
            },
            {
                "indicator": "Volume",
                "params": {},
                "comparator": "higher_than",
                "value": "0"
            }
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 12, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "ema_crossover_trend": {
        "name": "EMA 9/21 Crossover",
        "description": "Classic short-term trend following: EMA(9) crosses above EMA(21) indicating a bullish trend shift. Confirmed by positive MACD histogram.",
        "strategy_type": "Equity Intraday",
        "direction": "BUY",
        "timeframe": "15 Min",
        "entry_conditions": [
            {
                "indicator": "EMA",
                "params": {"period": 9},
                "comparator": "crosses_above",
                "value": "Close(0)"
            },
            {
                "indicator": "EMA",
                "params": {"period": 21},
                "comparator": "lower_than",
                "value": "Close(0)"
            },
            {
                "indicator": "MACD",
                "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"},
                "comparator": "higher_than",
                "value": "0"
            }
        ],
        "exit_config": {"sl_pct": 1.5, "tp_pct": 3, "tsl_pct": 0.5, "exit_mode": "percentage"},
    },
    "bearish_rsi_divergence": {
        "name": "Bearish RSI Overbought",
        "description": "Short signal when RSI crosses below 70 (leaving overbought) with TEMA(50) above price, confirming bearish pressure.",
        "strategy_type": "Equity Swing",
        "direction": "SELL",
        "timeframe": "Day",
        "entry_conditions": [
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "comparator": "crosses_below",
                "value": "70"
            },
            {
                "indicator": "TEMA",
                "params": {"period": 50},
                "comparator": "higher_than",
                "value": "Close(0)"
            }
        ],
        "exit_config": {"sl_pct": 4, "tp_pct": 8, "tsl_pct": 2, "exit_mode": "percentage"},
    },
    "dema_crossover_trend": {
        "name": "DEMA 12/26 Crossover",
        "description": "Double Exponential Moving Average (DEMA) trend-following strategy with reduced lag. Enters long when the fast DEMA(12) crosses above the slow DEMA(26), confirming a bullish trend shift. ADX above 20 confirms sufficient trend strength for reliable signals.",
        "strategy_type": "Equity Swing",
        "direction": "BUY",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {
                "indicator": "DEMA",
                "params": {"period": 12},
                "comparator": "crosses_above",
                "value": "DEMA(26)"
            },
            {
                "indicator": "ADX",
                "params": {"period": 14},
                "comparator": "higher_than",
                "value": "20"
            },
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "comparator": "lower_than",
                "value": "70"
            }
        ],
        "exit_config": {"sl_pct": 3.5, "tp_pct": 9, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
    "dema_short_trend": {
        "name": "DEMA 12/26 Short",
        "description": "Short counterpart to DEMA crossover: enters short when fast DEMA(12) crosses below slow DEMA(26). Confirms with ADX above 20 and RSI below 30 for oversold signals.",
        "strategy_type": "Equity Swing",
        "direction": "SELL",
        "timeframe": "1 Hour",
        "entry_conditions": [
            {
                "indicator": "DEMA",
                "params": {"period": 12},
                "comparator": "crosses_below",
                "value": "DEMA(26)"
            },
            {
                "indicator": "ADX",
                "params": {"period": 14},
                "comparator": "higher_than",
                "value": "20"
            },
            {
                "indicator": "RSI",
                "params": {"period": 14},
                "comparator": "higher_than",
                "value": "30"
            }
        ],
        "exit_config": {"sl_pct": 3.5, "tp_pct": 9, "tsl_pct": 1.5, "exit_mode": "percentage"},
    },
}


# ── REST endpoints ──────────────────────────────────────────────────────────

@router.get("/indicators")
async def list_indicators():
    """Return list of available indicators for the condition builder."""
    return {
        "indicators": [
            {
                "id": "SMA", "name": "SMA",
                "description": "Simple Moving Average",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "📈"
            },
            {
                "id": "EMA", "name": "EMA",
                "description": "Exponential Moving Average",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "📈"
            },
            {
                "id": "TEMA", "name": "TEMA",
                "description": "Triple Exponential Moving Average",
                "params": [
                    {"name": "source", "type": "select", "options": ["close", "open", "high", "low"], "default": "close"},
                    {"name": "period", "type": "int", "default": 50},
                    {"name": "offset", "type": "int", "default": 0}
                ],
                "icon": "📊"
            },
            {
                "id": "DEMA", "name": "DEMA",
                "description": "Double Exponential Moving Average",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "📊"
            },
            {
                "id": "WMA", "name": "WMA",
                "description": "Weighted Moving Average",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "📊"
            },
            {
                "id": "RSI", "name": "RSI",
                "description": "Relative Strength Index",
                "params": [{"name": "period", "type": "int", "default": 14}],
                "icon": "💪"
            },
            {
                "id": "Stochastic", "name": "Stochastic",
                "description": "Stochastic Oscillator (%K / %D)",
                "params": [
                    {"name": "k_period", "type": "int", "default": 14},
                    {"name": "smoothing", "type": "select", "options": ["%k", "%d"], "default": "%k"},
                    {"name": "offset", "type": "int", "default": 0}
                ],
                "icon": "🔄"
            },
            {
                "id": "MACD", "name": "MACD",
                "description": "Moving Average Convergence Divergence",
                "params": [
                    {"name": "fast", "type": "int", "default": 12},
                    {"name": "slow", "type": "int", "default": 26},
                    {"name": "signal", "type": "int", "default": 9},
                    {"name": "component", "type": "select", "options": ["histogram", "macd", "signal"], "default": "histogram"}
                ],
                "icon": "📉"
            },
            {
                "id": "ADX", "name": "ADX",
                "description": "Average Directional Index",
                "params": [
                    {"name": "period", "type": "int", "default": 14},
                    {"name": "offset", "type": "int", "default": 0}
                ],
                "icon": "🧭"
            },
            {
                "id": "BB", "name": "Bollinger Bands",
                "description": "Bollinger Bands (upper / middle / lower / %B)",
                "params": [
                    {"name": "period", "type": "int", "default": 20},
                    {"name": "std_dev", "type": "float", "default": 2.0},
                    {"name": "band", "type": "select", "options": ["percent_b", "upper", "middle", "lower"], "default": "percent_b"}
                ],
                "icon": "📏"
            },
            {
                "id": "ATR", "name": "ATR",
                "description": "Average True Range",
                "params": [{"name": "period", "type": "int", "default": 14}],
                "icon": "📐"
            },
            {
                "id": "Close", "name": "Close",
                "description": "Closing Price",
                "params": [{"name": "offset", "type": "int", "default": 0}],
                "icon": "💰"
            },
            {
                "id": "Moving_Average", "name": "Moving Average",
                "description": "SMA or EMA configurable",
                "params": [
                    {"name": "type", "type": "select", "options": ["sma", "ema"], "default": "sma"},
                    {"name": "period", "type": "int", "default": 20}
                ],
                "icon": "〰️"
            },
            {
                "id": "CCI", "name": "CCI",
                "description": "Commodity Channel Index — >100 overbought, <-100 oversold",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "🌀"
            },
            {
                "id": "ROC", "name": "ROC",
                "description": "Rate of Change — % price change over N bars",
                "params": [{"name": "period", "type": "int", "default": 10}],
                "icon": "🚀"
            },
            {
                "id": "Williams_R", "name": "Williams %R",
                "description": "Williams Percent Range — 0 to -100; below -80 oversold, above -20 overbought",
                "params": [{"name": "period", "type": "int", "default": 14}],
                "icon": "📡"
            },
            {
                "id": "VWAP", "name": "VWAP",
                "description": "Volume Weighted Average Price over N bars",
                "params": [{"name": "period", "type": "int", "default": 20}],
                "icon": "⚖️"
            },
            {
                "id": "OBV", "name": "OBV",
                "description": "On-Balance Volume — cumulative volume flow (in thousands)",
                "params": [],
                "icon": "📦"
            },
            {
                "id": "Supertrend", "name": "Supertrend",
                "description": "Returns +1 (bullish) or -1 (bearish). Use 'higher than 0' for buy signals.",
                "params": [
                    {"name": "period", "type": "int", "default": 10},
                    {"name": "multiplier", "type": "float", "default": 3.0}
                ],
                "icon": "🔱"
            },
        ],
        "comparators": [
            {"id": "crosses_above", "label": "crosses above"},
            {"id": "crosses_below", "label": "crosses below"},
            {"id": "higher_than", "label": "higher than"},
            {"id": "lower_than", "label": "lower than"},
            {"id": "equal_to", "label": "equal to"},
            {"id": "between", "label": "between (lo,hi)"},
        ]
    }


@router.get("/prebuilt")
async def list_prebuilt():
    """Return available pre-built strategy templates."""
    return {
        "strategies": [
            {
                "key": key,
                "name": s["name"],
                "description": s["description"],
                "strategy_type": s["strategy_type"],
                "direction": s["direction"],
                "timeframe": s["timeframe"],
                "conditions_count": len(s["entry_conditions"]),
                "exit_config": s["exit_config"],
                "entry_conditions": s["entry_conditions"],
            }
            for key, s in PREBUILT_STRATEGIES.items()
        ]
    }


@router.post("/prebuilt/{key}/install")
async def install_prebuilt(key: str, db: Session = Depends(get_db)):
    """Install a pre-built strategy template as a user strategy."""
    template = PREBUILT_STRATEGIES.get(key)
    if not template:
        raise HTTPException(status_code=404, detail=f"Pre-built strategy '{key}' not found")

    if db.query(ConditionStrategy).filter_by(name=template["name"]).first():
        raise HTTPException(status_code=409, detail=f"Strategy '{template['name']}' already exists")

    row = ConditionStrategy(
        name=template["name"],
        description=template["description"],
        strategy_type=template["strategy_type"],
        direction=template["direction"],
        timeframe=template["timeframe"],
        instruments=[],
        universe="NIFTY50",
        entry_conditions=template["entry_conditions"],
        exit_config=template["exit_config"],
        is_active=True,
        auto_scan_enabled=False,
        auto_amount=10000.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": f"Installed '{template['name']}'", "strategy": row.to_dict()}


@router.post("/strategies")
async def create_strategy(data: StrategyCreate, db: Session = Depends(get_db)):
    """Create a new condition-based strategy."""
    if db.query(ConditionStrategy).filter_by(name=data.name).first():
        raise HTTPException(status_code=409, detail=f"Strategy '{data.name}' already exists")

    row = ConditionStrategy(
        name=data.name,
        description=data.description,
        strategy_type=data.strategy_type,
        direction=data.direction,
        timeframe=data.timeframe,
        universe=data.universe,
        instruments=data.instruments,
        entry_conditions=[c.model_dump() for c in data.entry_conditions],
        exit_config=data.exit_config.model_dump(),
        is_active=data.is_active,
        auto_scan_enabled=data.auto_scan_enabled,
        auto_amount=data.auto_amount,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "Strategy created", "strategy": row.to_dict()}


@router.get("/strategies")
async def list_strategies(strategy_type: Optional[str] = None, db: Session = Depends(get_db)):
    """List all user strategies plus the latest rolling discovery leaderboard."""
    q = db.query(ConditionStrategy).order_by(ConditionStrategy.id)
    if strategy_type:
        q = q.filter(ConditionStrategy.strategy_type == strategy_type)
    rows = q.all()
    discovery_snapshot = _get_discovery_leaderboard_snapshot()
    return {
        "strategies": [_strategy_with_backtest(db, r) for r in rows],
        "discovery_leaderboard": discovery_snapshot.get("rolling_top_results", []),
        "discovery_snapshot": discovery_snapshot,
    }


@router.get("/strategies/{strategy_id}")
async def get_strategy(strategy_id: int, db: Session = Depends(get_db)):
    row = _get_strategy_or_404(db, strategy_id)
    return _strategy_with_backtest(db, row)


@router.get("/strategies/{strategy_id}/explain")
async def explain_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """
    Generate a plain-English explanation of a strategy using the configured LLM
    (NVIDIA / Groq). Includes backtest context when available.

    Returns:
        { strategy_id, strategy_name, explanation, generated_at }
    """
    from app.services.llm_service import call_llm, is_available

    if not is_available():
        raise HTTPException(
            status_code=503,
            detail="LLM not configured — set LLM_API_KEY in .env",
        )

    row = _get_strategy_or_404(db, strategy_id)
    d = _strategy_with_backtest(db, row)

    # Build conditions text
    conditions_text = "\n".join(
        f"  - {c.get('indicator')} {c.get('params', {})} {c.get('comparator')} {c.get('value')}"
        for c in row.entry_conditions_list
    )
    ec = row.exit_config_dict
    exit_text = (
        f"Stop-loss {ec.get('sl_pct', 0)}% | "
        f"Take-profit {ec.get('tp_pct', 0)}% | "
        f"Trailing SL {ec.get('tsl_pct', 0)}%"
    )

    bt_lines = ""
    if "last_backtest_result" in d:
        summary = d["last_backtest_result"].get("summary", {})
        bt_lines = (
            f"\nBacktest summary (NIFTY50 universe, Indian stocks):\n"
            f"  - Annual return: {summary.get('annual_return_pct', 'N/A')}%\n"
            f"  - Win rate: {summary.get('win_rate', 'N/A')}%\n"
            f"  - Total trades: {summary.get('total_trades', 'N/A')}\n"
            f"  - Sharpe ratio: {summary.get('sharpe_ratio', 'N/A')}\n"
            f"  - Max drawdown: {summary.get('max_drawdown_pct', 'N/A')}%"
        )

    prompt = (
        f"Explain this Indian stock trading strategy in plain English for a retail trader. "
        f"Keep it under 120 words. Avoid jargon.\n\n"
        f"Strategy: {row.name}\n"
        f"Direction: {row.direction} | Timeframe: {row.timeframe} | Universe: {row.universe}\n"
        f"Entry conditions (ALL must be true simultaneously):\n{conditions_text}\n"
        f"Exit rules: {exit_text}"
        f"{bt_lines}\n\n"
        f"Write 2-3 sentences covering: what it does, when it fires, and its historical edge."
    )

    explanation = call_llm(prompt, max_tokens=200, temperature=0.3)
    if not explanation:
        raise HTTPException(status_code=503, detail="LLM call failed — check logs")

    return {
        "strategy_id": strategy_id,
        "strategy_name": row.name,
        "explanation": explanation,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.put("/strategies/{strategy_id}")
async def update_strategy(strategy_id: int, data: StrategyUpdate, db: Session = Depends(get_db)):
    row = _get_strategy_or_404(db, strategy_id)

    if data.name is not None:
        row.name = data.name
    if data.description is not None:
        row.description = data.description
    if data.strategy_type is not None:
        row.strategy_type = data.strategy_type
    if data.direction is not None:
        row.direction = data.direction
    if data.timeframe is not None:
        row.timeframe = data.timeframe
    if data.instruments is not None:
        row.instruments = data.instruments
    if data.universe is not None:
        row.universe = data.universe
    if data.entry_conditions is not None:
        row.entry_conditions = [
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in data.entry_conditions
        ]
    if data.exit_config is not None:
        row.exit_config = (
            data.exit_config.model_dump()
            if hasattr(data.exit_config, "model_dump")
            else data.exit_config
        )
    if data.is_active is not None:
        row.is_active = data.is_active
    if data.auto_scan_enabled is not None:
        row.auto_scan_enabled = data.auto_scan_enabled
    if data.auto_amount is not None:
        row.auto_amount = data.auto_amount

    db.commit()
    db.refresh(row)
    return {"message": "Updated", "strategy": _strategy_with_backtest(db, row)}


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    row = _get_strategy_or_404(db, strategy_id)
    # Also delete associated backtest records
    db.query(ConditionStrategyBacktest).filter(
        ConditionStrategyBacktest.strategy_id == strategy_id
    ).delete()
    db.delete(row)
    db.commit()
    return {"message": "Deleted"}


@router.post("/scan/{strategy_id}")
async def scan_strategy(
    strategy_id: int,
    auto_execute: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Run a strategy scan against the configured universe.
    Returns symbols where ALL entry conditions are met.
    """
    row = _get_strategy_or_404(db, strategy_id)
    strategy = row.to_dict()

    conditions = row.entry_conditions_list
    if not conditions:
        raise HTTPException(status_code=400, detail="No entry conditions defined")

    universe = row.universe
    symbols = row.instruments_list or get_symbols(universe)

    # Try to get live quotes for LTP
    quotes_data = kite_service.get_bulk_quotes(symbols) or {}

    signals = []
    scanned = 0

    for symbol in symbols:
        scanned += 1
        ltp = None
        volume = None
        quote = quotes_data.get(f"NSE:{symbol}")
        if quote:
            ltp = quote.get("last_price")
            volume = quote.get("volume")

        result = _scan_symbol(
            symbol,
            conditions,
            db,
            ltp=ltp,
            volume=volume,
            timeframe=row.timeframe or "Day",
            exit_config=row.exit_config_dict,
            capital_base=float(row.auto_amount or 10000.0),
        )
        if result:
            signals.append(result)

    # Update strategy scan metadata
    row.last_scan = now_ist()
    row.last_signal_count = len(signals)
    db.commit()

    mode = get_execution_mode()
    history_rows = []
    history_pairs: List[Tuple[Dict[str, Any], Any]] = []
    for signal in signals:
        history = record_scanner_signal(
            db,
            strategy_id=strategy_id,
            strategy_name=row.name,
            symbol=signal["symbol"],
            direction=row.direction,
            timeframe=row.timeframe,
            universe=universe,
            signal_payload=signal,
            auto_execute=bool(row.auto_scan_enabled or auto_execute),
            execution_mode=mode,
        )
        if history:
            history_rows.append(_serialize_signal_history(history))
            history_pairs.append((signal, history))

    auto_execute_requested = bool(auto_execute or row.auto_scan_enabled)
    auto_executed = 0
    auto_skipped = 0
    if auto_execute_requested and history_pairs:
        from app.core.condition_scanner_scheduler import _auto_execute_signal

        for signal, history in history_pairs:
            existing_status = str(getattr(history, "status", "") or "").upper()
            if existing_status in {"FILLED_PAPER", "PLACED_LIVE", "EXECUTED", "DRY_RUN"}:
                auto_skipped += 1
                continue
            try:
                quantity = int(signal.get("suggested_quantity") or (max(1, int((float(row.auto_amount or 10000.0) or 10000.0) // max(float(signal.get("ltp") or 1.0), 1.0)))))
                _auto_execute_signal(
                    history_id=getattr(history, "id", None),
                    strategy_id=strategy_id,
                    symbol=signal["symbol"],
                    ltp=float(signal.get("ltp") or 0.0),
                    direction=row.direction,
                    strategy_name=row.name,
                    exit_config=row.exit_config_dict,
                    timeframe=row.timeframe,
                    universe=universe,
                    quantity=max(1, quantity),
                    mode=mode,
                    db=db,
                )
                auto_executed += 1
            except Exception as exec_err:
                logger.error("Auto execute on scan failed for %s: %s", signal.get("symbol"), exec_err)

    return {
        "strategy_id": strategy_id,
        "strategy_name": row.name,
        "direction": row.direction,
        "signals": signals,
        "signal_history": history_rows,
        "total_scanned": scanned,
        "matches_found": len(signals),
        "execution_mode": mode,
        "exit_config": row.exit_config_dict,
        "auto_execute_requested": auto_execute_requested,
        "auto_executed": auto_executed,
        "auto_execute_skipped": auto_skipped,
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/execute-signal")
async def execute_signal(body: dict, db: Session = Depends(get_db)):
    """
    Execute a trade for a triggered signal.
    Routes to Paper or Zerodha based on EXECUTION_MODE env var.
    """
    symbol = body.get("symbol")
    direction = body.get("direction", "BUY")
    strategy_name = body.get("strategy_name", "Condition Scanner")
    strategy_id = body.get("strategy_id")
    exit_config = body.get("exit_config", {})
    quantity = body.get("quantity") or body.get("suggested_quantity") or 1
    try:
        quantity = max(1, int(float(quantity)))
    except Exception:
        quantity = 1
    timeframe = body.get("timeframe")
    universe = body.get("universe")
    signal_history_id = body.get("signal_history_id")

    if not symbol:
        raise HTTPException(status_code=400, detail="symbol required")

    mode = get_execution_mode()

    # Get current price
    quote = kite_service.get_quote(symbol)
    ltp = None
    if quote:
        ltp = quote.get("last_price", 0)

    if not ltp or ltp == 0:
        # Try from DB
        latest = (
            db.query(CandleDaily)
            .filter(CandleDaily.symbol == symbol)
            .order_by(desc(CandleDaily.date))
            .first()
        )
        if latest:
            ltp = latest.close
        else:
            raise HTTPException(status_code=400, detail=f"Cannot get price for {symbol}")

    # Build order record
    order = {
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "price": ltp,
        "strategy": strategy_name,
        "sl_pct": exit_config.get("sl_pct", 5),
        "tp_pct": exit_config.get("tp_pct", 10),
        "tsl_pct": exit_config.get("tsl_pct", 0),
        "mode": mode,
        "timestamp": datetime.now().isoformat(),
    }

    history = record_scanner_signal(
        db,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        universe=universe,
        signal_payload={
            "symbol": symbol,
            "ltp": ltp,
            "change_percent": body.get("change_percent"),
            "indicators": body.get("indicators"),
            "timestamp": order["timestamp"],
        },
        auto_execute=bool(body.get("auto_executed", False)),
        execution_mode=mode,
    )
    if history and not signal_history_id:
        signal_history_id = history.id

    if is_paper_mode(mode):
        # Paper trade — just log it
        order["status"] = "FILLED_PAPER"
        order["order_id"] = f"PAPER-{datetime.now().strftime('%Y%m%d%H%M%S')}-{symbol}"
        order["fill_price"] = ltp
        logger.info(f"📝 Paper trade executed: {direction} {symbol} @ ₹{ltp}")

    elif is_live_mode(mode):
        # Live Zerodha order
        try:
            from app.core.broker.zerodha.client import get_kite_client
            kite = get_kite_client()

            transaction_type = kite.TRANSACTION_TYPE_BUY if direction == "BUY" else kite.TRANSACTION_TYPE_SELL

            order_id = kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NSE,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=kite.PRODUCT_CNC,
                order_type=kite.ORDER_TYPE_MARKET,
            )
            order["status"] = "PLACED_LIVE"
            order["order_id"] = str(order_id)
            order["fill_price"] = ltp
            logger.info(f"🔴 LIVE order placed: {direction} {symbol} @ ₹{ltp}, order_id={order_id}")

        except Exception as e:
            logger.error(f"Failed to place live order: {e}")
            order["status"] = "FAILED"
            order["error"] = str(e)

    else:
        # Dry-run
        order["status"] = "DRY_RUN"
        order["order_id"] = f"DRY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{symbol}"
        order["fill_price"] = ltp
        logger.info(f"🟡 Dry-run trade: {direction} {symbol} @ ₹{ltp}")

    mark_signal_execution(
        db,
        history_id=signal_history_id,
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        symbol=symbol,
        direction=direction,
        status=order.get("status", "SIGNAL_GENERATED"),
        execution_payload=order,
        quantity=quantity,
        execution_mode=mode,
        order_id=order.get("order_id"),
    )

    # Persist to execution log
    try:
        from app.db.models_auto_trader import AutoTraderLog
        log = AutoTraderLog(
            strategy=strategy_name,
            action="ENTRY",
            underlying=symbol,
            reason=f"{direction} @ {ltp} qty={quantity} mode={mode}",
            details=order,
            severity="SUCCESS" if "FAILED" not in str(order.get("status", "")) else "ERROR",
        )
        db.add(log)
        db.commit()
    except Exception as log_err:
        logger.warning(f"Could not log execution: {log_err}")

    return {
        "order": order,
        "execution_mode": mode,
        "message": f"{'Paper' if is_paper_mode(mode) else 'Live' if is_live_mode(mode) else 'Dry-run'} order for {direction} {symbol} @ ₹{ltp}",
        "signal_history_id": signal_history_id,
    }


@router.get("/history")
async def get_signal_history(
    limit: int = Query(50, ge=1, le=500),
    days: int = Query(30, ge=1, le=365),
    strategy_id: Optional[int] = None,
    symbol: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return recent persistent condition-scanner signal history."""
    query = db.query(ScannerSignalHistory).order_by(
        ScannerSignalHistory.signal_date.desc(),
        ScannerSignalHistory.last_seen_at.desc(),
    )

    cutoff_date = now_ist().date() - timedelta(days=days - 1)
    query = query.filter(ScannerSignalHistory.signal_date >= cutoff_date)

    if strategy_id is not None:
        query = query.filter(ScannerSignalHistory.strategy_id == strategy_id)
    if symbol:
        query = query.filter(ScannerSignalHistory.symbol == symbol.upper())
    if status:
        query = query.filter(ScannerSignalHistory.status == status.upper())

    rows = query.limit(limit).all()
    return {
        "history": [_serialize_signal_history(row) for row in rows],
        "count": len(rows),
        "days": days,
        "limit": limit,
    }


# ── Backtest engine for condition-based strategies ──────────────────────────

# Map strategy timeframe → (CandleModel, date_column_name, table label)
TIMEFRAME_CANDLE_MAP = {
    "1 Min":  (Candle1m,   "timestamp", "candles_1m"),
    "5 Min":  (Candle5m,   "timestamp", "candles_5m"),
    "15 Min": (Candle15m,  "timestamp", "candles_15m"),
    "1 Hour": (Candle1h,   "timestamp", "candles_1h"),
    "Day":    (CandleDaily, "date",     "candles_daily"),
}

AUTO_HTF_TIMEFRAME_MAP = {
    "1 Min": "5 Min",
    "5 Min": "15 Min",
    "15 Min": "1 Hour",
    "1 Hour": "Day",
    "Day": None,
}


def _resolve_confirmation_timeframe(timeframe: str, exit_config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    config = exit_config or {}
    requested = str(config.get("htf_timeframe") or "").strip()
    if requested and requested.lower() not in {"auto", "higher", "next"}:
        return requested if requested in TIMEFRAME_CANDLE_MAP else None
    return AUTO_HTF_TIMEFRAME_MAP.get(timeframe)


def _has_time_component(value: Any) -> bool:
    return isinstance(value, datetime) or hasattr(value, "hour")


def _marker_leq(left: Any, right: Any) -> bool:
    if right is None:
        return True

    if _has_time_component(left) and _has_time_component(right):
        return left <= right

    if _has_time_component(left) and not _has_time_component(right):
        return left.date() <= right

    if not _has_time_component(left) and _has_time_component(right):
        return left <= right.date()

    return left <= right


def _slice_candles_up_to(candles: List[Any], date_attr: str, reference_value: Any) -> List[Any]:
    if reference_value is None:
        return list(candles)
    return [candle for candle in candles if _marker_leq(getattr(candle, date_attr), reference_value)]


def _build_price_series(
    candles: List[Any],
    *,
    ltp: Optional[float] = None,
    volume: Optional[int] = None,
) -> Tuple[List[float], List[float], List[float], List[int]]:
    closes = [float(c.close) for c in candles]
    highs = [float(c.high) for c in candles]
    lows = [float(c.low) for c in candles]
    volumes = [int(c.volume or 0) for c in candles]

    if ltp and ltp > 0 and closes:
        last_close = closes[-1]
        closes.append(float(ltp))
        highs.append(max(last_close, float(ltp)))
        lows.append(min(last_close, float(ltp)))
        volumes.append(volume if volume and volume > 0 else volumes[-1])

    return closes, highs, lows, volumes


def _conditions_match_on_candles(
    conditions: List[dict],
    candles: List[Any],
    *,
    ltp: Optional[float] = None,
    volume: Optional[int] = None,
) -> bool:
    if len(candles) < _required_history_bars(conditions):
        return False

    closes, highs, lows, volumes = _build_price_series(candles, ltp=ltp, volume=volume)
    return all(_evaluate_condition(cond, closes, highs, lows, volumes) for cond in conditions)


def _recommended_position_size(
    *,
    entry_price: float,
    available_capital: float,
    position_size_pct: float,
    exit_config: Dict[str, Any],
    atr_value: Optional[float] = None,
) -> Dict[str, Any]:
    safe_entry = max(float(entry_price or 0.0), 0.01)
    safe_capital = max(float(available_capital or 0.0), safe_entry)
    capital_cap_pct = max(float(position_size_pct or 0.0), 0.0)
    max_position_value = safe_capital * (capital_cap_pct / 100.0) if capital_cap_pct > 0 else safe_capital
    max_position_value = max(max_position_value, safe_entry)
    fixed_qty = max(1, int(max_position_value // safe_entry))

    if not bool(exit_config.get("use_atr_sizing")):
        capital_used = round(fixed_qty * safe_entry, 2)
        return {
            "quantity": fixed_qty,
            "capital_used": capital_used,
            "risk_amount": round(max_position_value, 2),
            "atr": atr_value,
            "atr_stop_distance": None,
            "position_sizing": "FIXED",
        }

    risk_pct = max(float(exit_config.get("risk_per_trade_pct", 1.0) or 0.0), 0.1)
    atr_multiplier = max(float(exit_config.get("atr_multiplier", 1.5) or 0.0), 0.1)
    safe_atr = max(float(atr_value or 0.0), safe_entry * 0.002)
    stop_distance = max(safe_atr * atr_multiplier, 0.05)
    risk_amount = safe_capital * (risk_pct / 100.0)
    qty_by_risk = max(1, int(risk_amount // stop_distance))
    quantity = max(1, min(fixed_qty, qty_by_risk))
    capital_used = round(quantity * safe_entry, 2)

    return {
        "quantity": quantity,
        "capital_used": capital_used,
        "risk_amount": round(risk_amount, 2),
        "atr": round(float(atr_value or 0.0), 2) if atr_value is not None else None,
        "atr_stop_distance": round(stop_distance, 2),
        "position_sizing": "ATR",
    }


def _get_bar_date(candle, date_attr: str):
    """Normalise candle date/timestamp to a date object for comparisons."""
    val = getattr(candle, date_attr)
    if hasattr(val, "date"):          # datetime → date
        return val.date()
    return val                         # already a date


def _apply_slippage(price: float, direction: str, *, is_entry: bool, slippage_pct: float) -> float:
    safe_price = float(price or 0.0)
    slip_ratio = max(float(slippage_pct or 0.0), 0.0) / 100.0
    if safe_price <= 0 or slip_ratio <= 0:
        return round(safe_price, 2)

    side = str(direction or "BUY").upper()
    if side == "BUY":
        adjusted = safe_price * (1 + slip_ratio) if is_entry else safe_price * (1 - slip_ratio)
    else:
        adjusted = safe_price * (1 - slip_ratio) if is_entry else safe_price * (1 + slip_ratio)
    return round(adjusted, 2)


def _bar_date_str(candle, date_attr: str) -> str:
    """Normalise candle date/timestamp to a display string."""
    val = getattr(candle, date_attr)
    if hasattr(val, "isoformat"):
        return val.isoformat() if hasattr(val, "hour") else str(val)
    return str(val)


@router.get("/candle-range/{timeframe}")
async def get_candle_date_range(
    timeframe: str,
    universe: str = Query(default="NIFTY50"),
    db: Session = Depends(get_db),
):
    """
    Return the min/max available dates for a given candle timeframe
    so the frontend can constrain backtest date pickers.
    """
    from sqlalchemy import func as sqlfunc

    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe)
    if not candle_info:
        return {"min_date": None, "max_date": None, "total_rows": 0, "symbols": 0, "timeframe": timeframe}

    CandleModel, date_attr, table_label = candle_info
    date_col = getattr(CandleModel, date_attr)

    # Optionally filter to symbols in the universe
    symbols = get_symbols(universe)

    row = (
        db.query(
            sqlfunc.min(date_col),
            sqlfunc.max(date_col),
            sqlfunc.count(CandleModel.id),
        )
        .filter(CandleModel.symbol.in_(symbols))
        .first()
    )
    sym_count = (
        db.query(CandleModel.symbol)
        .filter(CandleModel.symbol.in_(symbols))
        .distinct()
        .count()
    )

    min_val, max_val, total = row if row else (None, None, 0)

    # Normalise to date strings
    if min_val and hasattr(min_val, "date"):
        min_val = min_val.date()
    if max_val and hasattr(max_val, "date"):
        max_val = max_val.date()

    return {
        "min_date": str(min_val) if min_val else None,
        "max_date": str(max_val) if max_val else None,
        "total_rows": total or 0,
        "symbols_with_data": sym_count,
        "symbols_in_universe": len(symbols),
        "table": table_label,
        "timeframe": timeframe,
        "zerodha_max_days": {
            "1 Min": 60, "5 Min": 100, "15 Min": 200,
            "1 Hour": 365, "Day": 2000,
        }.get(timeframe, 365),
    }


class BacktestRequest(BaseModel):
    start_date: Optional[str] = None   # YYYY-MM-DD, default 1 year ago
    end_date: Optional[str] = None     # YYYY-MM-DD, default today
    initial_capital: float = 100000.0
    position_size_pct: float = 10.0    # % of capital per trade
    max_open_trades: int = 5
    # Optional exit overrides; if omitted, strategy exit_config is used.
    sl_pct: Optional[float] = None
    tp_pct: Optional[float] = None
    tsl_pct: Optional[float] = None
    apply_slippage: Optional[bool] = None
    slippage_pct: Optional[float] = None


class StrategyDiscoveryRequest(BaseModel):
    timeframe: str = "Day"
    universe: str = "NIFTY50"
    max_candidates: int = Field(default=120, ge=10, le=500)
    top_n: int = Field(default=5, ge=1, le=20)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 100000.0
    position_size_pct: float = 10.0
    max_open_trades: int = 5
    max_per_family: int = Field(default=1, ge=1, le=10)
    fill_remaining: bool = False
    min_annual_return: float = Field(default=0.0, ge=0.0, le=500.0)
    optimize_exits: bool = False
    exit_optimize_on_top: int = Field(default=20, ge=1, le=200)
    sl_grid: List[float] = Field(default_factory=lambda: [1.5, 2.0, 2.5, 3.0, 4.0, 5.0])
    tp_grid: List[float] = Field(default_factory=lambda: [4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0])
    tsl_grid: List[float] = Field(default_factory=lambda: [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    max_exit_combos: int = Field(default=50, ge=1, le=500)
    save_top_strategies: bool = False


def _backtest_symbol(
    symbol: str,
    conditions: List[dict],
    direction: str,
    exit_config: dict,
    candles: List,
    initial_capital: float,
    position_size_pct: float,
    lookback: int = 60,
    date_attr: str = "date",
    timeframe: str = "Day",
    htf_timeframe: Optional[str] = None,
    htf_candles: Optional[List[Any]] = None,
    htf_date_attr: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Replay candles for one symbol using more realistic Streak-like rules:
    - signal is confirmed on the current bar close
    - entry happens on the *next* bar open
    - SL/TP/TSL are checked against candle high/low intrabar
    - optional higher-timeframe confirmation filters false positives
    - optional ATR sizing normalizes risk per trade
    """
    sl_pct = max(float(exit_config.get("sl_pct", 5.0) or 0.0), 0.0) / 100
    tp_pct = max(float(exit_config.get("tp_pct", 10.0) or 0.0), 0.0) / 100
    tsl_pct = max(float(exit_config.get("tsl_pct", 0.0) or 0.0), 0.0) / 100
    require_htf_confirm = bool(exit_config.get("require_htf_confirm"))
    resolved_htf_timeframe = htf_timeframe or _resolve_confirmation_timeframe(timeframe, exit_config)
    resolved_htf_date_attr = htf_date_attr or (TIMEFRAME_CANDLE_MAP.get(resolved_htf_timeframe, (None, "date", None))[1] if resolved_htf_timeframe else date_attr)
    use_atr_sizing = bool(exit_config.get("use_atr_sizing"))
    atr_period = max(int(exit_config.get("atr_period", 14) or 14), 2)
    apply_slippage = bool(exit_config.get("apply_slippage"))
    slippage_pct = max(float(exit_config.get("slippage_pct", 0.1) or 0.0), 0.0)

    trades: List[Dict[str, Any]] = []
    in_trade = False
    entry_price = 0.0
    entry_date = None
    entry_bar_idx = None
    peak_price = 0.0
    trough_price = float("inf")
    entry_quantity = 1
    entry_capital_used = 0.0
    entry_risk_amount = 0.0
    entry_atr = None
    entry_atr_stop_distance = None
    entry_position_sizing = "FIXED"
    entry_htf_confirmed = not require_htf_confirm
    entry_raw_price = 0.0

    for i in range(lookback, len(candles)):
        c = candles[i]
        bar_date = _bar_date_str(c, date_attr)
        bar_open = float(getattr(c, "open", c.close) or c.close)
        bar_high = float(getattr(c, "high", c.close) or c.close)
        bar_low = float(getattr(c, "low", c.close) or c.close)

        closes = [float(x.close) for x in candles[:i + 1]]
        highs = [float(x.high) for x in candles[:i + 1]]
        lows = [float(x.low) for x in candles[:i + 1]]
        volumes = [int(x.volume or 0) for x in candles[:i + 1]]

        if in_trade:
            exit_reason = None
            exit_price = None

            if direction == "BUY":
                peak_price = max(peak_price, bar_high)
                sl_level = entry_price * (1 - sl_pct) if sl_pct > 0 else None
                tp_level = entry_price * (1 + tp_pct) if tp_pct > 0 else None
                tsl_level = peak_price * (1 - tsl_pct) if tsl_pct > 0 and peak_price > entry_price else None

                sl_hit = sl_level is not None and bar_low <= sl_level
                tp_hit = tp_level is not None and bar_high >= tp_level
                tsl_hit = tsl_level is not None and bar_low <= tsl_level

                if sl_hit and bar_open <= sl_level:
                    exit_reason, exit_price = "SL", bar_open
                elif tp_hit and bar_open >= tp_level:
                    exit_reason, exit_price = "TP", bar_open
                elif tsl_hit and bar_open <= tsl_level:
                    exit_reason, exit_price = "TSL", bar_open
                else:
                    candidates = []
                    if sl_hit:
                        candidates.append(("SL", sl_level))
                    if tsl_hit:
                        candidates.append(("TSL", tsl_level))
                    if tp_hit:
                        candidates.append(("TP", tp_level))
                    if candidates:
                        exit_reason, exit_price = min(candidates, key=lambda item: item[1])

                # Conditional exit: fires only if SL/TP/TSL haven't already triggered
                if not exit_reason:
                    cond_exits = exit_config.get("exit_conditions") or []
                    if cond_exits and all(_evaluate_condition(ec, closes, highs, lows, volumes) for ec in cond_exits):
                        exit_reason, exit_price = "COND_EXIT", bar_open
            else:
                trough_price = min(trough_price, bar_low)
                sl_level = entry_price * (1 + sl_pct) if sl_pct > 0 else None
                tp_level = entry_price * (1 - tp_pct) if tp_pct > 0 else None
                tsl_level = trough_price * (1 + tsl_pct) if tsl_pct > 0 and trough_price < entry_price else None

                sl_hit = sl_level is not None and bar_high >= sl_level
                tp_hit = tp_level is not None and bar_low <= tp_level
                tsl_hit = tsl_level is not None and bar_high >= tsl_level

                if sl_hit and bar_open >= sl_level:
                    exit_reason, exit_price = "SL", bar_open
                elif tp_hit and bar_open <= tp_level:
                    exit_reason, exit_price = "TP", bar_open
                elif tsl_hit and bar_open >= tsl_level:
                    exit_reason, exit_price = "TSL", bar_open
                else:
                    candidates = []
                    if sl_hit:
                        candidates.append(("SL", sl_level))
                    if tsl_hit:
                        candidates.append(("TSL", tsl_level))
                    if tp_hit:
                        candidates.append(("TP", tp_level))
                    if candidates:
                        exit_reason, exit_price = max(candidates, key=lambda item: item[1])

                # Conditional exit: fires only if SL/TP/TSL haven't already triggered
                if not exit_reason:
                    cond_exits = exit_config.get("exit_conditions") or []
                    if cond_exits and all(_evaluate_condition(ec, closes, highs, lows, volumes) for ec in cond_exits):
                        exit_reason, exit_price = "COND_EXIT", bar_open

            if exit_reason and exit_price is not None:
                raw_exit_price = float(exit_price)
                effective_exit_price = _apply_slippage(raw_exit_price, direction, is_entry=False, slippage_pct=slippage_pct) if apply_slippage else round(raw_exit_price, 2)
                slippage_cost = 0.0
                if apply_slippage:
                    slippage_cost = (abs(entry_price - entry_raw_price) + abs(effective_exit_price - raw_exit_price)) * entry_quantity

                if direction == "BUY":
                    pnl_amount = (effective_exit_price - entry_price) * entry_quantity
                else:
                    pnl_amount = (entry_price - effective_exit_price) * entry_quantity
                pnl_pct = ((pnl_amount / entry_capital_used) * 100) if entry_capital_used > 0 else 0.0

                trades.append({
                    "entry_date": entry_date,
                    "exit_date": bar_date,
                    "entry_price": round(entry_price, 2),
                    "entry_price_raw": round(entry_raw_price, 2),
                    "exit_price": round(effective_exit_price, 2),
                    "exit_price_raw": round(raw_exit_price, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amount": round(pnl_amount, 2),
                    "slippage_cost": round(slippage_cost, 2),
                    "slippage_pct": round(slippage_pct, 3) if apply_slippage else 0.0,
                    "exit_reason": exit_reason,
                    "holding_bars": i - entry_bar_idx if entry_bar_idx is not None else 0,
                    "quantity": entry_quantity,
                    "capital_used": round(entry_capital_used, 2),
                    "risk_amount": round(entry_risk_amount, 2),
                    "atr": entry_atr,
                    "atr_stop_distance": entry_atr_stop_distance,
                    "position_sizing": entry_position_sizing,
                    "htf_confirmed": entry_htf_confirmed,
                    "htf_timeframe": resolved_htf_timeframe,
                })
                in_trade = False
                continue

        if not in_trade:
            all_met = True
            for cond in conditions:
                if not _evaluate_condition(cond, closes, highs, lows, volumes):
                    all_met = False
                    break

            htf_confirmed = not require_htf_confirm
            if all_met and require_htf_confirm:
                if resolved_htf_timeframe and htf_candles:
                    reference_value = getattr(c, date_attr)
                    htf_slice = _slice_candles_up_to(htf_candles, resolved_htf_date_attr, reference_value)
                    htf_confirmed = _conditions_match_on_candles(conditions, htf_slice)
                else:
                    htf_confirmed = False
                all_met = all_met and htf_confirmed

            # Enter on the next bar open after the signal bar closes.
            if all_met and i + 1 < len(candles):
                next_bar = candles[i + 1]
                next_open = float(getattr(next_bar, "open", next_bar.close) or next_bar.close)
                atr_value = TechnicalIndicators.calculate_atr(highs, lows, closes, atr_period) if len(closes) >= atr_period else None
                sizing = _recommended_position_size(
                    entry_price=next_open,
                    available_capital=initial_capital,
                    position_size_pct=position_size_pct,
                    exit_config=exit_config,
                    atr_value=atr_value if use_atr_sizing else None,
                )

                in_trade = True
                entry_raw_price = next_open
                entry_price = _apply_slippage(next_open, direction, is_entry=True, slippage_pct=slippage_pct) if apply_slippage else round(next_open, 2)
                entry_date = _bar_date_str(next_bar, date_attr)
                entry_bar_idx = i + 1
                peak_price = next_open
                trough_price = next_open
                entry_quantity = int(sizing["quantity"])
                entry_capital_used = float(sizing["capital_used"])
                entry_risk_amount = float(sizing["risk_amount"])
                entry_atr = sizing.get("atr")
                entry_atr_stop_distance = sizing.get("atr_stop_distance")
                entry_position_sizing = str(sizing.get("position_sizing") or "FIXED")
                entry_htf_confirmed = htf_confirmed

    if in_trade and len(candles) > 0:
        last = candles[-1]
        raw_last_close = float(getattr(last, "close", 0.0) or 0.0)
        effective_last_close = _apply_slippage(raw_last_close, direction, is_entry=False, slippage_pct=slippage_pct) if apply_slippage else round(raw_last_close, 2)
        slippage_cost = 0.0
        if apply_slippage:
            slippage_cost = (abs(entry_price - entry_raw_price) + abs(effective_last_close - raw_last_close)) * entry_quantity
        if direction == "BUY":
            pnl_amount = (effective_last_close - entry_price) * entry_quantity
        else:
            pnl_amount = (entry_price - effective_last_close) * entry_quantity
        pnl_pct = ((pnl_amount / entry_capital_used) * 100) if entry_capital_used > 0 else 0.0
        trades.append({
            "entry_date": entry_date,
            "exit_date": _bar_date_str(last, date_attr),
            "entry_price": round(entry_price, 2),
            "entry_price_raw": round(entry_raw_price, 2),
            "exit_price": round(effective_last_close, 2),
            "exit_price_raw": round(raw_last_close, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_amount": round(pnl_amount, 2),
            "slippage_cost": round(slippage_cost, 2),
            "slippage_pct": round(slippage_pct, 3) if apply_slippage else 0.0,
            "exit_reason": "OPEN",
            "holding_bars": len(candles) - 1 - (entry_bar_idx or 0),
            "quantity": entry_quantity,
            "capital_used": round(entry_capital_used, 2),
            "risk_amount": round(entry_risk_amount, 2),
            "atr": entry_atr,
            "atr_stop_distance": entry_atr_stop_distance,
            "position_sizing": entry_position_sizing,
            "htf_confirmed": entry_htf_confirmed,
            "htf_timeframe": resolved_htf_timeframe,
        })

    total_trades = len(trades)
    winners = [t for t in trades if t["pnl_pct"] > 0]
    losers = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
    avg_pnl = sum(t["pnl_pct"] for t in trades) / total_trades if total_trades > 0 else 0
    total_pnl = sum(t["pnl_pct"] for t in trades)
    avg_win = sum(t["pnl_pct"] for t in winners) / len(winners) if winners else 0
    avg_loss = sum(t["pnl_pct"] for t in losers) / len(losers) if losers else 0
    max_win = max((t["pnl_pct"] for t in trades), default=0)
    max_loss = min((t["pnl_pct"] for t in trades), default=0)
    avg_holding = sum(t.get("holding_bars", 0) for t in trades) / total_trades if total_trades > 0 else 0
    total_slippage_cost = sum(float(t.get("slippage_cost") or 0.0) for t in trades)

    return {
        "symbol": symbol,
        "total_trades": total_trades,
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(win_rate, 1),
        "total_pnl_pct": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "max_win_pct": round(max_win, 2),
        "max_loss_pct": round(max_loss, 2),
        "avg_holding_bars": round(avg_holding, 1),
        "total_slippage_cost": round(total_slippage_cost, 2),
        "trades": trades,
    }


def _run_backtest_for_strategy_payload(
    strategy: Dict[str, Any],
    req: BacktestRequest,
    db: Session,
) -> Dict[str, Any]:
    """Run the condition-scanner backtest for an in-memory strategy payload."""
    strategy_id = strategy.get("id")
    conditions = strategy.get("entry_conditions", [])
    direction = strategy.get("direction", "BUY")
    exit_config = dict(strategy.get("exit_config", {}) or {})
    universe = strategy.get("universe", "NIFTY50")
    timeframe = strategy.get("timeframe", "Day")
    required_bars = _required_history_bars(conditions)

    # Allow request-level exit overrides from UI backtest form.
    if req.sl_pct is not None:
        exit_config["sl_pct"] = req.sl_pct
    if req.tp_pct is not None:
        exit_config["tp_pct"] = req.tp_pct
    if req.tsl_pct is not None:
        exit_config["tsl_pct"] = req.tsl_pct
    if req.apply_slippage is not None:
        exit_config["apply_slippage"] = req.apply_slippage
    if req.slippage_pct is not None:
        exit_config["slippage_pct"] = req.slippage_pct

    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe)
    if not candle_info:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported timeframe '{timeframe}'. Supported: {list(TIMEFRAME_CANDLE_MAP.keys())}",
        )
    CandleModel, date_attr, table_label = candle_info
    date_col = getattr(CandleModel, date_attr)
    resolved_htf_timeframe = _resolve_confirmation_timeframe(timeframe, exit_config)
    htf_candle_info = TIMEFRAME_CANDLE_MAP.get(resolved_htf_timeframe) if resolved_htf_timeframe else None

    if req.end_date:
        end_date = datetime.strptime(req.end_date, "%Y-%m-%d").date()
    else:
        end_date = datetime.now().date()

    if req.start_date:
        start_date = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    else:
        start_date = end_date - timedelta(days=30 if date_attr == "timestamp" else 365)

    if date_attr == "timestamp":
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())
        warmup_days = max(30, math.ceil(required_bars / 8) * 5)
        lookback_start_dt = datetime.combine(
            start_date - timedelta(days=warmup_days), datetime.min.time()
        )
    else:
        start_dt = start_date
        end_dt = end_date
        warmup_days = max(180, required_bars * 3)
        lookback_start_dt = start_date - timedelta(days=warmup_days)

    instruments = strategy.get("instruments", [])
    symbols = instruments if instruments else get_symbols(universe)

    symbol_results = []
    total_candles_used = 0
    symbols_with_data = 0

    for symbol in symbols:
        candles = (
            db.query(CandleModel)
            .filter(
                CandleModel.symbol == symbol,
                date_col >= lookback_start_dt,
                date_col <= end_dt,
            )
            .order_by(date_col)
            .all()
        )

        min_bars = max(required_bars, 60 if date_attr == "date" else 40)
        if len(candles) < min_bars:
            continue

        total_candles_used += len(candles)
        symbols_with_data += 1

        start_idx = 0
        for idx, candle in enumerate(candles):
            bar_d = _get_bar_date(candle, date_attr)
            if bar_d >= start_date:
                start_idx = idx
                break

        lookback = max(start_idx, min_bars)

        htf_candles = None
        htf_date_attr = None
        if bool(exit_config.get("require_htf_confirm")) and htf_candle_info:
            HtfModel, htf_date_attr, _htf_table = htf_candle_info
            htf_date_col = getattr(HtfModel, htf_date_attr)
            htf_window_start = lookback_start_dt.date() if htf_date_attr == "date" and hasattr(lookback_start_dt, "date") else lookback_start_dt
            htf_window_end = end_dt.date() if htf_date_attr == "date" and hasattr(end_dt, "date") else end_dt
            htf_candles = (
                db.query(HtfModel)
                .filter(
                    HtfModel.symbol == symbol,
                    htf_date_col >= htf_window_start,
                    htf_date_col <= htf_window_end,
                )
                .order_by(htf_date_col)
                .all()
            )

        result = _backtest_symbol(
            symbol=symbol,
            conditions=conditions,
            direction=direction,
            exit_config=exit_config,
            candles=candles,
            initial_capital=req.initial_capital,
            position_size_pct=req.position_size_pct,
            lookback=lookback,
            date_attr=date_attr,
            timeframe=timeframe,
            htf_timeframe=resolved_htf_timeframe,
            htf_candles=htf_candles,
            htf_date_attr=htf_date_attr,
        )

        if result["total_trades"] > 0:
            symbol_results.append(result)

    if symbols_with_data == 0:
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.get("name", ""),
            "direction": direction,
            "universe": universe,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "initial_capital": req.initial_capital,
            "final_capital": req.initial_capital,
            "error": f"No {timeframe} candle data found in table '{table_label}'. Load {timeframe} candles first or change strategy timeframe.",
            "summary": {
                "total_trades": 0, "winners": 0, "losers": 0, "win_rate": 0,
                "total_return_pct": 0, "annual_return_pct": 0, "max_drawdown_pct": 0,
                "profit_factor": 0, "sharpe_ratio": 0, "avg_pnl_pct": 0,
                "avg_win_pct": 0, "avg_loss_pct": 0, "max_win_pct": 0, "max_loss_pct": 0,
                "symbols_traded": 0, "symbols_scanned": len(symbols),
                "total_candles_used": 0,
                "data_source": f"{table_label} (NO DATA)",
                "timeframe": timeframe,
            },
            "equity_curve": [],
            "per_symbol": [],
            "all_trades": [],
        }

    all_trades = []
    for sr in symbol_results:
        for trade in sr["trades"]:
            all_trades.append({**trade, "symbol": sr["symbol"]})

    all_trades.sort(key=lambda t: t.get("entry_date", ""))

    total_trades = len(all_trades)
    winners = [t for t in all_trades if t["pnl_pct"] > 0]
    losers = [t for t in all_trades if t["pnl_pct"] <= 0]
    total_slippage_cost = sum(float(t.get("slippage_cost") or 0.0) for t in all_trades)

    capital = req.initial_capital
    curves = [{"date": str(start_date), "equity": capital}]
    for trade in all_trades:
        trade_capital = float(trade.get("capital_used") or (capital * (req.position_size_pct / 100)))
        pnl_amount = float(trade.get("pnl_amount") or (trade_capital * (trade["pnl_pct"] / 100)))
        capital += pnl_amount
        curves.append({
            "date": trade.get("exit_date", trade.get("entry_date", "")),
            "equity": round(capital, 2),
            "symbol": trade.get("symbol", ""),
            "pnl_pct": trade["pnl_pct"],
            "pnl_amount": round(pnl_amount, 2),
        })

    peak_equity = req.initial_capital
    max_dd = 0.0
    for point in curves:
        eq = point["equity"]
        if eq > peak_equity:
            peak_equity = eq
        dd = ((peak_equity - eq) / peak_equity) * 100 if peak_equity > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_return = ((capital - req.initial_capital) / req.initial_capital) * 100
    days_span = (end_date - start_date).days or 1
    _tr = total_return / 100.0
    annual_return = ((1 + _tr) ** (365.0 / days_span) - 1) * 100 if _tr > -1 else -100.0

    gross_profit = sum(t["pnl_pct"] for t in winners)
    gross_loss = abs(sum(t["pnl_pct"] for t in losers))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    if total_trades > 1:
        returns = [t["pnl_pct"] for t in all_trades]
        mean_r = sum(returns) / len(returns)
        std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1))
        sharpe = (mean_r / std_r) * math.sqrt(252 / max(1, days_span / total_trades)) if std_r > 0 else 0
    else:
        sharpe = 0

    walk_forward = _run_walk_forward_analysis(strategy, req, db, start_date, end_date)

    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy.get("name", ""),
        "direction": direction,
        "universe": universe,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "initial_capital": req.initial_capital,
        "final_capital": round(capital, 2),
        "summary": {
            "total_trades": total_trades,
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": round(len(winners) / total_trades * 100, 1) if total_trades > 0 else 0,
            "total_return_pct": round(total_return, 2),
            "annual_return_pct": round(annual_return, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999,
            "sharpe_ratio": round(sharpe, 2),
            "avg_pnl_pct": round(sum(t["pnl_pct"] for t in all_trades) / total_trades, 2) if total_trades > 0 else 0,
            "avg_win_pct": round(sum(t["pnl_pct"] for t in winners) / len(winners), 2) if winners else 0,
            "avg_loss_pct": round(sum(t["pnl_pct"] for t in losers) / len(losers), 2) if losers else 0,
            "max_win_pct": round(max((t["pnl_pct"] for t in all_trades), default=0), 2),
            "max_loss_pct": round(min((t["pnl_pct"] for t in all_trades), default=0), 2),
            "symbols_traded": len(symbol_results),
            "symbols_scanned": len(symbols),
            "total_candles_used": total_candles_used,
            "data_source": f"{table_label} (real DB data)",
            "timeframe": timeframe,
            "htf_confirmation": bool(exit_config.get("require_htf_confirm")),
            "htf_timeframe": resolved_htf_timeframe,
            "position_sizing": "ATR" if bool(exit_config.get("use_atr_sizing")) else "FIXED",
            "risk_per_trade_pct": float(exit_config.get("risk_per_trade_pct", 1.0) or 1.0),
            "atr_period": int(exit_config.get("atr_period", 14) or 14),
            "atr_multiplier": float(exit_config.get("atr_multiplier", 1.5) or 1.5),
            "slippage_enabled": bool(exit_config.get("apply_slippage")),
            "slippage_pct": float(exit_config.get("slippage_pct", 0.0) or 0.0),
            "total_slippage_cost": round(total_slippage_cost, 2),
            "walk_forward_enabled": bool(exit_config.get("walk_forward_enabled")),
            "walk_forward_pass_rate_pct": float((walk_forward or {}).get("pass_rate_pct", 0.0) or 0.0),
        },
        "walk_forward": walk_forward,
        "equity_curve": curves,
        "per_symbol": [
            {
                "symbol": sr["symbol"],
                "total_trades": sr["total_trades"],
                "win_rate": sr["win_rate"],
                "total_pnl_pct": sr["total_pnl_pct"],
                "avg_pnl_pct": sr["avg_pnl_pct"],
                "max_win_pct": sr["max_win_pct"],
                "max_loss_pct": sr["max_loss_pct"],
                "avg_holding_bars": sr["avg_holding_bars"],
            }
            for sr in sorted(symbol_results, key=lambda x: x["total_pnl_pct"], reverse=True)
        ],
        "all_trades": [
            {
                "symbol": t.get("symbol", ""),
                "entry_date": t["entry_date"],
                "exit_date": t["exit_date"],
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
                "pnl_pct": t["pnl_pct"],
                "exit_reason": t["exit_reason"],
                "holding_bars": t.get("holding_bars", 0),
                "quantity": t.get("quantity"),
                "capital_used": t.get("capital_used"),
                "pnl_amount": t.get("pnl_amount"),
                "atr": t.get("atr"),
                "position_sizing": t.get("position_sizing"),
                "htf_confirmed": t.get("htf_confirmed"),
                "htf_timeframe": t.get("htf_timeframe"),
            }
            for t in all_trades
        ],
    }


def _run_walk_forward_analysis(
    strategy: Dict[str, Any],
    req: BacktestRequest,
    db: Session,
    start_date: dt_date,
    end_date: dt_date,
) -> Dict[str, Any]:
    exit_config = dict(strategy.get("exit_config", {}) or {})
    if not bool(exit_config.get("walk_forward_enabled")):
        return {
            "enabled": False,
            "train_pct": float(exit_config.get("walk_forward_train_pct", 67.0) or 67.0),
            "windows": [],
            "pass_rate_pct": 0.0,
            "consistency_score": 0.0,
            "avg_out_of_sample_return_pct": 0.0,
        }

    requested_windows = max(int(exit_config.get("walk_forward_windows", 3) or 3), 1)
    train_pct = min(max(float(exit_config.get("walk_forward_train_pct", 67.0) or 67.0), 50.0), 90.0)
    total_days = max((end_date - start_date).days + 1, 1)
    segment_days = max(total_days // requested_windows, 14)

    wf_strategy = dict(strategy)
    wf_exit = dict(exit_config)
    wf_exit["walk_forward_enabled"] = False
    wf_strategy["exit_config"] = wf_exit

    windows: List[Dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date and len(windows) < requested_windows:
        segment_end = min(end_date, cursor + timedelta(days=segment_days - 1))
        span_days = max((segment_end - cursor).days + 1, 1)
        train_days = max(1, int(span_days * (train_pct / 100.0)))
        if train_days >= span_days:
            train_days = span_days - 1
        if train_days <= 0:
            break

        train_start = cursor
        train_end = train_start + timedelta(days=train_days - 1)
        test_start = train_end + timedelta(days=1)
        test_end = segment_end
        if test_start > test_end:
            break

        train_req = BacktestRequest(
            start_date=str(train_start),
            end_date=str(train_end),
            initial_capital=req.initial_capital,
            position_size_pct=req.position_size_pct,
            max_open_trades=req.max_open_trades,
            sl_pct=req.sl_pct,
            tp_pct=req.tp_pct,
            tsl_pct=req.tsl_pct,
            apply_slippage=req.apply_slippage,
            slippage_pct=req.slippage_pct,
        )
        test_req = BacktestRequest(
            start_date=str(test_start),
            end_date=str(test_end),
            initial_capital=req.initial_capital,
            position_size_pct=req.position_size_pct,
            max_open_trades=req.max_open_trades,
            sl_pct=req.sl_pct,
            tp_pct=req.tp_pct,
            tsl_pct=req.tsl_pct,
            apply_slippage=req.apply_slippage,
            slippage_pct=req.slippage_pct,
        )

        train_result = _run_backtest_for_strategy_payload(wf_strategy, train_req, db)
        test_result = _run_backtest_for_strategy_payload(wf_strategy, test_req, db)
        train_summary = train_result.get("summary") or {}
        test_summary = test_result.get("summary") or {}
        out_return = float(test_summary.get("total_return_pct") or 0.0)
        train_return = float(train_summary.get("total_return_pct") or 0.0)
        passed = bool((test_summary.get("total_trades") or 0) > 0 and out_return >= 0)

        windows.append({
            "train_start": str(train_start),
            "train_end": str(train_end),
            "test_start": str(test_start),
            "test_end": str(test_end),
            "train_return_pct": round(train_return, 2),
            "out_of_sample_return_pct": round(out_return, 2),
            "out_of_sample_trades": int(test_summary.get("total_trades") or 0),
            "out_of_sample_win_rate": float(test_summary.get("win_rate") or 0.0),
            "max_drawdown_pct": float(test_summary.get("max_drawdown_pct") or 0.0),
            "passed": passed,
            "overfit_gap_pct": round(train_return - out_return, 2),
        })
        cursor = segment_end + timedelta(days=1)

    pass_count = sum(1 for row in windows if row.get("passed"))
    pass_rate_pct = (pass_count / len(windows) * 100.0) if windows else 0.0
    avg_oos_return = sum(float(row.get("out_of_sample_return_pct") or 0.0) for row in windows) / len(windows) if windows else 0.0

    return {
        "enabled": True,
        "train_pct": round(train_pct, 2),
        "windows": windows,
        "pass_rate_pct": round(pass_rate_pct, 1),
        "consistency_score": round(pass_rate_pct, 1),
        "avg_out_of_sample_return_pct": round(avg_oos_return, 2),
    }


@router.post("/backtest/{strategy_id}")
async def run_backtest(
    strategy_id: int,
    req: BacktestRequest = BacktestRequest(),
    db: Session = Depends(get_db),
):
    """
    Backtest a condition-based strategy across its universe.
    Uses the candle timeframe matching the strategy (1m/5m/15m/1h/daily),
    evaluates entry conditions bar-by-bar, and applies SL/TP/TSL exits.
    Returns per-symbol and aggregate results.
    """
    row = _get_strategy_or_404(db, strategy_id)
    result = _run_backtest_for_strategy_payload(row.to_dict(), req, db)

    # Save backtest result to its own table
    bt = ConditionStrategyBacktest(
        strategy_id=strategy_id,
        strategy_name=row.name,
        start_date=req.start_date or "",
        end_date=req.end_date or "",
        initial_capital=req.initial_capital,
        final_capital=result.get("final_capital"),
        result=result,
    )
    db.add(bt)
    db.flush()

    row.last_backtest_at = now_ist()
    row.last_backtest_id = bt.id
    db.commit()

    return result


@router.post("/discover")
async def discover_strategies(
    req: StrategyDiscoveryRequest,
    db: Session = Depends(get_db),
):
    """Generate many condition strategies, backtest them, and return the top-ranked ones."""
    if req.timeframe not in TIMEFRAME_CANDLE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported timeframe '{req.timeframe}'. Supported: {list(TIMEFRAME_CANDLE_MAP.keys())}",
        )

    backtest_req = BacktestRequest(
        start_date=req.start_date,
        end_date=req.end_date,
        initial_capital=req.initial_capital,
        position_size_pct=req.position_size_pct,
        max_open_trades=req.max_open_trades,
    )

    candidates = generate_candidate_strategies(
        timeframe=req.timeframe,
        universe=req.universe,
        max_candidates=req.max_candidates,
    )

    ranked_results: List[Dict[str, Any]] = []
    for candidate in candidates:
        result = _run_backtest_for_strategy_payload(candidate, backtest_req, db)
        summary = result.get("summary") or {}
        score = score_backtest_summary(summary)
        ranked_results.append(
            {
                "strategy": candidate,
                "summary": summary,
                "score": score,
                "final_capital": result.get("final_capital"),
                "error": result.get("error"),
            }
        )

    ranked_results.sort(
        key=lambda item: (
            item["score"],
            float((item.get("summary") or {}).get("total_return_pct") or 0.0),
            float((item.get("summary") or {}).get("sharpe_ratio") or 0.0),
        ),
        reverse=True,
    )

    exit_optimization = {
        "enabled": bool(req.optimize_exits),
        "base_tested": len(ranked_results),
        "shortlisted": 0,
        "combos_per_base": 0,
        "variants_tested": 0,
    }

    if req.optimize_exits and ranked_results:
        shortlisted_items = ranked_results[: req.exit_optimize_on_top]
        shortlisted_strategies = [item["strategy"] for item in shortlisted_items]
        exit_combos = generate_exit_param_combinations(
            sl_values=req.sl_grid,
            tp_values=req.tp_grid,
            tsl_values=req.tsl_grid,
            max_combos=req.max_exit_combos,
        )
        variant_strategies = expand_strategies_with_exit_variants(
            shortlisted_strategies,
            exit_combos=exit_combos,
        )

        ranked_variants: List[Dict[str, Any]] = []
        for variant in variant_strategies:
            result = _run_backtest_for_strategy_payload(variant, backtest_req, db)
            summary = result.get("summary") or {}
            score = score_backtest_summary(summary)
            ranked_variants.append(
                {
                    "strategy": variant,
                    "summary": summary,
                    "score": score,
                    "final_capital": result.get("final_capital"),
                    "error": result.get("error"),
                }
            )

        ranked_variants.sort(
            key=lambda item: (
                item["score"],
                float((item.get("summary") or {}).get("annual_return_pct") or 0.0),
                -float((item.get("summary") or {}).get("max_drawdown_pct") or 0.0),
                float((item.get("summary") or {}).get("sharpe_ratio") or 0.0),
            ),
            reverse=True,
        )
        ranked_results = ranked_variants
        exit_optimization = {
            "enabled": True,
            "base_tested": len(shortlisted_items),
            "shortlisted": len(shortlisted_strategies),
            "combos_per_base": len(exit_combos),
            "variants_tested": len(ranked_variants),
        }

    if req.min_annual_return > 0:
        ranked_results = [
            item
            for item in ranked_results
            if float((item.get("summary") or {}).get("annual_return_pct") or 0.0) >= req.min_annual_return
        ]

    top_results = select_diverse_top(
        ranked_results,
        top_n=req.top_n,
        max_per_family=req.max_per_family,
        fill_remaining=req.fill_remaining,
    )
    saved = []
    if req.save_top_strategies and top_results:
        existing_names = {
            name for (name,) in db.query(ConditionStrategy.name).all()
        }

        for rank, item in enumerate(top_results, start=1):
            strategy = dict(item["strategy"])
            base_name = strategy["name"]
            save_name = base_name
            suffix = 2
            while save_name in existing_names:
                save_name = f"{base_name} #{suffix}"
                suffix += 1

            description = (
                f"Auto-discovered candidate ranked #{rank}. "
                f"Score={item['score']}, Return={item['summary'].get('total_return_pct', 0)}%, "
                f"Sharpe={item['summary'].get('sharpe_ratio', 0)}"
            )
            new_row = ConditionStrategy(
                name=save_name,
                description=description,
                strategy_type=strategy.get("strategy_type", "Equity Swing"),
                direction=strategy.get("direction", "BUY"),
                timeframe=strategy.get("timeframe", "1 Hour"),
                universe=strategy.get("universe", "NIFTY50"),
                instruments=strategy.get("instruments", []),
                entry_conditions=strategy.get("entry_conditions", []),
                exit_config=strategy.get("exit_config", {}),
                is_active=True,
                auto_scan_enabled=False,
                auto_amount=10000.0,
            )
            db.add(new_row)
            db.flush()

            # Also persist the backtest result so it shows up in the UI
            bt = ConditionStrategyBacktest(
                strategy_id=new_row.id,
                strategy_name=save_name,
                start_date=req.start_date or "",
                end_date=req.end_date or "",
                initial_capital=req.initial_capital,
                final_capital=item.get("final_capital"),
                result={**item.get("summary", {}), "strategy": strategy, "summary": item.get("summary")},
            )
            db.add(bt)
            db.flush()
            new_row.last_backtest_at = now_ist()
            new_row.last_backtest_id = bt.id

            existing_names.add(save_name)
            saved.append({"id": new_row.id, "name": save_name, "rank": rank})

        db.commit()

    return {
        "generated_count": len(candidates),
        "tested_count": len(ranked_results),
        "top_n": req.top_n,
        "timeframe": req.timeframe,
        "universe": req.universe,
        "min_annual_return": req.min_annual_return,
        "fill_remaining": req.fill_remaining,
        "exit_optimization": exit_optimization,
        "top_strategies": [
            {
                "rank": index,
                "score": item["score"],
                "strategy": item["strategy"],
                "family": strategy_family(item["strategy"]),
                "summary": item["summary"],
                "final_capital": item["final_capital"],
                "error": item["error"],
            }
            for index, item in enumerate(top_results, start=1)
        ],
        "saved_strategies": saved,
    }


# ── Auto-scan scheduler endpoints ──────────────────────────────────────────

@router.post("/scheduler/start/{strategy_id}")
async def start_auto_scan(strategy_id: int, db: Session = Depends(get_db)):
    """Enable auto-scanning for a strategy. Starts the background scheduler."""
    row = _get_strategy_or_404(db, strategy_id)
    row.auto_scan_enabled = True
    db.commit()

    from app.core.condition_scanner_scheduler import (
        ensure_scanner_scheduler, _get_interval_for_timeframe,
    )
    timeframe = row.timeframe or "1 Hour"
    active = db.query(ConditionStrategy).filter_by(auto_scan_enabled=True).all()
    intervals = [_get_interval_for_timeframe(s.timeframe or "1 Hour") for s in active]
    min_interval = max(min(intervals), 60) if intervals else 300
    ensure_scanner_scheduler(min_interval)

    return {
        "message": f"Auto-scan enabled for '{row.name}'",
        "interval_sec": min_interval,
        "strategy_timeframe": timeframe,
        "active_strategies": len(active),
    }


@router.post("/scheduler/stop/{strategy_id}")
async def stop_auto_scan(strategy_id: int, db: Session = Depends(get_db)):
    """Disable auto-scanning for a strategy. Removes scheduler if no active strategies."""
    row = _get_strategy_or_404(db, strategy_id)
    row.auto_scan_enabled = False
    db.commit()

    from app.core.condition_scanner_scheduler import (
        ensure_scanner_scheduler, remove_scanner_scheduler,
        _get_interval_for_timeframe,
    )
    active = db.query(ConditionStrategy).filter_by(auto_scan_enabled=True).all()
    if not active:
        remove_scanner_scheduler()
        return {"message": "Auto-scan disabled. No active strategies — scheduler stopped."}
    else:
        intervals = [_get_interval_for_timeframe(s.timeframe or "1 Hour") for s in active]
        min_interval = max(min(intervals), 60)
        ensure_scanner_scheduler(min_interval)
        return {
            "message": f"Auto-scan disabled for '{row.name}'",
            "remaining_active": len(active),
        }


@router.get("/scheduler/status")
async def get_auto_scan_status():
    """Get the current auto-scan scheduler status."""
    from app.core.condition_scanner_scheduler import get_scheduler_status
    return get_scheduler_status()


@router.put("/scheduler/amount/{strategy_id}")
async def set_auto_amount(strategy_id: int, amount: float = Query(default=10000, ge=100, le=10000000), db: Session = Depends(get_db)):
    """Set the auto-execution amount (₹) for a strategy. Quantity is calculated as floor(amount / stock_price)."""
    row = _get_strategy_or_404(db, strategy_id)
    row.auto_amount = amount
    db.commit()
    return {"message": f"Auto amount set to ₹{amount:,.0f}", "strategy_id": strategy_id}


# ── Candle backfill endpoints ──────────────────────────────────────────────

@router.post("/backfill-candles/{strategy_id}")
async def backfill_candles_for_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
):
    """
    Load candle data for all symbols in a strategy's universe,
    using the correct timeframe.  Fetches from Zerodha historical API.
    """
    row = _get_strategy_or_404(db, strategy_id)
    timeframe = row.timeframe or "Day"
    universe = row.universe or "NIFTY50"
    symbols = get_symbols(universe)

    from app.core.market.candles import TIMEFRAME_FETCHER, aggregate_15m_to_1h
    fetcher = TIMEFRAME_FETCHER.get(timeframe)
    if not fetcher:
        raise HTTPException(status_code=400, detail=f"No fetcher for timeframe '{timeframe}'")

    success = 0
    failed = 0
    errors = []

    for symbol in symbols:
        try:
            fetcher(db, symbol)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(f"{symbol}: {str(e)[:80]}")
            logger.warning(f"Backfill {timeframe} {symbol} failed: {e}")

    # If 1h and we have 15m data, also aggregate as fallback
    aggregated = 0
    if timeframe == "1 Hour":
        for symbol in symbols:
            try:
                aggregate_15m_to_1h(db, symbol)
                aggregated += 1
            except Exception:
                pass

    # Count total rows after backfill
    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe)
    total_rows = 0
    if candle_info:
        CandleModel = candle_info[0]
        total_rows = db.query(CandleModel).count()

    return {
        "message": f"Backfill complete for {timeframe} candles",
        "timeframe": timeframe,
        "universe": universe,
        "symbols_attempted": len(symbols),
        "success": success,
        "failed": failed,
        "aggregated_from_15m": aggregated if timeframe == "1 Hour" else None,
        "total_rows_in_table": total_rows,
        "errors": errors[:10],  # first 10 errors
    }


@router.post("/backfill-candles")
async def backfill_candles_manual(
    timeframe: str = Query(default="1 Hour", description="Timeframe: 1 Min, 5 Min, 15 Min, 1 Hour, Day"),
    symbols: str = Query(default="", description="Comma-separated symbols, or empty for NIFTY50"),
    days: int = Query(default=30, ge=1, le=900, description="Number of days to fetch"),
    db: Session = Depends(get_db),
):
    """
    Manually backfill candle data for specific symbols and timeframe.
    """
    from app.core.market.candles import TIMEFRAME_FETCHER, aggregate_15m_to_1h

    fetcher = TIMEFRAME_FETCHER.get(timeframe)
    if not fetcher:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown timeframe '{timeframe}'. Use: {list(TIMEFRAME_FETCHER.keys())}",
        )

    if symbols.strip():
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        sym_list = get_symbols("NIFTY50")

    success = 0
    failed = 0
    errors = []

    for symbol in sym_list:
        try:
            fetcher(db, symbol, days=days)
            success += 1
        except Exception as e:
            failed += 1
            errors.append(f"{symbol}: {str(e)[:80]}")

    # 1h fallback: aggregate from 15m
    aggregated = 0
    if timeframe == "1 Hour":
        for symbol in sym_list:
            try:
                aggregate_15m_to_1h(db, symbol)
                aggregated += 1
            except Exception:
                pass

    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe)
    total_rows = 0
    if candle_info:
        total_rows = db.query(candle_info[0]).count()

    return {
        "message": f"Backfill complete",
        "timeframe": timeframe,
        "symbols_attempted": len(sym_list),
        "days": days,
        "success": success,
        "failed": failed,
        "aggregated_from_15m": aggregated if timeframe == "1 Hour" else None,
        "total_rows_in_table": total_rows,
        "errors": errors[:10],
    }