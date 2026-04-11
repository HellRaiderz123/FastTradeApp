from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.api.routes.condition_scanner import BacktestRequest, _backtest_symbol, _run_backtest_for_strategy_payload
from app.api.routes.journal import _build_tax_export_row
from app.core.condition_scanner_scheduler import _scan_and_execute_strategy
from app.core.condition_strategy_lab import generate_candidate_strategies
from app.core.market.scheduler import _merge_discovery_leaderboard, _slice_discovery_batch
from scripts.discover_condition_strategies import _prepare_discovery_batch


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


def test_generated_intraday_candidates_use_htf_and_atr_controls():
    candidates = generate_candidate_strategies(timeframe="15 Min", universe="NIFTY50", max_candidates=12)

    assert candidates
    exit_config = candidates[0]["exit_config"]
    assert exit_config["require_htf_confirm"] is True
    assert exit_config["htf_timeframe"] == "1 Hour"
    assert exit_config["use_atr_sizing"] is True
    assert exit_config["apply_slippage"] is True


def test_slice_discovery_batch_advances_cursor_and_wraps():
    items = list(range(120))

    batch = _slice_discovery_batch(items, start_offset=50, batch_size=25)
    assert batch["items"] == list(range(50, 75))
    assert batch["next_offset"] == 75
    assert batch["completed_cycle"] is False

    wrapped = _slice_discovery_batch(items, start_offset=110, batch_size=25)
    assert wrapped["items"] == list(range(110, 120))
    assert wrapped["next_offset"] == 0
    assert wrapped["completed_cycle"] is True


def test_prepare_discovery_batch_resumes_shared_progress_cursor():
    progress_state = {
        "version": 1,
        "runs": 2,
        "strategy_batches": {
            "NIFTY50|Day|1 Hour|15 Min": {"next_offset": 2}
        },
    }
    candidates_by_timeframe = {
        "Day": [{"name": "D1"}, {"name": "D2"}],
        "1 Hour": [{"name": "H1"}, {"name": "H2"}],
        "15 Min": [{"name": "M1"}, {"name": "M2"}],
    }

    selected, batch_meta, state_key = _prepare_discovery_batch(
        timeframe="Day",
        timeframes=["Day", "1 Hour", "15 Min"],
        universe="NIFTY50",
        max_candidates=6,
        batch_size=2,
        resume_progress=True,
        progress_state=progress_state,
        candidates_by_timeframe=candidates_by_timeframe,
    )

    assert state_key == "NIFTY50|Day|1 Hour|15 Min"
    assert [item["name"] for item in selected] == ["M1", "D2"]
    assert batch_meta["start_offset"] == 2
    assert batch_meta["next_offset"] == 4


def test_merge_discovery_leaderboard_keeps_best_five_across_batches():
    existing = [
        {"name": "Old 1", "score": 40.0, "annual_return_pct": 10.0, "max_drawdown_pct": 12.0},
        {"name": "Old 2", "score": 35.0, "annual_return_pct": 9.0, "max_drawdown_pct": 10.0},
        {"name": "Old 3", "score": 30.0, "annual_return_pct": 8.0, "max_drawdown_pct": 8.0},
        {"name": "Old 4", "score": 25.0, "annual_return_pct": 7.0, "max_drawdown_pct": 9.0},
        {"name": "Old 5", "score": 20.0, "annual_return_pct": 6.0, "max_drawdown_pct": 7.0},
    ]
    ranked_batch = [
        {
            "strategy": {"name": "New Best", "timeframe": "15 Min", "universe": "NIFTY50"},
            "score": 55.0,
            "summary": {"annual_return_pct": 14.0, "max_drawdown_pct": 11.0, "total_trades": 30},
            "final_capital": 114000.0,
            "error": None,
        },
        {
            "strategy": {"name": "Not Better", "timeframe": "Day", "universe": "NIFTY50"},
            "score": 18.0,
            "summary": {"annual_return_pct": 5.0, "max_drawdown_pct": 10.0, "total_trades": 15},
            "final_capital": 105000.0,
            "error": None,
        },
    ]

    merged = _merge_discovery_leaderboard(existing, ranked_batch, top_n=5)

    assert len(merged) == 5
    assert merged[0]["name"] == "New Best"
    assert "Old 5" not in [row["name"] for row in merged]


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
