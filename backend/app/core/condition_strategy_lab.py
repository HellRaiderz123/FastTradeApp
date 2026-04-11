from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List


_TIMEFRAME_PROFILES: Dict[str, Dict[str, Any]] = {
    "Day": {
        "sl_pct": 3.2,
        "tp_pct": 9.5,
        "tsl_pct": 1.8,
        "require_htf_confirm": False,
        "htf_timeframe": None,
        "atr_period": 14,
        "atr_multiplier": 2.0,
        "risk_per_trade_pct": 1.0,
        "apply_slippage": True,
        "slippage_pct": 0.05,
        "walk_forward_windows": 4,
        "walk_forward_train_pct": 70.0,
        "volume_breakout_floors": (800000, 1500000, 2500000),
    },
    "1 Hour": {
        "sl_pct": 2.2,
        "tp_pct": 5.8,
        "tsl_pct": 1.2,
        "require_htf_confirm": True,
        "htf_timeframe": "Day",
        "atr_period": 14,
        "atr_multiplier": 1.6,
        "risk_per_trade_pct": 0.8,
        "apply_slippage": True,
        "slippage_pct": 0.08,
        "walk_forward_windows": 4,
        "walk_forward_train_pct": 67.0,
        "volume_breakout_floors": (250000, 500000, 900000),
    },
    "15 Min": {
        "sl_pct": 1.2,
        "tp_pct": 3.2,
        "tsl_pct": 0.8,
        "require_htf_confirm": True,
        "htf_timeframe": "1 Hour",
        "atr_period": 14,
        "atr_multiplier": 1.35,
        "risk_per_trade_pct": 0.6,
        "apply_slippage": True,
        "slippage_pct": 0.12,
        "walk_forward_windows": 3,
        "walk_forward_train_pct": 65.0,
        "volume_breakout_floors": (75000, 150000, 300000),
    },
    "5 Min": {
        "sl_pct": 0.9,
        "tp_pct": 2.4,
        "tsl_pct": 0.6,
        "require_htf_confirm": True,
        "htf_timeframe": "15 Min",
        "atr_period": 14,
        "atr_multiplier": 1.2,
        "risk_per_trade_pct": 0.45,
        "apply_slippage": True,
        "slippage_pct": 0.15,
        "walk_forward_windows": 3,
        "walk_forward_train_pct": 65.0,
        "volume_breakout_floors": (30000, 60000, 120000),
    },
    "1 Min": {
        "sl_pct": 0.6,
        "tp_pct": 1.5,
        "tsl_pct": 0.4,
        "require_htf_confirm": True,
        "htf_timeframe": "5 Min",
        "atr_period": 14,
        "atr_multiplier": 1.0,
        "risk_per_trade_pct": 0.3,
        "apply_slippage": True,
        "slippage_pct": 0.2,
        "walk_forward_windows": 2,
        "walk_forward_train_pct": 60.0,
        "volume_breakout_floors": (15000, 30000, 60000),
    },
}


def _strategy_type_for_timeframe(timeframe: str) -> str:
    return "Equity Swing" if timeframe == "Day" else "Equity Intraday"


def _timeframe_profile(timeframe: str) -> Dict[str, Any]:
    return deepcopy(_TIMEFRAME_PROFILES.get(timeframe, _TIMEFRAME_PROFILES["1 Hour"]))


def _default_exit_config(timeframe: str, *, style: str = "trend") -> Dict[str, Any]:
    profile = _timeframe_profile(timeframe)
    style_multipliers = {
        "trend": (1.0, 1.0, 1.0),
        "mean_reversion": (0.82, 0.82, 0.75),
        "breakout": (1.1, 1.18, 1.05),
        "position": (1.25, 1.3, 1.1),
    }
    sl_mult, tp_mult, tsl_mult = style_multipliers.get(style, style_multipliers["trend"])

    return {
        "sl_pct": round(profile["sl_pct"] * sl_mult, 2),
        "tp_pct": round(profile["tp_pct"] * tp_mult, 2),
        "tsl_pct": round(profile["tsl_pct"] * tsl_mult, 2),
        "exit_mode": "percentage",
        "require_htf_confirm": bool(profile.get("require_htf_confirm")),
        "htf_timeframe": profile.get("htf_timeframe"),
        "use_atr_sizing": True,
        "atr_period": int(profile.get("atr_period", 14) or 14),
        "atr_multiplier": float(profile.get("atr_multiplier", 1.5) or 1.5),
        "risk_per_trade_pct": float(profile.get("risk_per_trade_pct", 1.0) or 1.0),
        "apply_slippage": bool(profile.get("apply_slippage", True)),
        "slippage_pct": float(profile.get("slippage_pct", 0.1) or 0.0),
        "walk_forward_enabled": True,
        "walk_forward_windows": int(profile.get("walk_forward_windows", 3) or 3),
        "walk_forward_train_pct": float(profile.get("walk_forward_train_pct", 67.0) or 67.0),
    }


