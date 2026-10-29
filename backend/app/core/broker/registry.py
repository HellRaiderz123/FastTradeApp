"""
Broker capability registry.

Every broker declares what it supports. Callers check capabilities before
calling — if a feature is unsupported the registry raises BrokerUnsupportedError
immediately with a clear message instead of silently failing or falling back.

Usage:
    from app.core.broker.registry import get_registry, BrokerUnsupportedError

    reg = get_registry()
    reg.require(broker, "historical_data")   # raises if not supported
    reg.require(broker, "live_ltp")
    reg.require(broker, "order_placement")
    reg.require(broker, "gtt_orders")
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Set


class BrokerUnsupportedError(NotImplementedError):
    """Raised when a broker does not support a requested capability."""

    def __init__(self, broker: str, capability: str, hint: str = ""):
        msg = f"Broker '{broker}' does not support '{capability}'."
        if hint:
            msg += f" {hint}"
        super().__init__(msg)
        self.broker = broker
        self.capability = capability


@dataclass
class BrokerCapabilities:
    name: str
    display_name: str
    # Data capabilities
    historical_data: bool = False
    live_ltp: bool = False
    live_quotes: bool = False
    market_depth: bool = False
    # Execution capabilities
    order_placement: bool = False
    order_cancellation: bool = False
    gtt_orders: bool = False
    margin_calculation: bool = False
    # Account capabilities
    positions: bool = False
    holdings: bool = False
    order_book: bool = False
    funds: bool = False
    # Notes shown in error messages
    unsupported_hints: Dict[str, str] = field(default_factory=dict)

    def supports(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))

    def require(self, capability: str) -> None:
        if not self.supports(capability):
            hint = self.unsupported_hints.get(capability, "")
            raise BrokerUnsupportedError(self.name, capability, hint)


# ── Broker definitions ─────────────────────────────────────────────────────

_ZERODHA = BrokerCapabilities(
    name="ZERODHA",
    display_name="Zerodha (Kite)",
    historical_data=True,
    live_ltp=True,
    live_quotes=True,
    market_depth=True,
    order_placement=True,
    order_cancellation=True,
    gtt_orders=True,
    margin_calculation=True,
    positions=True,
    holdings=True,
    order_book=True,
    funds=True,
)

_INDMONEY = BrokerCapabilities(
    name="INDMONEY",
    display_name="INDMoney / INDstocks",
    historical_data=True,
    live_ltp=True,
    live_quotes=True,
    market_depth=True,
    order_placement=True,
    order_cancellation=True,
    gtt_orders=False,
    margin_calculation=False,
    positions=True,
    holdings=False,
    order_book=True,
    funds=True,
    unsupported_hints={
        "gtt_orders": "INDstocks does not expose a GTT API. Use app-side SL/TP monitoring instead.",
        "margin_calculation": "INDstocks does not provide a basket margin API. Margin is not calculated.",
        "holdings": "INDstocks holdings API is not yet integrated.",
    },
)

# Stub for future brokers — add real capabilities when implemented
_DHAN = BrokerCapabilities(
    name="DHAN",
    display_name="Dhan",
    historical_data=False,
    live_ltp=False,
    live_quotes=False,
    market_depth=False,
    order_placement=False,
    order_cancellation=False,
    gtt_orders=False,
    margin_calculation=False,
    positions=False,
    holdings=False,
    order_book=False,
    funds=False,
    unsupported_hints={
        "historical_data": "Dhan broker integration is not yet implemented in FastTrade.",
        "live_ltp": "Dhan broker integration is not yet implemented in FastTrade.",
        "order_placement": "Dhan broker integration is not yet implemented in FastTrade.",
    },
)

_UPSTOX = BrokerCapabilities(
    name="UPSTOX",
    display_name="Upstox",
    historical_data=False,
    live_ltp=False,
    live_quotes=False,
    market_depth=False,
    order_placement=False,
    order_cancellation=False,
    gtt_orders=False,
    margin_calculation=False,
    positions=False,
    holdings=False,
    order_book=False,
    funds=False,
    unsupported_hints={
        "historical_data": "Upstox broker integration is not yet implemented in FastTrade.",
        "order_placement": "Upstox broker integration is not yet implemented in FastTrade.",
    },
)

_REGISTRY: Dict[str, BrokerCapabilities] = {
    "ZERODHA": _ZERODHA,
    "INDMONEY": _INDMONEY,
    "DHAN": _DHAN,
    "UPSTOX": _UPSTOX,
}


class BrokerRegistry:
    def __init__(self, brokers: Dict[str, BrokerCapabilities]):
        self._brokers = brokers

    def get(self, broker_name: str) -> BrokerCapabilities:
        key = broker_name.upper().strip()
        caps = self._brokers.get(key)
        if caps is None:
            raise BrokerUnsupportedError(
                broker_name,
                "any",
                f"Broker '{broker_name}' is not registered. "
                f"Supported brokers: {', '.join(self._brokers)}.",
            )
        return caps

    def require(self, broker_name: str, capability: str) -> BrokerCapabilities:
        """Get broker caps and assert the capability is supported. Returns caps."""
        caps = self.get(broker_name)
        caps.require(capability)
        return caps

    def supports(self, broker_name: str, capability: str) -> bool:
        try:
            caps = self.get(broker_name)
            return caps.supports(capability)
        except BrokerUnsupportedError:
            return False

    def list_brokers(self) -> list[str]:
        return list(self._brokers.keys())

    def list_supported(self, capability: str) -> list[str]:
        return [name for name, caps in self._brokers.items() if caps.supports(capability)]


_registry_instance: BrokerRegistry | None = None


def get_registry() -> BrokerRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = BrokerRegistry(_REGISTRY)
    return _registry_instance


def get_active_broker() -> str:
    """Read active broker from DB first, env fallback, normalize, validate."""
    aliases = {
        "IND_MONEY": "INDMONEY",
        "IND-MONEY": "INDMONEY",
        "INDSTOCKS": "INDMONEY",
    }
    try:
        from app.db.session import SessionLocal
        from app.db.broker_credentials_repo import get_active_broker_from_db
        db = SessionLocal()
        try:
            db_broker = get_active_broker_from_db(db)
            if db_broker:
                raw = db_broker.upper().strip()
                return aliases.get(raw, raw)
        finally:
            db.close()
    except Exception:
        pass
    raw = os.getenv("ACTIVE_BROKER", "ZERODHA").upper().strip()
    return aliases.get(raw, raw)


def get_data_broker() -> str:
    """
    Which broker to use for market data (candles, LTP).
    Reads CANDLES_SOURCE first, falls back to ACTIVE_BROKER.
    INDSTOCKS is an alias for INDMONEY data APIs.
    """
    raw = os.getenv("CANDLES_SOURCE", "").upper().strip()
    if raw in ("INDSTOCKS", "INDMONEY"):
        return "INDMONEY"
    if raw == "ZERODHA":
        return "ZERODHA"
    # Fall back to active broker
    return get_active_broker()
