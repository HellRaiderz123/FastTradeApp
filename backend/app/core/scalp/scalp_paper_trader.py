"""
scalp_paper_trader.py
---------------------
5-Minute Scalping Paper Trading Engine

Features:
- Runs every 5 minutes during market hours
- Generates SCALP_CALL / SCALP_PUT signals
- Auto-executes paper trades with TP/SL
- Tracks all trades in database for analysis
- Calculates win rate, accuracy, P&L metrics
"""

import logging
import os
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Date, func

from app.db.session import SessionLocal, Base
from app.core.signals.ta_engine import ta_signal_5m
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)

# ================================================================
# CONFIGURATION
# ================================================================

SCALP_CONFIG = {
    # Underlyings to scan
    "underlyings": ["NIFTY", "BANKNIFTY"],
    
    # Position sizing
    "lots": 1,
    "capital_per_trade": 50000,
    
    # TP/SL as % of premium
    "tp_pct": 30,   # 30% profit target
    "sl_pct": 20,   # 20% stop loss
    
    # Time-based exit (minutes)
    "max_hold_minutes": 30,
    
    # Signal filters
    "min_confidence": 60,
    "require_scalp_ready": True,
    
    # Risk limits
    "max_open_scalps": 2,
    "max_daily_trades": 10,
    "max_daily_loss": 5000,
}


# ================================================================
# DATABASE MODEL FOR SCALP TRADES
# ================================================================

class ScalpTrade(Base):
    """Track all scalp paper trades for analysis."""
    __tablename__ = "scalp_trades"
    
    id = Column(Integer, primary_key=True)
    trade_id = Column(String, unique=True, index=True)
    underlying = Column(String, index=True)
    trade_date = Column(Date, index=True)
    
    # Signal info
    signal_type = Column(String)
    signal_confidence = Column(Float)
    signal_reason = Column(String)
    signal_indicators = Column(JSON)
    
    # Option details
    option_symbol = Column(String)
    option_type = Column(String)
    strike = Column(Integer)
    expiry = Column(String)
    
    # Entry
    entry_time = Column(DateTime(timezone=True))
    entry_price = Column(Float)
    spot_at_entry = Column(Float)
    
    # Exit
    exit_time = Column(DateTime(timezone=True), nullable=True)
    exit_price = Column(Float, nullable=True)
    spot_at_exit = Column(Float, nullable=True)
    exit_reason = Column(String, nullable=True)
    
    # P&L
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    
    # Targets
    tp_price = Column(Float)
    sl_price = Column(Float)
    
    # Status
    status = Column(String, default="OPEN")
    lots = Column(Integer, default=1)
    lot_size = Column(Integer)
    
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def generate_trade_id() -> str:
    import uuid
    return f"SCALP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"


def get_option_ltp(symbol: str) -> Optional[float]:
    """Get current LTP for an option symbol."""
    try:
        from app.core.broker.zerodha.client import get_kite_client
        kite = get_kite_client()
        data = kite.ltp([f"NFO:{symbol}"])
        return data.get(f"NFO:{symbol}", {}).get("last_price")
    except Exception as e:
        logger.warning(f"Could not fetch LTP for {symbol}: {e}")
        return None


def get_lot_size(underlying: str) -> int:
    return {"NIFTY": 75, "BANKNIFTY": 30, "FINNIFTY": 65}.get(underlying, 50)


def check_daily_limits(db: Session) -> Tuple[bool, str]:
    """Check if daily trading limits are exceeded."""
    today = date.today()
    
    trade_count = db.query(ScalpTrade).filter(ScalpTrade.trade_date == today).count()
    if trade_count >= SCALP_CONFIG["max_daily_trades"]:
        return False, f"Daily trade limit reached ({trade_count}/{SCALP_CONFIG['max_daily_trades']})"
    
    daily_pnl = db.query(func.sum(ScalpTrade.pnl)).filter(
        ScalpTrade.trade_date == today, ScalpTrade.status == "CLOSED"
    ).scalar() or 0
    
    if daily_pnl <= -SCALP_CONFIG["max_daily_loss"]:
        return False, f"Daily loss limit reached (₹{daily_pnl:.2f})"
    
    open_count = db.query(ScalpTrade).filter(ScalpTrade.status == "OPEN").count()
    if open_count >= SCALP_CONFIG["max_open_scalps"]:
        return False, f"Max open scalps reached ({open_count}/{SCALP_CONFIG['max_open_scalps']})"
    
    return True, "OK"


