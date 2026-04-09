from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.api.routes.condition_scanner import BacktestRequest, _backtest_symbol, _run_backtest_for_strategy_payload
from app.api.routes.journal import _build_tax_export_row
from app.core.condition_scanner_scheduler import _scan_and_execute_strategy


def _candle(day_offset: int, open_: float, high: float, low: float, close: float):
    return SimpleNamespace(
        date=date(2026, 1, 1) + timedelta(days=day_offset),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1000,
    )


def test_backtest_slippage_reduces_realistic_returns():
    candles = [
        _candle(0, 95, 96, 94, 95),
        _candle(1, 96, 99, 95, 99),
        _candle(2, 100, 106, 99, 105),
        _candle(3, 102, 110, 101, 104),
        _candle(4, 104, 105, 103, 104),
    ]

    base = _backtest_symbol(
        symbol="TEST",
        conditions=[{"indicator": "CLOSE", "params": {}, "comparator": "crosses_above", "value": "100"}],
        direction="BUY",
        exit_config={"sl_pct": 5.0, "tp_pct": 5.0, "tsl_pct": 0.0},
        candles=candles,
        initial_capital=100000.0,
        position_size_pct=10.0,
        lookback=1,
        date_attr="date",
    )
    slipped = _backtest_symbol(
        symbol="TEST",
        conditions=[{"indicator": "CLOSE", "params": {}, "comparator": "crosses_above", "value": "100"}],
        direction="BUY",
        exit_config={
            "sl_pct": 5.0,
            "tp_pct": 5.0,
            "tsl_pct": 0.0,
            "apply_slippage": True,
            "slippage_pct": 0.5,
        },
        candles=candles,
        initial_capital=100000.0,
        position_size_pct=10.0,
        lookback=1,
        date_attr="date",
    )

    assert slipped["total_trades"] == 1
    assert slipped["trades"][0]["pnl_amount"] < base["trades"][0]["pnl_amount"]
    assert slipped["trades"][0]["entry_price"] > base["trades"][0]["entry_price"]


class _FakeQuery:
    def __init__(self, candles):
        self._candles = candles

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self._candles)


class _FakeDB:
    def __init__(self, candles):
        self._candles = candles

    def query(self, model):
        return _FakeQuery(self._candles)


def test_walk_forward_summary_is_returned_for_backtests():
    candles = []
    price = 100.0
    for i in range(120):
        price += 0.8 if i < 60 else (-0.4 if i < 90 else 0.6)
        candles.append(_candle(i, price - 0.5, price + 1.5, price - 1.5, price))

    strategy = {
        "id": 1,
        "name": "WF Test",
        "direction": "BUY",
        "timeframe": "Day",
        "universe": "NIFTY50",
        "instruments": ["TEST"],
        "entry_conditions": [{"indicator": "CLOSE", "params": {}, "comparator": "higher_than", "value": "100"}],
        "exit_config": {
            "sl_pct": 3.0,
            "tp_pct": 6.0,
            "tsl_pct": 0.0,
            "walk_forward_enabled": True,
            "walk_forward_windows": 3,
            "walk_forward_train_pct": 67.0,
        },
    }
    req = BacktestRequest(
        start_date=str(candles[0].date),
        end_date=str(candles[-1].date),
        initial_capital=100000.0,
        position_size_pct=10.0,
        max_open_trades=5,
    )

    result = _run_backtest_for_strategy_payload(strategy, req, _FakeDB(candles))

    assert "walk_forward" in result
    assert result["walk_forward"]["enabled"] is True
    assert len(result["walk_forward"]["windows"]) >= 1


def test_auto_scan_skips_duplicate_executed_signal(monkeypatch):
    import app.core.condition_scanner_scheduler as sched

    monkeypatch.setattr(sched, "get_symbols", lambda universe: ["RELIANCE"])
    monkeypatch.setattr(sched._kite_service, "get_bulk_quotes", lambda symbols: {"NSE:RELIANCE": {"last_price": 2500.0, "volume": 100000}})
    monkeypatch.setattr(
        sched,
        "record_scanner_signal",
        lambda *args, **kwargs: SimpleNamespace(id=99, status="FILLED_PAPER"),
    )

    executed = {"count": 0}

    def _fake_exec(**kwargs):
        executed["count"] += 1

    monkeypatch.setattr(sched, "_auto_execute_signal", _fake_exec)
    monkeypatch.setattr(
        "app.api.routes.condition_scanner._scan_symbol",
        lambda *args, **kwargs: {
            "symbol": "RELIANCE",
            "ltp": 2500.0,
            "change_percent": 1.2,
            "position_sizing": "FIXED",
            "suggested_quantity": 4,
        },
    )

    strategy = {
        "id": 1,
        "name": "Auto Scan",
        "entry_conditions": [{"indicator": "CLOSE", "params": {}, "comparator": "higher_than", "value": "100"}],
        "direction": "BUY",
        "timeframe": "Day",
        "exit_config": {},
        "universe": "NIFTY50",
        "instruments": ["RELIANCE"],
        "auto_amount": 10000.0,
    }

    _scan_and_execute_strategy(strategy, [], db=SimpleNamespace())

    assert executed["count"] == 0


def test_tax_export_row_includes_costs_and_net_pnl():
    intent = SimpleNamespace(
        intent_id="intent-1",
        strategy="IRON_CONDOR",
        underlying="NIFTY",
        created_at="2026-04-01T10:00:00+05:30",
        closed_at="2026-04-01T14:00:00+05:30",
        entry_credit=5000.0,
        pnl=1200.0,
        exit_reason="TARGET",
        status="CLOSED",
        execution_result={"mode": "ZERODHA_DRY_RUN"},
        ticket_dict={
            "lots": 1,
            "lot_size": 50,
            "legs": [
                {"side": "SELL", "price": 120.0},
                {"side": "BUY", "price": 70.0},
            ],
        },
    )

    row = _build_tax_export_row(intent)

    assert row["gross_pnl"] == 1200.0
    assert row["estimated_charges"] > 0
    assert row["net_pnl"] < row["gross_pnl"]
