"""
Broker-agnostic option symbol builder.

Routes to the appropriate symbol format based on the active data broker.
- Zerodha: NIFTY26N0322450PE (YY + month-code + DD + strike + CE/PE)
- INDMoney: Uses scrip-code from instruments CSV (NFO segment)
"""

from datetime import date
from typing import Optional
import logging

from app.core.broker.registry import get_data_broker

logger = logging.getLogger(__name__)


def build_option_symbol(
    *,
    underlying: str,
    strike: int,
    option_type: str,  # CE / PE
    expiry: date,
) -> str:
    """
    Build an option symbol in the format required by the active data broker.
    
    For Zerodha: Returns tradingsymbol like NIFTY26N0322450PE
    For INDMoney: Returns tradingsymbol that can be resolved via instruments cache
    """
    broker = get_data_broker()
    
    if broker == "INDMONEY":
        return _build_indmoney_option_symbol(
            underlying=underlying,
            strike=strike,
            option_type=option_type,
            expiry=expiry,
        )
    
    # Default to Zerodha format
    return _build_zerodha_option_symbol(
        underlying=underlying,
        strike=strike,
        option_type=option_type,
        expiry=expiry,
    )


def _build_zerodha_option_symbol(
    *,
    underlying: str,
    strike: int,
    option_type: str,
    expiry: date,
) -> str:
    """Build Zerodha-format option symbol."""
    from app.core.market.expiry import format_zerodha_expiry
    
    underlying = underlying.upper().replace(" ", "")
    option_type = option_type.upper()
    if option_type not in {"CE", "PE"}:
        raise ValueError(f"Invalid option type: {option_type}")
    
    expiry_code = format_zerodha_expiry(expiry)
    return f"{underlying}{expiry_code}{int(strike)}{option_type}"


def _build_indmoney_option_symbol(
    *,
    underlying: str,
    strike: int,
    option_type: str,
    expiry: date,
) -> str:
    """
    Build INDMoney-format option symbol.
    
    INDMoney uses tradingsymbols like: NIFTY24JAN22000CE (similar to Zerodha monthly)
    or NIFTY2410322000CE for weekly expiries.
    
    The key difference is that INDMoney instruments CSV contains the exact
    tradingsymbol we need to use for LTP lookup.
    """
    underlying = underlying.upper().replace(" ", "")
    option_type = option_type.upper()
    if option_type not in {"CE", "PE"}:
        raise ValueError(f"Invalid option type: {option_type}")
    
    # Try to find the exact symbol in INDMoney instruments cache
    symbol = _lookup_indmoney_option_symbol(underlying, strike, option_type, expiry)
    if symbol:
        return symbol
    
    # Fallback: construct symbol in Zerodha format (may work for some cases)
    # INDMoney often accepts Zerodha-style symbols for F&O
    logger.warning(
        "INDMoney option symbol not found in cache for %s %s %s %s, using Zerodha format",
        underlying, expiry, strike, option_type
    )
    return _build_zerodha_option_symbol(
        underlying=underlying,
        strike=strike,
        option_type=option_type,
        expiry=expiry,
    )


def _lookup_indmoney_option_symbol(
    underlying: str,
    strike: int,
    option_type: str,
    expiry: date,
) -> Optional[str]:
    """
    Look up the exact option tradingsymbol from INDMoney instruments cache.
    
    Returns None if not found.
    """
    try:
        from app.core.broker.indstocks.market_data import _instruments_cache
        
        cache = _instruments_cache()
        if not cache:
            return None
        
        # Build possible symbol patterns to search for
        # INDMoney uses various formats, try common ones
        patterns = _generate_option_symbol_patterns(underlying, strike, option_type, expiry)
        
        for pattern in patterns:
            if pattern in cache:
                logger.debug("Found INDMoney option symbol: %s", pattern)
                return pattern
        
        return None
        
    except Exception as e:
        logger.warning("Failed to lookup INDMoney option symbol: %s", e)
        return None


def _generate_option_symbol_patterns(
    underlying: str,
    strike: int,
    option_type: str,
    expiry: date,
) -> list[str]:
    """
    Generate possible option symbol patterns to search in INDMoney cache.
    
    INDMoney F&O symbols follow patterns like:
    - NIFTY24JAN22000CE (monthly)
    - NIFTY2410322000CE (weekly: YY + single-char-month + DD)
    - NIFTY24N0322000CE (weekly with N for Nov)
    """
    patterns = []
    
    # Pattern 1: Zerodha weekly format (YY + month-code + DD + strike + CE/PE)
    from app.core.market.expiry import format_zerodha_expiry, _is_last_weekday_of_month
    expiry_code = format_zerodha_expiry(expiry)
    patterns.append(f"{underlying}{expiry_code}{strike}{option_type}")
    
    # Pattern 2: Monthly format (YYMMMDD or YYMMM)
    if _is_last_weekday_of_month(expiry):
        month_str = expiry.strftime("%b").upper()
        patterns.append(f"{underlying}{expiry.year % 100}{month_str}{strike}{option_type}")
    
    # Pattern 3: Alternative weekly format with zero-padded day
    year_2d = expiry.year % 100
    month_codes = {
        1: "1", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
        7: "7", 8: "8", 9: "9", 10: "O", 11: "N", 12: "D"
    }
    month_code = month_codes.get(expiry.month, str(expiry.month))
    patterns.append(f"{underlying}{year_2d}{month_code}{expiry.day:02d}{strike}{option_type}")
    
    # Pattern 4: With single-digit day (no zero padding)
    if expiry.day < 10:
        patterns.append(f"{underlying}{year_2d}{month_code}{expiry.day}{strike}{option_type}")
    
    return patterns