def _volume_breakout_floors(timeframe: str) -> tuple[int, ...]:
    profile = _timeframe_profile(timeframe)
    floors = profile.get("volume_breakout_floors") or (800000, 1500000, 2500000)
    return tuple(int(x) for x in floors)


def _base_strategy(
    *,
    name: str,
    description: str,
    direction: str,
    timeframe: str,
    universe: str,
    entry_conditions: List[Dict[str, Any]],
    exit_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strategy_type": _strategy_type_for_timeframe(timeframe),
        "direction": direction,
        "timeframe": timeframe,
        "instruments": [],
        "universe": universe,
        "entry_conditions": deepcopy(entry_conditions),
        "exit_config": deepcopy(exit_config),
        "is_active": False,
        "auto_scan_enabled": False,
        "auto_amount": 10000.0,
    }


def generate_candidate_strategies(
    *,
    timeframe: str = "Day",
    universe: str = "NIFTY50",
    max_candidates: int = 120,
) -> List[Dict[str, Any]]:
    """Generate a deterministic grid of condition-scanner candidates."""
    candidates: List[Dict[str, Any]] = []
    seen_names = set()

    def add_candidate(candidate: Dict[str, Any]) -> None:
        name = candidate["name"]
        if name in seen_names:
            return
        seen_names.add(name)
        candidates.append(candidate)

    buy_exit = _default_exit_config(timeframe, style="trend")
    sell_exit = _default_exit_config(timeframe, style="trend")
    mean_reversion_exit = _default_exit_config(timeframe, style="mean_reversion")
    breakout_exit = _default_exit_config(timeframe, style="breakout")
    position_exit = _default_exit_config(timeframe, style="position")

    for fast in (5, 9, 12):
        for slow in (20, 21, 34, 50):
            if fast >= slow:
                continue
            for rsi_floor in (45, 50, 55):
                for adx_floor in (18, 22, 25):
                    add_candidate(
                        _base_strategy(
                            name=f"LAB EMA Trend Buy {fast}-{slow} RSI{rsi_floor} ADX{adx_floor} {timeframe}",
                            description="Generated trend-following long strategy using EMA trend, RSI strength, and ADX confirmation.",
                            direction="BUY",
                            timeframe=timeframe,
                            universe=universe,
                            entry_conditions=[
                                {"indicator": "EMA", "params": {"period": fast}, "comparator": "lower_than", "value": "Close(0)"},
                                {"indicator": "EMA", "params": {"period": slow}, "comparator": "lower_than", "value": "Close(0)"},
                                {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": str(rsi_floor)},
                                {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                            ],
                            exit_config=buy_exit,
                        )
                    )
                    add_candidate(
                        _base_strategy(
                            name=f"LAB EMA Trend Sell {fast}-{slow} RSI{100 - rsi_floor} ADX{adx_floor} {timeframe}",
                            description="Generated trend-following short strategy using EMA weakness, RSI softness, and ADX confirmation.",
                            direction="SELL",
                            timeframe=timeframe,
                            universe=universe,
                            entry_conditions=[
                                {"indicator": "EMA", "params": {"period": fast}, "comparator": "higher_than", "value": "Close(0)"},
                                {"indicator": "EMA", "params": {"period": slow}, "comparator": "higher_than", "value": "Close(0)"},
                                {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": str(100 - rsi_floor)},
                                {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                            ],
                            exit_config=sell_exit,
                        )
                    )

    for oversold in (25, 30, 35):
        for ema_period in (20, 34, 50):
            for tp in (5, 8):
                add_candidate(
                    _base_strategy(
                        name=f"LAB RSI Rebound Buy {oversold} EMA{ema_period} TP{tp} {timeframe}",
                        description="Generated mean-reversion long strategy using RSI rebound and EMA trend filter.",
                        direction="BUY",
                        timeframe=timeframe,
                        universe=universe,
                        entry_conditions=[
                            {"indicator": "RSI", "params": {"period": 14}, "comparator": "crosses_above", "value": str(oversold)},
                            {"indicator": "EMA", "params": {"period": ema_period}, "comparator": "lower_than", "value": "Close(0)"},
                        ],
                        exit_config={**mean_reversion_exit, "tp_pct": float(tp)},
                    )
                )
                add_candidate(
                    _base_strategy(
                        name=f"LAB RSI Fade Sell {100 - oversold} EMA{ema_period} TP{tp} {timeframe}",
                        description="Generated mean-reversion short strategy using RSI fade from overbought and EMA weakness filter.",
                        direction="SELL",
                        timeframe=timeframe,
                        universe=universe,
                        entry_conditions=[
                            {"indicator": "RSI", "params": {"period": 14}, "comparator": "crosses_below", "value": str(100 - oversold)},
                            {"indicator": "EMA", "params": {"period": ema_period}, "comparator": "higher_than", "value": "Close(0)"},
                        ],
                        exit_config={**mean_reversion_exit, "tp_pct": float(tp)},
                    )
                )

    for adx_floor in (18, 22, 25):
        for rsi_floor in (45, 50, 55):
            add_candidate(
                _base_strategy(
                    name=f"LAB MACD Breakout Buy RSI{rsi_floor} ADX{adx_floor} {timeframe}",
                    description="Generated breakout long strategy using MACD histogram with RSI and ADX confirmation.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "crosses_above", "value": "0"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": str(rsi_floor)},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=buy_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB MACD Breakdown Sell RSI{100 - rsi_floor} ADX{adx_floor} {timeframe}",
                    description="Generated breakout short strategy using MACD histogram with RSI and ADX confirmation.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "crosses_below", "value": "0"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": str(100 - rsi_floor)},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=sell_exit,
                )
            )

    for rsi_floor in (50, 55, 60):
        for adx_floor in (16, 20, 24):
            add_candidate(
                _base_strategy(
                    name=f"LAB RSI Regime Buy RSI{rsi_floor} ADX{adx_floor} {timeframe}",
                    description="Generated momentum strategy using RSI regime strength with MACD confirmation.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": str(rsi_floor)},
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=breakout_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB RSI Regime Sell RSI{100 - rsi_floor} ADX{adx_floor} {timeframe}",
                    description="Generated momentum short strategy using RSI weakness with MACD confirmation.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": str(100 - rsi_floor)},
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "lower_than", "value": "0"},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=breakout_exit,
                )
            )

    for stoch in (20, 25, 30):
        for ema_period in (21, 34, 50):
            add_candidate(
                _base_strategy(
                    name=f"LAB STOCH Pullback Buy K{stoch} EMA{ema_period} {timeframe}",
                    description="Generated trend-pullback strategy using Stochastic rebound inside EMA uptrend.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "STOCHASTIC", "params": {"k_period": 14, "d_period": 3, "smoothing": "%k"}, "comparator": "crosses_above", "value": str(stoch)},
                        {"indicator": "EMA", "params": {"period": ema_period}, "comparator": "lower_than", "value": "Close(0)"},
                    ],
                    exit_config=mean_reversion_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB STOCH Pullback Sell K{100 - stoch} EMA{ema_period} {timeframe}",
                    description="Generated trend-pullback short strategy using Stochastic fade inside EMA downtrend.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "STOCHASTIC", "params": {"k_period": 14, "d_period": 3, "smoothing": "%k"}, "comparator": "crosses_below", "value": str(100 - stoch)},
                        {"indicator": "EMA", "params": {"period": ema_period}, "comparator": "higher_than", "value": "Close(0)"},
                    ],
                    exit_config=mean_reversion_exit,
                )
            )

    for pb in (0.7, 0.8, 0.9):
        for adx_floor in (16, 20, 24):
            add_candidate(
                _base_strategy(
                    name=f"LAB BB Momentum Buy PB{pb} ADX{adx_floor} {timeframe}",
                    description="Generated volatility-momentum strategy using Bollinger %B breakout with ADX filter.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "BB", "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"}, "comparator": "crosses_above", "value": str(pb)},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=breakout_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB BB Momentum Sell PB{round(1 - pb, 1)} ADX{adx_floor} {timeframe}",
                    description="Generated volatility-momentum short strategy using Bollinger %B breakdown with ADX filter.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "BB", "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"}, "comparator": "crosses_below", "value": str(round(1 - pb, 1))},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": str(adx_floor)},
                    ],
                    exit_config=breakout_exit,
                )
            )

    for rsi in (45, 50, 55):
        for sma_period in (100, 150, 200):
            add_candidate(
                _base_strategy(
                    name=f"LAB SMA Position Buy SMA{sma_period} RSI{rsi} {timeframe}",
                    description="Generated position strategy using long-term SMA structure with RSI confirmation.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "SMA", "params": {"period": sma_period}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": str(rsi)},
                    ],
                    exit_config=position_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB SMA Position Sell SMA{sma_period} RSI{100 - rsi} {timeframe}",
                    description="Generated position short strategy using long-term SMA weakness with RSI confirmation.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "SMA", "params": {"period": sma_period}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": str(100 - rsi)},
                    ],
                    exit_config=position_exit,
                )
            )

    for fast in (20, 34):
        for slow in (50, 89):
            if fast >= slow:
                continue
            add_candidate(
                _base_strategy(
                    name=f"LAB SMA Cross Buy {fast}-{slow} {timeframe}",
                    description="Generated crossover strategy using dual SMAs for trend entry.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "SMA", "params": {"period": fast}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "SMA", "params": {"period": slow}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
                    ],
                    exit_config=position_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB SMA Cross Sell {fast}-{slow} {timeframe}",
                    description="Generated crossover short strategy using dual SMAs for trend entry.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "SMA", "params": {"period": fast}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "SMA", "params": {"period": slow}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "lower_than", "value": "0"},
                    ],
                    exit_config=position_exit,
                )
            )

    for fast in (9, 12):
        for slow in (34, 50):
            if fast >= slow:
                continue
            add_candidate(
                _base_strategy(
                    name=f"LAB WMA Trend Buy {fast}-{slow} {timeframe}",
                    description="Generated trend strategy using WMA alignment and RSI confirmation.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "WMA", "params": {"period": fast}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "WMA", "params": {"period": slow}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "52"},
                    ],
                    exit_config=buy_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB WMA Trend Sell {fast}-{slow} {timeframe}",
                    description="Generated trend short strategy using WMA alignment and RSI confirmation.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "WMA", "params": {"period": fast}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "WMA", "params": {"period": slow}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": "48"},
                    ],
                    exit_config=sell_exit,
                )
            )

    for dema in (20, 34):
        for tema in (20, 34):
            add_candidate(
                _base_strategy(
                    name=f"LAB DEMA TEMA Buy D{dema} T{tema} {timeframe}",
                    description="Generated trend strategy using DEMA/TEMA alignment with ADX confirmation.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "DEMA", "params": {"period": dema}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "TEMA", "params": {"period": tema}, "comparator": "lower_than", "value": "Close(0)"},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "20"},
                    ],
                    exit_config=buy_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB DEMA TEMA Sell D{dema} T{tema} {timeframe}",
                    description="Generated trend short strategy using DEMA/TEMA alignment with ADX confirmation.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "DEMA", "params": {"period": dema}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "TEMA", "params": {"period": tema}, "comparator": "higher_than", "value": "Close(0)"},
                        {"indicator": "ADX", "params": {"period": 14}, "comparator": "higher_than", "value": "20"},
                    ],
                    exit_config=sell_exit,
                )
            )

    for upper_pb in (0.82, 0.88):
        for lower_pb in (0.18, 0.12):
            add_candidate(
                _base_strategy(
                    name=f"LAB BB MeanRev Buy PB{lower_pb} {timeframe}",
                    description="Generated mean-reversion long strategy using Bollinger %B oversold rebound.",
                    direction="BUY",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "BB", "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"}, "comparator": "crosses_above", "value": str(lower_pb)},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "40"},
                    ],
                    exit_config=mean_reversion_exit,
                )
            )
            add_candidate(
                _base_strategy(
                    name=f"LAB BB MeanRev Sell PB{upper_pb} {timeframe}",
                    description="Generated mean-reversion short strategy using Bollinger %B overbought fade.",
                    direction="SELL",
                    timeframe=timeframe,
                    universe=universe,
                    entry_conditions=[
                        {"indicator": "BB", "params": {"period": 20, "std_dev": 2.0, "band": "percent_b"}, "comparator": "crosses_below", "value": str(upper_pb)},
                        {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": "60"},
                    ],
                    exit_config=mean_reversion_exit,
                )
            )

    for k_level in (20, 30):
        add_candidate(
            _base_strategy(
                name=f"LAB STOCH MACD Buy K{k_level} {timeframe}",
                description="Generated momentum strategy using Stochastic rebound and MACD histogram confirmation.",
                direction="BUY",
                timeframe=timeframe,
                universe=universe,
                entry_conditions=[
                    {"indicator": "STOCHASTIC", "params": {"k_period": 14, "d_period": 3, "smoothing": "%k"}, "comparator": "crosses_above", "value": str(k_level)},
                    {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "higher_than", "value": "0"},
                ],
                exit_config=breakout_exit,
            )
        )
        add_candidate(
            _base_strategy(
                name=f"LAB STOCH MACD Sell K{100 - k_level} {timeframe}",
                description="Generated momentum short strategy using Stochastic fade and MACD histogram confirmation.",
                direction="SELL",
                timeframe=timeframe,
                universe=universe,
                entry_conditions=[
                    {"indicator": "STOCHASTIC", "params": {"k_period": 14, "d_period": 3, "smoothing": "%k"}, "comparator": "crosses_below", "value": str(100 - k_level)},
                    {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "lower_than", "value": "0"},
                ],
                exit_config=breakout_exit,
            )
        )

    for vol_floor in _volume_breakout_floors(timeframe):
        add_candidate(
            _base_strategy(
                name=f"LAB Volume Breakout Buy VOL{vol_floor} {timeframe}",
                description="Generated breakout strategy with volume participation filter.",
                direction="BUY",
                timeframe=timeframe,
                universe=universe,
                entry_conditions=[
                    {"indicator": "VOLUME", "params": {}, "comparator": "higher_than", "value": str(vol_floor)},
                    {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "crosses_above", "value": "0"},
                    {"indicator": "RSI", "params": {"period": 14}, "comparator": "higher_than", "value": "52"},
                ],
                exit_config=breakout_exit,
            )
        )
        add_candidate(
            _base_strategy(
                name=f"LAB Volume Breakout Sell VOL{vol_floor} {timeframe}",
                description="Generated breakout short strategy with volume participation filter.",
                direction="SELL",
                timeframe=timeframe,
                universe=universe,
                entry_conditions=[
                    {"indicator": "VOLUME", "params": {}, "comparator": "higher_than", "value": str(vol_floor)},
                    {"indicator": "MACD", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "histogram"}, "comparator": "crosses_below", "value": "0"},
                    {"indicator": "RSI", "params": {"period": 14}, "comparator": "lower_than", "value": "48"},
                ],
                exit_config=breakout_exit,
            )
        )

    # Only keep BUY strategies — SELL (short) is not viable for equity cash segment
    candidates = [c for c in candidates if c.get("direction", "BUY") == "BUY"]

    family_buckets = defaultdict(list)
    for candidate in candidates:
        family_buckets[strategy_family(candidate)].append(candidate)

    preferred_order = [
        "EMA_TREND",
        "SMA_CROSS",
        "SMA_POSITION",
        "WMA_TREND",
        "DEMA_TEMA_TREND",
        "RSI_MEAN_REVERSION",
        "BB_MEAN_REVERSION",
        "MACD_MOMENTUM",
        "STOCH_MACD",
        "RSI_REGIME_MOMENTUM",
        "STOCH_PULLBACK",
        "BB_MOMENTUM",
        "VOLUME_BREAKOUT",
    ]
    ordered_families = [fam for fam in preferred_order if fam in family_buckets]
    ordered_families.extend(
        fam for fam in sorted(family_buckets.keys()) if fam not in ordered_families
    )

    selected: List[Dict[str, Any]] = []
    cursors = {fam: 0 for fam in ordered_families}

    while len(selected) < max_candidates:
        added_in_round = False
        for family in ordered_families:
            idx = cursors[family]
            if idx >= len(family_buckets[family]):
                continue
            selected.append(family_buckets[family][idx])
            cursors[family] += 1
            added_in_round = True
            if len(selected) >= max_candidates:
                break
        if not added_in_round:
            break

    return selected


