from app.db.session import SessionLocal
from app.db.repository import save_strategy_run
from app.db.models import StrategyRun
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.core.market.expiry import get_current_weekly_expiry
from sqlalchemy.orm import Session

from app.core.signals.signals import generate_signal

"""
engine.py
---------
Master orchestration engine for 15m Option Spread strategy.
This replaces the Streamlit implementation entirely.
"""

from typing import Dict, Any, Optional
import os

# Services
from app.services.market_data import (
    get_spot,
    pick_atm_strike,
    get_option_chain,
)

# Strategy modules
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy
from app.core.strategies.option_spread_15m.strikes import compute_spread_strikes
from app.core.strategies.option_spread_15m.risk import (
    check_spread_risk,
    check_condor_risk,
    check_straddle_strangle_risk,
    check_butterfly_risk,
    check_ratio_backspread_risk,
)
from app.core.risk.risk_limits_config import get_risk_limits

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

def run_option_spread(db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
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
    sig = generate_signal(
        db=db,
        symbol=payload["underlying"],
        use_ml=payload.get("use_ml", False),
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

    # =====================================================
    # BACKTEST MODE: signal-only (no live Zerodha calls)
    # =====================================================
    backtest_mode = bool(payload.get("backtest")) or (os.getenv("BACKTEST_MODE") == "1")
    if backtest_mode:
        spot = float(payload.get("spot") or 0.0)
        result = {
            "strategy": strategy_mode,
            "approved": strategy_mode != "NO_TRADE",
            "reason": f"BACKTEST_MODE: {strategy_reason}",
            "signal": sig,
            "context": ctx,
            "spot": spot,
        }
        run = _log_strategy_run(result, payload.get("underlying") or "")
        if run:
            result["run_id"] = run.id
        return result

    # =====================================================
    # 4️⃣ MARKET DATA (FETCH FOR ALL CASES - for analysis)
    # =====================================================
    underlying = payload["underlying"]
    spot = get_spot(underlying)
    atm = pick_atm_strike(underlying, spot)

    # =====================================================
    # 5️⃣ STRIKE SELECTION (CALCULATE FOR ALL CASES)
    # =====================================================
    strikes = compute_spread_strikes(
        underlying=underlying,
        spot=spot,
        atm=atm,
        risk_mode=payload.get("risk_mode", "Conservative"),
        iv_regime=str(ctx.get("iv_regime") or "LOW"),
        recommendation=str(sig.get("recommendation") or "NO_TRADE"),
    )

    if strategy_mode == "NO_TRADE":
        result = {
            "strategy": "NO_TRADE",
            "approved": False,
            "reason": strategy_reason,
            "signal": sig,
            "context": ctx,
            "spot": spot,
            "atm": atm,
            "strike_meta": strikes.get("meta"),
        }

        run = _log_strategy_run(result, payload["underlying"])
        if run:
            result["run_id"] = run.id
        return result

    # Needed later for lot size
    chain = get_option_chain(underlying)
    
    # Enrich with live LTP
    from app.services.market_data import enrich_chain_with_live_oi
    chain = enrich_chain_with_live_oi(chain)
    
    # Get lot_size from chain, with fallback based on underlying
    if not chain.empty:
        lot_size = int(chain.iloc[0]["lot_size"])
    else:
        # Fallback to standard lot sizes
        lot_size_map = {
            "NIFTY": 50,
            "BANKNIFTY": 20,
            "FINNIFTY": 40,
        }
        lot_size = lot_size_map.get(underlying, 50)
        import logging
        logging.getLogger(__name__).warning(
            f"⚠️  Option chain empty for {underlying}, using fallback lot size: {lot_size}"
        )


    # ============================
    # EXTRACT STRIKES BY STRATEGY TYPE
    # ============================
    if strategy_mode == "BULL_PUT":
        short_strike, long_strike = strikes["bull"]
        opt_type = "PE"
    elif strategy_mode == "BEAR_CALL":
        short_strike, long_strike = strikes["bear"]
        opt_type = "CE"
    elif strategy_mode == "IRON_CONDOR":
        short_put, long_put, short_call, long_call = strikes["condor"]
    elif strategy_mode == "SHORT_STRADDLE":
        straddle_call, straddle_put = strikes["straddle"]
    elif strategy_mode == "LONG_STRADDLE":
        straddle_call, straddle_put = strikes["straddle"]
    elif strategy_mode == "SHORT_STRANGLE":
        strangle_call, strangle_put = strikes["strangle"]
    elif strategy_mode == "LONG_STRANGLE":
        strangle_call, strangle_put = strikes["strangle"]
    elif strategy_mode == "BUTTERFLY_SPREAD":
        butterfly_lower, butterfly_middle, butterfly_upper = strikes["butterfly_call"]
    elif strategy_mode == "CALL_RATIO_BACKSPREAD":
        ratio_short, ratio_long_near, ratio_long_far = strikes["call_ratio_backspread"]
    elif strategy_mode == "PUT_RATIO_BACKSPREAD":
        ratio_short, ratio_long_near, ratio_long_far = strikes["put_ratio_backspread"]
    else:
        return {
            "strategy": strategy_mode,
            "approved": False,
            "reason": "Strategy not supported",
            "signal": sig,
            "context": ctx,
        }

    # =====================================================
    # 6️⃣ RISK CHECK (FINAL GATE)
    # =====================================================
    # Load DB-backed risk limits (env/profile fallback if DB unavailable)
    risk_config = get_risk_limits()
    
    capital = float(payload.get("capital", 0))
    lots = int(payload.get("lots", 1))
    iv_regime_str = str(ctx.get("iv_regime") or "LOW")

    # Route to appropriate risk check function
    if strategy_mode in ["BULL_PUT", "BEAR_CALL"]:
        ok, risk_reason, risk_metrics = check_spread_risk(
            short_strike=short_strike,
            long_strike=long_strike,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            risk_config=risk_config,
        )
    elif strategy_mode == "IRON_CONDOR":
        ok, risk_reason, risk_metrics = check_condor_risk(
            short_put=short_put,
            long_put=long_put,
            short_call=short_call,
            long_call=long_call,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            risk_config=risk_config,
        )
    elif strategy_mode in ["SHORT_STRADDLE", "LONG_STRADDLE"]:
        ok, risk_reason, risk_metrics = check_straddle_strangle_risk(
            call_strike=straddle_call,
            put_strike=straddle_put,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            is_short=(strategy_mode == "SHORT_STRADDLE"),
            risk_config=risk_config,
        )
    elif strategy_mode in ["SHORT_STRANGLE", "LONG_STRANGLE"]:
        ok, risk_reason, risk_metrics = check_straddle_strangle_risk(
            call_strike=strangle_call,
            put_strike=strangle_put,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            is_short=(strategy_mode == "SHORT_STRANGLE"),
            risk_config=risk_config,
        )
    elif strategy_mode == "BUTTERFLY_SPREAD":
        ok, risk_reason, risk_metrics = check_butterfly_risk(
            lower_strike=butterfly_lower,
            middle_strike=butterfly_middle,
            upper_strike=butterfly_upper,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            risk_config=risk_config,
        )
    elif strategy_mode == "CALL_RATIO_BACKSPREAD":
        ok, risk_reason, risk_metrics = check_ratio_backspread_risk(
            short_strike=ratio_short,
            long_strike_near=ratio_long_near,
            long_strike_far=ratio_long_far,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            is_call=True,
            risk_config=risk_config,
        )
    elif strategy_mode == "PUT_RATIO_BACKSPREAD":
        ok, risk_reason, risk_metrics = check_ratio_backspread_risk(
            short_strike=ratio_short,
            long_strike_near=ratio_long_near,
            long_strike_far=ratio_long_far,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=iv_regime_str,
            is_call=False,
            risk_config=risk_config,
        )
    else:
        # Unknown strategy
        ok = False
        risk_reason = f"No risk check defined for {strategy_mode}"
        risk_metrics = {}


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
    # 7️⃣ BUILD TICKET (PAPER)
    # =====================================================
    expiry = get_current_weekly_expiry(underlying)
    lots = int(payload.get("lots", 1))

    # ============================
    # CREDIT/DEBIT SPREADS
    # ============================
    if strategy_mode in ["BULL_PUT", "BEAR_CALL"]:
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": short_strike,
                    "type": opt_type,
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=short_strike,
                        option_type=opt_type,
                    ),
                },
                {
                    "side": "BUY",
                    "strike": long_strike,
                    "type": opt_type,
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=long_strike,
                        option_type=opt_type,
                    ),
                },
            ],
        }
    
    # ============================
    # IRON CONDOR
    # ============================
    elif strategy_mode == "IRON_CONDOR":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": short_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=short_put,
                        option_type="PE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": long_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=long_put,
                        option_type="PE",
                    ),
                },
                {
                    "side": "SELL",
                    "strike": short_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=short_call,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": long_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=long_call,
                        option_type="CE",
                    ),
                },
            ],
        }
    
    # ============================
    # SHORT STRADDLE
    # ============================
    elif strategy_mode == "SHORT_STRADDLE":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": straddle_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=straddle_call,
                        option_type="CE",
                    ),
                },
                {
                    "side": "SELL",
                    "strike": straddle_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=straddle_put,
                        option_type="PE",
                    ),
                },
            ],
        }
    
    # ============================
    # LONG STRADDLE
    # ============================
    elif strategy_mode == "LONG_STRADDLE":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "BUY",
                    "strike": straddle_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=straddle_call,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": straddle_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=straddle_put,
                        option_type="PE",
                    ),
                },
            ],
        }
    
    # ============================
    # SHORT STRANGLE
    # ============================
    elif strategy_mode == "SHORT_STRANGLE":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": strangle_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=strangle_call,
                        option_type="CE",
                    ),
                },
                {
                    "side": "SELL",
                    "strike": strangle_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=strangle_put,
                        option_type="PE",
                    ),
                },
            ],
        }
    
    # ============================
    # LONG STRANGLE
    # ============================
    elif strategy_mode == "LONG_STRANGLE":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "BUY",
                    "strike": strangle_call,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=strangle_call,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": strangle_put,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=strangle_put,
                        option_type="PE",
                    ),
                },
            ],
        }
    
    # ============================
    # BUTTERFLY SPREAD (CALL)
    # ============================
    elif strategy_mode == "BUTTERFLY_SPREAD":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "BUY",
                    "strike": butterfly_lower,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=butterfly_lower,
                        option_type="CE",
                    ),
                },
                {
                    "side": "SELL",
                    "strike": butterfly_middle,
                    "type": "CE",
                    "quantity": lots * lot_size * 2,  # 2x middle
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=butterfly_middle,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": butterfly_upper,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=butterfly_upper,
                        option_type="CE",
                    ),
                },
            ],
        }
    
    # ============================
    # CALL RATIO BACKSPREAD
    # ============================
    elif strategy_mode == "CALL_RATIO_BACKSPREAD":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": ratio_short,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_short,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": ratio_long_near,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_long_near,
                        option_type="CE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": ratio_long_far,
                    "type": "CE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_long_far,
                        option_type="CE",
                    ),
                },
            ],
        }
    
    # ============================
    # PUT RATIO BACKSPREAD
    # ============================
    elif strategy_mode == "PUT_RATIO_BACKSPREAD":
        ticket = {
            "strategy": strategy_mode,
            "underlying": underlying,
            "lot_size": lot_size,
            "lots": lots,
            "legs": [
                {
                    "side": "SELL",
                    "strike": ratio_short,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_short,
                        option_type="PE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": ratio_long_near,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_long_near,
                        option_type="PE",
                    ),
                },
                {
                    "side": "BUY",
                    "strike": ratio_long_far,
                    "type": "PE",
                    "symbol": build_zerodha_option_symbol(
                        underlying=underlying,
                        expiry=expiry,
                        strike=ratio_long_far,
                        option_type="PE",
                    ),
                },
            ],
        }
    
    else:
        return {
            "strategy": strategy_mode,
            "approved": False,
            "reason": "Ticket builder not implemented for this strategy",
            "signal": sig,
            "context": ctx,
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


# =====================================================
# STRATEGY CLASS (for registry)
# =====================================================

class OptionSpread15m:
    """Option Spread 15m Strategy - multi-strategy compatible"""
    
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute strategy.
        
        Args:
            context: {
                underlying: str,
                parameters: Dict,
                config_id: int (optional)
            }
        
        Returns:
            Strategy execution result
        """
        db = SessionLocal()
        try:
            candle = context.get("candle") or {}
            spot = candle.get("close") if isinstance(candle, dict) else None

            underlying = context.get("backtest_symbol") or context.get("underlying")

            payload = {
                "underlying": underlying,
                "interval": "15minute",
                "use_ml": context.get("parameters", {}).get("use_ml", False),
                "min_confidence": context.get("parameters", {}).get("min_confidence", 75),
                "risk_mode": context.get("parameters", {}).get("risk_mode", "Conservative"),
                "lots": context.get("parameters", {}).get("lots", 1),
                "capital": context.get("parameters", {}).get("capital", 100000),
                "backtest": True if spot is not None else False,
                "spot": float(spot) if spot is not None else None,
            }
            
            return run_option_spread(db, payload)
        
        finally:
            db.close()

