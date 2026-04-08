import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.execution.indmoney import INDMoneyExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter


class _FakeKite:
    VARIETY_REGULAR = "regular"
    TRANSACTION_TYPE_BUY = "BUY"
    TRANSACTION_TYPE_SELL = "SELL"
    ORDER_TYPE_LIMIT = "LIMIT"
    ORDER_TYPE_MARKET = "MARKET"
    PRODUCT_NRML = "NRML"
    VALIDITY_DAY = "DAY"
    GTT_TYPE_OCO = "two-leg"

    def __init__(self):
        self.orders = []
        self.gtts = []
        self.deleted_gtts = []

    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return f"ord-{len(self.orders)}"

    def basket_order_margins(self, basket):
        return {"final": {"total": 12345.0}}

    def place_gtt(self, trigger_type, tradingsymbol, exchange, trigger_values, last_price, orders):
        self.gtts.append(
            {
                "trigger_type": trigger_type,
                "tradingsymbol": tradingsymbol,
                "exchange": exchange,
                "trigger_values": trigger_values,
                "last_price": last_price,
                "orders": orders,
            }
        )
        return f"gtt-{len(self.gtts)}"

    def delete_gtt(self, trigger_id):
        self.deleted_gtts.append(trigger_id)
        return {"status": "success", "trigger_id": trigger_id}


class _FakeINDMoneyClient:
    def __init__(self):
        self.orders = []
        self.gtts = []
        self.cancelled = []
        self.gtt_path = "/gtt"

    def place_order(self, order):
        self.orders.append(order)
        return {"order_id": f"ind-order-{len(self.orders)}", "response": {"status": "ok"}}

    def place_gtt(self, payload):
        self.gtts.append(payload)
        return {"trigger_id": f"ind-gtt-{len(self.gtts)}", "response": {"status": "ok"}}

    def cancel_gtt(self, trigger_id):
        self.cancelled.append(("gtt", trigger_id))
        return {"status": "cancelled", "trigger_id": trigger_id}

    def cancel_order(self, order_id):
        self.cancelled.append(("order", order_id))
        return {"status": "cancelled", "order_id": order_id}


def _make_intent(*, side="BUY"):
    symbol = "NIFTY26APR22000CE"
    return SimpleNamespace(
        underlying="NIFTY",
        expiry="2026-04-30",
        tp=1200.0,
        sl=-800.0,
        entry_credit=1000.0,
        execution_result={},
        ticket={
            "lots": 1,
            "lot_size": 50,
            "exchange": "NFO",
            "legs": [
                {
                    "symbol": symbol,
                    "strike": 22000,
                    "type": "CE",
                    "side": side,
                    "qty": 50,
                    "price": 100.0,
                    "exchange": "NFO",
                    "security_id": "12345",
                }
            ],
        },
    )


def test_zerodha_execute_places_broker_side_gtt(monkeypatch):
    intent = _make_intent(side="BUY")
    kite = _FakeKite()

    monkeypatch.setattr("app.core.execution.zerodha.get_ltp", lambda symbols: {symbols[0]: 100.0})
    monkeypatch.setattr("app.core.execution.zerodha.subscribe_to_ticker", lambda symbols: None)

    adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=False)
    result = adapter.execute(intent)

    assert result["mode"] == "ZERODHA_LIVE"
    assert result["protection"]["provider"] == "ZERODHA_GTT"
    assert result["protection"]["enabled"] is True
    assert kite.gtts


def test_zerodha_exit_cancels_existing_gtt(monkeypatch):
    intent = _make_intent(side="SELL")
    intent.execution_result = {
        "protection": {
            "provider": "ZERODHA_GTT",
            "orders": [{"trigger_id": "gtt-1"}],
        }
    }
    kite = _FakeKite()

    monkeypatch.setattr("app.core.execution.zerodha.get_ltp", lambda symbols: {symbols[0]: 95.0})

    adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=False)
    result = adapter.exit(intent)

    assert result["mode"] == "ZERODHA_LIVE"
    assert "gtt-1" in kite.deleted_gtts


def test_indmoney_execute_places_broker_side_protection(monkeypatch):
    intent = _make_intent(side="BUY")
    client = _FakeINDMoneyClient()

    monkeypatch.setattr("app.core.execution.indmoney.get_ltp", lambda symbols: {symbols[0]: 100.0})

    adapter = INDMoneyExecutionAdapter(client=client, dry_run=False)
    result = adapter.execute(intent)

    assert result["mode"] == "INDMONEY_LIVE"
    assert result["protection"]["enabled"] is True
    assert result["protection"]["provider"] in {"INDMONEY_GTT", "INDMONEY_BROKER_ORDERS"}
    assert client.gtts or len(client.orders) > 1
