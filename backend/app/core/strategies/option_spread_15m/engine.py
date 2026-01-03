from app.db.session import SessionLocal
from app.db.repository import save_strategy_run
from app.db.models import StrategyRun


"""
engine.py
---------
Master orchestration engine for 15m Option Spread strategy.
This replaces the Streamlit implementation entirely.
"""

from typing import Dict, Any, Optional

# Services
from app.services.signals import recommend_smart_option
from app.services.market_data import (
    get_spot,
    pick_atm_strike,
    get_option_chain,
)

# Strategy modules
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy
from app.core.strategies.option_spread_15m.strikes import compute_spread_strikes
from app.core.strategies.option_spread_15m.risk import check_spread_risk

def _log_strategy_run(result: dict, underlying: str) -> Optional[StrategyRun]:
    """
    Persist strategy run to DB.
    Never raises (DB failure must not block engine).
    Returns StrategyRun if saved, else None.
    """
    db = SessionLocal()
    try:
        run = save_strategy_run(
            db=db,
            strategy=str(result.get("strategy") or "NO_TRADE"),
            underlying=str(underlying),
            approved=bool(result.get("approved")),
            reason=str(result.get("reason") or ""),
            risk_metrics=result.get("risk_metrics") or {},
            ticket=result.get("ticket"),
            signal=result.get("signal") or {},
            context=result.get("context") or {},
        )
        return run

    except Exception as e:
        print("⚠️ DB log failed:", e)
        return None

    finally:
        db.close()

def run_option_spread(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    MAIN ENTRY POINT for 15m option spread strategy.

    This function is what:
    - API
    - Mobile app
    - Scheduler
    will call.

    payload must contain:
        underlying
        interval
        use_ml
        min_confidence
        risk_mode
        lots
        capital
    """

    # =====================================================
    # 1️⃣ SIGNAL GENERATION (ML + TA)
    # =====================================================
    sig = recommend_smart_option(
        underlying=payload["underlying"],
        interval=payload.get("interval", "15minute"),
        use_ml=payload.get("use_ml", True),
        min_confidence=payload.get("min_confidence", 75),
    )

    confidence = float(sig.get("confidence", 0.0))

    # =====================================================
    # 2️⃣ MARKET CONTEXT
    # =====================================================
    ctx = build_market_context(sig)

    # =====================================================
    # 3️⃣ STRATEGY DECISION
    # =====================================================
    strategy_mode, strategy_reason = decide_strategy(
        sig=sig,
        ctx=ctx,
        confidence=confidence,
        min_confidence=payload.get("min_confidence", 75),
    )

    if strategy_mode == "NO_TRADE":
        result = {
            "strategy": "NO_TRADE",
            "approved": False,
            "reason": strategy_reason,
            "signal": sig,
            "context": ctx,
        }

        run = _log_strategy_run(result, payload["underlying"])
        if run:
            result["run_id"] = run.id
        return result


    # =====================================================
    # 4️⃣ MARKET DATA
    # =====================================================
    underlying = payload["underlying"]
    spot = get_spot(underlying)
    atm = pick_atm_strike(underlying, spot)

    # Needed later for lot size
    chain = get_option_chain(underlying)
    lot_size = int(chain.iloc[0]["lot_size"]) if not chain.empty else 0

    if lot_size <= 0:
        result = {
            "strategy": strategy_mode,
            "approved": False,
            "reason": "Lot size unavailable from option chain",
            "signal": sig,
            "context": ctx,
        }

        run = _log_strategy_run(result, payload["underlying"])
        if run:
            result["run_id"] = run.id
        return result

    # =====================================================
    # 5️⃣ STRIKE SELECTION
    # =====================================================
    strikes = compute_spread_strikes(
        underlying=underlying,
        spot=spot,
        atm=atm,
        risk_mode=payload.get("risk_mode", "Conservative"),
        iv_regime=str(ctx.get("iv_regime") or "LOW"),
        recommendation=str(sig.get("recommendation") or "NO_TRADE"),
    )


    if strategy_mode == "BULL_PUT":
        short_strike, long_strike = strikes["bull"]
        opt_type = "PE"
    elif strategy_mode == "BEAR_CALL":
        short_strike, long_strike = strikes["bear"]
        opt_type = "CE"
    else:
        return {
            "strategy": strategy_mode,
            "approved": False,
            "reason": "Strategy not supported yet",
            "signal": sig,
            "context": ctx,
        }

    # =====================================================
    # 6️⃣ RISK CHECK (FINAL GATE)
    # =====================================================
    ok, risk_reason, risk_metrics = check_spread_risk(
        short_strike=short_strike,
        long_strike=long_strike,
        spot=spot,
        capital=float(payload.get("capital", 0)),
        lot_size=lot_size,
        lots=int(payload.get("lots", 1)),
        iv_regime=str(ctx.get("iv_regime") or "LOW"),
    )


    if not ok:
        result = {
            "strategy": strategy_mode,
            "approved": False,
            "reason": risk_reason,
            "risk_metrics": risk_metrics,
            "signal": sig,
            "context": ctx,
        }

        run = _log_strategy_run(result, payload["underlying"])
        if run:
            result["run_id"] = run.id
        return result




    # =====================================================
    # 7️⃣ BUILD SPREAD TICKET (PAPER)
    # =====================================================
    ticket = {
        "strategy": strategy_mode,
        "underlying": underlying,
        "lot_size": lot_size,
        "lots": int(payload.get("lots", 1)),
        "legs": [
            {
                "side": "SELL",
                "strike": short_strike,
                "type": opt_type,
            },
            {
                "side": "BUY",
                "strike": long_strike,
                "type": opt_type,
            },
        ],
    }

    # =====================================================
    # 8️⃣ FINAL RESPONSE
    # =====================================================
    result = {
        "strategy": strategy_mode,
        "approved": True,
        "reason": strategy_reason,
        "ticket": ticket,
        "risk_metrics": risk_metrics,
        "signal": sig,
        "context": ctx,
        "spot": spot,
        "atm": atm,
        "strike_meta": strikes["meta"],
    }

    run = _log_strategy_run(result, payload["underlying"])
    if run:
        result["run_id"] = run.id
    return result
