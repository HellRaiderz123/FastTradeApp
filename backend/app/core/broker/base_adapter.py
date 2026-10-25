"""
BaseBrokerAdapter — Abstract interface for all broker integrations.

Phase 1.2: Broker Abstraction Layer
Standardizes data and execution operations across brokers (Zerodha, Paper, future brokers).
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


@dataclass
class Quote:
    """Standardized quote response."""
    symbol: str
    last_price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    oi: int = 0
    bid: float = 0.0
    ask: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class Candle:
    """Standardized OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class OptionChainRow:
    """Single row in option chain."""
    strike: float
    expiry: date
    option_type: str  # CE or PE
    symbol: str
    ltp: float = 0.0
    oi: int = 0
    change_oi: int = 0
    volume: int = 0
    iv: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    lot_size: int = 1


@dataclass
class Position:
    """Standardized position."""
    symbol: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    product: str  # NRML, MIS, CNC
    exchange: str


@dataclass
class OrderResult:
    """Standardized order result."""
    order_id: str
    status: str  # PLACED, FILLED, REJECTED, CANCELLED
    symbol: str
    quantity: int
    price: float
    transaction_type: str  # BUY, SELL
    message: Optional[str] = None


class BaseBrokerAdapter(ABC):
    """
    Abstract base class for broker integrations.
    
    All broker-specific implementations must inherit from this class
    and implement all abstract methods.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Broker name identifier."""
        pass

    @property
    @abstractmethod
    def supports_live_trading(self) -> bool:
        """Whether this adapter supports live order execution."""
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Market Data Methods
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        """
        Get real-time quote for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "RELIANCE", "NIFTY")
            exchange: Exchange code (NSE, NFO, BSE)
        
        Returns:
            Quote object or None if unavailable
        """
        pass

    @abstractmethod
    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        """
        Get real-time quotes for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            exchange: Exchange code
        
        Returns:
            Dict mapping symbol to Quote
        """
        pass

    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        interval: str,  # "5minute", "15minute", "60minute", "day"
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        """
        Fetch historical OHLCV candles.
        
        Args:
            symbol: Trading symbol
            interval: Candle interval
            from_date: Start date
            to_date: End date
            exchange: Exchange code
        
        Returns:
            List of Candle objects ordered oldest-first
        """
        pass

    @abstractmethod
    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        """
        Fetch option chain for an underlying.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, stock symbol)
            expiry: Specific expiry date (None = nearest expiry)
        
        Returns:
            List of OptionChainRow objects
        """
        pass

    @abstractmethod
    def get_expiries(self, underlying: str) -> List[date]:
        """
        Get available expiry dates for an underlying.
        
        Args:
            underlying: Underlying symbol
        
        Returns:
            List of expiry dates sorted ascending
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Order Execution Methods
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,  # BUY, SELL
        quantity: int,
        order_type: str = "MARKET",  # MARKET, LIMIT, SL, SL-M
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "NRML",  # NRML, MIS, CNC
    ) -> OrderResult:
        """
        Place a single order.
        
        Args:
            symbol: Trading symbol
            exchange: Exchange code
            transaction_type: BUY or SELL
            quantity: Order quantity
            order_type: Order type
            price: Limit price (for LIMIT orders)
            trigger_price: Trigger price (for SL orders)
            product: Product type
        
        Returns:
            OrderResult with order_id and status
        """
        pass

    @abstractmethod
    def place_basket_order(
        self,
        orders: List[Dict[str, Any]],
    ) -> List[OrderResult]:
        """
        Place multiple orders as a basket.
        
        Args:
            orders: List of order dicts with keys:
                    symbol, exchange, transaction_type, quantity,
                    order_type, price, trigger_price, product
        
        Returns:
            List of OrderResult objects
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        """
        Cancel an open order.
        
        Args:
            order_id: Order ID to cancel
            variety: Order variety
        
        Returns:
            True if cancelled successfully
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        Get all open positions.
        
        Returns:
            List of Position objects
        """
        pass

    @abstractmethod
    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Get equity holdings (CNC positions).
        
        Returns:
            List of holding dicts
        """
        pass

    @abstractmethod
    def get_margins(self) -> Dict[str, float]:
        """
        Get account margin details.
        
        Returns:
            Dict with keys: available, used, total
        """
        pass

    @abstractmethod
    def get_order_book(self) -> List[Dict[str, Any]]:
        """
        Get today's order book.
        
        Returns:
            List of order dicts
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_lot_size(self, symbol: str) -> int:
        """Get lot size for F&O symbol. Override in subclass."""
        return 1

    def is_market_open(self) -> bool:
        """Check if market is currently open. Override in subclass."""
        from datetime import datetime
        now = datetime.now()
        # IST market hours: 9:15 AM - 3:30 PM, Mon-Fri
        if now.weekday() >= 5:
            return False
        hour, minute = now.hour, now.minute
        if (hour, minute) < (9, 15) or (hour, minute) > (15, 30):
            return False
        return True
