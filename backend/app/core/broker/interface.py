"""
Broker Interface Protocol — Centralized abstraction for all broker operations.

This module provides:
1. BrokerInterface - Protocol defining the contract all brokers must implement
2. BrokerManager - Singleton that manages broker instances and provides unified access
3. Helper functions for common broker operations

Usage:
    from app.core.broker.interface import get_broker, get_broker_manager

    # Get the active broker adapter
    broker = get_broker()
    quote = broker.get_quote("RELIANCE")
    
    # Or use the manager for more control
    manager = get_broker_manager()
    manager.get_quote("RELIANCE")
"""

from __future__ import annotations

import logging
import os
from abc import abstractmethod
from datetime import date
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from app.core.broker.base_adapter import (
    BaseBrokerAdapter,
    Candle,
    OptionChainRow,
    OrderResult,
    Position,
    Quote,
)
from app.core.broker.registry import (
    BrokerCapabilities,
    BrokerUnsupportedError,
    get_active_broker,
    get_data_broker,
    get_registry,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class BrokerInterface(Protocol):
    """
    Protocol defining the interface all broker adapters must implement.
    
    This is a structural subtyping protocol - any class implementing these
    methods is considered a valid BrokerInterface, even without explicit inheritance.
    """

    @property
    def name(self) -> str:
        """Broker identifier name."""
        ...

    @property
    def supports_live_trading(self) -> bool:
        """Whether this broker supports live order execution."""
        ...

    # Market Data
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        ...

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        ...

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        ...

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        ...

    def get_expiries(self, underlying: str) -> List[date]:
        ...

    # Order Execution
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "NRML",
    ) -> OrderResult:
        ...

    def place_basket_order(self, orders: List[Dict[str, Any]]) -> List[OrderResult]:
        ...

    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        ...

    # Portfolio
    def get_positions(self) -> List[Position]:
        ...

    def get_holdings(self) -> List[Dict[str, Any]]:
        ...

    def get_margins(self) -> Dict[str, float]:
        ...

    def get_order_book(self) -> List[Dict[str, Any]]:
        ...

    # Utility
    def get_lot_size(self, symbol: str) -> int:
        ...

    def is_market_open(self) -> bool:
        ...


