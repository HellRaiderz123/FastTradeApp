"""
tp_sl_calculator.py
-------------------
Calculates Take Profit (TP) and Stop Loss (SL) levels dynamically.

Instead of hardcoded values (tp=1500, sl=-2000), we calculate based on:
- Capital available
- Risk percentage per trade (user preference)
- Position size (lot size × number of lots)
- Strategy type (spread margins are different from directional)

Formula:
  max_loss_amount = capital × risk_percentage
  tp = max_loss_amount  (profit target = risk amount for 1:1 ratio)
  sl = -max_loss_amount (stop loss = maximum acceptable loss)

Example:
  capital = 100,000
  risk_pct = 2% = 2,000
  tp = 2,000 (profit target)
  sl = -2,000 (stop loss)
"""

from typing import Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_tp_sl(
    capital: float,
    risk_percentage: float = 2.0,
    position_size: int = 1,
    lot_size: int = 65,
    strategy_type: str = "BULL_PUT",
) -> Dict[str, float]:
    """
    Calculate Take Profit and Stop Loss based on capital and risk tolerance.
    
    Args:
        capital: Available trading capital (in rupees)
        risk_percentage: Max % of capital to risk per trade (default 2%)
        position_size: Number of spreads (number of lots)
        lot_size: Size per lot (e.g., 65 for NIFTY options)
        strategy_type: BULL_PUT, BEAR_CALL, IRON_CONDOR, etc.
    
    Returns:
        {
            "tp": Take Profit amount (positive, absolute rupees),
            "sl": Stop Loss amount (negative, absolute rupees),
            "max_risk": Maximum risk amount,
            "position_size_qty": Total quantity traded,
            "risk_per_lot": Risk per lot,
            "tp_ratio": Profit target as % of capital,
            "sl_ratio": Loss tolerance as % of capital
        }
    
    Example:
        >>> calc_tp_sl(capital=100000, risk_percentage=2.0)
        {
            'tp': 2000.0,
            'sl': -2000.0,
            'max_risk': 2000.0,
            ...
        }
    """
    
    # =========================================
    # BASIC CALCULATIONS
    # =========================================
    
    # Validate inputs
    if capital <= 0:
        raise ValueError(f"Capital must be positive, got {capital}")
    if risk_percentage <= 0 or risk_percentage > 100:
        raise ValueError(f"Risk percentage must be 0-100, got {risk_percentage}")
    if position_size < 1:
        raise ValueError(f"Position size must be >= 1, got {position_size}")
    
    # Max loss in rupees
    max_risk = capital * (risk_percentage / 100)
    
    # Position size in quantity
    position_qty = position_size * lot_size
    
    # Risk per lot
    risk_per_lot = max_risk / position_size if position_size > 0 else max_risk
    
    # =========================================
    # TP/SL CALCULATION
    # =========================================
    
    # Simple 1:1 ratio (risk:reward)
    # TP = max_risk (profit target)
    # SL = -max_risk (stop loss)
    tp = max_risk
    sl = -max_risk
    
    # =========================================
    # STRATEGY-SPECIFIC ADJUSTMENTS
    # =========================================
    
    if strategy_type in ["BULL_PUT", "BEAR_CALL"]:
        # Credit spread: Limited profit potential, high loss potential
        # For spreads, margin is only 1 lot_size difference (100-200 per spread)
        # Risk = spread_width × lot_size × num_spreads
        spread_width = 100  # Typical 100-point spread for NIFTY
        inherent_risk = spread_width * position_qty  # Max possible loss
        
        # Scale TP/SL based on actual spread risk
        if inherent_risk > 0 and inherent_risk < max_risk:
            # If spread's max loss is less than our risk tolerance,
            # adjust TP to be a fraction of the max spread loss
            tp = inherent_risk * 0.5  # Aim for 50% of max spread loss
            sl = -inherent_risk * 0.9  # Stop at 90% of max loss
        
        logger.info(f"SPREAD TP/SL: {strategy_type} - Spread Width: {spread_width}, "
                   f"Inherent Risk: {inherent_risk}, Adjusted TP: {tp}, SL: {sl}")
    
    elif strategy_type == "IRON_CONDOR":
        # Iron condor: Similar to spreads but double-sided
        # Max loss = higher spread × lot_size × num
        spread_width = 200  # Higher width for iron condor
        inherent_risk = spread_width * position_qty
        
        if inherent_risk > 0 and inherent_risk < max_risk:
            tp = inherent_risk * 0.4  # Aim for 40% of max loss
            sl = -inherent_risk * 0.85
        
        logger.info(f"IRON_CONDOR TP/SL: Spread Width: {spread_width}, "
                   f"Inherent Risk: {inherent_risk}, Adjusted TP: {tp}, SL: {sl}")
    
    # =========================================
    # RETURN RESULT
    # =========================================
    
    result = {
        "tp": float(round(tp, 2)),
        "sl": float(round(sl, 2)),
        "max_risk": float(round(max_risk, 2)),
        "position_size_qty": position_qty,
        "risk_per_lot": float(round(risk_per_lot, 2)),
        "tp_ratio": float(round((tp / capital) * 100, 2)) if capital > 0 else 0,
        "sl_ratio": float(round((abs(sl) / capital) * 100, 2)) if capital > 0 else 0,
        "strategy": strategy_type,
        "capital": float(capital),
        "risk_percentage": float(risk_percentage),
    }
    
    logger.info(f"TP/SL Calculated: TP={result['tp']}, SL={result['sl']}, "
               f"Risk={result['max_risk']} ({result['tp_ratio']}% of capital)")
    
    return result


