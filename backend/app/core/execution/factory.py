import logging
import os

from app.core.broker.registry import (
    BrokerUnsupportedError,
    get_active_broker,
    get_registry,
)
from app.core.execution.mode import is_live_mode, is_paper_mode, normalize_execution_mode
from app.core.execution.paper import PaperExecutionAdapter

logger = logging.getLogger(__name__)

SUPPORTED_BROKERS = {"ZERODHA", "INDMONEY"}


def normalize_broker_name(broker: str | None) -> str:
    raw = (broker or "").strip().upper().replace(" ", "")
    aliases = {
        "IND_MONEY": "INDMONEY",
        "IND-MONEY": "INDMONEY",
        "INDSTOCKS": "INDMONEY",
    }
    return aliases.get(raw, raw) if raw else get_active_broker()


def get_execution_adapter(mode: str, broker: str | None = None):
    """
    Return the right execution adapter for the given mode + broker.

    Paper mode always returns PaperExecutionAdapter regardless of broker.

    For live/dry-run modes:
      - ZERODHA → ZerodhaExecutionAdapter
      - INDMONEY → INDMoneyExecutionAdapter
      - Any other broker → raises BrokerUnsupportedError immediately

    Raises:
        BrokerUnsupportedError — if broker doesn't support order_placement
        RuntimeError — if broker client cannot be initialised (token missing, etc.)
    """
    norm_mode = normalize_execution_mode(mode)
    # PAPER_TRADING, BACKTEST, and DRY_RUN all use PaperExecutionAdapter —
    # no real orders are placed, no broker security_id resolution needed.
    if norm_mode in {"PAPER_TRADING", "BACKTEST", "DRY_RUN"}:
        return PaperExecutionAdapter()

    resolved_broker = normalize_broker_name(broker) if broker else get_active_broker()

    # Check registry — raises BrokerUnsupportedError for unknown or unsupported brokers
    reg = get_registry()
    reg.require(resolved_broker, "order_placement")

    if resolved_broker == "ZERODHA":
        from app.core.broker.zerodha.client import get_kite_client
        from app.core.execution.zerodha import ZerodhaExecutionAdapter
        kite = get_kite_client()
        return ZerodhaExecutionAdapter(
            kite_client=kite,
            dry_run=not is_live_mode(norm_mode),
        )

    if resolved_broker == "INDMONEY":
        from app.core.broker.indmoney.client import get_indmoney_client
        from app.core.execution.indmoney import INDMoneyExecutionAdapter
        client = get_indmoney_client()
        return INDMoneyExecutionAdapter(
            client=client,
            dry_run=not is_live_mode(norm_mode),
        )

    # Should never reach here — registry.require() would have raised
    raise BrokerUnsupportedError(resolved_broker, "order_placement")


def get_broker_capabilities(broker: str | None = None) -> dict:
    """Return capability dict for a broker (for UI/diagnostics)."""
    name = normalize_broker_name(broker) if broker else get_active_broker()
    try:
        caps = get_registry().get(name)
        return {
            "broker": name,
            "display_name": caps.display_name,
            "order_placement": caps.order_placement,
            "order_cancellation": caps.order_cancellation,
            "gtt_orders": caps.gtt_orders,
            "margin_calculation": caps.margin_calculation,
            "positions": caps.positions,
            "holdings": caps.holdings,
            "order_book": caps.order_book,
            "funds": caps.funds,
        }
    except BrokerUnsupportedError as exc:
        return {"broker": name, "error": str(exc)}
