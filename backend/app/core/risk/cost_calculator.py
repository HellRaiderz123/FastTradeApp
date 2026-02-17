"""
cost_calculator.py
------------------
Phase 2 Safety Feature — Zerodha Transaction Cost Model.

Without this, backtest and paper trade P&L is overstated.
A typical options spread trade at ₹50 premium costs ~₹150–₹250 in charges.
On a ₹2,000 credit, that's 7–12% hidden drag on every trade.

Charges modelled (as of 2025–2026):
  - Brokerage:            ₹20 per executed order (flat, Zerodha)
  - STT (Sell side):      0.0625% of premium on SELL options
  - Transaction charges:  0.05% of turnover (NSE)
  - GST:                  18% on (brokerage + transaction charges)
  - Stamp duty:           0.003% of buy-side turnover (capped at ₹1,500/trade)
  - SEBI charges:         ₹10 per crore of turnover

Usage:
    from app.core.risk.cost_calculator import calculate_trade_costs, apply_costs_to_pnl

    # For a single spread trade:
    costs = calculate_trade_costs(
        legs=[
            {"side": "SELL", "price": 120, "quantity": 50},
            {"side": "BUY",  "price":  60, "quantity": 50},
        ]
    )
    net_pnl = apply_costs_to_pnl(gross_pnl=1500.0, legs=costs["legs"])
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


# ── Zerodha F&O charge rates (2025–2026) ─────────────────────────────────
BROKERAGE_PER_ORDER: float = 20.0          # ₹20 flat per executed order
STT_SELL_RATE: float = 0.000625            # 0.0625% on sell premium
TRANSACTION_CHARGE_RATE: float = 0.0005   # 0.05% of turnover (NSE)
GST_RATE: float = 0.18                    # 18% on (brokerage + transaction charges)
STAMP_DUTY_RATE: float = 0.00003          # 0.003% on buy-side turnover
STAMP_DUTY_CAP: float = 1500.0            # Max ₹1,500 per trade
SEBI_CHARGE_RATE: float = 10.0 / 1e7     # ₹10 per crore = 0.000001 of turnover


@dataclass
class LegCost:
    side: str           # "SELL" or "BUY"
    price: float        # premium per unit
    quantity: int       # lot_size * lots
    turnover: float     # price * quantity
    brokerage: float
    stt: float
    transaction: float
    gst: float
    stamp_duty: float
    sebi: float
    total: float


@dataclass
class TradeCosts:
    legs: List[LegCost]
    total_brokerage: float
    total_stt: float
    total_transaction: float
    total_gst: float
    total_stamp_duty: float
    total_sebi: float
    total_charges: float    # sum of everything
    effective_drag_pct: float  # total_charges / gross_premium * 100


def _calc_leg_cost(side: str, price: float, quantity: int) -> LegCost:
    """Compute all charges for a single option leg."""
    price = max(0.0, float(price))
    quantity = max(1, int(quantity))
    turnover = price * quantity

    brokerage = BROKERAGE_PER_ORDER  # flat per order regardless of size

    # STT: only on SELL side for options
    stt = turnover * STT_SELL_RATE if side.upper() == "SELL" else 0.0

    # Transaction charges: both sides
    transaction = turnover * TRANSACTION_CHARGE_RATE

    # GST: on brokerage + transaction charges
    gst = (brokerage + transaction) * GST_RATE

    # Stamp duty: only on BUY side, capped
    stamp_duty = min(turnover * STAMP_DUTY_RATE, STAMP_DUTY_CAP) if side.upper() == "BUY" else 0.0

    # SEBI charges: both sides
    sebi = turnover * SEBI_CHARGE_RATE

    total = brokerage + stt + transaction + gst + stamp_duty + sebi

    return LegCost(
        side=side,
        price=price,
        quantity=quantity,
        turnover=turnover,
        brokerage=round(brokerage, 4),
        stt=round(stt, 4),
        transaction=round(transaction, 4),
        gst=round(gst, 4),
        stamp_duty=round(stamp_duty, 4),
        sebi=round(sebi, 4),
        total=round(total, 4),
    )


def calculate_trade_costs(
    legs: List[Dict[str, Any]],
) -> TradeCosts:
    """
    Calculate full Zerodha charges for a multi-leg options trade.

    Args:
        legs: List of dicts with keys: side (SELL/BUY), price (premium), quantity (lot_size*lots)

    Returns:
        TradeCosts with per-leg breakdown and totals.

    Example:
        calculate_trade_costs([
            {"side": "SELL", "price": 120, "quantity": 50},
            {"side": "BUY",  "price":  60, "quantity": 50},
        ])
    """
    leg_costs = [
        _calc_leg_cost(
            side=str(leg.get("side", "BUY")),
            price=float(leg.get("price", 0.0)),
            quantity=int(leg.get("quantity", 1)),
        )
        for leg in legs
    ]

    total_brokerage   = sum(lc.brokerage   for lc in leg_costs)
    total_stt         = sum(lc.stt         for lc in leg_costs)
    total_transaction = sum(lc.transaction for lc in leg_costs)
    total_gst         = sum(lc.gst         for lc in leg_costs)
    total_stamp_duty  = sum(lc.stamp_duty  for lc in leg_costs)
    total_sebi        = sum(lc.sebi        for lc in leg_costs)
    total_charges     = sum(lc.total       for lc in leg_costs)

    # Effective drag as % of gross premium collected (SELL side turnover)
    gross_premium = sum(
        lc.turnover for lc in leg_costs if lc.side.upper() == "SELL"
    )
    effective_drag_pct = (
        total_charges / gross_premium * 100 if gross_premium > 0 else 0.0
    )

    return TradeCosts(
        legs=leg_costs,
        total_brokerage=round(total_brokerage, 2),
        total_stt=round(total_stt, 2),
        total_transaction=round(total_transaction, 2),
        total_gst=round(total_gst, 2),
        total_stamp_duty=round(total_stamp_duty, 2),
        total_sebi=round(total_sebi, 2),
        total_charges=round(total_charges, 2),
        effective_drag_pct=round(effective_drag_pct, 2),
    )


def calculate_costs_from_intent(intent) -> TradeCosts:
    """
    Convenience wrapper — takes an ExecutionIntent and extracts leg data.
    Handles missing prices gracefully (returns zero costs).
    """
    ticket = intent.ticket or {}
    lots = int(ticket.get("lots", 1))
    lot_size = int(ticket.get("lot_size", 1))
    quantity = lots * lot_size

    legs = []
    for leg in ticket.get("legs", []):
        price = leg.get("price")
        if price is None:
            logger.warning(
                f"cost_calculator: leg has no stored price (symbol={leg.get('symbol')}), "
                "using 0.0 — costs will be understated."
            )
            price = 0.0
        legs.append({
            "side": str(leg.get("side", "BUY")),
            "price": float(price),
            "quantity": quantity,
        })

    return calculate_trade_costs(legs)


def apply_costs_to_pnl(gross_pnl: float, trade_costs: TradeCosts) -> float:
    """
    Subtract total transaction costs from gross P&L.

    For an options credit spread:
    - Entry charges are paid when the trade opens
    - Exit charges are paid when the trade closes
    Pass the sum of both entry + exit costs as trade_costs.

    Returns net P&L after all charges.
    """
    return round(gross_pnl - trade_costs.total_charges, 2)


def estimate_round_trip_costs(
    legs: List[Dict[str, Any]],
) -> float:
    """
    Estimate total charges for the full round-trip (entry + exit).
    Assumes exit prices are approximately the same as entry prices.
    Useful for pre-trade cost estimation.
    """
    entry_costs = calculate_trade_costs(legs)
    # Exit reverses BUY/SELL sides
    exit_legs = [
        {**leg, "side": "BUY" if leg["side"].upper() == "SELL" else "SELL"}
        for leg in legs
    ]
    exit_costs = calculate_trade_costs(exit_legs)
    return round(entry_costs.total_charges + exit_costs.total_charges, 2)


def format_cost_breakdown(costs: TradeCosts) -> str:
    """Human-readable breakdown for logs and notifications."""
    return (
        f"Brokerage: ₹{costs.total_brokerage:.2f} | "
        f"STT: ₹{costs.total_stt:.2f} | "
        f"Transaction: ₹{costs.total_transaction:.2f} | "
        f"GST: ₹{costs.total_gst:.2f} | "
        f"Stamp: ₹{costs.total_stamp_duty:.2f} | "
        f"SEBI: ₹{costs.total_sebi:.2f} | "
        f"Total: ₹{costs.total_charges:.2f} ({costs.effective_drag_pct:.1f}% of premium)"
    )