# ================================================================
# CORE TRADING FUNCTIONS
# ================================================================

def create_scalp_entry(db: Session, underlying: str, signal: Dict) -> Optional[ScalpTrade]:
    """Create a new scalp paper trade entry."""
    try:
        from app.services.market_data import get_spot, pick_atm_strike
        from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
        from app.core.market.expiry import get_next_weekly_expiry_from_kite
        
        spot = get_spot(underlying)
        atm = pick_atm_strike(underlying, spot)
        expiry = get_next_weekly_expiry_from_kite(underlying)
        lot_size = get_lot_size(underlying)
        
        signal_type = signal.get("signal", "")
        if "BULLISH" in signal_type:
            option_type = "CE"
        elif "BEARISH" in signal_type:
            option_type = "PE"
        else:
            return None
        
        strike = atm
        option_symbol = build_zerodha_option_symbol(
            underlying=underlying, expiry=expiry, strike=strike, option_type=option_type
        )
        
        entry_price = get_option_ltp(option_symbol)
        if not entry_price:
            logger.warning(f"Could not get LTP for {option_symbol}")
            return None
        
        tp_price = entry_price * (1 + SCALP_CONFIG["tp_pct"] / 100)
        sl_price = entry_price * (1 - SCALP_CONFIG["sl_pct"] / 100)
        
        trade = ScalpTrade(
            trade_id=generate_trade_id(),
            underlying=underlying,
            trade_date=date.today(),
            signal_type=signal_type,
            signal_confidence=signal.get("confidence", 0),
            signal_reason=signal.get("reason", ""),
            signal_indicators=signal.get("indicators", {}),
            option_symbol=option_symbol,
            option_type=option_type,
            strike=strike,
            expiry=str(expiry),
            entry_time=now_ist(),
            entry_price=entry_price,
            spot_at_entry=spot,
            tp_price=round(tp_price, 2),
            sl_price=round(sl_price, 2),
            status="OPEN",
            lots=SCALP_CONFIG["lots"],
            lot_size=lot_size,
        )
        
        db.add(trade)
        db.commit()
        db.refresh(trade)
        
        logger.info(
            f"📈 SCALP ENTRY | {trade.trade_id} | {underlying} {option_type} {strike} | "
            f"Entry: ₹{entry_price:.2f} | TP: ₹{tp_price:.2f} | SL: ₹{sl_price:.2f}"
        )
        return trade
        
    except Exception as e:
        logger.exception(f"Error creating scalp entry: {e}")
        db.rollback()
        return None