class BrokerManager:
    """
    Singleton manager for broker adapters.
    
    Provides:
    - Lazy initialization of broker adapters
    - Unified access to active broker
    - Capability checking before operations
    - Fallback handling for unsupported operations
    """

    _instance: Optional["BrokerManager"] = None
    _adapters: Dict[str, BaseBrokerAdapter] = {}

    def __new__(cls) -> "BrokerManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._adapters = {}
        return cls._instance

    def _get_adapter(self, broker_name: str) -> BaseBrokerAdapter:
        """Get or create adapter for a broker."""
        key = broker_name.upper().strip()
        
        if key not in self._adapters:
            self._adapters[key] = self._create_adapter(key)
        
        return self._adapters[key]

    def _create_adapter(self, broker_name: str) -> BaseBrokerAdapter:
        """Factory method to create broker adapters."""
        if broker_name == "ZERODHA":
            from app.core.broker.zerodha_adapter import ZerodhaBrokerAdapter
            dry_run = os.getenv("EXECUTION_MODE", "").upper() == "ZERODHA_DRY_RUN"
            return ZerodhaBrokerAdapter(dry_run=dry_run)
        
        elif broker_name == "INDMONEY":
            # Import and create INDMoney adapter when implemented
            # For now, fall back to a stub that raises on unsupported ops
            from app.core.broker.indmoney_adapter import INDMoneyBrokerAdapter
            return INDMoneyBrokerAdapter()
        
        elif broker_name == "PAPER":
            from app.core.broker.paper_adapter import PaperBrokerAdapter
            return PaperBrokerAdapter()
        
        else:
            raise BrokerUnsupportedError(
                broker_name,
                "adapter_creation",
                f"No adapter implemented for broker '{broker_name}'",
            )

    def get_active_adapter(self) -> BaseBrokerAdapter:
        """Get adapter for the currently active broker."""
        broker = get_active_broker()
        return self._get_adapter(broker)

    def get_data_adapter(self) -> BaseBrokerAdapter:
        """Get adapter for market data operations."""
        broker = get_data_broker()
        return self._get_adapter(broker)

    def get_capabilities(self, broker_name: Optional[str] = None) -> BrokerCapabilities:
        """Get capabilities for a broker."""
        name = broker_name or get_active_broker()
        return get_registry().get(name)

    def supports(self, capability: str, broker_name: Optional[str] = None) -> bool:
        """Check if a capability is supported."""
        name = broker_name or get_active_broker()
        return get_registry().supports(name, capability)

    def require(self, capability: str, broker_name: Optional[str] = None) -> None:
        """Require a capability, raising if not supported."""
        name = broker_name or get_active_broker()
        get_registry().require(name, capability)

    # ─────────────────────────────────────────────────────────────────────────
    # Unified Market Data Methods (with capability checks)
    # ─────────────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        """Get quote with automatic broker selection and capability check."""
        adapter = self.get_data_adapter()
        return adapter.get_quote(symbol, exchange)

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        """Get multiple quotes."""
        adapter = self.get_data_adapter()
        return adapter.get_quotes(symbols, exchange)

    def get_ltp(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """Get last traded price for a symbol."""
        quote = self.get_quote(symbol, exchange)
        return quote.last_price if quote else None

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        """Get historical candles."""
        self.require("historical_data", get_data_broker())
        adapter = self.get_data_adapter()
        return adapter.get_historical_candles(symbol, interval, from_date, to_date, exchange)

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        """Get option chain."""
        adapter = self.get_data_adapter()
        return adapter.get_option_chain(underlying, expiry)

    # ─────────────────────────────────────────────────────────────────────────
    # Unified Execution Methods (with capability checks)
    # ─────────────────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "MARKET",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "NRML",
    ) -> OrderResult:
        """Place order with capability check."""
        self.require("order_placement")
        adapter = self.get_active_adapter()
        return adapter.place_order(
            symbol, exchange, transaction_type, quantity,
            order_type, price, trigger_price, product
        )

    def place_basket_order(self, orders: List[Dict[str, Any]]) -> List[OrderResult]:
        """Place basket order."""
        self.require("order_placement")
        adapter = self.get_active_adapter()
        return adapter.place_basket_order(orders)

    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        """Cancel order."""
        self.require("order_cancellation")
        adapter = self.get_active_adapter()
        return adapter.cancel_order(order_id, variety)

    # ─────────────────────────────────────────────────────────────────────────
    # Unified Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        """Get positions."""
        self.require("positions")
        adapter = self.get_active_adapter()
        return adapter.get_positions()

    def get_holdings(self) -> List[Dict[str, Any]]:
        """Get holdings."""
        self.require("holdings")
        adapter = self.get_active_adapter()
        return adapter.get_holdings()

    def get_margins(self) -> Dict[str, float]:
        """Get margin details."""
        self.require("funds")
        adapter = self.get_active_adapter()
        return adapter.get_margins()

    def get_order_book(self) -> List[Dict[str, Any]]:
        """Get order book."""
        self.require("order_book")
        adapter = self.get_active_adapter()
        return adapter.get_order_book()

    # ─────────────────────────────────────────────────────────────────────────
    # Status and Info
    # ─────────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get broker manager status for monitoring."""
        active = get_active_broker()
        data = get_data_broker()
        caps = self.get_capabilities(active)
        
        return {
            "active_broker": active,
            "data_broker": data,
            "adapters_loaded": list(self._adapters.keys()),
            "capabilities": {
                "historical_data": caps.historical_data,
                "live_ltp": caps.live_ltp,
                "live_quotes": caps.live_quotes,
                "market_depth": caps.market_depth,
                "order_placement": caps.order_placement,
                "gtt_orders": caps.gtt_orders,
                "positions": caps.positions,
                "holdings": caps.holdings,
                "funds": caps.funds,
            },
        }

    def clear_adapters(self) -> None:
        """Clear cached adapters (useful for testing or token refresh)."""
        self._adapters.clear()
        logger.info("BrokerManager: cleared all cached adapters")


# ─────────────────────────────────────────────────────────────────────────────
# Module-level convenience functions
# ─────────────────────────────────────────────────────────────────────────────

_manager: Optional[BrokerManager] = None


def get_broker_manager() -> BrokerManager:
    """Get the singleton BrokerManager instance."""
    global _manager
    if _manager is None:
        _manager = BrokerManager()
    return _manager


def get_broker() -> BaseBrokerAdapter:
    """Get the active broker adapter."""
    return get_broker_manager().get_active_adapter()


def get_data_broker_adapter() -> BaseBrokerAdapter:
    """Get the data broker adapter."""
    return get_broker_manager().get_data_adapter()