def score_backtest_summary(summary: Dict[str, Any]) -> float:
    """Score backtest summary with ROI-first, risk-aware, robustness-aware weighting."""
    total_return = float(summary.get("total_return_pct") or 0.0)
    annual_return = float(summary.get("annual_return_pct") or 0.0)
    sharpe = float(summary.get("sharpe_ratio") or 0.0)
    profit_factor = float(summary.get("profit_factor") or 0.0)
    win_rate = float(summary.get("win_rate") or 0.0)
    max_drawdown = float(summary.get("max_drawdown_pct") or 0.0)
    total_trades = int(summary.get("total_trades") or 0)
    avg_win = float(summary.get("avg_win_pct") or 0.0)
    avg_loss = abs(float(summary.get("avg_loss_pct") or 0.0))
    symbols_traded = int(summary.get("symbols_traded") or 0)
    walk_forward_pass_rate = float(summary.get("walk_forward_pass_rate_pct") or 0.0)
    total_slippage_cost = float(summary.get("total_slippage_cost") or 0.0)

    if total_trades <= 0 or symbols_traded <= 0:
        return -1e9

    capped_pf = min(profit_factor, 10.0)
    return_drawdown_ratio = annual_return / max(1.0, max_drawdown)
    expectancy = 0.0
    if avg_loss > 0:
        expectancy = (win_rate / 100.0) * avg_win - (1.0 - win_rate / 100.0) * avg_loss

    trade_bonus = min(total_trades, 80) * 0.25
    breadth_bonus = min(symbols_traded, 12) * 1.25
    walk_forward_bonus = walk_forward_pass_rate * 0.35
    small_sample_penalty = max(0, 25 - total_trades) * 2.0
    high_drawdown_penalty = max(0.0, max_drawdown - 25.0) * 1.3
    low_win_rate_penalty = max(0.0, 45.0 - win_rate) * 0.4
    slippage_penalty = min(total_slippage_cost / 250.0, 25.0)

    score = (
        total_return * 0.6
        + annual_return * 2.8
        + return_drawdown_ratio * 12.0
        + sharpe * 10.0
        + capped_pf * 5.0
        + expectancy * 4.0
        + max(0.0, win_rate - 45.0) * 0.15
        + trade_bonus
        + breadth_bonus
        + walk_forward_bonus
        - small_sample_penalty
        - high_drawdown_penalty
        - low_win_rate_penalty
        - slippage_penalty
    )
    return round(score, 2)