def check_and_exit_scalps(db: Session) -> List[Dict]:
    """Check all open scalps for TP/SL/Time exit."""
    from app.services.market_data import get_spot
    
    exits = []
    open_trades = db.query(ScalpTrade).filter(ScalpTrade.status == "OPEN").all()
    
    for trade in open_trades:
        try:
            current_price = get_option_ltp(trade.option_symbol)
            if not current_price:
                continue
            
            current_spot = get_spot(trade.underlying)
            exit_reason = None
            
            if current_price >= trade.tp_price:
                exit_reason = "TP_HIT"
            elif current_price <= trade.sl_price:
                exit_reason = "SL_HIT"
            elif trade.entry_time:
                hold_minutes = (now_ist() - trade.entry_time).total_seconds() / 60
                if hold_minutes >= SCALP_CONFIG["max_hold_minutes"]:
                    exit_reason = "TIME_EXIT"
            
            if exit_reason:
                pnl_per_unit = current_price - trade.entry_price
                total_pnl = pnl_per_unit * trade.lot_size * trade.lots
                pnl_pct = (pnl_per_unit / trade.entry_price) * 100
                
                trade.exit_time = now_ist()
                trade.exit_price = current_price
                trade.spot_at_exit = current_spot
                trade.exit_reason = exit_reason
                trade.pnl = round(total_pnl, 2)
                trade.pnl_pct = round(pnl_pct, 2)
                trade.status = "CLOSED"
                db.commit()
                
                emoji = "✅" if total_pnl > 0 else "❌"
                logger.info(
                    f"{emoji} SCALP EXIT | {trade.trade_id} | {exit_reason} | "
                    f"Entry: ₹{trade.entry_price:.2f} → Exit: ₹{current_price:.2f} | "
                    f"P&L: ₹{total_pnl:.2f} ({pnl_pct:+.1f}%)"
                )
                
                exits.append({
                    "trade_id": trade.trade_id,
                    "underlying": trade.underlying,
                    "exit_reason": exit_reason,
                    "pnl": total_pnl,
                    "pnl_pct": pnl_pct,
                })
        except Exception as e:
            logger.exception(f"Error checking scalp {trade.trade_id}: {e}")
    
    return exits


def scan_for_scalp_signals(db: Session) -> List[Dict]:
    """Scan underlyings for scalp signals."""
    signals = []
    
    for underlying in SCALP_CONFIG["underlyings"]:
        try:
            signal = ta_signal_5m(db, underlying)
            
            if signal.get("confidence", 0) < SCALP_CONFIG["min_confidence"]:
                continue
            if SCALP_CONFIG["require_scalp_ready"] and not signal.get("scalp_ready"):
                continue
            
            signal_type = signal.get("signal", "")
            if signal_type not in ["SCALP_BULLISH", "SCALP_BEARISH"]:
                continue
            
            signals.append({"underlying": underlying, "signal": signal})
            logger.info(
                f"🎯 SCALP SIGNAL | {underlying} | {signal_type} | "
                f"Conf: {signal.get('confidence')}% | {signal.get('reason')}"
            )
        except Exception as e:
            logger.warning(f"Error scanning {underlying}: {e}")
    
    return signals


