from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.db.session import SessionLocal
from app.db.repository import save_strategy_run

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Leg:
    side: str  # BUY/SELL
    option_type: str  # CE/PE
    strike: int  # Absolute strike (used when strike_type="ABSOLUTE")
    quantity: int
    strike_type: str = "ABSOLUTE"  # "ABSOLUTE" or "RELATIVE"
    strike_offset: int = 0  # Offset from ATM (used when strike_type="RELATIVE")


def _infer_strategy_name(legs: List[_Leg]) -> str:
    if len(legs) == 4:
        # Heuristic: two CE, two PE -> iron condor
        ce = [l for l in legs if l.option_type == "CE"]
        pe = [l for l in legs if l.option_type == "PE"]
        if len(ce) == 2 and len(pe) == 2:
            return "IRON_CONDOR"
        return "CUSTOM_4LEG"

    if len(legs) == 2:
        opt = legs[0].option_type
        if all(l.option_type == opt for l in legs):
            # Identify spread direction by option type and strikes
            sell = next((l for l in legs if l.side == "SELL"), None)
            buy = next((l for l in legs if l.side == "BUY"), None)
            if sell and buy:
                if opt == "CE" and sell.strike < buy.strike:
                    return "BEAR_CALL"
                if opt == "PE" and sell.strike > buy.strike:
                    return "BULL_PUT"
            return "CUSTOM_SPREAD"

    return "CUSTOM"


def _extract_legs(parameters: Dict[str, Any]) -> List[_Leg]:
    raw = parameters.get("legs") or []
    legs: List[_Leg] = []
    for item in raw:
        try:
            side = str(item.get("type") or item.get("side") or "").upper()
            option_type = str(item.get("option_type") or item.get("type") or "").upper()
            strike_type = str(item.get("strike_type", "ABSOLUTE")).upper()
            quantity = int(item.get("quantity") or 0)
            
            # Handle strike based on strike_type
            if strike_type == "RELATIVE":
                strike = 0  # Will be calculated later from ATM
                strike_offset = int(item.get("strike_offset", 0))
            else:
                strike = int(item.get("strike", 0))
                strike_offset = 0
                
        except Exception:
            continue

        if side not in {"BUY", "SELL"}:
            continue
        if option_type not in {"CE", "PE"}:
            continue
        if quantity <= 0:
            quantity = 1
        if strike_type not in {"ABSOLUTE", "RELATIVE"}:
            strike_type = "ABSOLUTE"

        legs.append(_Leg(
            side=side, 
            option_type=option_type, 
            strike=strike, 
            quantity=quantity,
            strike_type=strike_type,
            strike_offset=strike_offset
        ))

    return legs


def _resolve_strikes(legs: List[_Leg], underlying: str, spot: float) -> List[_Leg]:
    """Convert relative strikes to absolute strikes based on ATM.
    
    Returns new list of legs with absolute strikes calculated.
    """
    from app.services.market_data import pick_atm_strike
    
    atm = pick_atm_strike(underlying, spot)
    resolved_legs: List[_Leg] = []
    
    for leg in legs:
        if leg.strike_type == "RELATIVE":
            # Calculate absolute strike from ATM + offset
            absolute_strike = atm + leg.strike_offset
            resolved_legs.append(_Leg(
                side=leg.side,
                option_type=leg.option_type,
                strike=absolute_strike,
                quantity=leg.quantity,
                strike_type="ABSOLUTE",
                strike_offset=leg.strike_offset
            ))
        else:
            # Already absolute
            resolved_legs.append(leg)
    
    return resolved_legs


def _derive_lots_and_lot_size(legs: List[_Leg]) -> tuple[int, int]:
    """Derive lots/lot_size from saved per-leg quantities.

    Execution adapters generally compute qty = lots * lot_size.

    Strategy Builder currently saves actual contract quantity per leg.
    We infer a common quantity and represent it as (lots, lot_size).
    """
    if not legs:
        return 1, 1

    quantities = [max(1, int(l.quantity)) for l in legs]
    common_qty = min(quantities)

    # Prefer a clean factorization if all legs have the same quantity.
    if all(q == common_qty for q in quantities):
        # Common cases for NIFTY: 65, 130, 195...
        if common_qty % 65 == 0:
            return common_qty // 65, 65
        # Fallback: treat the whole quantity as lot_size
        return 1, common_qty

    # Mixed quantities: choose minimum as unit and represent as 1 lot.
    return 1, common_qty


