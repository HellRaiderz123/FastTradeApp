"""
Stock Suggestions API

Generate trade suggestions for stock symbols using enabled strategies.
Works like options suggestions - can run on-the-fly without database strategies.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from pydantic import BaseModel
from datetime import datetime

from app.core.strategies.executor import StrategyExecutor
from app.db.models import StrategyConfig

from app.db.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/suggestions/stocks", tags=["suggestions"])


class StockSuggestionsRequest(BaseModel):
    """Request model for stock suggestions"""
    symbols: List[str]  # List of stock symbols to analyze
    min_confidence: int = 50  # Minimum confidence level
    quantity: int = 100  # Default quantity per trade
    capital: float = 100000.0  # Available capital
    timeframe: str = "15m"  # Timeframe: "15m" (intraday) or "daily" (swing)
    use_ml: bool = False  # Whether to apply ML signal override


def _compute_stock_score(result: Dict[str, Any]) -> float:
    """
    Compute a score for ranking stock suggestions.
    
    Scoring factors:
    - Confidence level (0-100)
    - Signal strength (BUY/SELL adds bonus)
    - Risk/reward ratio (higher is better)
    - Technical indicator quality
    
    Returns score from 0-100
    """
    signal_data = result.get("signal", {})
    confidence = signal_data.get("confidence", 0)
    
    # Base score from confidence
    score = confidence
    
    # Bonus for strong signals
    signal = signal_data.get("signal", "HOLD")
    if signal in ["BUY", "SELL"]:
        score += 10
    elif signal == "STRONG_BUY" or signal == "STRONG_SELL":
        score += 20
    
    # Bonus for good risk/reward
    rr_ratio = result.get("risk_reward_ratio", 0)
    if rr_ratio >= 2.0:
        score += 15
    elif rr_ratio >= 1.5:
        score += 10
    elif rr_ratio >= 1.0:
        score += 5
    
    # Bonus for quality indicators
    indicators = signal_data.get("indicators", {})
    if len(indicators) >= 3:
        score += 5
    
    # Cap at 100
    return min(score, 100)


@router.post("", response_model=Dict[str, Any])
def get_stock_suggestions(
    request: StockSuggestionsRequest, 
    db: Session = Depends(get_db)
):
    """
    Get trade suggestions for multiple stock symbols.
    
    Works like options suggestions - generates suggestions on-the-fly.
    If no database strategies exist, uses default stock strategies directly.
    """
    generated_at = datetime.utcnow().isoformat() + "Z"
    suggestions: List[Dict[str, Any]] = []
    
    # Determine strategy types based on timeframe
    if request.timeframe == "daily":
        strategy_type_filter = [
            'stock_momentum_daily',
            'stock_trend_following_daily',
            'stock_mean_reversion_daily'
        ]
    else:  # Default to 15m
        strategy_type_filter = [
            'stock_momentum_15m',
            'stock_trend_following_15m',
            'stock_mean_reversion_15m',
            'momentum',
            'trend_following',
            'mean_reversion'
        ]
    
    # Get all enabled stock strategies from database
    stock_strategies = (
        db.query(StrategyConfig)
        .filter(
            StrategyConfig.enabled == True,
            StrategyConfig.strategy_type.in_(strategy_type_filter)
        )
        .all()
    )
    
    # Determine execution mode
    use_direct_execution = len(stock_strategies) == 0
    
    if use_direct_execution:
        # Run strategies directly without database entries
        from app.core.strategies.registry import StrategyRegistry
        from app.core.signals.base import Signal, SignalStrength, AssetType, MarketBias
        from app.core.signals.ta_engine import ta_signal_15m_from_candles, ta_signal_daily_from_df
        from app.core.signals.signal_enricher import merge_signals
        from app.core.signals.ml_engine import ml_stock_signal
        from app.core.market.candles import fetch_15m_candles
        from app.db.models_candles import Candle15m, CandleDaily
        import pandas as pd
        import traceback
        
        # Determine which strategies to use based on timeframe
        if request.timeframe == "daily":
            default_strategy_types = [
                'stock_momentum_daily',
                'stock_trend_following_daily',
                'stock_mean_reversion_daily'
            ]
        else:
            default_strategy_types = [
                'stock_momentum_15m',
                'stock_trend_following_15m',
                'stock_mean_reversion_15m'
            ]
        
        # For each symbol, run default strategies
        for symbol in request.symbols:
            # Fetch appropriate candles based on timeframe
            if request.timeframe == "daily":
                # Get daily candles
                candle_records = (
                    db.query(CandleDaily)
                    .filter(CandleDaily.symbol == symbol)
                    .order_by(CandleDaily.date.desc())
                    .limit(250)
                    .all()
                )
                min_candles = 200
                
                if not candle_records or len(candle_records) < min_candles:
                    # Add no-trade suggestion for insufficient data
                    suggestion = {
                        "symbol": symbol,
                        "strategy": "all",
                        "strategy_name": "Technical Analysis (Daily)",
                        "approved": False,
                        "reason": f"Insufficient daily candle data ({len(candle_records) if candle_records else 0} candles, need {min_candles})",
                        "score": 0,
                        "current_price": candle_records[0].close if candle_records else None,
                        "signal": "NO_TRADE",
                        "entry_price": None,
                        "stop_loss": None,
                        "target": None,
                        "confidence": 0,
                        "indicators": {},
                        "risk_reward_ratio": 0,
                    }
                    suggestions.append(suggestion)
                    continue
                
                # Convert to DataFrame for daily analysis
                df = pd.DataFrame(
                    [
                        {
                            "close": c.close,
                            "open": c.open,
                            "high": c.high,
                            "low": c.low,
                            "volume": c.volume,
                        }
                        for c in reversed(candle_records)
                    ]
                )
                
                # Run daily TA analysis
                ta_result = ta_signal_daily_from_df(df)
                latest = {"close": candle_records[0].close, "timestamp": candle_records[0].date}
            else:
                # Get 15m candles
                candle_records = (
                    db.query(Candle15m)
                    .filter(Candle15m.symbol == symbol)
                    .order_by(Candle15m.timestamp.desc())
                    .limit(300)
                    .all()
                )

                if not candle_records or len(candle_records) < 120:
                    # Auto-fetch candles if missing
                    try:
                        fetch_15m_candles(db, symbol, days=30)
                    except Exception as exc:
                        print(f"Candle fetch failed for {symbol}: {exc}")

                    candle_records = (
                        db.query(Candle15m)
                        .filter(Candle15m.symbol == symbol)
                        .order_by(Candle15m.timestamp.desc())
                        .limit(300)
                        .all()
                    )

                if not candle_records or len(candle_records) < 120:
                    # Add no-trade suggestion for insufficient data
                    suggestion = {
                        "symbol": symbol,
                        "strategy": "all",
                        "strategy_name": "Technical Analysis (15m)",
                        "approved": False,
                        "reason": f"Insufficient candle data ({len(candle_records) if candle_records else 0} candles)",
                        "score": 0,
                        "current_price": candle_records[0].close if candle_records else None,
                        "signal": "NO_TRADE",
                        "entry_price": None,
                        "stop_loss": None,
                        "target": None,
                        "confidence": 0,
                        "indicators": {},
                        "risk_reward_ratio": 0,
                    }
                    suggestions.append(suggestion)
                    continue
                
                # Convert to dict format (reverse to chronological order)
                candles = [
                    {
                        "close": c.close,
                        "open": c.open,
                        "high": c.high,
                        "low": c.low,
                        "volume": c.volume,
                        "timestamp": c.timestamp
                    }
                    for c in reversed(candle_records)
                ]
                
                # Run 15m TA analysis
                ta_result = ta_signal_15m_from_candles(candles)
                latest = candles[-1]

            if request.use_ml:
                ml = ml_stock_signal(db, symbol, timeframe=request.timeframe)
                ta_result = merge_signals(ta_result, ml)
            
            # Create Signal object from TA result
            signal_strength_map = {
                "BULLISH": SignalStrength.BUY,
                "BEARISH": SignalStrength.SELL,
                "RANGE": SignalStrength.HOLD,
                "NO_TRADE": SignalStrength.NO_TRADE,
            }
            
            bias_map = {
                "BULLISH": MarketBias.BULLISH,
                "BEARISH": MarketBias.BEARISH,
                "NEUTRAL": MarketBias.NEUTRAL,
            }

            signal = Signal(
                asset_type=AssetType.STOCK,
                symbol=symbol,
                timestamp=latest.get("timestamp") or datetime.utcnow(),
                signal=signal_strength_map.get(ta_result.get("signal", "NO_TRADE"), SignalStrength.HOLD),
                confidence=ta_result.get("confidence", 0),
                bias=bias_map.get(ta_result.get("bias", "NEUTRAL"), MarketBias.NEUTRAL),
                reasoning=ta_result.get("reason", ""),
                indicators=ta_result.get("indicators", {}),
                quality_score=ta_result.get("quality_score", 0),
                trade_readiness_score=ta_result.get("trade_readiness_score", 0),
            )
            
            # Now try each strategy with this signal
            for strategy_type in default_strategy_types:
                try:
                    # Get strategy from registry
                    strategy_class = StrategyRegistry.get(strategy_type)
                    if not strategy_class:
                        continue
                    
                    strategy_instance = strategy_class() if callable(strategy_class) else strategy_class
                    
                    # Execute strategy
                    result = None
                    if hasattr(strategy_instance, 'evaluate_and_generate'):
                        result = strategy_instance.evaluate_and_generate(signal, {
                            "symbol": symbol,
                            "quantity": request.quantity,
                            "capital": request.capital
                        })
                    elif hasattr(strategy_instance, 'generate_legs'):
                        legs = strategy_instance.generate_legs(signal, {
                            "symbol": symbol,
                            "quantity": request.quantity
                        })
                        if legs:
                            result = {
                                "approved": len(legs) > 0,
                                "signal": signal.model_dump(),
                                "legs": [leg.model_dump() for leg in legs],
                                "reason": ta_result.get("reason", f"Strategy generated {len(legs)} legs"),
                                "risk_reward_ratio": 1.5
                            }
                    
                    # Always include suggestion, even if not approved
                    if not result:
                        # Use TA analysis reason for why no trade
                        ta_reason = ta_result.get("reason", "No clear directional edge")
                        ta_signal = ta_result.get("signal", "NO_TRADE")
                        ta_confidence = ta_result.get("confidence", 0)
                        
                        suggestion = {
                            "symbol": symbol,
                            "strategy": strategy_type,
                            "strategy_name": strategy_type.replace('_', ' ').title(),
                            "approved": False,
                            "reason": ta_reason,
                            "score": 0,
                            "current_price": latest["close"],
                            "signal": ta_signal,
                            "entry_price": None,
                            "stop_loss": None,
                            "target": None,
                            "confidence": ta_confidence,
                            "indicators": ta_result.get("indicators", {}),
                            "risk_reward_ratio": 0,
                        }
                        suggestions.append(suggestion)
                        continue
                    
                    # Extract signal data
                    signal_data = result.get("signal", {})
                    approved = result.get("approved", False)
                    confidence = signal_data.get("confidence", 0)
                    
                    # Compute score
                    score = _compute_stock_score(result) if approved else 0
                    
                    # Build suggestion (include both approved and not approved)
                    suggestion = {
                        "symbol": symbol,
                        "strategy": strategy_type,
                        "strategy_name": strategy_type.replace('_', ' ').title(),
                        "approved": approved,
                        "reason": result.get("reason", f"Generated by {strategy_type}" if approved else "No trade opportunity"),
                        "score": score,
                        "current_price": latest["close"],
                        "signal": signal_data.get("signal", "NO_TRADE" if not approved else "HOLD"),
                        "entry_price": latest["close"] if approved else None,
                        "stop_loss": result.get("stop_loss"),
                        "target": result.get("target"),
                        "confidence": confidence,
                        "indicators": signal_data.get("indicators", {}),
                        "risk_reward_ratio": result.get("risk_reward_ratio", 0),
                    }
                    
                    suggestions.append(suggestion)
                    
                except Exception as e:
                    print(f"Error executing {strategy_type} for {symbol}: {e}")
                    traceback.print_exc()
                    continue
    
    else:
        # Use database strategies
        for symbol in request.symbols:
            for strategy_config in stock_strategies:
                # Skip if strategy is symbol-specific and doesn't match
                if strategy_config.underlying and strategy_config.underlying != symbol:
                    continue
                
                try:
                    executor = StrategyExecutor(strategy_config.id, db)
                    
                    # Execute with symbol context
                    result = executor.execute(additional_context={
                        "symbol": symbol,
                        "quantity": request.quantity,
                        "capital": request.capital
                    })
                    
                    # Always include suggestion, even if not approved
                    if not result:
                        suggestion = {
                            "symbol": symbol,
                            "strategy": strategy_config.strategy_type,
                            "strategy_name": strategy_config.name,
                            "approved": False,
                            "reason": "Strategy execution failed",
                            "score": 0,
                            "current_price": None,
                            "signal": "NO_TRADE",
                            "entry_price": None,
                            "stop_loss": None,
                            "target": None,
                            "confidence": 0,
                            "indicators": {},
                            "risk_reward_ratio": 0,
                        }
                        suggestions.append(suggestion)
                        continue
                    
                    # Extract relevant data
                    approved = result.get("approved", False)
                    signal_data = result.get("signal", {})
                    confidence = signal_data.get("confidence", 0)
                    
                    # Compute score
                    score = _compute_stock_score(result) if approved else 0
                    
                    # Build suggestion item (include both approved and not approved)
                    suggestion = {
                        "symbol": symbol,
                        "strategy": strategy_config.strategy_type,
                        "strategy_name": strategy_config.name,
                        "approved": approved,
                        "reason": result.get("reason", "No trade opportunity"),
                        "score": score,
                        "current_price": signal_data.get("close") or signal_data.get("current_price"),
                        "signal": signal_data.get("signal", "NO_TRADE"),
                        "entry_price": result.get("entry_price"),
                        "stop_loss": result.get("stop_loss"),
                        "target": result.get("target"),
                        "confidence": confidence,
                        "indicators": signal_data.get("indicators", {}),
                        "risk_reward_ratio": result.get("risk_reward_ratio", 0),
                    }
                    
                    suggestions.append(suggestion)
                    
                except Exception as e:
                    # Log error but add a no-trade suggestion
                    print(f"Error executing {strategy_config.name} for {symbol}: {e}")
                    suggestion = {
                        "symbol": symbol,
                        "strategy": strategy_config.strategy_type,
                        "strategy_name": strategy_config.name,
                        "approved": False,
                        "reason": f"Error: {str(e)[:100]}",
                        "score": 0,
                        "current_price": None,
                        "signal": "NO_TRADE",
                        "entry_price": None,
                        "stop_loss": None,
                        "target": None,
                        "confidence": 0,
                        "indicators": {},
                        "risk_reward_ratio": 0,
                    }
                    suggestions.append(suggestion)
                    continue
    
    # Collapse to one best suggestion per symbol
    grouped: Dict[str, Dict[str, Any]] = {}
    strategy_lists: Dict[str, List[str]] = {}
    for item in suggestions:
        symbol = item.get("symbol") or ""
        if symbol not in strategy_lists:
            strategy_lists[symbol] = []
        strategy_label = item.get("strategy_name") or item.get("strategy") or "Unknown"
        if strategy_label not in strategy_lists[symbol]:
            strategy_lists[symbol].append(strategy_label)

        if symbol not in grouped:
            grouped[symbol] = item
            continue

        current = grouped[symbol]
        key_new = (bool(item.get("approved", False)), float(item.get("score") or 0))
        key_cur = (bool(current.get("approved", False)), float(current.get("score") or 0))
        if key_new > key_cur:
            grouped[symbol] = item

    suggestions = list(grouped.values())
    for item in suggestions:
        symbol = item.get("symbol") or ""
        item["strategies_attempted"] = strategy_lists.get(symbol, [])
        item["strategies_count"] = len(item["strategies_attempted"])

    # Sort approved first, then by score (like options suggestions)
    suggestions.sort(key=lambda x: (x.get("approved", False), x.get("score", 0)), reverse=True)
    
    return {
        "generated_at": generated_at,
        "suggestions": suggestions,
        "count": len(suggestions),
        "symbols_analyzed": request.symbols,
        "strategies_used": len(stock_strategies) if not use_direct_execution else 3,
        "mode": "direct" if use_direct_execution else "database"
    }


@router.get("/available-symbols", response_model=Dict[str, Any])
def get_available_symbols():
    """Get list of available stock symbols for suggestions"""
    # NIFTY 50 stocks (sample list)
    nifty50_stocks = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "HINDUNILVR", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK",
        "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "HCLTECH",
        "WIPRO", "ULTRACEMCO", "BAJFINANCE", "SUNPHARMA", "TITAN",
        "TECHM", "NESTLEIND", "POWERGRID", "NTPC", "M&M",
        "TATASTEEL", "INDUSINDBK", "ADANIPORTS", "COALINDIA", "ONGC",
        "BAJAJFINSV", "DIVISLAB", "DRREDDY", "GRASIM", "BRITANNIA",
        "HINDALCO", "JSWSTEEL", "CIPLA", "EICHERMOT", "TATAMOTORS",
        "HEROMOTOCO", "TATACONSUM", "SBILIFE", "BPCL", "APOLLOHOSP",
        "UPL", "SHREECEM", "TATAPOWER", "VEDL", "ADANIENT"
    ]
    
    return {
        "symbols": nifty50_stocks,
        "count": len(nifty50_stocks)
    }
