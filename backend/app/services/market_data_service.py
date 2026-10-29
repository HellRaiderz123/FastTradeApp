"""
Broker-agnostic market data service.

Active broker is resolved from ACTIVE_BROKER env var (ZERODHA | INDMONEY).
Falls back to the other broker automatically if the primary is unavailable.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Normalised types ───────────────────────────────────────────────────────

class SpotQuote:
    __slots__ = ("symbol", "last_price", "open", "high", "low", "close", "volume")

    def __init__(self, symbol: str, last_price: float, open: float = 0.0,
                 high: float = 0.0, low: float = 0.0, close: float = 0.0, volume: int = 0):
        self.symbol = symbol
        self.last_price = last_price
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


class OptionQuote:
    __slots__ = ("symbol", "ltp", "open", "high", "low", "close", "volume", "oi", "bid", "ask")

    def __init__(self, symbol: str, ltp: float, open: float = 0.0, high: float = 0.0,
                 low: float = 0.0, close: float = 0.0, volume: int = 0,
                 oi: int = 0, bid: float = 0.0, ask: float = 0.0):
        self.symbol = symbol
        self.ltp = ltp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.oi = oi
        self.bid = bid
        self.ask = ask


class DepthLevel:
    __slots__ = ("price", "quantity", "orders")

    def __init__(self, price: float, quantity: int, orders: int = 0):
        self.price = price
        self.quantity = quantity
        self.orders = orders


class MarketDepth:
    __slots__ = ("symbol", "bids", "asks", "ltp", "volume", "open", "high", "low",
                 "prev_close", "oi", "total_buy_qty", "total_sell_qty", "data_source")

    def __init__(self, symbol: str, bids: List[DepthLevel], asks: List[DepthLevel],
                 ltp: float = 0.0, volume: int = 0, open: float = 0.0,
                 high: float = 0.0, low: float = 0.0, prev_close: float = 0.0,
                 oi: int = 0, total_buy_qty: int = 0, total_sell_qty: int = 0,
                 data_source: str = ""):
        self.symbol = symbol
        self.bids = bids
        self.asks = asks
        self.ltp = ltp
        self.volume = volume
        self.open = open
        self.high = high
        self.low = low
        self.prev_close = prev_close
        self.oi = oi
        self.total_buy_qty = total_buy_qty
        self.total_sell_qty = total_sell_qty
        self.data_source = data_source


# ── Abstract broker data adapter ───────────────────────────────────────────

class BrokerDataAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_spot_quote(self, symbol: str) -> Optional[SpotQuote]: ...

    @abstractmethod
    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> Optional[MarketDepth]: ...

    @abstractmethod
    def get_option_quotes(self, nfo_symbols: List[str]) -> Dict[str, OptionQuote]:
        """Keys in returned dict are plain tradingsymbols (no exchange prefix)."""
        ...

    @abstractmethod
    def get_option_expiries(self, underlying: str) -> List[date]: ...

    @abstractmethod
    def get_option_strikes(self, underlying: str, expiry: date) -> List[Tuple[int, str]]:
        """Returns list of (strike, option_type) tuples available for the expiry."""
        ...


# ── Zerodha adapter ────────────────────────────────────────────────────────

class ZerodhaDataAdapter(BrokerDataAdapter):
    @property
    def name(self) -> str:
        return "ZERODHA"

    def is_available(self) -> bool:
        try:
            from app.db.session import SessionLocal
            from app.core.broker.zerodha.oauth import get_active_session
            db = SessionLocal()
            try:
                return get_active_session(db) is not None
            finally:
                db.close()
        except Exception:
            return False

    def get_spot_quote(self, symbol: str) -> Optional[SpotQuote]:
        try:
            from app.services.zerodha import KiteConnectService
            data = KiteConnectService().get_full_quote(symbol)
            if not data or not data.get("last_price"):
                return None
            ohlc = data.get("ohlc") or {}
            return SpotQuote(
                symbol=symbol,
                last_price=float(data["last_price"]),
                open=float(ohlc.get("open", 0)),
                high=float(ohlc.get("high", 0)),
                low=float(ohlc.get("low", 0)),
                close=float(ohlc.get("close", 0)),
                volume=int(data.get("volume", 0)),
            )
        except Exception as e:
            logger.warning("ZerodhaDataAdapter.get_spot_quote failed for %s: %s", symbol, e)
            return None

    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> Optional[MarketDepth]:
        try:
            from app.services.zerodha import KiteConnectService
            data = KiteConnectService().get_full_quote(symbol)
            if not data:
                return None
            ohlc = data.get("ohlc") or {}
            ltp = float(data.get("last_price") or 0)
            raw_depth = data.get("depth") or {}
            buy_levels = raw_depth.get("buy") or []
            sell_levels = raw_depth.get("sell") or []

            bids = [
                DepthLevel(
                    price=float(lvl.get("price", 0)),
                    quantity=int(lvl.get("quantity", 0)),
                    orders=int(lvl.get("orders", 0)),
                )
                for lvl in buy_levels[:5]
            ]
            asks = [
                DepthLevel(
                    price=float(lvl.get("price", 0)),
                    quantity=int(lvl.get("quantity", 0)),
                    orders=int(lvl.get("orders", 0)),
                )
                for lvl in sell_levels[:5]
            ]
            # Pad to 5 levels
            while len(bids) < 5:
                bids.append(DepthLevel(0.0, 0))
            while len(asks) < 5:
                asks.append(DepthLevel(0.0, 0))

            return MarketDepth(
                symbol=symbol,
                bids=bids,
                asks=asks,
                ltp=ltp,
                volume=int(data.get("volume", 0)),
                open=float(ohlc.get("open", 0)),
                high=float(ohlc.get("high", 0)),
                low=float(ohlc.get("low", 0)),
                prev_close=float(ohlc.get("close", 0)),
                oi=int(data.get("oi", 0)),
                total_buy_qty=int(data.get("buy_quantity", 0)),
                total_sell_qty=int(data.get("sell_quantity", 0)),
                data_source="ZERODHA",
            )
        except Exception as e:
            logger.warning("ZerodhaDataAdapter.get_market_depth failed for %s: %s", symbol, e)
            return None

    def get_option_quotes(self, nfo_symbols: List[str]) -> Dict[str, OptionQuote]:
        try:
            from app.services.zerodha import KiteConnectService
            raw = KiteConnectService().get_bulk_quotes([f"NFO:{s}" for s in nfo_symbols])
            if not raw:
                return {}
            result: Dict[str, OptionQuote] = {}
            for key, q in raw.items():
                sym = key.replace("NFO:", "")
                ohlc = q.get("ohlc") or {}
                depth = q.get("depth") or {}
                buy_levels = depth.get("buy") or [{}]
                sell_levels = depth.get("sell") or [{}]
                result[sym] = OptionQuote(
                    symbol=sym,
                    ltp=float(q.get("last_price", 0)),
                    open=float(ohlc.get("open", 0)),
                    high=float(ohlc.get("high", 0)),
                    low=float(ohlc.get("low", 0)),
                    close=float(ohlc.get("close", 0)),
                    volume=int(q.get("volume", 0)),
                    oi=int(q.get("oi", 0)),
                    bid=float((buy_levels[0] if buy_levels else {}).get("price", 0)),
                    ask=float((sell_levels[0] if sell_levels else {}).get("price", 0)),
                )
            return result
        except Exception as e:
            logger.warning("ZerodhaDataAdapter.get_option_quotes failed: %s", e)
            return {}

    def get_option_expiries(self, underlying: str) -> List[date]:
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            import pandas as pd
            df = load_instruments(exchange="NFO")
            df = df[(df["name"] == underlying.upper()) & (df["instrument_type"].isin(["CE", "PE"]))]
            today = date.today()
            expiries = pd.to_datetime(df["expiry"]).dt.date.unique()
            return sorted(e for e in expiries if e >= today)
        except Exception as e:
            logger.warning("ZerodhaDataAdapter.get_option_expiries failed: %s", e)
            return []

    def get_option_strikes(self, underlying: str, expiry: date) -> List[Tuple[int, str]]:
        try:
            from app.core.broker.zerodha.instruments import load_instruments
            df = load_instruments(exchange="NFO")
            df = df[
                (df["name"] == underlying.upper()) &
                (df["expiry"] == expiry) &
                (df["instrument_type"].isin(["CE", "PE"]))
            ]
            return [(int(row["strike"]), str(row["instrument_type"])) for _, row in df.iterrows()]
        except Exception as e:
            logger.warning("ZerodhaDataAdapter.get_option_strikes failed: %s", e)
            return []


# ── INDMoney adapter ───────────────────────────────────────────────────────

def _clean_num(value, default=0):
    """Strip commas and convert to int or float (mirrors OpenAlgo's _clean_number)."""
    if value is None:
        return default
    try:
        v = float(str(value).replace(",", "").strip())
        return int(v) if isinstance(default, int) and v == int(v) else v
    except (ValueError, TypeError):
        return default


def _extract_ind_market_depth(container: dict, scrip_code: str) -> dict:
    """
    Pull the {aggregate, depth} object out of a market_depth value.
    Handles both the documented flat shape and the observed extra scrip-keyed level.
    Mirrors OpenAlgo's BrokerData._extract_market_depth.
    """
    if not isinstance(container, dict):
        return {}
    nested = container.get(scrip_code)
    if isinstance(nested, dict) and ("depth" in nested or "aggregate" in nested):
        return nested
    if "depth" in container or "aggregate" in container:
        return container
    if len(container) == 1:
        only = next(iter(container.values()))
        if isinstance(only, dict) and ("depth" in only or "aggregate" in only):
            return only
    return {}


class INDMoneyDataAdapter(BrokerDataAdapter):
    @property
    def name(self) -> str:
        return "INDMONEY"

    def is_available(self) -> bool:
        try:
            from app.core.broker.indstocks.market_data import _access_token
            return bool(_access_token())
        except Exception:
            return False

    def _get_scrip_code(self, symbol: str, exchange: str = "NSE") -> str:
        """
        Resolve symbol + exchange to INDstocks scrip-code (e.g. NSE_2885).
        Exchange segment map mirrors OpenAlgo's BrokerData._get_scrip_code.
        """
        from app.core.broker.indstocks.market_data import get_scrip_code, _instruments_cache

        exchange_upper = exchange.upper()
        # Index exchanges need NIDX/BIDX segment prefix
        segment_map = {
            "NSE": "NSE", "BSE": "BSE",
            "NFO": "NFO", "BFO": "BFO",
            "MCX": "MCX", "CDS": "CDS",
            "NSE_INDEX": "NIDX", "BSE_INDEX": "BIDX",
        }

        # Try the market_data helper first (handles fallback map + DB)
        try:
            return get_scrip_code(symbol)
        except KeyError:
            pass

        # Manual construction: look up security_id from instruments cache
        cache = _instruments_cache()
        scrip = cache.get(symbol.upper())
        if scrip:
            return scrip

        raise KeyError(f"INDstocks scrip-code not found for '{symbol}' on {exchange}")

    def get_spot_quote(self, symbol: str) -> Optional[SpotQuote]:
        try:
            from app.core.broker.indstocks.market_data import fetch_full_quotes, get_scrip_code
            scrip = get_scrip_code(symbol)
            data = fetch_full_quotes([scrip])
            q = data.get(scrip)
            if not q or not q.get("ltp"):
                return None
            return SpotQuote(
                symbol=symbol,
                last_price=float(q["ltp"]),
                open=float(q.get("open", 0)),
                high=float(q.get("high", 0)),
                low=float(q.get("low", 0)),
                close=float(q.get("close", 0)),
                volume=int(q.get("volume", 0)),
            )
        except Exception as e:
            logger.warning("INDMoneyDataAdapter.get_spot_quote failed for %s: %s", symbol, e)
            return None

    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> Optional[MarketDepth]:
        """
        Fetch real Level 2 market depth from INDstocks /market/quotes/mkt endpoint.
        Response shape: data.<scrip_code>.market_depth.depth[]
        Each depth level: {buy: {price, quantity}, sell: {price, quantity}}
        Also fetches OHLC from /market/quotes/full as a companion call.
        """
        try:
            from app.core.broker.indstocks.market_data import _access_token, _rate_limiter, BASE_URL
            import requests

            scrip_code = self._get_scrip_code(symbol, exchange)
            token = _access_token()
            headers = {"Authorization": token}
            params = {"scrip-codes": scrip_code}

            # ── Full quote for LTP + OHLC ──────────────────────────────────
            ltp = prev_close = open_p = high_p = low_p = 0.0
            volume = oi = 0
            try:
                _rate_limiter.wait()
                resp = requests.get(
                    f"{BASE_URL}/market/quotes/full",
                    params=params, headers=headers, timeout=10,
                )
                resp.raise_for_status()
                full_data = (resp.json().get("data") or {}).get(scrip_code) or {}
                ltp = _clean_num(full_data.get("live_price") or full_data.get("ltp"), 0.0)
                open_p = _clean_num(full_data.get("day_open"), 0.0)
                high_p = _clean_num(full_data.get("day_high"), 0.0)
                low_p = _clean_num(full_data.get("day_low"), 0.0)
                prev_close = _clean_num(full_data.get("prev_close") or full_data.get("close"), 0.0)
                volume = _clean_num(full_data.get("volume"), 0)
                oi = _clean_num(full_data.get("oi") or full_data.get("open_interest"), 0)
            except Exception as e:
                logger.warning("INDMoney full-quote failed for %s: %s", symbol, e)

            # ── Market depth from /market/quotes/mkt ──────────────────────
            bids: List[DepthLevel] = []
            asks: List[DepthLevel] = []
            total_buy_qty = total_sell_qty = 0

            try:
                _rate_limiter.wait()
                resp = requests.get(
                    f"{BASE_URL}/market/quotes/mkt",
                    params=params, headers=headers, timeout=10,
                )
                resp.raise_for_status()
                mkt_data = (resp.json().get("data") or {}).get(scrip_code) or {}

                md = _extract_ind_market_depth(mkt_data.get("market_depth") or {}, scrip_code)
                depth_levels = md.get("depth") or []
                aggregate = md.get("aggregate") or {}

                for i in range(5):
                    if i < len(depth_levels):
                        lvl = depth_levels[i]
                        buy = lvl.get("buy") or {}
                        sell = lvl.get("sell") or {}
                        bids.append(DepthLevel(
                            price=_clean_num(buy.get("price"), 0.0),
                            quantity=_clean_num(buy.get("quantity"), 0),
                        ))
                        asks.append(DepthLevel(
                            price=_clean_num(sell.get("price"), 0.0),
                            quantity=_clean_num(sell.get("quantity"), 0),
                        ))
                    else:
                        bids.append(DepthLevel(0.0, 0))
                        asks.append(DepthLevel(0.0, 0))

                total_buy_qty = _clean_num(aggregate.get("total_buy"), 0) or sum(b.quantity for b in bids)
                total_sell_qty = _clean_num(aggregate.get("total_sell"), 0) or sum(a.quantity for a in asks)

                # If LTP wasn't available from full-quote, use best bid as fallback
                if not ltp and bids and bids[0].price:
                    ltp = float(bids[0].price)

            except Exception as e:
                logger.warning("INDMoney mkt-depth failed for %s: %s", symbol, e)
                # Pad to 5 empty levels so callers always get a consistent shape
                while len(bids) < 5:
                    bids.append(DepthLevel(0.0, 0))
                while len(asks) < 5:
                    asks.append(DepthLevel(0.0, 0))

            return MarketDepth(
                symbol=symbol,
                bids=bids,
                asks=asks,
                ltp=ltp,
                volume=volume,
                open=open_p,
                high=high_p,
                low=low_p,
                prev_close=prev_close,
                oi=oi,
                total_buy_qty=total_buy_qty,
                total_sell_qty=total_sell_qty,
                data_source="INDMONEY",
            )
        except Exception as e:
            logger.warning("INDMoneyDataAdapter.get_market_depth failed for %s: %s", symbol, e)
            return None

    def get_option_quotes(self, nfo_symbols: List[str]) -> Dict[str, OptionQuote]:
        try:
            from app.core.broker.indstocks.market_data import _instruments_cache, fetch_full_quotes
            cache = _instruments_cache()
            sym_to_scrip: Dict[str, str] = {}
            for sym in nfo_symbols:
                scrip = cache.get(sym.upper())
                if scrip:
                    sym_to_scrip[sym] = scrip
            if not sym_to_scrip:
                return {}
            raw = fetch_full_quotes(list(sym_to_scrip.values()))
            result: Dict[str, OptionQuote] = {}
            for sym, scrip in sym_to_scrip.items():
                q = raw.get(scrip)
                if not q:
                    continue
                ltp = float(q.get("ltp", 0))
                result[sym] = OptionQuote(
                    symbol=sym,
                    ltp=ltp,
                    open=float(q.get("open", ltp)),
                    high=float(q.get("high", ltp)),
                    low=float(q.get("low", ltp)),
                    close=float(q.get("prev_close", ltp)),
                    volume=int(q.get("volume", 0)),
                    oi=0,
                    bid=0.0,
                    ask=0.0,
                )
            return result
        except Exception as e:
            logger.warning("INDMoneyDataAdapter.get_option_quotes failed: %s", e)
            return {}

    def get_option_expiries(self, underlying: str) -> List[date]:
        try:
            from app.core.broker.indstocks.market_data import _instruments_cache
            cache = _instruments_cache()
            prefix = f"{underlying.upper()}|"
            expiries = set()
            for key in cache:
                if key.startswith(prefix):
                    parts = key.split("|")
                    if len(parts) == 4:
                        try:
                            expiries.add(date.fromisoformat(parts[1]))
                        except ValueError:
                            pass
            today = date.today()
            return sorted(e for e in expiries if e >= today)
        except Exception as e:
            logger.warning("INDMoneyDataAdapter.get_option_expiries failed: %s", e)
            return []

    def get_option_strikes(self, underlying: str, expiry: date) -> List[Tuple[int, str]]:
        try:
            from app.core.broker.indstocks.market_data import _instruments_cache
            cache = _instruments_cache()
            prefix = f"{underlying.upper()}|{expiry}|"
            pairs: List[Tuple[int, str]] = []
            for key in cache:
                if key.startswith(prefix):
                    parts = key.split("|")
                    if len(parts) == 4:
                        try:
                            pairs.append((int(parts[2]), parts[3]))
                        except ValueError:
                            pass
            return pairs
        except Exception as e:
            logger.warning("INDMoneyDataAdapter.get_option_strikes failed: %s", e)
            return []


# ── Service with automatic broker selection + fallback ────────────────────

class MarketDataService:
    """
    Broker-agnostic market data service.

    Reads ACTIVE_BROKER from env (default ZERODHA).
    If the primary broker is unavailable, automatically falls back to the other.
    """

    _adapters: Dict[str, BrokerDataAdapter] = {
        "ZERODHA": ZerodhaDataAdapter(),
        "INDMONEY": INDMoneyDataAdapter(),
    }
    _fallback_order = ["ZERODHA", "INDMONEY"]  # overridden by _ordered_adapters at runtime

    def _primary(self) -> str:
        raw = os.getenv("ACTIVE_BROKER", "ZERODHA").upper().strip()
        aliases = {"IND_MONEY": "INDMONEY", "IND-MONEY": "INDMONEY", "INDSTOCKS": "INDMONEY"}
        return aliases.get(raw, raw)

    def _ordered_adapters(self) -> List[BrokerDataAdapter]:
        primary = self._primary()
        order = [primary] + [b for b in self._fallback_order if b != primary]
        return [self._adapters[b] for b in order if b in self._adapters]

    def get_active_adapter(self) -> Optional[BrokerDataAdapter]:
        for adapter in self._ordered_adapters():
            if adapter.is_available():
                return adapter
        return None

    def get_spot_quote(self, symbol: str) -> Optional[SpotQuote]:
        for adapter in self._ordered_adapters():
            if not adapter.is_available():
                continue
            result = adapter.get_spot_quote(symbol)
            if result:
                logger.debug("Spot quote for %s via %s", symbol, adapter.name)
                return result
        logger.error("All brokers failed to fetch spot quote for %s", symbol)
        return None

    def get_market_depth(self, symbol: str, exchange: str = "NSE") -> Optional[MarketDepth]:
        for adapter in self._ordered_adapters():
            if not adapter.is_available():
                continue
            result = adapter.get_market_depth(symbol, exchange)
            if result:
                logger.debug("Market depth for %s via %s", symbol, adapter.name)
                return result
        return None

    def get_option_quotes(self, nfo_symbols: List[str]) -> Dict[str, OptionQuote]:
        for adapter in self._ordered_adapters():
            if not adapter.is_available():
                continue
            result = adapter.get_option_quotes(nfo_symbols)
            if result:
                logger.debug("Option quotes (%d) via %s", len(result), adapter.name)
                return result
        return {}

    def get_option_expiries(self, underlying: str) -> List[date]:
        for adapter in self._ordered_adapters():
            if not adapter.is_available():
                continue
            result = adapter.get_option_expiries(underlying)
            if result:
                return result
        return []

    def get_option_strikes(self, underlying: str, expiry: date) -> List[Tuple[int, str]]:
        for adapter in self._ordered_adapters():
            if not adapter.is_available():
                continue
            result = adapter.get_option_strikes(underlying, expiry)
            if result:
                return result
        return []


# Singleton
_service: Optional[MarketDataService] = None


def get_market_data_service() -> MarketDataService:
    global _service
    if _service is None:
        _service = MarketDataService()
    return _service
