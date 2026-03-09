import logging
import os

from app.core.broker.indmoney.client import get_indmoney_client
from app.core.broker.zerodha.client import get_kite_client
from app.core.execution.indmoney import INDMoneyExecutionAdapter
from app.core.execution.mode import is_live_mode, is_paper_mode, normalize_execution_mode
from app.core.execution.paper import PaperExecutionAdapter
from app.core.execution.zerodha import ZerodhaExecutionAdapter

logger = logging.getLogger(__name__)

SUPPORTED_BROKERS = {"ZERODHA", "INDMONEY"}


def normalize_broker_name(broker: str | None) -> str:
    raw = (broker or "").strip().upper().replace(" ", "")
    aliases = {
        "IND_MONEY": "INDMONEY",
        "IND-MONEY": "INDMONEY",
    }
    normalized = aliases.get(raw, raw)
    if normalized in SUPPORTED_BROKERS:
        return normalized
    return "ZERODHA"


def get_active_broker() -> str:
    return normalize_broker_name(os.getenv("ACTIVE_BROKER", "ZERODHA"))


def get_execution_adapter(mode: str, broker: str | None = None):
    """Return the right execution adapter from execution mode + active broker.

    Safety rule: any non-implemented broker falls back to paper adapter.
    """
    norm_mode = normalize_execution_mode(mode)
    if is_paper_mode(norm_mode):
        return PaperExecutionAdapter()

    resolved_broker = normalize_broker_name(broker) if broker else get_active_broker()
    if resolved_broker == "ZERODHA":
        kite = get_kite_client()
        return ZerodhaExecutionAdapter(
            kite_client=kite,
            dry_run=not is_live_mode(norm_mode),
        )

    if resolved_broker == "INDMONEY":
        client = get_indmoney_client()
        return INDMoneyExecutionAdapter(
            client=client,
            dry_run=not is_live_mode(norm_mode),
        )

    logger.warning(
        "Broker '%s' adapter is not implemented yet. Falling back to PAPER adapter.",
        resolved_broker,
    )
    return PaperExecutionAdapter()
