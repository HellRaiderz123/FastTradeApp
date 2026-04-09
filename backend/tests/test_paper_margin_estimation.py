from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.schemas.journal import ExecutionIntentOut
from app.core.execution.paper import PaperExecutionAdapter


class _FakeZerodhaAdapter:
    def __init__(self, kite_client=None, dry_run=True):
        self.kite_client = kite_client
        self.dry_run = dry_run

    def calculate_margin_required(self, intent):
        return 68450.0


def _sample_intent():
    return SimpleNamespace(
        intent_id="paper-margin-1",
        underlying="NIFTY",
        expiry="2026-04-30",
        ticket={
            "lots": 8,
            "lot_size": 75,
            "legs": [
                {"strike": 22500, "type": "CE", "side": "SELL", "symbol": "NIFTY22500CE"},
                {"strike": 22600, "type": "CE", "side": "BUY", "symbol": "NIFTY22600CE"},
                {"strike": 22000, "type": "PE", "side": "SELL", "symbol": "NIFTY22000PE"},
                {"strike": 21900, "type": "PE", "side": "BUY", "symbol": "NIFTY21900PE"},
            ],
        },
        entry_credit=None,
    )


def test_paper_execution_includes_margin_required(monkeypatch):
    import app.core.execution.paper as paper_mod

    monkeypatch.setattr(
        paper_mod,
        "get_ltp",
        lambda symbols: {
            "NIFTY22500CE": 18.0,
            "NIFTY22600CE": 9.0,
            "NIFTY22000PE": 21.0,
            "NIFTY21900PE": 11.0,
        },
    )
    monkeypatch.setattr(paper_mod, "get_kite_client", lambda: object(), raising=False)
    monkeypatch.setattr(paper_mod, "ZerodhaExecutionAdapter", _FakeZerodhaAdapter, raising=False)

    result = PaperExecutionAdapter().execute(_sample_intent())

    assert result["mode"] == "PAPER"
    assert result.get("margin_required") == 68450.0


def test_execution_intent_schema_exposes_margin_required():
    payload = ExecutionIntentOut.model_validate(
        SimpleNamespace(
            id=1,
            intent_id="intent-margin",
            run_id=10,
            strategy="IRON_CONDOR",
            underlying="NIFTY",
            status="EXECUTED",
            executed=True,
            ticket={"legs": []},
            avg_price=None,
            pnl=250.0,
            unrealized_pnl=250.0,
            tp=None,
            sl=None,
            exit_reason=None,
            entry_credit=-7666.75,
            margin_required=68450.0,
            execution_result={"mode": "PAPER"},
            created_at="2026-04-09T10:00:00+05:30",
            closed_at=None,
        )
    )

    dumped = payload.model_dump()
    assert dumped.get("margin_required") == 68450.0
