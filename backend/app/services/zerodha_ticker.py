from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set

try:
    from kiteconnect import KiteTicker  # pyright: ignore[reportMissingImports]
except Exception:  # pragma: no cover
    KiteTicker = None  # type: ignore

from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import load_instruments

logger = logging.getLogger(__name__)


@dataclass
class _State:
    started: bool = False
    connecting: bool = False
    subscribed_tokens: Set[int] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.subscribed_tokens is None:
            self.subscribed_tokens = set()


class ZerodhaTickerManager:
    """Maintains a singleton KiteTicker connection and a simple LTP cache.

    - Uses KiteTicker (Zerodha websocket) if available and credentials exist.
    - Safe fallback: if ticker can't start, callers can still use REST LTP.

    Cache keys:
      - plain tradingsymbol (e.g., NIFTY26JAN26200CE)

    Notes:
      - KiteTicker subscriptions require instrument_token.
      - Mapping is resolved from `load_instruments()`.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._ltp_by_symbol: Dict[str, float] = {}
        self._token_to_symbol: Dict[int, str] = {}
        self._symbol_to_token: Dict[str, int] = {}
        self._ticker: Optional[object] = None
        self._state = _State()
        self._reconnect_attempts: int = 0
        self._max_reconnect_attempts: int = 5  # stop after 5 failures (token likely expired)

    def _can_start(self) -> bool:
        if KiteTicker is None:
            return False
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            return False
        return bool(os.getenv("ZERODHA_API_KEY") and os.getenv("ZERODHA_ACCESS_TOKEN"))

    def _ensure_symbol_map_loaded(self) -> None:
        if self._symbol_to_token:
            return
        df = load_instruments()
        if df is None or df.empty:
            return
        try:
            # tradingsymbol -> instrument_token
            for _, row in df[["tradingsymbol", "instrument_token"]].dropna().iterrows():
                sym = str(row["tradingsymbol"])
                tok = int(row["instrument_token"])
                self._symbol_to_token[sym] = tok
                self._token_to_symbol[tok] = sym
        except Exception as e:
            logger.warning(f"⚠️  Failed building symbol/token map: {e}")

    def start(self) -> None:
        with self._lock:
            if self._state.started or self._state.connecting:
                return
            if not self._can_start():
                logger.info("ZerodhaTicker not started (missing deps/creds)")
                return

            self._state.connecting = True

        try:
            kite = get_kite_client()
            # KiteConnect doesn't expose api_key directly; use env.
            api_key = os.getenv("ZERODHA_API_KEY")
            access_token = os.getenv("ZERODHA_ACCESS_TOKEN")
            if not api_key or not access_token:
                return

            if KiteTicker is None:
                return
            KiteTickerLocal = KiteTicker
            ticker = KiteTickerLocal(api_key, access_token)

            def on_connect(ws, _response):
                logger.info("✅ ZerodhaTicker connected")
                # Subscribe whatever is already requested.
                with self._lock:
                    tokens = list(self._state.subscribed_tokens)
                if tokens:
                    try:
                        ws.subscribe(tokens)
                        ws.set_mode(ws.MODE_LTP, tokens)
                    except Exception as e:
                        logger.warning(f"⚠️  Subscribe on connect failed: {e}")

            def on_ticks(_ws, ticks):
                with self._lock:
                    for t in ticks or []:
                        tok = t.get("instrument_token")
                        lp = t.get("last_price")
                        if tok is None or lp is None:
                            continue
                        sym = self._token_to_symbol.get(int(tok))
                        if not sym:
                            continue
                        self._ltp_by_symbol[sym] = float(lp)

            def on_error(_ws, code, reason):
                logger.warning(f"⚠️  ZerodhaTicker error {code}: {reason}")
                # 403 = token expired — stop reconnecting immediately
                if code == 1006 and "403" in str(reason):
                    with self._lock:
                        self._reconnect_attempts += 1
                    if self._reconnect_attempts >= self._max_reconnect_attempts:
                        logger.error(
                            "❌ ZerodhaTicker: too many 403 failures — "
                            "Zerodha access token is expired. "
                            "Update ZERODHA_ACCESS_TOKEN in .env and restart."
                        )

            def on_close(_ws, code, reason):
                logger.warning(f"⚠️  ZerodhaTicker closed {code}: {reason}")
                with self._lock:
                    self._state.started = False
                    self._state.connecting = False
                    self._ticker = None

            setattr(ticker, "on_connect", on_connect)
            setattr(ticker, "on_ticks", on_ticks)
            setattr(ticker, "on_error", on_error)
            setattr(ticker, "on_close", on_close)

            def _run():
                try:
                    ticker.connect(threaded=False)
                except Exception as e:
                    logger.warning(f"⚠️  ZerodhaTicker connect failed: {e}")
                finally:
                    with self._lock:
                        self._state.started = False
                        self._state.connecting = False
                        self._ticker = None
                        self._reconnect_attempts += 1
                    # Exponential backoff: 2s, 4s, 8s, 16s, 32s then give up
                    import time
                    backoff = min(32, 2 ** self._reconnect_attempts)
                    if self._reconnect_attempts < self._max_reconnect_attempts:
                        logger.info(f"ZerodhaTicker will retry in {backoff}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
                        time.sleep(backoff)

            t = threading.Thread(target=_run, name="zerodha-ticker", daemon=True)
            with self._lock:
                self._ticker = ticker
                self._state.started = True
                self._state.connecting = False
            t.start()

        except Exception as e:
            logger.warning(f"⚠️  ZerodhaTicker start failed: {e}")
            with self._lock:
                self._state.started = False
                self._state.connecting = False
                self._ticker = None

    def subscribe_symbols(self, symbols: Iterable[str]) -> None:
        """Ensure websocket subscription for these tradingsymbols."""
        syms = [self._strip_exchange_prefix(s) for s in symbols if s]
        if not syms:
            return

        self.start()
        with self._lock:
            ticker = self._ticker
        if ticker is None:
            return

        self._ensure_symbol_map_loaded()

        new_tokens: Set[int] = set()
        with self._lock:
            for sym in syms:
                tok = self._symbol_to_token.get(sym)
                if tok is None:
                    continue
                if tok not in self._state.subscribed_tokens:
                    self._state.subscribed_tokens.add(tok)
                    new_tokens.add(tok)

        if not new_tokens:
            return

        try:
            # KiteTicker has subscribe/set_mode methods.
            ticker.subscribe(list(new_tokens))  # type: ignore[attr-defined]
            ticker.set_mode(ticker.MODE_LTP, list(new_tokens))  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning(f"⚠️  ZerodhaTicker subscribe failed: {e}")

    def get_cached_ltp(self, symbol: str) -> Optional[float]:
        sym = self._strip_exchange_prefix(symbol)
        with self._lock:
            val = self._ltp_by_symbol.get(sym)
        return val

    @staticmethod
    def _strip_exchange_prefix(symbol: str) -> str:
        # e.g. NFO:NIFTY26JAN26200CE -> NIFTY26JAN26200CE
        if ":" in symbol:
            return symbol.split(":", 1)[1]
        return symbol


_ticker_singleton = ZerodhaTickerManager()


def subscribe_symbols(symbols: Iterable[str]) -> None:
    _ticker_singleton.subscribe_symbols(symbols)


def get_cached_ltp(symbol: str) -> Optional[float]:
    return _ticker_singleton.get_cached_ltp(symbol)
