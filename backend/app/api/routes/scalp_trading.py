"""
Scalp Trading — Live paper options engine.

Runs a real-time NIFTY/BANKNIFTY options strategy session:
- Scans VIX, PCR, spot every minute
- Decides IRON_CONDOR / BULL_PUT / BEAR_CALL / NO_TRADE
- Executes paper trades with real option symbols
- Streams log lines via SSE
- Tracks session P&L, MaxLoss, MaxProfit
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scalp", tags=["Scalp Trading"])


# ── Session state (singleton per process) ────────────────────────────────────

class _SessionState:
    def __init__(self):
        self.running = False
        self.underlying = "NIFTY"
        self.mode = "PAPER"
        self.stop_loss = 3000.0
        self.target = 2000.0
        self.daily_limit = 5000.0
        self.lots = 1
        self.log_lines: deque[str] = deque(maxlen=500)
        self.position: Optional[Dict[str, Any]] = None
        self.session_pnl = 0.0
        self.trade_count = 0
        self.expiry: Optional[str] = None
        self.lot_size = 65
        self.started_at: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_lines.append(line)
        logger.info("SCALP | %s", msg)

    def reset(self):
        self.position = None
        self.session_pnl = 0.0
        self.trade_count = 0
        self.log_lines.clear()


_state = _SessionState()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_lot_size(underlying: str) -> int:
    return {"NIFTY": 65, "BANKNIFTY": 30, "FINNIFTY": 60}.get(underlying.upper(), 65)


def _get_spot(underlying: str) -> float:
    try:
        from app.services.market_data import get_spot
        return float(get_spot(underlying))
    except Exception:
        return 0.0


def _get_vix() -> float:
    try:
        from app.core.market.provider import fetch_ltp
        prices = fetch_ltp(["NIFTYVIX"])
        return float(prices.get("NIFTYVIX") or 16.0)
    except Exception:
        return 16.0


def _get_pcr(underlying: str) -> float:
    """Get Put-Call Ratio from option chain."""
    try:
        from app.services.market_data import get_option_chain
        chain = get_option_chain(underlying)
        if chain.empty:
            return 1.0
        total_ce = chain["ce_oi"].sum() if "ce_oi" in chain.columns else 0
        total_pe = chain["pe_oi"].sum() if "pe_oi" in chain.columns else 0
        if total_ce > 0:
            return round(total_pe / total_ce, 3)
    except Exception:
        pass
    return 1.0


def _get_expiry(underlying: str) -> str:
    try:
        from app.core.market.expiry import get_next_weekly_expiry_from_kite
        exp = get_next_weekly_expiry_from_kite(underlying)
        return exp.strftime("%d%b%y").upper()
    except Exception:
        return "UNKNOWN"


def _decide(vix: float, pcr: float, spot: float) -> tuple[str, str]:
    """Decide strategy based on VIX, PCR, spot."""
    if vix > 20:
        if 0.7 <= pcr <= 1.3:
            return "IRON_CONDOR", f"HIGH IV + neutral PCR={pcr:.3f} — defined risk condor"
        if pcr > 1.3:
            return "BULL_PUT", f"HIGH IV + bullish PCR={pcr:.3f} — sell put spread"
        return "BEAR_CALL", f"HIGH IV + bearish PCR={pcr:.3f} — sell call spread"
    elif vix > 14:
        if 0.8 <= pcr <= 1.2:
            return "IRON_CONDOR", f"NORMAL IV + neutral PCR={pcr:.3f} — defined risk condor"
        if pcr > 1.2:
            return "BULL_PUT", f"NORMAL IV + bullish PCR={pcr:.3f} — sell put spread"
        return "BEAR_CALL", f"NORMAL IV + bearish PCR={pcr:.3f} — sell call spread"
    else:
        return "NO_TRADE", f"LOW IV ({vix:.2f}) — avoid premium selling"


def _build_condor_strikes(underlying: str, spot: float, vix: float) -> Dict[str, Any]:
    step = 50 if underlying == "NIFTY" else 100
    atm = round(spot / step) * step
    # Wing width: wider in high IV
    wing = step * 2 if vix > 18 else step
    short_call = atm + step
    long_call = short_call + wing
    short_put = atm - step
    long_put = short_put - wing
    return {
        "short_call": short_call, "long_call": long_call,
        "short_put": short_put, "long_put": long_put,
        "atm": atm,
    }


def _build_spread_strikes(underlying: str, spot: float, strategy: str) -> Dict[str, Any]:
    step = 50 if underlying == "NIFTY" else 100
    atm = round(spot / step) * step
    if strategy == "BULL_PUT":
        return {"short": atm - step, "long": atm - step * 2}
    return {"short": atm + step, "long": atm + step * 2}


def _option_symbol(underlying: str, expiry_str: str, strike: int, opt_type: str) -> str:
    try:
        from app.core.broker.option_symbols import build_option_symbol
        from app.core.market.expiry import get_next_weekly_expiry_from_kite
        exp = get_next_weekly_expiry_from_kite(underlying)
        return build_option_symbol(underlying, exp, strike, opt_type)
    except Exception:
        return f"{underlying}{expiry_str}{strike}{opt_type}"


def _estimate_premium(underlying: str, strike: int, opt_type: str, spot: float, vix: float) -> float:
    """Rough Black-Scholes ATM premium estimate."""
    import math
    moneyness = abs(strike - spot) / spot
    tau = 7 / 365  # ~1 week
    sigma = vix / 100
    # Simplified: ATM premium ≈ spot * sigma * sqrt(tau) * 0.4
    atm_prem = spot * sigma * math.sqrt(tau) * 0.4
    # OTM decay
    otm_factor = max(0.1, 1 - moneyness * 8)
    return round(atm_prem * otm_factor, 2)


def _execute_paper_condor(underlying: str, expiry: str, strikes: Dict, spot: float, vix: float, lot_size: int, lots: int) -> Dict[str, Any]:
    sc, lc = strikes["short_call"], strikes["long_call"]
    sp, lp = strikes["short_put"], strikes["long_put"]
    qty = lot_size * lots

    sc_prem = _estimate_premium(underlying, sc, "CE", spot, vix)
    lc_prem = _estimate_premium(underlying, lc, "CE", spot, vix)
    sp_prem = _estimate_premium(underlying, sp, "PE", spot, vix)
    lp_prem = _estimate_premium(underlying, lp, "PE", spot, vix)

    net_credit = round((sc_prem - lc_prem + sp_prem - lp_prem) * qty, 2)
    call_width = (lc - sc) * qty
    put_width = (sp - lp) * qty
    max_loss = round(min(call_width, put_width) - net_credit, 2)
    max_profit = net_credit
    rr = round(max_profit / max_loss, 2) if max_loss > 0 else 0

    legs = [
        {"side": "SELL", "symbol": _option_symbol(underlying, expiry, sc, "CE"), "strike": sc, "type": "CE", "qty": qty, "price": sc_prem},
        {"side": "BUY",  "symbol": _option_symbol(underlying, expiry, lc, "CE"), "strike": lc, "type": "CE", "qty": qty, "price": lc_prem},
        {"side": "SELL", "symbol": _option_symbol(underlying, expiry, sp, "PE"), "strike": sp, "type": "PE", "qty": qty, "price": sp_prem},
        {"side": "BUY",  "symbol": _option_symbol(underlying, expiry, lp, "PE"), "strike": lp, "type": "PE", "qty": qty, "price": lp_prem},
    ]
    return {
        "strategy": "IRON_CONDOR",
        "legs": legs,
        "net_credit": net_credit,
        "max_loss": max_loss,
        "max_profit": max_profit,
        "rr": rr,
        "entry_spot": spot,
        "entry_time": datetime.now().isoformat(),
    }


def _execute_paper_spread(underlying: str, expiry: str, strikes: Dict, strategy: str, spot: float, vix: float, lot_size: int, lots: int) -> Dict[str, Any]:
    short_s, long_s = strikes["short"], strikes["long"]
    opt_type = "PE" if strategy == "BULL_PUT" else "CE"
    qty = lot_size * lots

    short_prem = _estimate_premium(underlying, short_s, opt_type, spot, vix)
    long_prem = _estimate_premium(underlying, long_s, opt_type, spot, vix)
    net_credit = round((short_prem - long_prem) * qty, 2)
    width = abs(short_s - long_s) * qty
    max_loss = round(width - net_credit, 2)
    max_profit = net_credit
    rr = round(max_profit / max_loss, 2) if max_loss > 0 else 0

    legs = [
        {"side": "SELL", "symbol": _option_symbol(underlying, expiry, short_s, opt_type), "strike": short_s, "type": opt_type, "qty": qty, "price": short_prem},
        {"side": "BUY",  "symbol": _option_symbol(underlying, expiry, long_s, opt_type),  "strike": long_s,  "type": opt_type, "qty": qty, "price": long_prem},
    ]
    return {
        "strategy": strategy,
        "legs": legs,
        "net_credit": net_credit,
        "max_loss": max_loss,
        "max_profit": max_profit,
        "rr": rr,
        "entry_spot": spot,
        "entry_time": datetime.now().isoformat(),
    }


def _mtm_position(pos: Dict, spot: float, vix: float) -> float:
    """Estimate current P&L of open position."""
    pnl = 0.0
    for leg in pos.get("legs", []):
        current_prem = _estimate_premium(pos.get("underlying", "NIFTY"), leg["strike"], leg["type"], spot, vix)
        if leg["side"] == "SELL":
            pnl += (leg["price"] - current_prem) * leg["qty"]
        else:
            pnl += (current_prem - leg["price"]) * leg["qty"]
    return round(pnl, 2)


# ── Main scan loop ────────────────────────────────────────────────────────────

def _scan_loop():
    s = _state
    s.log(f"=== {s.underlying} Options Engine started [{s.mode}] ===")
    s.log(f"    Stop=Rs.{s.stop_loss:.0f}  Target=Rs.{s.target:.0f}  DailyLimit=Rs.{s.daily_limit:.0f}")
    s.log("--- New session: state reset ---")

    s.lot_size = _get_lot_size(s.underlying)
    s.expiry = _get_expiry(s.underlying)
    s.log(f"Expiry={s.expiry}  LotSize={s.lot_size}  Qty={s.lot_size * s.lots}")

    while not s._stop_event.is_set():
        try:
            _scan_once()
        except Exception as exc:
            s.log(f"ERROR in scan: {exc}")
        # Wait ~60s but check stop every second
        for _ in range(60):
            if s._stop_event.is_set():
                break
            time.sleep(1)

    s.log("=== Session stopped ===")
    s.running = False


def _scan_once():
    s = _state
    spot = _get_spot(s.underlying)
    vix = _get_vix()
    pcr = _get_pcr(s.underlying)

    s.log(f"PCR(full)={pcr:.3f}")
    s.log(f"Snapshot | VIX={vix:.2f}  PCR={pcr:.3f}  Premium=Rs.{spot * (vix / 100) * 0.4:.2f}  Spot={spot}")

    # MTM open position
    if s.position:
        pnl = _mtm_position(s.position, spot, vix)
        s.position["current_pnl"] = pnl
        s.log(f"MTM | {s.position['strategy']} | PnL=Rs.{pnl:.2f}")

        # Exit checks
        if pnl >= s.target:
            s.log(f"TARGET HIT | PnL=Rs.{pnl:.2f} >= Target=Rs.{s.target:.0f} — EXITING")
            _close_position(pnl, "TARGET_HIT")
            return
        if pnl <= -s.stop_loss:
            s.log(f"STOP LOSS HIT | PnL=Rs.{pnl:.2f} <= -Stop=Rs.{s.stop_loss:.0f} — EXITING")
            _close_position(pnl, "STOP_LOSS")
            return
        if s.session_pnl + pnl <= -s.daily_limit:
            s.log(f"DAILY LIMIT HIT | SessionPnL=Rs.{s.session_pnl + pnl:.2f} — EXITING")
            _close_position(pnl, "DAILY_LIMIT")
            s._stop_event.set()
            return
        return  # hold position

    # No position — decide entry
    strategy, reason = _decide(vix, pcr, spot)
    iv_regime = "HIGH" if vix > 20 else "NORMAL" if vix > 14 else "LOW"
    market_mode = "RANGE" if 0.8 <= pcr <= 1.2 else "TRENDING"
    s.log(f"Decision | {strategy} [{iv_regime}/{market_mode}] — {reason}")

    if strategy == "NO_TRADE":
        return

    # Build and execute
    if strategy == "IRON_CONDOR":
        strikes = _build_condor_strikes(s.underlying, spot, vix)
        pos = _execute_paper_condor(s.underlying, s.expiry, strikes, spot, vix, s.lot_size, s.lots)
        sc, lc = strikes["short_call"], strikes["long_call"]
        sp, lp = strikes["short_put"], strikes["long_put"]
        s.log(f"Trade | IRON_CONDOR | MaxLoss=Rs.{pos['max_loss']:.1f}  MaxProfit=Rs.{pos['max_profit']:.1f}  RR={pos['rr']:.2f}")
        s.log(f"[{s.mode}] Executing IRON_CONDOR | CE {sc}/{lc} PE {sp}/{lp} Credit~Rs.{pos['net_credit'] / (s.lot_size * s.lots):.1f} Qty={s.lot_size * s.lots}")
        for leg in pos["legs"]:
            s.log(f"  {leg['side']} {leg['symbol']} qty={leg['qty']} [{leg['type']} strike={leg['strike']}]")
    else:
        strikes = _build_spread_strikes(s.underlying, spot, strategy)
        pos = _execute_paper_spread(s.underlying, s.expiry, strikes, strategy, spot, vix, s.lot_size, s.lots)
        s.log(f"Trade | {strategy} | MaxLoss=Rs.{pos['max_loss']:.1f}  MaxProfit=Rs.{pos['max_profit']:.1f}  RR={pos['rr']:.2f}")
        s.log(f"[{s.mode}] Executing {strategy} | Strikes {strikes['short']}/{strikes['long']} Credit~Rs.{pos['net_credit'] / (s.lot_size * s.lots):.1f} Qty={s.lot_size * s.lots}")
        for leg in pos["legs"]:
            s.log(f"  {leg['side']} {leg['symbol']} qty={leg['qty']} [{leg['type']} strike={leg['strike']}]")

    net_per_unit = pos["net_credit"] / (s.lot_size * s.lots)
    s.log(f"ENTERED {strategy} | NetPremium=Rs.{net_per_unit}")
    pos["underlying"] = s.underlying
    pos["current_pnl"] = 0.0
    s.position = pos
    s.trade_count += 1


def _close_position(pnl: float, reason: str):
    s = _state
    s.session_pnl += pnl
    s.log(f"CLOSED {s.position['strategy']} | PnL=Rs.{pnl:.2f} | Reason={reason} | SessionPnL=Rs.{s.session_pnl:.2f}")
    s.position = None


# ── API models ────────────────────────────────────────────────────────────────

class StartRequest(BaseModel):
    underlying: str = "NIFTY"
    mode: str = "PAPER"
    stop_loss: float = 3000.0
    target: float = 2000.0
    daily_limit: float = 5000.0
    lots: int = 1


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/start")
def start_session(req: StartRequest):
    if _state.running:
        raise HTTPException(status_code=400, detail="Session already running")

    _state.reset()
    _state.underlying = req.underlying.upper()
    _state.mode = req.mode.upper()
    _state.stop_loss = req.stop_loss
    _state.target = req.target
    _state.daily_limit = req.daily_limit
    _state.lots = req.lots
    _state.running = True
    _state.started_at = datetime.now().isoformat()
    _state._stop_event.clear()

    t = threading.Thread(target=_scan_loop, name="scalp-engine", daemon=True)
    _state._thread = t
    t.start()

    return {"status": "started", "underlying": _state.underlying, "mode": _state.mode}


@router.post("/stop")
def stop_session():
    if not _state.running:
        raise HTTPException(status_code=400, detail="No session running")
    _state._stop_event.set()
    return {"status": "stopping"}


@router.get("/status")
def get_status():
    pos = _state.position
    return {
        "running": _state.running,
        "underlying": _state.underlying,
        "mode": _state.mode,
        "session_pnl": _state.session_pnl,
        "trade_count": _state.trade_count,
        "started_at": _state.started_at,
        "position": {
            "strategy": pos["strategy"],
            "current_pnl": pos.get("current_pnl", 0),
            "max_profit": pos["max_profit"],
            "max_loss": pos["max_loss"],
            "net_credit": pos["net_credit"],
            "entry_time": pos["entry_time"],
            "legs": pos["legs"],
        } if pos else None,
    }


@router.get("/logs")
def get_logs(limit: int = 100):
    lines = list(_state.log_lines)[-limit:]
    return {"lines": lines, "total": len(_state.log_lines)}


@router.get("/stream")
async def stream_logs():
    """SSE stream of log lines for real-time terminal display."""
    async def event_generator():
        sent = 0
        while True:
            lines = list(_state.log_lines)
            if len(lines) > sent:
                for line in lines[sent:]:
                    yield f"data: {json.dumps({'line': line})}\n\n"
                sent = len(lines)
            if not _state.running and sent >= len(list(_state.log_lines)):
                yield f"data: {json.dumps({'line': '[STREAM] Session ended', 'done': True})}\n\n"
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
