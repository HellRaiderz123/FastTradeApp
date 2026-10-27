import logging
from typing import List, Dict

from app.core.market.provider import fetch_ltp as _provider_fetch_ltp, is_indstocks

logger = logging.getLogger(__name__)


def _is_option_symbol(sym: str) -> bool:
    """Heuristic: option symbols end in CE or PE and are longer than a plain equity name."""
    s = sym.upper()
    return (s.endswith("CE") or s.endswith("PE")) and len(s) > 8


def _parse_zerodha_option_symbol(sym: str):
    """
    Parse a Zerodha option symbol like NIFTY26N0322500PE into components.
    Returns (underlying, expiry_date, strike, option_type) or None on failure.
    """
    import re
    from datetime import date as _date
    # Pattern: UNDERLYING + YY + MONTH_CODE + DD + STRIKE + CE/PE  (weekly)
    #       or UNDERLYING + YY + MMM + STRIKE + CE/PE              (monthly)
    _MONTH_CODE = {
        '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6,
        '7': 7, '8': 8, '9': 9, 'O': 10, 'N': 11, 'D': 12,
    }
    _MONTH_NAME = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12,
    }
    s = sym.upper()
    opt_type = s[-2:]  # CE or PE
    if opt_type not in ('CE', 'PE'):
        return None
    body = s[:-2]  # strip CE/PE

    # Try weekly: ends with digits (strike), preceded by 2-digit day, month code, 2-digit year
    # e.g. NIFTY26N0322500  -> underlying=NIFTY yy=26 mc=N dd=03 strike=22500
    m = re.match(r'^([A-Z]+)(\d{2})([1-9OND])(\d{2})(\d+)$', body)
    if m:
        underlying, yy, mc, dd, strike = m.groups()
        month = _MONTH_CODE.get(mc)
        if month:
            year = 2000 + int(yy)
            try:
                expiry = _date(year, month, int(dd))
                return underlying, expiry, int(strike), opt_type
            except ValueError:
                pass

    # Try monthly: e.g. NIFTY26JAN22500
    m = re.match(r'^([A-Z]+)(\d{2})([A-Z]{3})(\d+)$', body)
    if m:
        underlying, yy, mon, strike = m.groups()
        month = _MONTH_NAME.get(mon)
        if month:
            year = 2000 + int(yy)
            # Monthly expiry: last weekday of month — use day 1 as placeholder,
            # actual day resolved from cache key match
            from calendar import monthrange
            last_day = monthrange(year, month)[1]
            # Find last Thursday (or relevant weekday) — approximate with last day
            from datetime import timedelta
            d = _date(year, month, last_day)
            while d.weekday() > 4:  # skip weekend
                d -= timedelta(days=1)
            return underlying, d, int(strike), opt_type

    return None


def _is_scrip_code(sym: str) -> bool:
    """True if symbol is already an INDstocks scrip-code like NFO_53719 or NSE_2885."""
    s = sym.upper()
    return s.startswith("NFO_") or s.startswith("NSE_")


def _fetch_ltp_indmoney_options(symbols: List[str]) -> Dict[str, float]:
    """
    Fetch LTP for F&O option symbols via INDstocks instruments cache.
    Symbols are in Zerodha format (e.g. NIFTY26N0322500PE).
    Parses each symbol and looks up the normalised key UNDERLYING|DATE|STRIKE|TYPE
    built during cache load to get the NFO_ scrip-code.
    """
    from app.core.broker.indstocks.market_data import _instruments_cache, _refresh_instruments_cache, fetch_ltp as _ind_fetch_ltp

    def _resolve(cache: Dict[str, str], sym: str):
        # Already a scrip code — use directly
        if _is_scrip_code(sym):
            return sym
        parsed = _parse_zerodha_option_symbol(sym)
        if not parsed:
            return None
        underlying, expiry, strike, opt_type = parsed
        key = f"{underlying}|{expiry}|{strike}|{opt_type}"
        return cache.get(key)

    cache = _instruments_cache()
    sym_to_scrip: Dict[str, str] = {}
    missing: List[str] = []

    for sym in symbols:
        scrip = _resolve(cache, sym)
        if scrip:
            sym_to_scrip[sym] = scrip
        else:
            missing.append(sym)

    if missing:
        try:
            _refresh_instruments_cache()
            refreshed = _instruments_cache()
            still_missing: List[str] = []
            for sym in missing:
                scrip = _resolve(refreshed, sym)
                if scrip:
                    sym_to_scrip[sym] = scrip
                else:
                    still_missing.append(sym)
            if still_missing:
                logger.warning(
                    "INDMoney: option symbols not found in instruments cache after refresh: %s",
                    still_missing,
                )
        except Exception as exc:
            logger.warning("INDMoney: instruments cache refresh failed: %s", exc)

    if not sym_to_scrip:
        return {}

    scrip_to_ltp = _ind_fetch_ltp(list(sym_to_scrip.values()))
    return {
        sym: scrip_to_ltp[scrip]
        for sym, scrip in sym_to_scrip.items()
        if scrip in scrip_to_ltp
    }


def get_ltp(symbols: List[str]) -> Dict[str, float]:
    """
    Get last traded price for a list of symbols.

    When CANDLES_SOURCE=ZERODHA (default): uses Zerodha WebSocket cache first,
    falls back to REST LTP.
    When CANDLES_SOURCE=INDSTOCKS: uses INDstocks REST LTP directly.
    For INDMoney + option symbols: resolves via F&O instruments cache.
    """
    if is_indstocks():
        # Split equity/index vs option symbols — options need NFO scrip-code lookup
        # Scrip codes (NFO_/NSE_) are already resolved — fetch directly
        scrip_syms = [s for s in symbols if _is_scrip_code(s)]
        option_syms = [s for s in symbols if not _is_scrip_code(s) and _is_option_symbol(s)]
        equity_syms = [s for s in symbols if not _is_scrip_code(s) and not _is_option_symbol(s)]

        out: Dict[str, float] = {}

        if scrip_syms:
            from app.core.broker.indstocks.market_data import fetch_ltp as _ind_fetch_ltp
            scrip_ltps = _ind_fetch_ltp(scrip_syms)
            out.update(scrip_ltps)  # keyed by scrip code e.g. NFO_53719

        if equity_syms:
            out.update(_provider_fetch_ltp(equity_syms))
        if option_syms:
            option_ltps = _fetch_ltp_indmoney_options(option_syms)
            out.update(option_ltps)
            still_missing = [s for s in option_syms if s not in out]
            if still_missing:
                logger.warning(
                    "INDMoney: LTP unavailable for option symbols %s. "
                    "Ensure F&O instruments are loaded (source=fno) and token is valid.",
                    still_missing,
                )
        return out

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