def run_scalp_cycle(db: Session = None) -> Dict:
    """Main scalp trading cycle - call every 5 minutes."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        result = {
            "timestamp": now_ist().isoformat(),
            "entries": [],
            "exits": [],
            "signals_found": 0,
            "trades_skipped": 0,
            "error": None,
        }
        
        now = now_ist()
        market_start = now.replace(hour=9, minute=20, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=15, second=0, microsecond=0)
        
        if not (market_start <= now <= market_end):
            result["error"] = "Outside market hours"
            return result
        
        if now.weekday() >= 5:
            result["error"] = "Weekend - market closed"
            return result
        
        # Step 1: Check and exit existing positions
        exits = check_and_exit_scalps(db)
        result["exits"] = exits
        
        # Step 2: Check daily limits
        can_trade, limit_reason = check_daily_limits(db)
        if not can_trade:
            result["error"] = limit_reason
            return result
        
        # Step 3: Scan for new signals
        signals = scan_for_scalp_signals(db)
        result["signals_found"] = len(signals)
        
        # Step 4: Execute entries
        for sig_data in signals:
            can_trade, _ = check_daily_limits(db)
            if not can_trade:
                result["trades_skipped"] += 1
                continue
            
            trade = create_scalp_entry(db, sig_data["underlying"], sig_data["signal"])
            if trade:
                result["entries"].append({
                    "trade_id": trade.trade_id,
                    "underlying": trade.underlying,
                    "option_symbol": trade.option_symbol,
                    "entry_price": trade.entry_price,
                })
        
        return result
    
    except Exception as e:
        logger.exception(f"Scalp cycle error: {e}")
        return {"error": str(e)}
    finally:
        if close_db:
            db.close()


# ================================================================
# ANALYSIS FUNCTIONS
# ================================================================

def get_scalp_stats(db: Session, days: int = 30) -> Dict:
    """Get scalp trading statistics for analysis."""
    cutoff_date = date.today() - timedelta(days=days)
    
    trades = db.query(ScalpTrade).filter(
        ScalpTrade.trade_date >= cutoff_date, ScalpTrade.status == "CLOSED"
    ).all()
    
    if not trades:
        return {"error": "No trades found", "total_trades": 0}
    
    total_trades = len(trades)
    winning_trades = [t for t in trades if (t.pnl or 0) > 0]
    losing_trades = [t for t in trades if (t.pnl or 0) <= 0]
    
    total_pnl = sum(t.pnl or 0 for t in trades)
    total_wins = sum(t.pnl or 0 for t in winning_trades)
    total_losses = sum(t.pnl or 0 for t in losing_trades)
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    avg_win = (total_wins / len(winning_trades)) if winning_trades else 0
    avg_loss = (total_losses / len(losing_trades)) if losing_trades else 0
    rr_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
    profit_factor = abs(total_wins / total_losses) if total_losses != 0 else float('inf')
    
    # By exit reason
    by_exit_reason = {}
    for t in trades:
        reason = t.exit_reason or "UNKNOWN"
        if reason not in by_exit_reason:
            by_exit_reason[reason] = {"count": 0, "pnl": 0, "wins": 0}
        by_exit_reason[reason]["count"] += 1
        by_exit_reason[reason]["pnl"] += t.pnl or 0
        if (t.pnl or 0) > 0:
            by_exit_reason[reason]["wins"] += 1
    
    # By underlying
    by_underlying = {}
    for t in trades:
        ul = t.underlying or "UNKNOWN"
        if ul not in by_underlying:
            by_underlying[ul] = {"count": 0, "pnl": 0, "wins": 0}
        by_underlying[ul]["count"] += 1
        by_underlying[ul]["pnl"] += t.pnl or 0
        if (t.pnl or 0) > 0:
            by_underlying[ul]["wins"] += 1
    
    # By signal type
    by_signal = {}
    for t in trades:
        sig = t.signal_type or "UNKNOWN"
        if sig not in by_signal:
            by_signal[sig] = {"count": 0, "pnl": 0, "wins": 0}
        by_signal[sig]["count"] += 1
        by_signal[sig]["pnl"] += t.pnl or 0
        if (t.pnl or 0) > 0:
            by_signal[sig]["wins"] += 1
    
    return {
        "period_days": days,
        "total_trades": total_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "risk_reward_ratio": round(rr_ratio, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "∞",
        "by_exit_reason": by_exit_reason,
        "by_underlying": by_underlying,
        "by_signal_type": by_signal,
    }


def get_recent_trades(db: Session, limit: int = 20) -> List[Dict]:
    """Get recent scalp trades for display."""
    trades = db.query(ScalpTrade).order_by(ScalpTrade.created_at.desc()).limit(limit).all()
    
    return [
        {
            "trade_id": t.trade_id,
            "underlying": t.underlying,
            "signal_type": t.signal_type,
            "option_symbol": t.option_symbol,
            "entry_time": t.entry_time.isoformat() if t.entry_time else None,
            "entry_price": t.entry_price,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "exit_price": t.exit_price,
            "exit_reason": t.exit_reason,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "status": t.status,
        }
        for t in trades
    ]


def export_trades_csv(db: Session, filepath: str = None, days: int = 30) -> str:
    """Export trades to CSV for external analysis."""
    import csv
    
    if filepath is None:
        filepath = f"/app/data/scalp_trades_{date.today().isoformat()}.csv"
    
    cutoff_date = date.today() - timedelta(days=days)
    trades = db.query(ScalpTrade).filter(
        ScalpTrade.trade_date >= cutoff_date
    ).order_by(ScalpTrade.entry_time).all()
    
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "trade_id", "trade_date", "underlying", "signal_type", "confidence",
            "option_symbol", "option_type", "strike", "expiry",
            "entry_time", "entry_price", "spot_at_entry",
            "exit_time", "exit_price", "spot_at_exit", "exit_reason",
            "tp_price", "sl_price", "pnl", "pnl_pct", "status",
            "lots", "lot_size", "signal_reason"
        ])
        
        for t in trades:
            writer.writerow([
                t.trade_id, t.trade_date, t.underlying, t.signal_type, t.signal_confidence,
                t.option_symbol, t.option_type, t.strike, t.expiry,
                t.entry_time, t.entry_price, t.spot_at_entry,
                t.exit_time, t.exit_price, t.spot_at_exit, t.exit_reason,
                t.tp_price, t.sl_price, t.pnl, t.pnl_pct, t.status,
                t.lots, t.lot_size, t.signal_reason
            ])
    
    logger.info(f"📊 Exported {len(trades)} trades to {filepath}")
    return filepath


# ================================================================
# SCHEDULER INTEGRATION
# ================================================================

def _scalp_trading_job():
    """Scheduled job for scalp trading - runs every 5 minutes."""
    logger.info("⏱️ Running scalp trading cycle")
    
    db = SessionLocal()
    try:
        result = run_scalp_cycle(db)
        entries = len(result.get("entries", []))
        exits = len(result.get("exits", []))
        
        if entries > 0 or exits > 0:
            logger.info(f"📊 Scalp cycle: {entries} entries, {exits} exits")
        if result.get("error"):
            logger.debug(f"Scalp cycle note: {result['error']}")
    except Exception as e:
        logger.exception(f"Scalp trading job failed: {e}")
    finally:
        db.close()


def start_scalp_trading_scheduler(scheduler):
    """Start the 5-minute scalp trading scheduler."""
    scheduler.add_job(
        func=_scalp_trading_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*/5",
        id="scalp_trading_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("🟢 Scalp trading scheduler started (every 5 min, 9:20 AM - 3:15 PM IST)")


# ================================================================
# CLI
# ================================================================

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    
    db = SessionLocal()
    
    try:
        if len(sys.argv) > 1:
            cmd = sys.argv[1]
            
            if cmd == "run":
                result = run_scalp_cycle(db)
                print(f"\n📊 Cycle Result:\n{result}")
            
            elif cmd == "stats":
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
                stats = get_scalp_stats(db, days=days)
                print(f"\n📈 Scalp Stats ({days} days):")
                for k, v in stats.items():
                    print(f"  {k}: {v}")
            
            elif cmd == "trades":
                limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
                trades = get_recent_trades(db, limit=limit)
                print(f"\n📋 Recent Trades ({len(trades)}):")
                for t in trades:
                    emoji = "✅" if (t.get("pnl") or 0) > 0 else "❌" if t.get("status") == "CLOSED" else "⏳"
                    print(f"  {emoji} {t['trade_id']} | {t['underlying']} | {t['signal_type']} | P&L: ₹{t.get('pnl', 'N/A')}")
            
            elif cmd == "export":
                days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
                filepath = export_trades_csv(db, days=days)
                print(f"✅ Exported to {filepath}")
            
            elif cmd == "signal":
                signals = scan_for_scalp_signals(db)
                print(f"\n🎯 Current Signals ({len(signals)}):")
                for s in signals:
                    sig = s["signal"]
                    print(f"  {s['underlying']}: {sig.get('signal')} | Conf: {sig.get('confidence')}% | {sig.get('reason')}")
            
            else:
                print("Usage: python scalp_paper_trader.py [run|stats|trades|export|signal]")
        else:
            print("Usage: python scalp_paper_trader.py [run|stats|trades|export|signal]")
    finally:
        db.close()
