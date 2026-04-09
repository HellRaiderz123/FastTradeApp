from datetime import date, timedelta
from types import SimpleNamespace

from app.api.routes.condition_scanner import _backtest_symbol
from app.core.indicators.technical import TechnicalIndicators


def _candle(day_offset: int, open_: float, high: float, low: float, close: float):
    return SimpleNamespace(
        date=date(2026, 1, 1) + timedelta(days=day_offset),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def test_stochastic_uses_slow_k_and_smoothed_d_line():
    highs = [10, 12, 13, 15, 16, 18]
    lows = [5, 6, 7, 9, 10, 12]
    closes = [7, 11, 12, 14, 11, 17]

    result = TechnicalIndicators.calculate_stochastic(highs, lows, closes, k_period=3, d_period=3)

    assert result is not None

    fast_k_values = []
    for end in range(3, len(closes) + 1):
        window_high = max(highs[end - 3:end])
        window_low = min(lows[end - 3:end])
        close = closes[end - 1]
        k = ((close - window_low) / (window_high - window_low)) * 100
        fast_k_values.append(k)

    slow_k_values = []
    for idx in range(len(fast_k_values)):
        window = fast_k_values[max(0, idx - 2): idx + 1]
        slow_k_values.append(sum(window) / len(window))

    d_values = []
    for idx in range(len(slow_k_values)):
        window = slow_k_values[max(0, idx - 2): idx + 1]
        d_values.append(sum(window) / len(window))

    assert result["fast_k"] == round(fast_k_values[-1], 2)
    assert result["k"] == round(slow_k_values[-1], 2)
    assert result["d"] == round(d_values[-1], 2)
    assert result["d"] != result["fast_k"]


def test_backtest_enters_next_bar_and_uses_intrabar_tp_exit():
    candles = [
        _candle(0, 95, 96, 94, 95),
        _candle(1, 96, 99, 95, 99),
        _candle(2, 100, 106, 99, 105),  # signal candle: close crosses above 100
        _candle(3, 102, 110, 101, 104),  # next bar should be used for entry and TP hit
        _candle(4, 104, 105, 103, 104),
    ]

    result = _backtest_symbol(
        symbol="TEST",
        conditions=[
            {
                "indicator": "CLOSE",
                "params": {},
                "comparator": "crosses_above",
                "value": "100",
            }
        ],
        direction="BUY",
        exit_config={"sl_pct": 5.0, "tp_pct": 5.0, "tsl_pct": 0.0},
        candles=candles,
        initial_capital=100000.0,
        position_size_pct=10.0,
        lookback=1,
        date_attr="date",
    )

    assert result["total_trades"] == 1
    trade = result["trades"][0]

    assert trade["entry_date"] == str(candles[3].date)
    assert trade["entry_price"] == candles[3].open
    assert trade["exit_reason"] == "TP"
    assert trade["exit_price"] == round(candles[3].open * 1.05, 2)


def test_backtest_requires_higher_timeframe_confirmation():
    candles = [
        _candle(0, 95, 97, 94, 95),
        _candle(1, 96, 100, 95, 99),
        _candle(2, 100, 106, 99, 105),
        _candle(3, 102, 104, 101, 103),
    ]
    higher_tf_candles = [
        _candle(0, 94, 98, 93, 97),
        _candle(1, 97, 99, 95, 99),
    ]

    result = _backtest_symbol(
        symbol="TEST",
        conditions=[
            {
                "indicator": "CLOSE",
                "params": {},
                "comparator": "higher_than",
                "value": "100",
            }
        ],
        direction="BUY",
        exit_config={
            "sl_pct": 5.0,
            "tp_pct": 5.0,
            "tsl_pct": 0.0,
            "require_htf_confirm": True,
            "htf_timeframe": "Day",
        },
        candles=candles,
        initial_capital=100000.0,
        position_size_pct=10.0,
        lookback=1,
        date_attr="date",
        timeframe="1 Hour",
        htf_timeframe="Day",
        htf_candles=higher_tf_candles,
        htf_date_attr="date",
    )

    assert result["total_trades"] == 0


def test_backtest_atr_sizing_normalizes_quantity_by_risk():
    candles = [
        _candle(0, 100, 102, 98, 100),
        _candle(1, 100, 104, 96, 101),
        _candle(2, 101, 106, 96, 103),
        _candle(3, 100, 110, 99, 108),
    ]

    result = _backtest_symbol(
        symbol="TEST",
        conditions=[
            {
                "indicator": "CLOSE",
                "params": {},
                "comparator": "higher_than",
                "value": "102",
            }
        ],
        direction="BUY",
        exit_config={
            "sl_pct": 5.0,
            "tp_pct": 0.0,
            "tsl_pct": 0.0,
            "use_atr_sizing": True,
            "atr_period": 3,
            "atr_multiplier": 2.0,
            "risk_per_trade_pct": 1.0,
        },
        candles=candles,
        initial_capital=100000.0,
        position_size_pct=50.0,
        lookback=2,
        date_attr="date",
    )

    assert result["total_trades"] == 1
    trade = result["trades"][0]

    assert trade["position_sizing"] == "ATR"
    assert trade["quantity"] == 68
    assert trade["capital_used"] == 6800.0
