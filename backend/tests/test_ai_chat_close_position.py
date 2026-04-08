import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.api.routes.ai_chat import _execute_tool, _extract_direct_ai_action


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        self._rows = sorted(
            self._rows,
            key=lambda row: row.created_at or datetime.min,
            reverse=True,
        )
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, model):
        return _FakeQuery(self._rows)


def test_extract_direct_ai_action_understands_current_position_reference():
    action = _extract_direct_ai_action('close my current position')

    assert action == ('close_position', {'reference': 'current'})


def test_execute_tool_closes_latest_open_position_for_current_reference(monkeypatch):
    now = datetime.utcnow()
    intents = [
        SimpleNamespace(
            intent_id='older-intent',
            underlying='BANKNIFTY',
            strategy='Intraday Momentum',
            created_at=now - timedelta(minutes=15),
            closed_at=None,
            status='EXECUTED',
        ),
        SimpleNamespace(
            intent_id='latest-intent',
            underlying='NIFTY',
            strategy='Breakout',
            created_at=now,
            closed_at=None,
            status='EXECUTED',
        ),
    ]

    db = _FakeDB(intents)

    def _fake_post(url, timeout):
        assert url.endswith('/exit/manual/latest-intent')
        return SimpleNamespace(status_code=200, json=lambda: {'final_pnl': 2450.75}, text='ok')

    monkeypatch.setattr('app.api.routes.ai_chat.httpx.post', _fake_post)

    result = _execute_tool('close_position', {'reference': 'current'}, db)

    assert result['success'] is True
    assert result['action'] == 'closed_position'
    assert result['underlying'] == 'NIFTY'
    assert result['pnl'] == 2450.75
