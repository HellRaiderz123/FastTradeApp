from typing import List, Dict

from app.core.broker.zerodha.client import get_kite_client
from app.services.zerodha_ticker import get_cached_ltp, subscribe_symbols

def get_ltp(symbols: List[str]) -> Dict[str, float]:
    # Best-effort: subscribe via websocket so subsequent reads are real-time.
    try:
        subscribe_symbols(symbols)
    except Exception:
        pass

    # If websocket cache already has values, use them.
    out: Dict[str, float] = {}
    missing: List[str] = []
    for sym in symbols:
        cached = None
        try:
            cached = get_cached_ltp(sym)
        except Exception:
            cached = None
        if cached is not None and cached != 0.0:
            out[sym] = float(cached)
        else:
            missing.append(sym)

    if not missing:
        return out

    kite = get_kite_client()

    # Zerodha expects fully qualified instruments like "NFO:NIFTY26JAN26200CE".
    # Callers in this codebase often pass plain tradingsymbols; normalize them.
    normalized: List[str] = []
    original_to_normalized: Dict[str, str] = {}
    for sym in missing:
        if ":" in sym:
            normalized_sym = sym
        else:
            # Strategy tickets are option legs by default.
            normalized_sym = f"NFO:{sym}"
        normalized.append(normalized_sym)
        original_to_normalized[sym] = normalized_sym

    data = kite.ltp(normalized)

    # Return mapping keyed by original inputs so downstream code can look up by the
    # same string it provided.
    for original, full in original_to_normalized.items():
        info = None
        try:
            info = data.get(full) or data.get(original)  # type: ignore[attr-defined]
        except Exception:
            info = None
        if info and isinstance(info, dict) and "last_price" in info:
            out[original] = float(info["last_price"])  # type: ignore[index]
        else:
            # Missing LTP for this symbol; return 0.0 and let caller decide.
            out[original] = 0.0

    return out
