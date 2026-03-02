"""
Swing Trade Scanner API
Detect swing trading opportunities across NIFTY 50 stocks.

Data priority:
  1. Real daily candles from DB  (candles_daily table — 54k+ rows, 88 symbols)
  2. Synthetic history as fallback (only if DB has no data for a symbol)

Current quotes:
  1. Live Zerodha quotes
  2. Simulated quotes when Zerodha is unavailable
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import logging
import random
import math
import hashlib

from app.services.zerodha import KiteConnectService
from app.core.indicators.technical import TechnicalIndicators
from app.config.market_config import get_symbols, get_scanner_strategies
from app.db.session import SessionLocal
from app.db.models_candles import CandleDaily

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/swing-scanner", tags=["swing-scanner"])

kite_service = KiteConnectService()

MIN_CANDLES_FOR_ANALYSIS = 50  # Need at least 50 daily bars for reliable indicators


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_real_candles(db: Session, symbol: str, count: int = 100) -> Optional[tuple]:
    """
    Fetch REAL daily candles from DB for a symbol.
    Returns (closes, highs, lows, volumes) or None if insufficient data.
    """
    candles = (
        db.query(CandleDaily)
        .filter(CandleDaily.symbol == symbol)
        .order_by(desc(CandleDaily.date))
        .limit(count)
        .all()
    )

    if len(candles) < MIN_CANDLES_FOR_ANALYSIS:
        return None

    # Reverse to chronological order (oldest first)
    candles = candles[::-1]

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [int(c.volume) if c.volume else 0 for c in candles]

    return closes, highs, lows, volumes


def _generate_realistic_history(
    ltp: float, volume: int, symbol: str, bars: int = 100
) -> tuple:
    """
    Generate realistic-looking mock OHLCV history that can produce
    detectable swing patterns (mean-reversion, trends, volume spikes).
    Uses a seeded random walk keyed on symbol + date so results are
    deterministic per symbol per day but vary across symbols.
    """
    seed_str = f"{symbol}-{datetime.now().strftime('%Y-%m-%d')}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    # Pick a random "regime" for this symbol today
    regime = rng.choice(["uptrend", "downtrend", "oversold_bounce", "overbought_reversal", "range"])

    closes = []
    highs_list = []
    lows_list = []
    vols = []

    price = ltp * rng.uniform(0.88, 0.96)  # start below current LTP

    for i in range(bars):
        pct = i / bars
        # Base drift depends on regime
        if regime == "uptrend":
            drift = 0.002 + 0.001 * pct          # accelerating uptrend
        elif regime == "downtrend":
            drift = -0.002 - 0.001 * pct
        elif regime == "oversold_bounce":
            drift = -0.004 if pct < 0.6 else 0.006  # drop then sharp bounce
        elif regime == "overbought_reversal":
            drift = 0.004 if pct < 0.6 else -0.005  # rise then drop
        else:  # range
            drift = 0.003 * math.sin(2 * math.pi * pct * 2)  # oscillation

        noise = rng.gauss(0, 0.012)
        price = price * (1 + drift + noise)
        price = max(price, ltp * 0.5)  # floor

        bar_range = price * rng.uniform(0.005, 0.02)
        high = price + bar_range * rng.uniform(0.3, 1.0)
        low = price - bar_range * rng.uniform(0.3, 1.0)

        # Volume: base with random spikes
        vol_base = volume if volume > 0 else 500_000
        vol_mult = rng.uniform(0.6, 1.4)
        # Spike volume in last 20% for momentum regimes
        if pct > 0.8 and regime in ("uptrend", "oversold_bounce"):
            vol_mult *= rng.uniform(1.8, 3.0)
        elif pct > 0.8 and regime in ("downtrend", "overbought_reversal"):
            vol_mult *= rng.uniform(1.5, 2.5)

        closes.append(round(price, 2))
        highs_list.append(round(high, 2))
        lows_list.append(round(low, 2))
        vols.append(int(vol_base * vol_mult))

    # Ensure last close ≈ LTP
    closes[-1] = ltp

    return closes, highs_list, lows_list, vols


def _generate_simulated_quotes(symbols: List[str]) -> Dict[str, Any]:
    """
    Generate fully simulated quote data when Zerodha is not available.
    Provides realistic-looking prices for NIFTY50 stocks so the scanner
    can still demonstrate pattern detection.
    """
    # Representative base prices for common NIFTY stocks
    base_prices = {
        "RELIANCE": 2450, "TCS": 3850, "HDFCBANK": 1680, "INFY": 1620,
        "ICICIBANK": 1050, "HINDUNILVR": 2380, "ITC": 440, "SBIN": 780,
        "BHARTIARTL": 1150, "KOTAKBANK": 1760, "LT": 3400, "AXISBANK": 1080,
        "ASIANPAINT": 2700, "MARUTI": 10800, "TITAN": 3200, "SUNPHARMA": 1150,
        "BAJFINANCE": 6800, "WIPRO": 450, "HCLTECH": 1380, "ULTRACEMCO": 9500,
        "TATAMOTORS": 680, "NTPC": 340, "POWERGRID": 280, "NESTLEIND": 2400,
        "TECHM": 1250, "ONGC": 260, "TATASTEEL": 135, "JSWSTEEL": 780,
        "ADANIENT": 2800, "ADANIPORTS": 1100, "BPCL": 380, "COALINDIA": 390,
        "GRASIM": 2100, "BAJAJFINSV": 1600, "DIVISLAB": 3800, "DRREDDY": 5600,
        "CIPLA": 1400, "EICHERMOT": 4200, "HEROMOTOCO": 4600, "M&M": 1500,
        "INDUSINDBK": 1420, "APOLLOHOSP": 5800, "SBILIFE": 1450, "TATACONSUM": 820,
        "BRITANNIA": 4800, "HINDALCO": 520, "BAJAJ-AUTO": 7500, "HDFCLIFE": 640,
        "SHRIRAMFIN": 2200, "UPL": 540,
    }
    seed_str = f"sim-{datetime.now().strftime('%Y-%m-%d')}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    quotes = {}
    for sym in symbols:
        base = base_prices.get(sym, rng.uniform(200, 3000))
        noise = rng.uniform(-0.03, 0.03)
        ltp = round(base * (1 + noise), 2)
        prev = round(ltp * (1 + rng.uniform(-0.025, 0.025)), 2)
        vol = rng.randint(300_000, 8_000_000)
        quotes[f"NSE:{sym}"] = {
            "last_price": ltp,
            "volume": vol,
            "ohlc": {
                "open": round(prev * (1 + rng.uniform(-0.005, 0.005)), 2),
                "high": round(max(ltp, prev) * (1 + rng.uniform(0.002, 0.015)), 2),
                "low": round(min(ltp, prev) * (1 - rng.uniform(0.002, 0.015)), 2),
                "close": prev,
            },
        }
    return quotes


@router.get("/scan")
async def scan_for_opportunities(
    strategy: str = Query(default="all"),
    min_score: int = Query(default=50, ge=0, le=100),
    universe: str = Query(default="NIFTY50"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Scan stocks for trading opportunities.

    Quote source:  Live Zerodha → simulated fallback
    History source: Real daily candles from DB → synthetic fallback
    """
    try:
        opportunities = []
        scanned_count = 0
        real_candle_count = 0
        data_source = "live (zerodha)"
        
        # Get symbols from config
        symbols = get_symbols(universe)
        
        # ── Current quotes ──────────────────────────────────────────
        logger.info(f"Fetching quotes for {len(symbols)} symbols")
        quotes_data = kite_service.get_bulk_quotes(symbols)
        
        if not quotes_data:
            logger.warning("Zerodha unavailable — using simulated quotes for swing scanner")
            quotes_data = _generate_simulated_quotes(symbols)
            data_source = "simulated"
        else:
            logger.info(f"Received {len(quotes_data)} quotes from Zerodha")
        
        # ── Per-symbol analysis ─────────────────────────────────────
        for symbol in symbols:
            try:
                quote_key = f"NSE:{symbol}"
                quote = quotes_data.get(quote_key)
                
                if not quote:
                    logger.debug(f"No quote data for {symbol}")
                    continue
                
                scanned_count += 1
                
                ltp = quote.get("last_price", 0)
                volume = quote.get("volume", 0)
                ohlc_data = quote.get("ohlc", {})
                prev_close = ohlc_data.get("close", 0)
                
                if ltp == 0 or prev_close == 0:
                    continue
                
                # ── History: prefer REAL DB candles ──────────────────
                candle_data = _get_real_candles(db, symbol, count=100)
                if candle_data:
                    closes, highs, lows, vols = candle_data
                    # Append today's live price as the latest bar
                    closes.append(ltp)
                    highs.append(ltp * 1.005)
                    lows.append(ltp * 0.995)
                    vols.append(volume if volume > 0 else int(vols[-1]))
                    real_candle_count += 1
                else:
                    # Fallback: synthetic history
                    closes, highs, lows, vols = _generate_realistic_history(
                        ltp, volume, symbol
                    )
                
                # ── Pattern detection ───────────────────────────────
                pattern = TechnicalIndicators.detect_swing_pattern(
                    closes, vols, highs, lows
                )
                
                if not pattern or pattern["strength"] < min_score:
                    continue
                
                # Apply strategy filter
                if strategy != "all":
                    if not _matches_strategy(pattern, strategy):
                        continue
                
                change_pct = ((ltp - prev_close) / prev_close) * 100
                
                opportunities.append({
                    "symbol": symbol,
                    "ltp": round(ltp, 2),
                    "change_percent": round(change_pct, 2),
                    "signal": pattern["signal"],
                    "strength": pattern["strength"],
                    "patterns": pattern["patterns"],
                    "indicators": {
                        "rsi": pattern.get("rsi"),
                        "adx": pattern.get("adx"),
                        "volume_spike": pattern.get("volume_spike", False)
                    },
                    "volume": volume,
                    "strategy_match": strategy if strategy != "all" else "multiple"
                })
                
            except Exception as e:
                logger.warning(f"Error scanning {symbol}: {e}")
                continue
        
        # Sort by strength
        opportunities.sort(key=lambda x: x["strength"], reverse=True)
        
        # Annotate data source with candle info
        if real_candle_count > 0:
            data_source += f" | candles: real ({real_candle_count}/{scanned_count})"
        else:
            data_source += " | candles: synthetic"
        
        logger.info(
            f"Swing scan complete: {scanned_count} scanned, "
            f"{len(opportunities)} opportunities (min_score={min_score}), "
            f"{real_candle_count} with real candles"
        )
        
        return {
            "opportunities": opportunities,
            "total_scanned": scanned_count,
            "matches_found": len(opportunities),
            "strategy": strategy,
            "min_score": min_score,
            "timestamp": datetime.now().isoformat(),
            "data_source": data_source
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in swing scanner: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scan for opportunities: {str(e)}"
        )