def calculate_tp_sl_from_ticket(
    ticket: Dict,
    capital: float,
    risk_percentage: float = 2.0,
) -> Dict[str, float]:
    """
    Calculate TP/SL from a strategy ticket.
    
    Args:
        ticket: Strategy ticket containing strategy type and legs
        capital: Available capital
        risk_percentage: Risk tolerance
    
    Returns:
        TP/SL calculation result
    """
    
    strategy = ticket.get("strategy", "BULL_PUT")
    lot_size = ticket.get("lot_size", 65)
    lots = ticket.get("lots", 1)
    
    return calculate_tp_sl(
        capital=capital,
        risk_percentage=risk_percentage,
        position_size=lots,
        lot_size=lot_size,
        strategy_type=strategy,
    )


# =========================================
# PRESET RISK PROFILES
# =========================================

RISK_PROFILES = {
    "CONSERVATIVE": 1.0,    # 1% risk per trade
    "BALANCED": 2.0,         # 2% risk per trade (default)
    "AGGRESSIVE": 3.0,       # 3% risk per trade
    "VERY_AGGRESSIVE": 5.0,  # 5% risk per trade (not recommended)
}


def get_risk_percentage_from_mode(risk_mode: str) -> float:
    """
    Get risk percentage from preset risk mode.
    
    Args:
        risk_mode: One of CONSERVATIVE, BALANCED, AGGRESSIVE, VERY_AGGRESSIVE
    
    Returns:
        Risk percentage (e.g., 2.0 for 2%)
    """
    mode_upper = str(risk_mode).upper()
    
    if mode_upper not in RISK_PROFILES:
        logger.warning(f"Unknown risk mode '{risk_mode}', using BALANCED (2%)")
        return RISK_PROFILES["BALANCED"]
    
    return RISK_PROFILES[mode_upper]


# =========================================
# EXAMPLE USAGE
# =========================================

if __name__ == "__main__":
    # Example 1: Conservative trader, 100k capital
    print("Example 1: Conservative, 100k capital")
    result = calculate_tp_sl(
        capital=100000,
        risk_percentage=1.0,  # CONSERVATIVE = 1%
        position_size=1,
        lot_size=65,
        strategy_type="BULL_PUT"
    )
    print(f"  TP: {result['tp']}")
    print(f"  SL: {result['sl']}")
    print(f"  Max Risk: {result['max_risk']}")
    
    # Example 2: Balanced trader, 50k capital
    print("\nExample 2: Balanced, 50k capital")
    result = calculate_tp_sl(
        capital=50000,
        risk_percentage=2.0,  # BALANCED = 2%
        position_size=2,
        lot_size=65,
        strategy_type="BULL_PUT"
    )
    print(f"  TP: {result['tp']}")
    print(f"  SL: {result['sl']}")
    print(f"  Max Risk: {result['max_risk']}")
    
    # Example 3: Using risk profile
    print("\nExample 3: Using risk profile")
    risk_pct = get_risk_percentage_from_mode("AGGRESSIVE")
    result = calculate_tp_sl(
        capital=200000,
        risk_percentage=risk_pct,
        position_size=1,
        lot_size=65,
        strategy_type="IRON_CONDOR"
    )
    print(f"  TP: {result['tp']}")
    print(f"  SL: {result['sl']}")
    print(f"  Risk Mode: AGGRESSIVE ({risk_pct}%)")
