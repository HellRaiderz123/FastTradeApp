"""
PaperBrokerAdapter — Paper trading implementation of BaseBrokerAdapter.

Simulates trading without real orders. Uses mock data or falls back to
real market data from configured data broker for quotes.
"""

import logging
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.broker.base_adapter import (
    BaseBrokerAdapter,
    Candle,
    OptionChainRow,
    OrderResult,
    Position,
    Quote,
)

logger = logging.getLogger(__name__)


class PaperBrokerAdapter(BaseBrokerAdapter):
    """Paper trading adapter for simulation."""

    def __init__(self, initial_capital: float = 10_000_000.0):
        """
        Initialize paper trading adapter.
        
        Args:
            initial_capital: Starting capital for paper trading (default ₹1 Crore)
        """
        self._capital = initial_capital
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._orders: List[Dict[str, Any]] = []
        self._order_counter = 0

    @property
    def name(self) -> str:
        return "paper"

    @property
    def supports_live_trading(self) -> bool:
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Market Data Methods (delegate to data broker)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_data_adapter(self):
        """Get the data broker adapter for market data."""
        try:
            from app.core.broker.registry import get_data_broker
            broker = get_data_broker()
            if broker == "ZERODHA":
                from app.core.broker.zerodha_adapter import ZerodhaBrokerAdapter
                return ZerodhaBrokerAdapter()
            elif broker == "INDMONEY":
                from app.core.broker.indmoney_adapter import INDMoneyBrokerAdapter
                return INDMoneyBrokerAdapter()
        except Exception as e:
            logger.warning("PaperBrokerAdapter: data adapter fallback failed: %s", e)
        return None

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        adapter = self._get_data_adapter()
        if adapter:
            return adapter.get_quote(symbol, exchange)
        # Return mock quote if no data adapter
        return Quote(
            symbol=symbol,
            last_price=100.0,
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            volume=10000,
        )

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        adapter = self._get_data_adapter()
        if adapter:
            return adapter.get_quotes(symbols, exchange)
        return {s: self.get_quote(s, exchange) for s in symbols}

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        adapter = self._get_data_adapter()
        if adapter:
            return adapter.get_historical_candles(symbol, interval, from_date, to_date, exchange)
        return []

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        adapter = self._get_data_adapter()
        if adapter:
            return adapter.get_option_chain(underlying, expiry)
        return []

    def get_expiries(self, underlying: str) -> List[date]:
        adapter = self._get_data_adapter()
        if adapter:
            return adapter.get_expiries(underlying)
        return []

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
        order_id = f"PAPER_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._order_counter}"
        
        # Get current price for the symbol
        quote = self.get_quote(symbol, exchange)
        fill_price = price if price else (quote.last_price if quote else 100.0)
        
        # Record the order
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "exchange": exchange,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "order_type": order_type,
            "price": fill_price,
            "trigger_price": trigger_price,
            "product": product,
            "status": "COMPLETE",
            "filled_quantity": quantity,
            "timestamp": datetime.now().isoformat(),
        }
        self._orders.append(order)
        
        # Update positions
        self._update_position(symbol, exchange, transaction_type, quantity, fill_price, product)
        
        logger.info(
            "PaperBrokerAdapter: %s %d %s @ %.2f (order_id=%s)",
            transaction_type, quantity, symbol, fill_price, order_id
        )
        
        return OrderResult(
            order_id=order_id,
            status="COMPLETE",
            symbol=symbol,
            quantity=quantity,
            price=fill_price,
            transaction_type=transaction_type,
            message="Paper trade executed",
        )

    def _update_position(
        self,
        symbol: str,
        exchange: str,
        transaction_type: str,
        quantity: int,
        price: float,
        product: str,
    ):
        """Update internal position tracking."""
        key = f"{exchange}:{symbol}"
        
        if key not in self._positions:
            self._positions[key] = {
                "symbol": symbol,
                "exchange": exchange,
                "quantity": 0,
                "average_price": 0.0,
                "product": product,
            }
        
        pos = self._positions[key]
        
        if transaction_type == "BUY":
            # Calculate new average price
            total_value = (pos["quantity"] * pos["average_price"]) + (quantity * price)
            new_qty = pos["quantity"] + quantity
            pos["average_price"] = total_value / new_qty if new_qty > 0 else 0
            pos["quantity"] = new_qty
        else:  # SELL
            pos["quantity"] -= quantity
            if pos["quantity"] <= 0:
                pos["quantity"] = 0
                pos["average_price"] = 0.0

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
        for order in self._orders:
            if order["order_id"] == order_id and order["status"] != "COMPLETE":
                order["status"] = "CANCELLED"
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        positions: List[Position] = []
        for key, pos in self._positions.items():
            if pos["quantity"] == 0:
                continue
            
            # Get current price
            quote = self.get_quote(pos["symbol"], pos["exchange"])
            last_price = quote.last_price if quote else pos["average_price"]
            pnl = (last_price - pos["average_price"]) * pos["quantity"]
            
            positions.append(Position(
                symbol=pos["symbol"],
                quantity=pos["quantity"],
                average_price=pos["average_price"],
                last_price=last_price,
                pnl=pnl,
                product=pos["product"],
                exchange=pos["exchange"],
            ))
        return positions

    def get_holdings(self) -> List[Dict[str, Any]]:
        # Paper trading doesn't have holdings (CNC positions)
        return []

    def get_margins(self) -> Dict[str, float]:
        # Calculate used margin from positions
        used = sum(
            abs(pos["quantity"] * pos["average_price"]) * 0.2  # Assume 20% margin
            for pos in self._positions.values()
            if pos["quantity"] != 0
        )
        return {
            "available": self._capital - used,
            "used": used,
            "total": self._capital,
        }

    def get_order_book(self) -> List[Dict[str, Any]]:
        return self._orders.copy()

    # ─────────────────────────────────────────────────────────────────────────
    # Paper Trading Specific Methods
    # ─────────────────────────────────────────────────────────────────────────

    def reset(self, capital: Optional[float] = None):
        """Reset paper trading state."""
        self._positions.clear()
        self._orders.clear()
        self._order_counter = 0
        if capital is not None:
            self._capital = capital
        logger.info("PaperBrokerAdapter: reset (capital=%.2f)", self._capital)

    def get_pnl(self) -> float:
        """Get total unrealized P&L."""
        return sum(pos.pnl for pos in self.get_positions())