class OptionSpreadCustom:
    """Execute a user-defined option spread/condor built in Strategy Builder.

    Expects StrategyConfig.parameters to contain:
      - expiry: 'YYYY-MM-DD'
      - legs: [{type: BUY/SELL, option_type: CE/PE, strike: int, quantity: int}, ...]

    Produces a ticket compatible with existing execution adapters.
    """

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        underlying = str(context.get("underlying") or "NIFTY")
        parameters: Dict[str, Any] = dict(context.get("parameters") or {})

        expiry_str = parameters.get("expiry")
        if not expiry_str:
            return {
                "approved": False,
                "strategy": "CUSTOM",
                "reason": "Missing expiry in strategy parameters",
                "ticket": None,
                "risk_metrics": {},
                "signal": {},
                "context": {"underlying": underlying},
            }

        try:
            expiry_dt = date.fromisoformat(str(expiry_str))
        except Exception:
            return {
                "approved": False,
                "strategy": "CUSTOM",
                "reason": f"Invalid expiry format: {expiry_str}",
                "ticket": None,
                "risk_metrics": {},
                "signal": {},
                "context": {"underlying": underlying, "expiry": expiry_str},
            }

        legs = _extract_legs(parameters)
        if not legs:
            return {
                "approved": False,
                "strategy": "CUSTOM",
                "reason": "No legs found in strategy parameters",
                "ticket": None,
                "risk_metrics": {},
                "signal": {},
                "context": {"underlying": underlying, "expiry": expiry_str},
            }

        # Resolve relative strikes to absolute strikes
        from app.services.market_data import get_spot
        has_relative = any(leg.strike_type == "RELATIVE" for leg in legs)
        
        if has_relative:
            spot = get_spot(underlying)
            legs = _resolve_strikes(legs, underlying, spot)
            logger.info(f"✅ Resolved relative strikes for {underlying} @ spot={spot}")

        lots, lot_size = _derive_lots_and_lot_size(legs)
        strategy_name = _infer_strategy_name(legs)

        ticket_legs: List[Dict[str, Any]] = []
        for leg in legs:
            symbol = build_zerodha_option_symbol(
                underlying=underlying,
                expiry=expiry_dt,
                strike=leg.strike,
                option_type=leg.option_type,
            )
            ticket_legs.append(
                {
                    "side": leg.side,
                    "strike": leg.strike,
                    "type": leg.option_type,
                    "qty": leg.quantity,
                    "quantity": leg.quantity,
                    "symbol": symbol,
                }
            )

        ticket: Dict[str, Any] = {
            "strategy": strategy_name,
            "underlying": underlying,
            "lot_size": int(lot_size),
            "lots": int(lots),
            "legs": ticket_legs,
        }

        result: Dict[str, Any] = {
            "strategy": strategy_name,
            "approved": True,
            "reason": "User-defined strategy",
            "ticket": ticket,
            "risk_metrics": {},
            "signal": {},
            "context": {
                "underlying": underlying,
                "expiry": expiry_str,
                "source": "strategy_builder",
            },
        }

        # Log as StrategyRun so downstream intent creation can work.
        db = SessionLocal()
        try:
            run = save_strategy_run(
                db=db,
                strategy=strategy_name,
                underlying=str(underlying),
                approved=True,
                reason=str(result.get("reason") or ""),
                risk_metrics=result.get("risk_metrics") or {},
                ticket=ticket,
                signal=result.get("signal") or {},
                context=result.get("context") or {},
            )
            if run and run.id:
                result["run_id"] = run.id
        except Exception:
            # Never block execution if logging fails.
            pass
        finally:
            db.close()

        return result