@router.get("/strategies")
async def get_scanner_strategies_endpoint() -> Dict[str, List[Dict]]:
    """
    Get list of available scanner strategies with descriptions
    
    Returns:
        {
            "strategies": [...]
        }
    """
    strategies_config = get_scanner_strategies()
    
    strategies = [
        {
            "id": key,
            "name": config["name"],
            "description": config["description"],
            "criteria": config["criteria"],
            "ideal_for": config["ideal_for"],
            "timeframe": config.get("timeframe", "N/A"),
            "risk_level": config.get("risk_level", "Medium")
        }
        for key, config in strategies_config.items()
    ]
    
    return {"strategies": strategies}


def _matches_strategy(pattern: Dict, strategy_id: str) -> bool:
    """Check if pattern matches specific strategy"""
    # Get strategy config
    strategies_config = get_scanner_strategies()
    strategy_config = strategies_config.get(strategy_id)
    
    if not strategy_config:
        return True  # If strategy not found, don't filter
    
    patterns_list = pattern.get("patterns", [])
    rsi = pattern.get("rsi", 50)
    adx = pattern.get("adx", 0)
    volume_spike = pattern.get("volume_spike", False)
    
    # Use config parameters for matching
    if strategy_id == "momentum_breakout":
        min_adx = strategy_config.get("min_adx", 25)
        min_rsi = strategy_config.get("min_rsi", 50)
        return (
            "STRONG_UPTREND" in patterns_list
            and adx > min_adx
            and volume_spike
            and rsi > min_rsi
        )
    
    elif strategy_id == "oversold_bounce":
        max_rsi = strategy_config.get("max_rsi", 35)
        return (
            "OVERSOLD_REVERSAL" in patterns_list
            or "BB_BOUNCE" in patterns_list
        ) and rsi < max_rsi
    
    elif strategy_id == "trend_following":
        min_adx = strategy_config.get("min_adx", 25)
        return (
            "STRONG_UPTREND" in patterns_list
            or "STRONG_DOWNTREND" in patterns_list
        ) and adx > min_adx
    
    elif strategy_id == "volume_surge":
        return volume_spike and pattern["strength"] > 60
    
    elif strategy_id == "bollinger_squeeze":
        return (
            "BB_BOUNCE" in patterns_list
            or "BB_REJECTION" in patterns_list
        )
    
    return True
