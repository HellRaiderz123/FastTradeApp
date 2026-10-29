"""
Real Options Chain — broker-agnostic.

Fetches actual option premiums, OI, volume, and IV from whichever broker
is active (ZERODHA or INDMONEY). Set ACTIVE_BROKER in backend/.env.
Falls back to the other broker automatically if the primary is unavailable.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
import math

from app.services.market_data_service import get_market_data_service
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/options/real", tags=["options_real"])


# ── Black-Scholes helpers ──────────────────────────────────────────────────

def _bs_price(spot: float, strike: float, t: float, vol: float, r: float, opt_type: str) -> float:
    if t <= 0 or vol <= 0:
        return max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    if opt_type == "CE":
        return spot * N(d1) - strike * math.exp(-r * t) * N(d2)
    return strike * math.exp(-r * t) * N(-d2) - spot * N(-d1)


def _calc_iv(ltp: float, spot: float, strike: float, t: float, r: float, opt_type: str) -> float:
    if ltp <= 0 or t <= 0:
        return 0.0
    intrinsic = max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
    if ltp <= intrinsic:
        return 0.0
    vol = 0.3
    sqrt_t = math.sqrt(t)
    N_pdf = lambda x: math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
    for _ in range(50):
        price = _bs_price(spot, strike, t, vol, r, opt_type)
        d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
        vega = spot * N_pdf(d1) * sqrt_t
        diff = price - ltp
        if abs(diff) < 0.001:
            break
        if vega < 1e-10:
            break
        vol -= diff / vega
        vol = max(0.001, min(vol, 5.0))
    return round(vol * 100, 2)


def _calc_greeks(spot: float, strike: float, t: float, vol_pct: float, r: float, opt_type: str) -> dict:
    try:
        vol = vol_pct / 100.0
        if t <= 0 or vol <= 0:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
        sqrt_t = math.sqrt(t)
        d1 = (math.log(spot / strike) + (r + 0.5 * vol ** 2) * t) / (vol * sqrt_t)
        d2 = d1 - vol * sqrt_t
        N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
        N_pdf = lambda x: math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)
        gamma = round(N_pdf(d1) / (spot * vol * sqrt_t), 6)
        vega = round(spot * N_pdf(d1) * sqrt_t / 100, 4)
        if opt_type == "CE":
            delta = round(N(d1), 4)
            theta = round((-spot * N_pdf(d1) * vol / (2 * sqrt_t) - r * strike * math.exp(-r * t) * N(d2)) / 365, 4)
            rho = round(strike * t * math.exp(-r * t) * N(d2) / 100, 4)
        else:
            delta = round(-N(-d1), 4)
            theta = round((-spot * N_pdf(d1) * vol / (2 * sqrt_t) + r * strike * math.exp(-r * t) * N(-d2)) / 365, 4)
            rho = round(-strike * t * math.exp(-r * t) * N(-d2) / 100, 4)
        return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}
    except Exception:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}


# ── In-process caches ──────────────────────────────────────────────────────

_CHAIN_CACHE: Dict[str, Dict[str, Any]] = {}
_EXPIRY_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_get(cache: Dict[str, Dict[str, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    payload = cache.get(key)
    if not payload:
        return None
    if (datetime.now() - payload["ts"]).total_seconds() > ttl_seconds:
        cache.pop(key, None)
        return None
    return payload.get("value")


def _cache_set(cache: Dict[str, Dict[str, Any]], key: str, value: Any) -> None:
    cache[key] = {"ts": datetime.now(), "value": value}


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/chain/{symbol}")
async def get_real_option_chain(symbol: str, expiry: Optional[str] = None):
    """
    Fetch real option chain data from the active broker (Zerodha or INDMoney).

    Args:
        symbol: NIFTY, BANKNIFTY, FINNIFTY
        expiry: Date in YYYY-MM-DD format (defaults to nearest expiry)
    """
    try:
        symbol = symbol.upper().strip()
        svc = get_market_data_service()

        # 1. Get spot price
        spot_quote = svc.get_spot_quote(symbol)
        if not spot_quote or not spot_quote.last_price:
            active = svc.get_active_adapter()
            broker_name = active.name if active else "any broker"
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Could not fetch spot price for {symbol} from {broker_name}. "
                    "Ensure your broker session is active (check Settings)."
                ),
            )

        spot = float(spot_quote.last_price)
        active_adapter = svc.get_active_adapter()
        data_source = active_adapter.name if active_adapter else "UNKNOWN"
        logger.info("Spot price for %s: %s (via %s)", symbol, spot, data_source)

        # 2. Resolve expiry
        if not expiry:
            today = datetime.now().date()
            days_until_tuesday = (1 - today.weekday()) % 7 or 7
            expiry_date = today + timedelta(days=days_until_tuesday)
        else:
            expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()

        cache_key = f"{symbol}:{expiry_date.isoformat()}"
        cached = _cache_get(_CHAIN_CACHE, cache_key, ttl_seconds=8)
        if cached is not None:
            return cached

        # 3. Get available strikes for this expiry
        available_pairs = set(svc.get_option_strikes(symbol, expiry_date))
        if not available_pairs:
            raise HTTPException(
                status_code=404,
                detail=f"No options found for {symbol} expiry {expiry_date}",
            )

        # 4. Determine ATM ± 10 strikes
        strike_step = 50 if symbol == "NIFTY" else 100
        atm_strike = round(spot / strike_step) * strike_step
        strikes_to_fetch = [atm_strike + i * strike_step for i in range(-10, 11)]

        # 5. Build tradingsymbols for available strikes
        symbols_to_quote = []
        strike_map: Dict[str, tuple] = {}
        for strike in strikes_to_fetch:
            for opt_type in ("CE", "PE"):
                if (int(strike), opt_type) in available_pairs:
                    ts = build_zerodha_option_symbol(
                        underlying=symbol,
                        expiry=expiry_date,
                        strike=strike,
                        option_type=opt_type,
                    )
                    symbols_to_quote.append(ts)
                    strike_map[ts] = (strike, opt_type)

        if not symbols_to_quote:
            raise HTTPException(
                status_code=404,
                detail=f"No valid option symbols found for strikes around {atm_strike}",
            )

        # 6. Fetch quotes via active broker
        quotes = svc.get_option_quotes(symbols_to_quote)
        if not quotes:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Broker API returned no option quotes for {symbol} {expiry_date}. "
                    "Please try again in a few moments."
                ),
            )

        # 7. Build option chain
        today = datetime.now().date()
        days_to_expiry = (expiry_date - today).days
        chain_data: Dict[int, Dict] = {}

        for tradingsymbol, q in quotes.items():
            if tradingsymbol not in strike_map:
                continue
            strike, opt_type = strike_map[tradingsymbol]
            if strike not in chain_data:
                chain_data[strike] = {"strike": strike, "call": None, "put": None}

            ltp = q.ltp
            close = q.close
            change = ltp - close
            change_pct = round(change / close * 100, 2) if close > 0 else 0.0

            t = max(days_to_expiry / 365, 0.001)
            r = 0.07
            iv = _calc_iv(ltp, spot, strike, t, r, opt_type)
            greeks = _calc_greeks(spot, strike, t, iv, r, opt_type)

            intrinsic = max(spot - strike, 0) if opt_type == "CE" else max(strike - spot, 0)
            option_data = {
                "ltp": ltp,
                "change": round(change, 2),
                "change_percent": change_pct,
                "volume": q.volume,
                "oi": q.oi,
                "iv": iv,
                "delta": greeks["delta"],
                "gamma": greeks["gamma"],
                "theta": greeks["theta"],
                "vega": greeks["vega"],
                "rho": greeks["rho"],
                "bid": q.bid,
                "ask": q.ask,
                "high": q.high,
                "low": q.low,
                "open": q.open,
                "close": close,
                "intrinsic": intrinsic,
                "time_value": max(ltp - intrinsic, 0),
            }

            if opt_type == "CE":
                chain_data[strike]["call"] = option_data
            else:
                chain_data[strike]["put"] = option_data

        # 8. Sort and return
        strikes_list = [chain_data[s] for s in sorted(chain_data)]
        response_payload = {
            "symbol": symbol,
            "spot": round(spot, 2),
            "expiry": expiry_date.strftime("%Y-%m-%d"),
            "days_to_expiry": days_to_expiry,
            "strikes": strikes_list,
            "atm_strike": atm_strike,
            "total_strikes": len(strikes_list),
            "data_source": data_source,
            "timestamp": datetime.now().isoformat(),
        }
        _cache_set(_CHAIN_CACHE, cache_key, response_payload)
        return response_payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Real options chain error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch real options chain: {e}")


@router.get("/expiries/{symbol}")
async def get_real_expiries(symbol: str):
    """Get available expiry dates from the active broker."""
    try:
        symbol = symbol.upper()
        cached = _cache_get(_EXPIRY_CACHE, symbol, ttl_seconds=120)
        if cached is not None:
            return cached

        svc = get_market_data_service()
        expiries = svc.get_option_expiries(symbol)
        if not expiries:
            raise HTTPException(status_code=404, detail=f"No options found for {symbol}")

        active = svc.get_active_adapter()
        response_payload = {
            "symbol": symbol,
            "expiries": [e.strftime("%Y-%m-%d") for e in expiries],
            "count": len(expiries),
            "data_source": active.name if active else "UNKNOWN",
        }
        _cache_set(_EXPIRY_CACHE, symbol, response_payload)
        return response_payload

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching real expiries: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
