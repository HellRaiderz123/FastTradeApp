from typing import List, Dict

from app.core.market.provider import fetch_ltp as _provider_fetch_ltp, is_indstocks


def get_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Get last traded price for a list of symbols.

    When CANDLES_SOURCE=ZERODHA (default): uses Zerodha WebSocket cache first,
    falls back to REST LTP.
    When CANDLES_SOURCE=INDSTOCKS: uses INDstocks REST LTP directly.
    """
    if is_indstocks():
        return _provider_fetch_ltp(symbols)

    # Zerodha path: try WebSocket cache first, REST for misses
    from app.services.zerodha_ticker import get_cached_ltp, subscribe_symbols

    try:
        subscribe_symbols(symbols)
    except Exception:
        pass

    out: Dict[str, float] = {}
    missing: List[str] = []
    for sym in symbols:
        try:
            cached = get_cached_ltp(sym)
        except Exception:
            cached = None
        if cached is not None and float(cached) > 0.5:
            out[sym] = float(cached)
        else:
            missing.append(sym)

    if missing:
        rest_prices = _provider_fetch_ltp(missing)
        out.update(rest_prices)

    return out
