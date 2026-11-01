"""
INDMoneyBrokerAdapter — INDMoney/INDstocks implementation of BaseBrokerAdapter.

Phase 1.2: Broker Abstraction Layer
"""

import logging
import os
from datetime import date, datetime, timedelta
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


class INDMoneyBrokerAdapter(BaseBrokerAdapter):
    """INDMoney/INDstocks implementation."""

    def __init__(self):
        """Initialize INDMoney adapter."""
        self._client = None

    @property
    def client(self):
        """Lazy-load INDMoney client."""
        if self._client is None:
            try:
                from app.core.broker.indmoney.client import get_indmoney_client
                self._client = get_indmoney_client()
            except Exception as e:
                logger.warning("INDMoneyBrokerAdapter: client init failed: %s", e)
        return self._client

    @property
    def name(self) -> str:
        return "indmoney"

    @property
    def supports_live_trading(self) -> bool:
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # Market Data Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        try:
            from app.core.broker.indstocks.market_data import get_quote as indstocks_quote
            data = indstocks_quote(symbol)
            if not data:
                return None
            return Quote(
                symbol=symbol,
                last_price=float(data.get("ltp") or data.get("last_price") or 0),
                open=float(data.get("open") or 0),
                high=float(data.get("high") or 0),
                low=float(data.get("low") or 0),
                close=float(data.get("close") or data.get("prev_close") or 0),
                volume=int(data.get("volume") or 0),
                oi=int(data.get("oi") or 0),
                bid=float(data.get("bid") or 0),
                ask=float(data.get("ask") or 0),
            )
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_quote failed for %s: %s", symbol, e)
            return None

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        result: Dict[str, Quote] = {}
        try:
            from app.core.broker.indstocks.market_data import get_bulk_quotes
            data = get_bulk_quotes(symbols)
            for sym, q in (data or {}).items():
                result[sym] = Quote(
                    symbol=sym,
                    last_price=float(q.get("ltp") or q.get("last_price") or 0),
                    open=float(q.get("open") or 0),
                    high=float(q.get("high") or 0),
                    low=float(q.get("low") or 0),
                    close=float(q.get("close") or q.get("prev_close") or 0),
                    volume=int(q.get("volume") or 0),
                    oi=int(q.get("oi") or 0),
                    bid=float(q.get("bid") or 0),
                    ask=float(q.get("ask") or 0),
                )
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_quotes failed: %s", e)
        return result

    def get_historical_candles(
        self,
        symbol: str,
        interval: str,
        from_date: date,
        to_date: date,
        exchange: str = "NSE",
    ) -> List[Candle]:
        try:
            from app.core.broker.indstocks.market_data import get_historical_data
            
            # Map interval to INDstocks format
            interval_map = {
                "5minute": "5m",
                "15minute": "15m",
                "60minute": "1h",
                "hour": "1h",
                "1h": "1h",
                "day": "1d",
                "daily": "1d",
            }
            ind_interval = interval_map.get(interval.lower(), interval)
            
            data = get_historical_data(symbol, ind_interval, from_date, to_date)
            
            return [
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]) if isinstance(row["timestamp"], str) else row["timestamp"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row.get("volume", 0)),
                )
                for row in (data or [])
            ]
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_historical_candles failed for %s: %s", symbol, e)
            return []

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        try:
            from app.core.broker.indstocks.market_data import get_option_chain as ind_option_chain
            data = ind_option_chain(underlying, expiry)
            
            rows: List[OptionChainRow] = []
            for row in (data or []):
                rows.append(OptionChainRow(
                    strike=float(row.get("strike", 0)),
                    expiry=expiry or date.today(),
                    option_type=row.get("option_type", "CE"),
                    symbol=row.get("symbol", ""),
                    ltp=float(row.get("ltp", 0)),
                    oi=int(row.get("oi", 0)),
                    volume=int(row.get("volume", 0)),
                    bid=float(row.get("bid", 0)),
                    ask=float(row.get("ask", 0)),
                    lot_size=int(row.get("lot_size", 1)),
                ))
            return rows
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_option_chain failed for %s: %s", underlying, e)
            return []

    def get_expiries(self, underlying: str) -> List[date]:
        try:
            from app.core.broker.indstocks.market_data import get_expiries as ind_expiries
            return ind_expiries(underlying) or []
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_expiries failed: %s", e)
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Order Execution Methods
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
        try:
            if not self.client:
                return OrderResult(
                    order_id="",
                    status="REJECTED",
                    symbol=symbol,
                    quantity=quantity,
                    price=price or 0.0,
                    transaction_type=transaction_type,
                    message="INDMoney client not initialized",
                )
            
            result = self.client.place_order(
                symbol=symbol,
                exchange=exchange,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price,
                product=product,
            )
            
            return OrderResult(
                order_id=str(result.get("order_id", "")),
                status=result.get("status", "PLACED"),
                symbol=symbol,
                quantity=quantity,
                price=price or 0.0,
                transaction_type=transaction_type,
                message=result.get("message"),
            )
        except Exception as e:
            logger.error("INDMoneyBrokerAdapter.place_order failed: %s", e)
            return OrderResult(
                order_id="",
                status="REJECTED",
                symbol=symbol,
                quantity=quantity,
                price=price or 0.0,
                transaction_type=transaction_type,
                message=str(e),
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
        try:
            if not self.client:
                return False
            self.client.cancel_order(order_id)
            return True
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.cancel_order failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        try:
            if not self.client:
                return []
            data = self.client.get_positions()
            positions: List[Position] = []
            for pos in (data or []):
                if pos.get("quantity", 0) == 0:
                    continue
                positions.append(Position(
                    symbol=pos.get("symbol", ""),
                    quantity=int(pos.get("quantity", 0)),
                    average_price=float(pos.get("average_price", 0)),
                    last_price=float(pos.get("last_price", 0)),
                    pnl=float(pos.get("pnl", 0)),
                    product=pos.get("product", "NRML"),
                    exchange=pos.get("exchange", "NFO"),
                ))
            return positions
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_positions failed: %s", e)
            return []

    def get_holdings(self) -> List[Dict[str, Any]]:
        # INDMoney holdings API not yet integrated
        logger.warning("INDMoneyBrokerAdapter.get_holdings not implemented")
        return []

    def get_margins(self) -> Dict[str, float]:
        try:
            if not self.client:
                return {"available": 0.0, "used": 0.0, "total": 0.0}
            data = self.client.get_funds()
            return {
                "available": float(data.get("available_balance") or data.get("available") or 0),
                "used": float(data.get("used_margin") or data.get("used") or 0),
                "total": float(data.get("total") or data.get("net") or 0),
            }
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_margins failed: %s", e)
            return {"available": 0.0, "used": 0.0, "total": 0.0}

    def get_order_book(self) -> List[Dict[str, Any]]:
        try:
            if not self.client:
                return []
            return self.client.get_orders() or []
        except Exception as e:
            logger.warning("INDMoneyBrokerAdapter.get_order_book failed: %s", e)
            return []

    def get_lot_size(self, symbol: str) -> int:
        """Get lot size for F&O symbol."""
        try:
            from app.core.broker.indstocks.instruments_sync import get_lot_size
            return get_lot_size(symbol) or 1
        except Exception:
            return 1
