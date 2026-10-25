"""
PaperTradingBrokerAdapter — Paper trading implementation with realistic simulation.

Phase 1.2: Broker Abstraction Layer
Implements realistic slippage (0.05% for cash, bid-ask spread for options)
and brokerage/STT/GST cost deduction.
"""

import logging
import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from app.core.broker.base_adapter import (
    BaseBrokerAdapter,
    Candle,
    OptionChainRow,
    OrderResult,
    Position,
    Quote,
)

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """Internal paper position tracking."""
    symbol: str
    quantity: int
    average_price: float
    product: str
    exchange: str
    entry_time: datetime = field(default_factory=datetime.now)


@dataclass
class PaperOrder:
    """Internal paper order tracking."""
    order_id: str
    symbol: str
    exchange: str
    transaction_type: str
    quantity: int
    price: float
    status: str
    timestamp: datetime = field(default_factory=datetime.now)


class PaperTradingBrokerAdapter(BaseBrokerAdapter):
    """
    Paper trading adapter with realistic simulation.
    
    Features:
    - Slippage: 0.05% for equities, bid-ask spread for options
    - Brokerage: Rs 20 per order (Zerodha-style)
    - STT: 0.1% on sell side for delivery, 0.025% for intraday
    - GST: 18% on brokerage
    - Exchange charges: ~0.003%
    """

    # Cost parameters (Zerodha-style)
    BROKERAGE_PER_ORDER = 20.0
    STT_DELIVERY_SELL = 0.001  # 0.1%
    STT_INTRADAY = 0.00025    # 0.025%
    STT_OPTIONS = 0.0005      # 0.05% on premium (sell side)
    GST_RATE = 0.18           # 18%
    EXCHANGE_CHARGES = 0.00003  # 0.003%
    SEBI_CHARGES = 0.000001   # Rs 10 per crore
    STAMP_DUTY = 0.00015      # 0.015% (buy side)
    
    # Slippage parameters
    EQUITY_SLIPPAGE = 0.0005  # 0.05%
    OPTION_SLIPPAGE_TICKS = 0.05  # Rs 0.05 per lot

    def __init__(self, initial_capital: float = 1_00_00_000.0):  # 1 Crore default
        """
        Initialize paper trading adapter.
        
        Args:
            initial_capital: Starting capital in INR
        """
        self._initial_capital = initial_capital
        self._available_capital = initial_capital
        self._positions: Dict[str, PaperPosition] = {}
        self._orders: List[PaperOrder] = []
        self._order_counter = 0
        self._realized_pnl = 0.0
        self._total_costs = 0.0
        
        # Data source adapter (uses Zerodha for market data)
        self._data_adapter: Optional[BaseBrokerAdapter] = None

    @property
    def data_adapter(self) -> BaseBrokerAdapter:
        """Lazy-load data adapter."""
        if self._data_adapter is None:
            from app.core.broker.zerodha_adapter import ZerodhaBrokerAdapter
            self._data_adapter = ZerodhaBrokerAdapter(dry_run=True)
        return self._data_adapter

    @property
    def name(self) -> str:
        return "paper"

    @property
    def supports_live_trading(self) -> bool:
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Market Data Methods (delegated to data adapter)
    # ─────────────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        return self.data_adapter.get_quote(symbol, exchange)

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        return self.data_adapter.get_quotes(symbols, exchange)

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        return self.data_adapter.get_historical_candles(symbol, interval, from_date, to_date, exchange)

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        return self.data_adapter.get_option_chain(underlying, expiry)

    def get_expiries(self, underlying: str) -> List[date]:
        return self.data_adapter.get_expiries(underlying)

    # ─────────────────────────────────────────────────────────────────────────
    # Order Execution Methods (simulated)
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
        self._order_counter += 1
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d')}_{self._order_counter:06d}"
        
        # Get current market price
        quote = self.get_quote(symbol, exchange)
        if not quote:
            return OrderResult(
                order_id=order_id,
                status="REJECTED",
                symbol=symbol,
                quantity=quantity,
                price=0.0,
                transaction_type=transaction_type,
                message="Could not fetch market price",
            )
        
        # Calculate execution price with slippage
        is_option = exchange == "NFO" and any(x in symbol for x in ["CE", "PE"])
        exec_price = self._apply_slippage(
            quote.last_price,
            quote.bid,
            quote.ask,
            transaction_type,
            is_option,
        )
        
        # Calculate transaction costs
        is_intraday = product in ("MIS", "INTRADAY")
        costs = self._calculate_costs(
            exec_price,
            quantity,
            transaction_type,
            is_option,
            is_intraday,
        )
        
        # Check capital for buy orders
        total_value = exec_price * quantity + costs
        if transaction_type == "BUY" and total_value > self._available_capital:
            return OrderResult(
                order_id=order_id,
                status="REJECTED",
                symbol=symbol,
                quantity=quantity,
                price=exec_price,
                transaction_type=transaction_type,
                message=f"Insufficient capital. Required: {total_value:.2f}, Available: {self._available_capital:.2f}",
            )
        
        # Execute order
        if transaction_type == "BUY":
            self._execute_buy(symbol, exchange, quantity, exec_price, product, costs)
        else:
            pnl = self._execute_sell(symbol, exchange, quantity, exec_price, product, costs)
            self._realized_pnl += pnl
        
        self._total_costs += costs
        
        # Record order
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            price=exec_price,
            status="FILLED",
        )
        self._orders.append(order)
        
        logger.info(
            "Paper order executed: %s %s %d @ %.2f (costs: %.2f)",
            transaction_type, symbol, quantity, exec_price, costs
        )
        
        return OrderResult(
            order_id=order_id,
            status="FILLED",
            symbol=symbol,
            quantity=quantity,
            price=exec_price,
            transaction_type=transaction_type,
            message=f"Simulated fill with costs: {costs:.2f}",
        )

    def place_basket_order(self, orders: List[Dict[str, Any]]) -> List[OrderResult]:
        results: List[OrderResult] = []
        for order in orders:
            result = self.place_order(
                symbol=order["symbol"],
                exchange=order.get("exchange", "NFO"),
                transaction_type=order["transaction_type"],
                quantity=order["quantity"],
                order_type=order.get("order_type", "MARKET"),
                price=order.get("price"),
                trigger_price=order.get("trigger_price"),
                product=order.get("product", "NRML"),
            )
            results.append(result)
        return results

    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        # Paper orders are instant-fill, so nothing to cancel
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        positions: List[Position] = []
        for key, pos in self._positions.items():
            if pos.quantity == 0:
                continue
            
            # Get current price
            quote = self.get_quote(pos.symbol, pos.exchange)
            last_price = quote.last_price if quote else pos.average_price
            pnl = (last_price - pos.average_price) * pos.quantity
            
            positions.append(Position(
                symbol=pos.symbol,
                quantity=pos.quantity,
                average_price=pos.average_price,
                last_price=last_price,
                pnl=pnl,
                product=pos.product,
                exchange=pos.exchange,
            ))
        return positions

    def get_holdings(self) -> List[Dict[str, Any]]:
        # Paper trading doesn't have CNC holdings
        return []

    def get_margins(self) -> Dict[str, float]:
        # Calculate used margin from positions
        used = sum(
            pos.average_price * abs(pos.quantity)
            for pos in self._positions.values()
            if pos.quantity != 0
        )
        return {
            "available": self._available_capital,
            "used": used,
            "total": self._initial_capital,
        }

    def get_order_book(self) -> List[Dict[str, Any]]:
        return [
            {
                "order_id": o.order_id,
                "tradingsymbol": o.symbol,
                "exchange": o.exchange,
                "transaction_type": o.transaction_type,
                "quantity": o.quantity,
                "price": o.price,
                "status": o.status,
                "order_timestamp": o.timestamp.isoformat(),
            }
            for o in self._orders[-100:]  # Last 100 orders
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Paper Trading Specific Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_pnl_summary(self) -> Dict[str, float]:
        """Get P&L summary for paper trading."""
        unrealized = sum(
            (self.get_quote(pos.symbol, pos.exchange).last_price - pos.average_price) * pos.quantity
            for pos in self._positions.values()
            if pos.quantity != 0 and self.get_quote(pos.symbol, pos.exchange)
        )
        return {
            "realized_pnl": self._realized_pnl,
            "unrealized_pnl": unrealized,
            "total_pnl": self._realized_pnl + unrealized,
            "total_costs": self._total_costs,
            "net_pnl": self._realized_pnl + unrealized - self._total_costs,
            "initial_capital": self._initial_capital,
            "current_capital": self._available_capital + unrealized,
        }

    def reset(self) -> None:
        """Reset paper trading state."""
        self._available_capital = self._initial_capital
        self._positions.clear()
        self._orders.clear()
        self._order_counter = 0
        self._realized_pnl = 0.0
        self._total_costs = 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_slippage(
        self,
        last_price: float,
        bid: float,
        ask: float,
        transaction_type: str,
        is_option: bool,
    ) -> float:
        """Apply realistic slippage to execution price."""
        if is_option:
            # Options: use bid-ask spread + small random slippage
            if transaction_type == "BUY":
                base = ask if ask > 0 else last_price
                slippage = self.OPTION_SLIPPAGE_TICKS * random.uniform(0.5, 1.5)
                return round(base + slippage, 2)
            else:
                base = bid if bid > 0 else last_price
                slippage = self.OPTION_SLIPPAGE_TICKS * random.uniform(0.5, 1.5)
                return round(max(0.05, base - slippage), 2)
        else:
            # Equities: percentage slippage
            slippage_pct = self.EQUITY_SLIPPAGE * random.uniform(0.5, 1.5)
            if transaction_type == "BUY":
                return round(last_price * (1 + slippage_pct), 2)
            else:
                return round(last_price * (1 - slippage_pct), 2)

    def _calculate_costs(
        self,
        price: float,
        quantity: int,
        transaction_type: str,
        is_option: bool,
        is_intraday: bool,
    ) -> float:
        """Calculate transaction costs (brokerage, STT, GST, etc.)."""
        turnover = price * quantity
        
        # Brokerage (capped at Rs 20)
        brokerage = min(self.BROKERAGE_PER_ORDER, turnover * 0.0003)
        
        # STT (only on sell side for options, both sides for equity delivery)
        stt = 0.0
        if is_option:
            if transaction_type == "SELL":
                stt = turnover * self.STT_OPTIONS
        else:
            if is_intraday:
                if transaction_type == "SELL":
                    stt = turnover * self.STT_INTRADAY
            else:
                stt = turnover * self.STT_DELIVERY_SELL
        
        # GST on brokerage
        gst = brokerage * self.GST_RATE
        
        # Exchange charges
        exchange = turnover * self.EXCHANGE_CHARGES
        
        # SEBI charges
        sebi = turnover * self.SEBI_CHARGES
        
        # Stamp duty (buy side only)
        stamp = turnover * self.STAMP_DUTY if transaction_type == "BUY" else 0.0
        
        return round(brokerage + stt + gst + exchange + sebi + stamp, 2)

    def _execute_buy(
        self,
        symbol: str,
        exchange: str,
        quantity: int,
        price: float,
        product: str,
        costs: float,
    ) -> None:
        """Execute a buy order."""
        key = f"{exchange}:{symbol}"
        total_cost = price * quantity + costs
        
        if key in self._positions:
            pos = self._positions[key]
            # Average up/down
            total_qty = pos.quantity + quantity
            if total_qty != 0:
                pos.average_price = (
                    (pos.average_price * pos.quantity + price * quantity) / total_qty
                )
            pos.quantity = total_qty
        else:
            self._positions[key] = PaperPosition(
                symbol=symbol,
                quantity=quantity,
                average_price=price,
                product=product,
                exchange=exchange,
            )
        
        self._available_capital -= total_cost

    def _execute_sell(
        self,
        symbol: str,
        exchange: str,
        quantity: int,
        price: float,
        product: str,
        costs: float,
    ) -> float:
        """Execute a sell order. Returns realized P&L."""
        key = f"{exchange}:{symbol}"
        
        if key not in self._positions:
            # Short sell (new position)
            self._positions[key] = PaperPosition(
                symbol=symbol,
                quantity=-quantity,
                average_price=price,
                product=product,
                exchange=exchange,
            )
            self._available_capital += price * quantity - costs
            return 0.0
        
        pos = self._positions[key]
        
        if pos.quantity > 0:
            # Closing long position
            sell_qty = min(quantity, pos.quantity)
            pnl = (price - pos.average_price) * sell_qty - costs
            pos.quantity -= sell_qty
            self._available_capital += price * sell_qty - costs
            
            if pos.quantity == 0:
                del self._positions[key]
            
            return pnl
        else:
            # Adding to short position
            total_qty = pos.quantity - quantity
            pos.average_price = (
                (pos.average_price * abs(pos.quantity) + price * quantity) / abs(total_qty)
            )
            pos.quantity = total_qty
            self._available_capital += price * quantity - costs
            return 0.0
