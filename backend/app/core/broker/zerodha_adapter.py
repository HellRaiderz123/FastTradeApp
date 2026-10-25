"""
ZerodhaBrokerAdapter — Zerodha Kite Connect implementation of BaseBrokerAdapter.

Phase 1.2: Broker Abstraction Layer
"""

import logging
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


class ZerodhaBrokerAdapter(BaseBrokerAdapter):
    """Zerodha Kite Connect implementation."""

    def __init__(self, kite_client=None, dry_run: bool = False):
        """
        Initialize Zerodha adapter.
        
        Args:
            kite_client: KiteConnect client instance (auto-fetched if None)
            dry_run: If True, orders are simulated
        """
        self._kite = kite_client
        self._dry_run = dry_run
        self._instruments_cache: Optional[Dict] = None
        self._instruments_loaded_at: Optional[datetime] = None

    @property
    def kite(self):
        """Lazy-load Kite client."""
        if self._kite is None:
            from app.core.broker.zerodha.client import get_kite_client
            self._kite = get_kite_client()
        return self._kite

    @property
    def name(self) -> str:
        return "zerodha"

    @property
    def supports_live_trading(self) -> bool:
        return not self._dry_run

    # ─────────────────────────────────────────────────────────────────────────
    # Market Data Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_quote(self, symbol: str, exchange: str = "NSE") -> Optional[Quote]:
        try:
            key = f"{exchange}:{symbol}"
            data = self.kite.quote([key])
            if key not in data:
                return None
            q = data[key]
            return Quote(
                symbol=symbol,
                last_price=float(q.get("last_price", 0)),
                open=float(q.get("ohlc", {}).get("open", 0)),
                high=float(q.get("ohlc", {}).get("high", 0)),
                low=float(q.get("ohlc", {}).get("low", 0)),
                close=float(q.get("ohlc", {}).get("close", 0)),
                volume=int(q.get("volume", 0)),
                oi=int(q.get("oi", 0)),
                bid=float((q.get("depth", {}).get("buy", [{}])[0]).get("price", 0)),
                ask=float((q.get("depth", {}).get("sell", [{}])[0]).get("price", 0)),
                timestamp=q.get("timestamp"),
            )
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_quote failed for %s: %s", symbol, e)
            return None

    def get_quotes(self, symbols: List[str], exchange: str = "NSE") -> Dict[str, Quote]:
        result: Dict[str, Quote] = {}
        try:
            keys = [f"{exchange}:{s}" for s in symbols]
            data = self.kite.quote(keys)
            for key, q in data.items():
                sym = key.split(":")[-1]
                result[sym] = Quote(
                    symbol=sym,
                    last_price=float(q.get("last_price", 0)),
                    open=float(q.get("ohlc", {}).get("open", 0)),
                    high=float(q.get("ohlc", {}).get("high", 0)),
                    low=float(q.get("ohlc", {}).get("low", 0)),
                    close=float(q.get("ohlc", {}).get("close", 0)),
                    volume=int(q.get("volume", 0)),
                    oi=int(q.get("oi", 0)),
                    bid=float((q.get("depth", {}).get("buy", [{}])[0]).get("price", 0)),
                    ask=float((q.get("depth", {}).get("sell", [{}])[0]).get("price", 0)),
                    timestamp=q.get("timestamp"),
                )
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_quotes failed: %s", e)
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
            token = self._get_instrument_token(symbol, exchange)
            if not token:
                return []
            
            # Map interval to Kite format
            interval_map = {
                "5minute": "5minute",
                "15minute": "15minute",
                "60minute": "60minute",
                "hour": "60minute",
                "1h": "60minute",
                "day": "day",
                "daily": "day",
            }
            kite_interval = interval_map.get(interval.lower(), interval)
            
            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval=kite_interval,
            )
            
            return [
                Candle(
                    timestamp=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row.get("volume", 0)),
                )
                for row in data
            ]
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_historical_candles failed for %s: %s", symbol, e)
            return []

    def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[date] = None,
    ) -> List[OptionChainRow]:
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            import pandas as pd
            
            instruments = load_instruments()
            if instruments.empty:
                return []
            
            # Filter for underlying
            df = instruments[instruments["name"] == underlying.upper()]
            df = df[df["segment"].str.contains("OPT")]
            
            if df.empty:
                return []
            
            # Get expiry
            if expiry is None:
                today = date.today()
                expiries = pd.to_datetime(df["expiry"]).dt.date.unique()
                future_expiries = sorted([e for e in expiries if e >= today])
                if not future_expiries:
                    return []
                expiry = future_expiries[0]
            
            df = df[pd.to_datetime(df["expiry"]).dt.date == expiry]
            
            # Get LTP for all options
            symbols = df["tradingsymbol"].tolist()
            quotes = self.get_quotes(symbols, exchange="NFO")
            
            rows: List[OptionChainRow] = []
            for _, row in df.iterrows():
                sym = row["tradingsymbol"]
                q = quotes.get(sym)
                rows.append(OptionChainRow(
                    strike=float(row["strike"]),
                    expiry=expiry,
                    option_type=row["instrument_type"],
                    symbol=sym,
                    ltp=q.last_price if q else 0.0,
                    oi=q.oi if q else 0,
                    volume=q.volume if q else 0,
                    bid=q.bid if q else 0.0,
                    ask=q.ask if q else 0.0,
                    lot_size=int(row.get("lot_size", 1)),
                ))
            
            return sorted(rows, key=lambda r: (r.strike, r.option_type))
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_option_chain failed for %s: %s", underlying, e)
            return []

    def get_expiries(self, underlying: str) -> List[date]:
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            import pandas as pd
            
            instruments = load_instruments()
            df = instruments[instruments["name"] == underlying.upper()]
            df = df[df["segment"].str.contains("OPT")]
            
            today = date.today()
            expiries = pd.to_datetime(df["expiry"]).dt.date.unique()
            return sorted([e for e in expiries if e >= today])
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_expiries failed: %s", e)
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
        if self._dry_run:
            return OrderResult(
                order_id=f"DRY_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                status="SIMULATED",
                symbol=symbol,
                quantity=quantity,
                price=price or 0.0,
                transaction_type=transaction_type,
                message="Dry run - order not placed",
            )
        
        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price,
                product=product,
                validity=self.kite.VALIDITY_DAY,
            )
            return OrderResult(
                order_id=str(order_id),
                status="PLACED",
                symbol=symbol,
                quantity=quantity,
                price=price or 0.0,
                transaction_type=transaction_type,
            )
        except Exception as e:
            logger.error("ZerodhaBrokerAdapter.place_order failed: %s", e)
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
        if self._dry_run:
            return True
        try:
            self.kite.cancel_order(variety=variety, order_id=order_id)
            return True
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.cancel_order failed: %s", e)
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Position]:
        try:
            data = self.kite.positions()
            positions: List[Position] = []
            for pos in data.get("net", []):
                if pos.get("quantity", 0) == 0:
                    continue
                positions.append(Position(
                    symbol=pos["tradingsymbol"],
                    quantity=int(pos["quantity"]),
                    average_price=float(pos.get("average_price", 0)),
                    last_price=float(pos.get("last_price", 0)),
                    pnl=float(pos.get("pnl", 0)),
                    product=pos.get("product", "NRML"),
                    exchange=pos.get("exchange", "NFO"),
                ))
            return positions
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_positions failed: %s", e)
            return []

    def get_holdings(self) -> List[Dict[str, Any]]:
        try:
            return self.kite.holdings() or []
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_holdings failed: %s", e)
            return []

    def get_margins(self) -> Dict[str, float]:
        try:
            data = self.kite.margins()
            equity = data.get("equity", {})
            return {
                "available": float(equity.get("available", {}).get("cash", 0)),
                "used": float(equity.get("utilised", {}).get("debits", 0)),
                "total": float(equity.get("net", 0)),
            }
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_margins failed: %s", e)
            return {"available": 0.0, "used": 0.0, "total": 0.0}

    def get_order_book(self) -> List[Dict[str, Any]]:
        try:
            return self.kite.orders() or []
        except Exception as e:
            logger.warning("ZerodhaBrokerAdapter.get_order_book failed: %s", e)
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _get_instrument_token(self, symbol: str, exchange: str) -> Optional[int]:
        """Get instrument token for a symbol."""
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            
            instruments = load_instruments()
            if instruments.empty:
                return None
            
            # Handle index symbols
            if symbol.upper() in ("NIFTY", "NIFTY 50"):
                row = instruments[
                    (instruments["tradingsymbol"] == "NIFTY 50") &
                    (instruments["exchange"] == "NSE")
                ]
            elif symbol.upper() in ("BANKNIFTY", "NIFTY BANK"):
                row = instruments[
                    (instruments["tradingsymbol"] == "NIFTY BANK") &
                    (instruments["exchange"] == "NSE")
                ]
            else:
                row = instruments[
                    (instruments["tradingsymbol"] == symbol) &
                    (instruments["exchange"] == exchange)
                ]
            
            if row.empty:
                return None
            return int(row.iloc[0]["instrument_token"])
        except Exception as e:
            logger.warning("_get_instrument_token failed for %s: %s", symbol, e)
            return None

    def get_lot_size(self, symbol: str) -> int:
        """Get lot size for F&O symbol."""
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            
            instruments = load_instruments()
            row = instruments[instruments["name"] == symbol.upper()]
            if not row.empty:
                return int(row.iloc[0].get("lot_size", 1))
            return 1
        except Exception:
            return 1
