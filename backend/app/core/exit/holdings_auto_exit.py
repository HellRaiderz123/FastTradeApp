"""
holdings_auto_exit.py
---------------------
Auto-exit monitoring for StockHolding (scanner/AI trades).

Monitors:
1. TP/SL percentage exits
2. Trailing stop loss
3. Condition-based exits (e.g., Supertrend turns bearish)

Runs every minute during market hours.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import SessionLocal
from app.db.models_stock_holding import StockHolding
from app.db.models_scanner_signal import ScannerSignalHistory
from app.db.models_condition_strategy import ConditionStrategy
from app.core.utils.time import now_ist
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
kite_service = KiteConnectService()


def _get_bulk_ltps(symbols: List[str]) -> Dict[str, float]:
    """Fetch LTPs for multiple symbols."""
    if not symbols:
        return {}
    try:
        quotes = kite_service.get_bulk_quotes(symbols) or {}
        ltps = {}
        for sym in symbols:
            q = quotes.get(f"NSE:{sym}") or quotes.get(sym)
            if q:
                ltps[sym] = float(q.get("last_price") or 0)
        return ltps
    except Exception as e:
        logger.warning(f"Failed to fetch LTPs: {e}")
        return {}


def _check_exit_conditions(
    db: Session,
    symbol: str,
    strategy_id: Optional[int],
    timeframe: str = "Day",
) -> bool:
    """
    Check if exit conditions are met for a holding.
    Returns True if should exit.
    """
    if not strategy_id:
        return False
    
    try:
        # Get strategy exit conditions
        strategy = db.query(ConditionStrategy).filter(
            ConditionStrategy.id == strategy_id
        ).first()
        
        if not strategy:
            return False
        
        exit_config = strategy.exit_config_dict or {}
        exit_conditions = exit_config.get("exit_conditions") or []
        
        if not exit_conditions:
            return False
        
        # Import condition evaluation functions
        from app.api.routes.condition_scanner import (
            _evaluate_condition, _build_price_series, TIMEFRAME_CANDLE_MAP
        )
        
        candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe, TIMEFRAME_CANDLE_MAP["Day"])
        CandleModel, date_attr, _ = candle_info
        date_col = getattr(CandleModel, date_attr)
        
        candles = (
            db.query(CandleModel)
            .filter(CandleModel.symbol == symbol)
            .order_by(desc(date_col))
            .limit(100)
            .all()
        )[::-1]
        
        if len(candles) < 2:
            return False
        
        closes, highs, lows, volumes = _build_price_series(candles)
        
        # All exit conditions must be met
        return all(
            _evaluate_condition(cond, closes, highs, lows, volumes)
            for cond in exit_conditions
        )
        
    except Exception as e:
        logger.debug(f"Exit condition check failed for {symbol}: {e}")
        return False


def _check_supertrend_exit(
    db: Session,
    symbol: str,
    direction: str,
    timeframe: str = "Day",
) -> bool:
    """
    Check if Supertrend has reversed (bullish trade but Supertrend now bearish).
    This is a common exit condition for Supertrend strategies.
    """
    try:
        from app.api.routes.condition_scanner import (
            _compute_indicator, _build_price_series, TIMEFRAME_CANDLE_MAP
        )
        
        candle_info = TIMEFRAME_CANDLE_MAP.get(timeframe, TIMEFRAME_CANDLE_MAP["Day"])
        CandleModel, date_attr, _ = candle_info
        date_col = getattr(CandleModel, date_attr)
        
        candles = (
            db.query(CandleModel)
            .filter(CandleModel.symbol == symbol)
            .order_by(desc(date_col))
            .limit(50)
            .all()
        )[::-1]
        
        if len(candles) < 15:
            return False
        
        closes, highs, lows, volumes = _build_price_series(candles)
        
        # Calculate Supertrend
        supertrend = _compute_indicator(
            "SUPERTREND",
            {"period": 10, "multiplier": 3.0},
            closes, highs, lows, volumes
        )
        
        if supertrend is None:
            return False
        
        # For BUY positions: exit if Supertrend turns bearish (-1)
        # For SELL positions: exit if Supertrend turns bullish (+1)
        if direction == "BUY" and supertrend < 0:
            return True
        if direction == "SELL" and supertrend > 0:
            return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Supertrend exit check failed for {symbol}: {e}")
        return False


def run_holdings_auto_exit(db: Session = None) -> Dict[str, Any]:
    """
    Main auto-exit function for StockHolding.
    Checks TP/SL/TSL and condition-based exits.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    result = {
        "checked": 0,
        "exited": [],
        "errors": [],
    }
    
    try:
        # Get all open holdings
        holdings = db.query(StockHolding).filter(
            StockHolding.status == "OPEN"
        ).all()
        
        if not holdings:
            return result
        
        result["checked"] = len(holdings)
        
        # Fetch LTPs in bulk
        symbols = list({h.symbol for h in holdings})
        ltps = _get_bulk_ltps(symbols)
        
        now = now_ist()
        
        for holding in holdings:
            try:
                ltp = ltps.get(holding.symbol)
                if not ltp or ltp <= 0:
                    continue
                
                # Update current price
                holding.current_price = ltp
                
                # Calculate P&L
                if holding.direction == "BUY":
                    pnl = (ltp - holding.entry_price) * holding.quantity
                    pnl_pct = ((ltp - holding.entry_price) / holding.entry_price) * 100
                else:
                    pnl = (holding.entry_price - ltp) * holding.quantity
                    pnl_pct = ((holding.entry_price - ltp) / holding.entry_price) * 100
                
                holding.pnl = round(pnl, 2)
                
                exit_reason = None
                
                # Check TP
                if holding.tp_pct and pnl_pct >= holding.tp_pct:
                    exit_reason = "TP_HIT"
                
                # Check SL
                elif holding.sl_pct and pnl_pct <= -holding.sl_pct:
                    exit_reason = "SL_HIT"
                
                # Check TSL (trailing stop)
                # TODO: Track max_pnl for proper TSL
                
                # Check condition-based exit
                if not exit_reason:
                    # Get strategy ID from signal history
                    signal = db.query(ScannerSignalHistory).filter(
                        ScannerSignalHistory.symbol == holding.symbol,
                        ScannerSignalHistory.strategy_name == holding.strategy_name,
                        ScannerSignalHistory.status == "FILLED_PAPER",
                    ).order_by(ScannerSignalHistory.executed_at.desc()).first()
                    
                    strategy_id = signal.strategy_id if signal else None
                    timeframe = "Day"  # Default, could be stored in holding
                    
                    if signal and signal.signal_payload:
                        timeframe = signal.signal_payload.get("timeframe", "Day")
                    
                    # Check explicit exit conditions
                    if _check_exit_conditions(db, holding.symbol, strategy_id, timeframe):
                        exit_reason = "COND_EXIT"
                    
                    # Check Supertrend reversal for Supertrend strategies
                    elif holding.strategy_name and "supertrend" in holding.strategy_name.lower():
                        if _check_supertrend_exit(db, holding.symbol, holding.direction, timeframe):
                            exit_reason = "SUPERTREND_REVERSAL"
                
                # Execute exit
                if exit_reason:
                    holding.status = "CLOSED"
                    holding.exit_price = ltp
                    holding.exit_reason = exit_reason
                    holding.closed_at = now
                    
                    result["exited"].append({
                        "symbol": holding.symbol,
                        "direction": holding.direction,
                        "entry_price": holding.entry_price,
                        "exit_price": ltp,
                        "pnl": holding.pnl,
                        "pnl_pct": round(pnl_pct, 2),
                        "exit_reason": exit_reason,
                        "strategy": holding.strategy_name,
                    })
                    
                    logger.info(
                        f"📤 HOLDING EXIT | {holding.symbol} | {exit_reason} | "
                        f"Entry: ₹{holding.entry_price:.2f} → Exit: ₹{ltp:.2f} | "
                        f"P&L: ₹{holding.pnl:.2f} ({pnl_pct:+.1f}%)"
                    )
                    
                    # Also close the corresponding ExecutionIntent if exists
                    try:
                        from app.db.models_intent import ExecutionIntent
                        intent = db.query(ExecutionIntent).filter(
                            ExecutionIntent.underlying == holding.symbol,
                            ExecutionIntent.status == "EXECUTED",
                            ExecutionIntent.intent_id.like("SCANNER-%"),
                        ).first()
                        if intent:
                            intent.status = "CLOSED"
                            intent.exit_reason = exit_reason
                            intent.closed_at = now
                            intent.pnl = holding.pnl
                    except Exception:
                        pass
                    
            except Exception as e:
                result["errors"].append(f"{holding.symbol}: {str(e)}")
                logger.warning(f"Error checking holding {holding.symbol}: {e}")
        
        db.commit()
        
        if result["exited"]:
            logger.info(f"📊 Holdings auto-exit: {len(result['exited'])} positions closed")
        
    except Exception as e:
        logger.exception(f"Holdings auto-exit error: {e}")
        result["errors"].append(str(e))
    finally:
        if close_db:
            db.close()
    
    return result


def _holdings_exit_job():
    """Scheduled job for holdings auto-exit."""
    logger.debug("⏱️ Running holdings auto-exit check")
    
    # Only run during market hours
    now = now_ist()
    if now.weekday() >= 5:  # Weekend
        return
    
    market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if not (market_start <= now <= market_end):
        return
    
    result = run_holdings_auto_exit()
    
    if result["exited"]:
        logger.info(f"📤 Holdings exit job: {len(result['exited'])} exits triggered")


def start_holdings_exit_scheduler(scheduler):
    """Start the holdings auto-exit scheduler (every 1 minute during market hours)."""
    scheduler.add_job(
        func=_holdings_exit_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*",
        id="holdings_auto_exit_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("🟢 Holdings auto-exit scheduler started (every 1 min, 9:15 AM - 3:30 PM IST)")