def strategy_family(strategy: Dict[str, Any]) -> str:
    """Classify a generated condition strategy into a broad family bucket."""
    name = str(strategy.get("name") or "").upper()
    if "EMA TREND" in name:
        return "EMA_TREND"
    if "SMA CROSS" in name:
        return "SMA_CROSS"
    if "SMA POSITION" in name:
        return "SMA_POSITION"
    if "WMA TREND" in name:
        return "WMA_TREND"
    if "DEMA TEMA" in name:
        return "DEMA_TEMA_TREND"
    if "RSI REBOUND" in name or "RSI FADE" in name:
        return "RSI_MEAN_REVERSION"
    if "RSI REGIME" in name:
        return "RSI_REGIME_MOMENTUM"
    if "MACD BREAKOUT" in name or "MACD BREAKDOWN" in name:
        return "MACD_MOMENTUM"
    if "STOCH MACD" in name:
        return "STOCH_MACD"
    if "STOCH PULLBACK" in name:
        return "STOCH_PULLBACK"
    if "BB MEANREV" in name:
        return "BB_MEAN_REVERSION"
    if "BB MOMENTUM" in name:
        return "BB_MOMENTUM"
    if "VOLUME BREAKOUT" in name:
        return "VOLUME_BREAKOUT"
    if "EMA" in name:
        return "EMA_MISC"
    if "RSI" in name:
        return "RSI_MISC"
    if "MACD" in name:
        return "MACD_MISC"
    return "OTHER"


