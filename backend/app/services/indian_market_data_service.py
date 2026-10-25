"""
IndianMarketDataService — Legitimate zero-cost institutional Indian market telemetry.

Phase 2: Market Data Layer Upgrade
Sources:
- NSE Official APIs (option chain, equity trade info, corporate announcements)
- India VIX and sectoral indices
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import json

import httpx

logger = logging.getLogger(__name__)

# NSE requires browser-like headers and session cookies
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}

NSE_BASE_URL = "https://www.nseindia.com"


@dataclass
class OptionChainStrike:
    """Single strike data from NSE option chain."""
    strike: float
    expiry: str
    # Call side
    ce_oi: int = 0
    ce_change_oi: int = 0
    ce_volume: int = 0
    ce_iv: float = 0.0
    ce_ltp: float = 0.0
    ce_bid: float = 0.0
    ce_ask: float = 0.0
    # Put side
    pe_oi: int = 0
    pe_change_oi: int = 0
    pe_volume: int = 0
    pe_iv: float = 0.0
    pe_ltp: float = 0.0
    pe_bid: float = 0.0
    pe_ask: float = 0.0


@dataclass
class OptionChainData:
    """Complete option chain response."""
    underlying: str
    spot: float
    expiry: str
    timestamp: datetime
    strikes: List[OptionChainStrike] = field(default_factory=list)
    total_ce_oi: int = 0
    total_pe_oi: int = 0
    pcr_oi: float = 0.0
    max_pain: float = 0.0
    atm_strike: float = 0.0


@dataclass
class DeliveryData:
    """Equity delivery percentage data."""
    symbol: str
    delivery_qty: int = 0
    traded_qty: int = 0
    delivery_pct: float = 0.0
    is_institutional_accumulation: bool = False


@dataclass
class CorporateAnnouncement:
    """Corporate announcement/filing."""
    symbol: str
    subject: str
    announcement_date: datetime
    category: str  # Results, Board Meeting, Insider, etc.
    description: str = ""


@dataclass
class MacroTelemetry:
    """India macro and regime data."""
    india_vix: float = 0.0
    nifty50: float = 0.0
    nifty_bank: float = 0.0
    nifty_it: float = 0.0
    nifty_auto: float = 0.0
    nifty_pharma: float = 0.0
    nifty_metal: float = 0.0
    nifty_fmcg: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class IndianMarketDataService:
    """
    Service for fetching legitimate Indian market data from NSE.
    
    Uses httpx.AsyncClient with automatic session cookie handling.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._session_initialized = False
        self._last_session_init: Optional[datetime] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client with NSE session."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=NSE_HEADERS,
                timeout=httpx.Timeout(15.0),
                follow_redirects=True,
            )
            self._session_initialized = False
        
        # Initialize session if needed (NSE requires visiting homepage first)
        if not self._session_initialized or self._session_expired():
            await self._init_nse_session()
        
        return self._client

    def _session_expired(self) -> bool:
        """Check if NSE session needs refresh (every 5 minutes)."""
        if self._last_session_init is None:
            return True
        return datetime.now() - self._last_session_init > timedelta(minutes=5)

    async def _init_nse_session(self) -> None:
        """Initialize NSE session by visiting homepage."""
        try:
            if self._client:
                await self._client.get(NSE_BASE_URL)
                self._session_initialized = True
                self._last_session_init = datetime.now()
                logger.debug("NSE session initialized")
        except Exception as e:
            logger.warning("Failed to initialize NSE session: %s", e)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ─────────────────────────────────────────────────────────────────────────
    # Option Chain
    # ─────────────────────────────────────────────────────────────────────────

    async def get_option_chain(
        self,
        underlying: str,
        expiry: Optional[str] = None,
    ) -> Optional[OptionChainData]:
        """
        Fetch NSE option chain for index or equity.
        
        Args:
            underlying: NIFTY, BANKNIFTY, FINNIFTY, or stock symbol
            expiry: Specific expiry (DD-Mon-YYYY format) or None for nearest
        
        Returns:
            OptionChainData with all strikes
        """
        try:
            client = await self._get_client()
            
            # Determine endpoint
            if underlying.upper() in ("NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTY BANK"):
                url = f"{NSE_BASE_URL}/api/option-chain-indices?symbol={underlying.upper()}"
            else:
                url = f"{NSE_BASE_URL}/api/option-chain-equities?symbol={underlying.upper()}"
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            records = data.get("records", {})
            filtered = data.get("filtered", {})
            
            # Get spot and expiry
            spot = float(records.get("underlyingValue", 0))
            expiries = records.get("expiryDates", [])
            selected_expiry = expiry or (expiries[0] if expiries else "")
            
            # Parse strikes
            strikes: List[OptionChainStrike] = []
            total_ce_oi = 0
            total_pe_oi = 0
            
            for row in filtered.get("data", []):
                strike_price = float(row.get("strikePrice", 0))
                
                ce = row.get("CE", {})
                pe = row.get("PE", {})
                
                ce_oi = int(ce.get("openInterest", 0))
                pe_oi = int(pe.get("openInterest", 0))
                total_ce_oi += ce_oi
                total_pe_oi += pe_oi
                
                strikes.append(OptionChainStrike(
                    strike=strike_price,
                    expiry=selected_expiry,
                    ce_oi=ce_oi,
                    ce_change_oi=int(ce.get("changeinOpenInterest", 0)),
                    ce_volume=int(ce.get("totalTradedVolume", 0)),
                    ce_iv=float(ce.get("impliedVolatility", 0)),
                    ce_ltp=float(ce.get("lastPrice", 0)),
                    ce_bid=float(ce.get("bidprice", 0)),
                    ce_ask=float(ce.get("askPrice", 0)),
                    pe_oi=pe_oi,
                    pe_change_oi=int(pe.get("changeinOpenInterest", 0)),
                    pe_volume=int(pe.get("totalTradedVolume", 0)),
                    pe_iv=float(pe.get("impliedVolatility", 0)),
                    pe_ltp=float(pe.get("lastPrice", 0)),
                    pe_bid=float(pe.get("bidprice", 0)),
                    pe_ask=float(pe.get("askPrice", 0)),
                ))
            
            # Calculate PCR and Max Pain
            pcr_oi = total_pe_oi / total_ce_oi if total_ce_oi > 0 else 0.0
            max_pain = self._calculate_max_pain(strikes, spot)
            atm_strike = self._find_atm_strike(strikes, spot)
            
            return OptionChainData(
                underlying=underlying.upper(),
                spot=spot,
                expiry=selected_expiry,
                timestamp=datetime.now(),
                strikes=strikes,
                total_ce_oi=total_ce_oi,
                total_pe_oi=total_pe_oi,
                pcr_oi=round(pcr_oi, 3),
                max_pain=max_pain,
                atm_strike=atm_strike,
            )
        except Exception as e:
            logger.warning("Failed to fetch NSE option chain for %s: %s", underlying, e)
            return None

    def _calculate_max_pain(self, strikes: List[OptionChainStrike], spot: float) -> float:
        """Calculate max pain strike (where option writers lose least)."""
        if not strikes:
            return 0.0
        
        min_pain = float("inf")
        max_pain_strike = 0.0
        
        for target in strikes:
            pain = 0.0
            for s in strikes:
                # Call pain: if spot > strike, call buyers profit
                if target.strike > s.strike:
                    pain += (target.strike - s.strike) * s.ce_oi
                # Put pain: if spot < strike, put buyers profit
                if target.strike < s.strike:
                    pain += (s.strike - target.strike) * s.pe_oi
            
            if pain < min_pain:
                min_pain = pain
                max_pain_strike = target.strike
        
        return max_pain_strike

    def _find_atm_strike(self, strikes: List[OptionChainStrike], spot: float) -> float:
        """Find ATM strike closest to spot."""
        if not strikes:
            return 0.0
        return min(strikes, key=lambda s: abs(s.strike - spot)).strike

    # ─────────────────────────────────────────────────────────────────────────
    # Delivery Percentage
    # ─────────────────────────────────────────────────────────────────────────

    async def get_delivery_data(self, symbol: str) -> Optional[DeliveryData]:
        """
        Fetch delivery percentage for an equity.
        
        High delivery % (>60%) with volume expansion = institutional accumulation.
        """
        try:
            client = await self._get_client()
            url = f"{NSE_BASE_URL}/api/quote-equity?symbol={symbol.upper()}&section=trade_info"
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            trade_info = data.get("securityWiseDP", {})
            
            delivery_qty = int(trade_info.get("deliveryQuantity", 0) or 0)
            traded_qty = int(trade_info.get("quantityTraded", 0) or 0)
            delivery_pct = float(trade_info.get("deliveryToTradedQuantity", 0) or 0)
            
            # Flag institutional accumulation
            is_accumulation = delivery_pct > 60.0
            
            return DeliveryData(
                symbol=symbol.upper(),
                delivery_qty=delivery_qty,
                traded_qty=traded_qty,
                delivery_pct=delivery_pct,
                is_institutional_accumulation=is_accumulation,
            )
        except Exception as e:
            logger.warning("Failed to fetch delivery data for %s: %s", symbol, e)
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Corporate Announcements
    # ─────────────────────────────────────────────────────────────────────────

    async def get_corporate_announcements(
        self,
        symbol: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        limit: int = 50,
    ) -> List[CorporateAnnouncement]:
        """
        Fetch corporate announcements from NSE.
        
        Args:
            symbol: Filter by symbol (None = all)
            from_date: Start date
            to_date: End date
            limit: Max announcements to return
        """
        try:
            client = await self._get_client()
            
            # Build URL
            params = {"index": "equities"}
            if symbol:
                params["symbol"] = symbol.upper()
            if from_date:
                params["from_date"] = from_date.strftime("%d-%m-%Y")
            if to_date:
                params["to_date"] = to_date.strftime("%d-%m-%Y")
            
            url = f"{NSE_BASE_URL}/api/corporate-announcements"
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            announcements: List[CorporateAnnouncement] = []
            for item in data[:limit]:
                try:
                    ann_date = datetime.strptime(
                        item.get("an_dt", ""),
                        "%d-%b-%Y %H:%M:%S"
                    )
                except ValueError:
                    ann_date = datetime.now()
                
                announcements.append(CorporateAnnouncement(
                    symbol=item.get("symbol", ""),
                    subject=item.get("desc", ""),
                    announcement_date=ann_date,
                    category=item.get("attchmntText", "General"),
                    description=item.get("attchmntFile", ""),
                ))
            
            return announcements
        except Exception as e:
            logger.warning("Failed to fetch corporate announcements: %s", e)
            return []

    # ─────────────────────────────────────────────────────────────────────────
    # Macro Telemetry
    # ─────────────────────────────────────────────────────────────────────────

    async def get_macro_telemetry(self) -> MacroTelemetry:
        """
        Fetch India VIX and sectoral indices.
        
        Returns:
            MacroTelemetry with VIX and major indices
        """
        telemetry = MacroTelemetry()
        
        try:
            client = await self._get_client()
            
            # Fetch India VIX
            try:
                vix_url = f"{NSE_BASE_URL}/api/allIndices"
                response = await client.get(vix_url)
                response.raise_for_status()
                data = response.json()
                
                for idx in data.get("data", []):
                    name = idx.get("index", "").upper()
                    value = float(idx.get("last", 0))
                    
                    if "VIX" in name:
                        telemetry.india_vix = value
                    elif name == "NIFTY 50":
                        telemetry.nifty50 = value
                    elif name == "NIFTY BANK":
                        telemetry.nifty_bank = value
                    elif name == "NIFTY IT":
                        telemetry.nifty_it = value
                    elif name == "NIFTY AUTO":
                        telemetry.nifty_auto = value
                    elif name == "NIFTY PHARMA":
                        telemetry.nifty_pharma = value
                    elif name == "NIFTY METAL":
                        telemetry.nifty_metal = value
                    elif name == "NIFTY FMCG":
                        telemetry.nifty_fmcg = value
            except Exception as e:
                logger.warning("Failed to fetch indices: %s", e)
            
            telemetry.timestamp = datetime.now()
            
        except Exception as e:
            logger.warning("Failed to fetch macro telemetry: %s", e)
        
        return telemetry

    # ─────────────────────────────────────────────────────────────────────────
    # Bulk/Block Deals
    # ─────────────────────────────────────────────────────────────────────────

    async def get_bulk_deals(self, trade_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Fetch bulk deals from NSE."""
        try:
            client = await self._get_client()
            url = f"{NSE_BASE_URL}/api/snapshot-capital-market-largedeal"
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            return data.get("BULK_DEALS", [])
        except Exception as e:
            logger.warning("Failed to fetch bulk deals: %s", e)
            return []

    async def get_block_deals(self, trade_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Fetch block deals from NSE."""
        try:
            client = await self._get_client()
            url = f"{NSE_BASE_URL}/api/snapshot-capital-market-largedeal"
            
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            return data.get("BLOCK_DEALS", [])
        except Exception as e:
            logger.warning("Failed to fetch block deals: %s", e)
            return []


# ─────────────────────────────────────────────────────────────────────────────
# Singleton instance
# ─────────────────────────────────────────────────────────────────────────────

_service: Optional[IndianMarketDataService] = None


def get_indian_market_data_service() -> IndianMarketDataService:
    """Get singleton instance of IndianMarketDataService."""
    global _service
    if _service is None:
        _service = IndianMarketDataService()
    return _service


# ─────────────────────────────────────────────────────────────────────────────
# Sync wrappers for use in non-async contexts
# ─────────────────────────────────────────────────────────────────────────────

def get_nse_option_chain_sync(underlying: str, expiry: Optional[str] = None) -> Optional[OptionChainData]:
    """Synchronous wrapper for get_option_chain."""
    service = get_indian_market_data_service()
    return asyncio.run(service.get_option_chain(underlying, expiry))


def get_delivery_data_sync(symbol: str) -> Optional[DeliveryData]:
    """Synchronous wrapper for get_delivery_data."""
    service = get_indian_market_data_service()
    return asyncio.run(service.get_delivery_data(symbol))


def get_macro_telemetry_sync() -> MacroTelemetry:
    """Synchronous wrapper for get_macro_telemetry."""
    service = get_indian_market_data_service()
    return asyncio.run(service.get_macro_telemetry())
