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
    exit_conditions: List[Condition] = []

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

    else:
        logger.warning(f"Unknown indicator: {indicator}")
        return None


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
    Could be a plain number ("20") or an indicator ref ("Close(0)").
    """
    v = value_str.strip()

    # Plain number
    try:
        return float(v)
    except ValueError:
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
    else:
        logger.warning(f"Unknown comparator: {comparator}")
        return False


def _scan_symbol(
    symbol: str,
    conditions: List[dict],
    db: Session,
    ltp: Optional[float] = None,
    volume: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Scan a single symbol against entry conditions.
    Uses real daily candles from DB if available.
    Returns match info or None.
    """
    # Fetch real candles
    candles = (
        db.query(CandleDaily)
        .filter(CandleDaily.symbol == symbol)
        .order_by(desc(CandleDaily.date))
        .limit(200)
        .all()
    )

    if len(candles) < 50:
        return None

    candles = candles[::-1]  # chronological

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [int(c.volume or 0) for c in candles]

    # Append today's live data if available
    if ltp and ltp > 0:
        closes.append(ltp)
        highs.append(ltp * 1.005)
        lows.append(ltp * 0.995)
        volumes.append(volume if volume and volume > 0 else volumes[-1])

    # All conditions must pass (AND logic)
    for cond in conditions:
        if not _evaluate_condition(cond, closes, highs, lows, volumes):
            return None

    # Compute indicator values for display
    indicator_values = {}
    for cond in conditions:
        ind = cond["indicator"]
        val = _compute_indicator(ind, cond.get("params", {}), closes, highs, lows, volumes)
        if val is not None:
            indicator_values[ind] = round(val, 2)

    change_pct = 0.0
    if len(closes) >= 2 and closes[-2] != 0:
        change_pct = ((closes[-1] - closes[-2]) / closes[-2]) * 100

    return {
        "symbol": symbol,
        "ltp": round(closes[-1], 2),
        "change_percent": round(change_pct, 2),
        "indicators": indicator_values,
        "conditions_met": len(conditions),
        "timestamp": datetime.now().isoformat(),
    }


# ── Pre-built strategy templates ────────────────────────────────────────────

PREBUILT_STRATEGIES: Dict[str, dict] = {
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
        ],
        "comparators": [
            {"id": "crosses_above", "label": "crosses above"},
            {"id": "crosses_below", "label": "crosses below"},
            {"id": "higher_than", "label": "higher than"},
            {"id": "lower_than", "label": "lower than"},
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
    """List all user strategies."""
    q = db.query(ConditionStrategy).order_by(ConditionStrategy.id)
    if strategy_type:
        q = q.filter(ConditionStrategy.strategy_type == strategy_type)
    rows = q.all()
    return {"strategies": [_strategy_with_backtest(db, r) for r in rows]}


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

        result = _scan_symbol(symbol, conditions, db, ltp=ltp, volume=volume)
        if result:
            signals.append(result)

    # Update strategy scan metadata
    row.last_scan = now_ist()
    row.last_signal_count = len(signals)
    db.commit()

    mode = get_execution_mode()
    history_rows = []
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
            auto_execute=bool(row.auto_scan_enabled),
            execution_mode=mode,
        )
        if history:
            history_rows.append(_serialize_signal_history(history))

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
    quantity = body.get("quantity", 1)
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
            symbol=symbol,
            direction=direction,
            price=ltp,
            quantity=quantity,
            execution_mode=mode,
            details=json.dumps(order),
            timestamp=datetime.now(),
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