def select_diverse_top(
    ranked_results: List[Dict[str, Any]],
    *,
    top_n: int,
    max_per_family: int = 2,
    fill_remaining: bool = False,
) -> List[Dict[str, Any]]:
    """Pick top-ranked strategies with family diversity constraints."""
    if top_n <= 0:
        return []

    if max_per_family <= 0:
        max_per_family = 1

    family_counts = defaultdict(int)
    family_buckets = defaultdict(list)
    selected: List[Dict[str, Any]] = []

    for item in ranked_results:
        family = strategy_family(item.get("strategy") or {})
        family_buckets[family].append(item)

    families_ordered = sorted(
        family_buckets.keys(),
        key=lambda fam: family_buckets[fam][0].get("score", -1e9),
        reverse=True,
    )

    cursors = {fam: 0 for fam in families_ordered}
    while len(selected) < top_n:
        picked_in_round = False
        for family in families_ordered:
            if family_counts[family] >= max_per_family:
                continue
            idx = cursors[family]
            if idx >= len(family_buckets[family]):
                continue
            selected.append(family_buckets[family][idx])
            cursors[family] += 1
            family_counts[family] += 1
            picked_in_round = True
            if len(selected) >= top_n:
                break
        if not picked_in_round:
            break

    if fill_remaining and len(selected) < top_n:
        selected_ids = {id(x) for x in selected}
        for item in ranked_results:
            if id(item) in selected_ids:
                continue
            selected.append(item)
            if len(selected) >= top_n:
                break

    return selected


