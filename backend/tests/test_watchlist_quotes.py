import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.api.routes import watchlists as watchlists_route
import app.services.zerodha as zerodha_service


class _FakeQuery:
    def __init__(self, watchlist):
        self._watchlist = watchlist

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._watchlist


class _FakeDB:
    def __init__(self, watchlist):
        self._watchlist = watchlist

    def query(self, model):
        return _FakeQuery(self._watchlist)


class _DummyKiteService:
    def get_quote(self, symbol: str):
        # Mimics the lightweight LTP response, which does not include OHLC/change.
        return {
            "last_price": 24000.90,
            "volume": 1234567,
        }

    def get_full_quote(self, symbol: str):
        return {
            "last_price": 24000.90,
            "ohlc": {
                "open": 23910.00,
                "high": 24125.00,
                "low": 23780.00,
                "close": 23850.00,
            },
            "volume": 1234567,
        }


def test_watchlist_quotes_include_change_percent_from_full_quote(monkeypatch):
    watchlist = SimpleNamespace(
        id=1,
        name="NIFTY 50",
        color="#3b82f6",
        symbols=["NIFTY"],
    )
    db = _FakeDB(watchlist)

    monkeypatch.setattr(zerodha_service, "KiteConnectService", lambda: _DummyKiteService())

    result = asyncio.run(watchlists_route.get_watchlist_quotes(1, db))

    assert result["watchlist"]["name"] == "NIFTY 50"
    quote = result["quotes"][0]

    assert quote["ltp"] == 24000.90
    assert quote["change"] == pytest.approx(150.90, rel=1e-6)
    expected_change_pct = round((24000.90 - 23850.00) / 23850.00 * 100, 2)
    assert quote["change_pct"] == pytest.approx(expected_change_pct, rel=1e-6)
    assert quote["open"] == 23910.00
    assert quote["high"] == 24125.00
    assert quote["low"] == 23780.00
    assert quote["close"] == 23850.00
    assert quote["volume"] == 1234567