def _get_bar_date(candle, date_attr: str):
    """Normalise candle date/timestamp to a date object for comparisons."""
    val = getattr(candle, date_attr)
    if hasattr(val, "date"):          # datetime → date
        return val.date()
    return val                         # already a date


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
) -> Dict[str, Any]:
    """
    Replay candles for one symbol, evaluate entry conditions bar-by-bar,
    apply SL/TP/TSL exits.  Returns trade list + metrics for this symbol.
    Works with any timeframe candle (1m / 5m / 15m / 1h / daily).
    """
    sl_pct = exit_config.get("sl_pct", 5.0) / 100
    tp_pct = exit_config.get("tp_pct", 10.0) / 100
    tsl_pct = exit_config.get("tsl_pct", 0.0) / 100

    trades: List[Dict[str, Any]] = []
    in_trade = False
    entry_price = 0.0
    entry_date = None
    entry_bar_idx = None
    peak_price = 0.0
    trough_price = float('inf')

    for i in range(lookback, len(candles)):
        c = candles[i]
        bar_date = _bar_date_str(c, date_attr)

        closes = [x.close for x in candles[:i + 1]]
        highs = [x.high for x in candles[:i + 1]]
        lows = [x.low for x in candles[:i + 1]]
        volumes = [int(x.volume or 0) for x in candles[:i + 1]]
        current_close = c.close

        if in_trade:
            # Track peak/trough for TSL
            if direction == "BUY":
                if current_close > peak_price:
                    peak_price = current_close
            else:
                if current_close < trough_price:
                    trough_price = current_close

            # Check SL
            if direction == "BUY":
                sl_hit = current_close <= entry_price * (1 - sl_pct)
            else:
                sl_hit = current_close >= entry_price * (1 + sl_pct)

            # Check TP
            if direction == "BUY":
                tp_hit = current_close >= entry_price * (1 + tp_pct)
            else:
                tp_hit = current_close <= entry_price * (1 - tp_pct)

            # Check TSL
            tsl_hit = False
            if tsl_pct > 0:
                if direction == "BUY":
                    tsl_trigger = peak_price * (1 - tsl_pct)
                    tsl_hit = current_close <= tsl_trigger and peak_price > entry_price
                else:
                    tsl_trigger = trough_price * (1 + tsl_pct)
                    tsl_hit = current_close >= tsl_trigger and trough_price < entry_price

            exit_reason = None
            if sl_hit:
                exit_reason = "SL"
            elif tp_hit:
                exit_reason = "TP"
            elif tsl_hit:
                exit_reason = "TSL"

            if exit_reason:
                if direction == "BUY":
                    pnl_pct = ((current_close - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - current_close) / entry_price) * 100

                trades.append({
                    "entry_date": entry_date,
                    "exit_date": bar_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(current_close, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "exit_reason": exit_reason,
                    "holding_bars": i - entry_bar_idx if entry_bar_idx is not None else 0,
                })
                in_trade = False
                continue

        if not in_trade:
            # Evaluate entry conditions
            all_met = True
            for cond in conditions:
                if not _evaluate_condition(cond, closes, highs, lows, volumes):
                    all_met = False
                    break

            if all_met:
                in_trade = True
                entry_price = current_close
                entry_date = bar_date
                entry_bar_idx = i
                peak_price = current_close
                trough_price = current_close

    # Close any open trade at last bar
    if in_trade and len(candles) > 0:
        last = candles[-1]
        if direction == "BUY":
            pnl_pct = ((last.close - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - last.close) / entry_price) * 100
        trades.append({
            "entry_date": entry_date,
            "exit_date": _bar_date_str(last, date_attr),
            "entry_price": round(entry_price, 2),
            "exit_price": round(last.close, 2),
            "pnl_pct": round(pnl_pct, 2),
            "exit_reason": "OPEN",
            "holding_bars": len(candles) - 1 - (entry_bar_idx or 0),
        })

    # Compute per-symbol metrics
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

    # Allow request-level exit overrides from UI backtest form.
    if req.sl_pct is not None:
        exit_config["sl_pct"] = req.sl_pct
    if req.tp_pct is not None:
        exit_config["tp_pct"] = req.tp_pct
    if req.tsl_pct is not None:
        exit_config["tsl_pct"] = req.tsl_pct

    candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe)
    if not candle_info:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported timeframe '{timeframe}'. Supported: {list(TIMEFRAME_CANDLE_MAP.keys())}",
        )
    CandleModel, date_attr, table_label = candle_info
    date_col = getattr(CandleModel, date_attr)

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
        lookback_start_dt = datetime.combine(
            start_date - timedelta(days=30), datetime.min.time()
        )
    else:
        start_dt = start_date
        end_dt = end_date
        lookback_start_dt = start_date - timedelta(days=120)

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

        min_bars = 60 if date_attr == "date" else 20
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

    capital = req.initial_capital
    curves = [{"date": str(start_date), "equity": capital}]
    for trade in all_trades:
        trade_capital = capital * (req.position_size_pct / 100)
        pnl_amount = trade_capital * (trade["pnl_pct"] / 100)
        capital += pnl_amount
        curves.append({
            "date": trade.get("exit_date", trade.get("entry_date", "")),
            "equity": round(capital, 2),
            "symbol": trade.get("symbol", ""),
            "pnl_pct": trade["pnl_pct"],
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
    annual_return = total_return * (365 / days_span)

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
        },
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
            }
            for t in all_trades
        ],
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