def generate_exit_param_combinations(
    *,
    sl_values: List[float],
    tp_values: List[float],
    tsl_values: List[float],
    max_combos: int = 0,
    min_reward_risk: float = 1.3,
    max_tsl_to_tp_ratio: float = 0.8,
) -> List[Dict[str, float]]:
    """Generate valid exit parameter combinations for optimization sweeps."""
    combos: List[Dict[str, float]] = []
    seen = set()

    for sl in sl_values:
        for tp in tp_values:
            if tp <= sl:
                continue
            reward_risk = tp / sl if sl > 0 else 0
            if reward_risk < min_reward_risk:
                continue
            for tsl in tsl_values:
                if tsl < 0:
                    continue
                if tsl >= tp:
                    continue
                if tp > 0 and (tsl / tp) > max_tsl_to_tp_ratio:
                    continue
                key = (round(float(sl), 4), round(float(tp), 4), round(float(tsl), 4))
                if key in seen:
                    continue
                seen.add(key)
                combos.append(
                    {
                        "sl_pct": float(key[0]),
                        "tp_pct": float(key[1]),
                        "tsl_pct": float(key[2]),
                        "exit_mode": "percentage",
                    }
                )

    combos.sort(key=lambda c: (c["sl_pct"], c["tp_pct"], c["tsl_pct"]))
    if max_combos > 0:
        return combos[:max_combos]
    return combos


def expand_strategies_with_exit_variants(
    strategies: List[Dict[str, Any]],
    *,
    exit_combos: List[Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Clone strategy list into multiple variants with different exit configs."""
    if not exit_combos:
        return [dict(s) for s in strategies]

    expanded: List[Dict[str, Any]] = []
    for strategy in strategies:
        base_name = str(strategy.get("name") or "LAB Strategy")
        for combo in exit_combos:
            variant = dict(strategy)
            variant["name"] = (
                f"{base_name} SL{combo['sl_pct']} TP{combo['tp_pct']} TSL{combo['tsl_pct']}"
            )
            variant["exit_config"] = dict(combo)
            variant["exit_optimization"] = {
                "base_name": base_name,
                "sl_pct": combo["sl_pct"],
                "tp_pct": combo["tp_pct"],
                "tsl_pct": combo["tsl_pct"],
            }
            expanded.append(variant)

    return expanded