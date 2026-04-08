import logging
import os
from typing import Dict, Any, List
from datetime import date

from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.services.zerodha_ticker import subscribe_symbols as subscribe_to_ticker
from app.core.execution.base import get_ticket
from app.core.execution.protection import (
    get_protection_ratios,
    get_protection_state,
    round_to_tick,
    store_protection_state,
)

logger = logging.getLogger(__name__)


def _parse_expiry(expiry_str: str | None) -> date | None:
    """Convert expiry string to date object.
    
    Handles formats: 'YYYY-MM-DD' or date objects.
    Returns None if expiry_str is None or invalid.
    """
    if expiry_str is None:
        return None
    
    # If it's already a date object, return it
    if isinstance(expiry_str, date):
        return expiry_str
    
    # Parse string format
    try:
        return date.fromisoformat(str(expiry_str))
    except (ValueError, AttributeError):
        return None


class ZerodhaExecutionAdapter:
    def __init__(self, kite_client, dry_run: bool = True):
        self.kite = kite_client
        self.dry_run = dry_run

    @staticmethod
    def _resolve_leg_qty(leg: Dict[str, Any], ticket_qty: int) -> int:
        raw = leg.get("qty", leg.get("quantity"))
        if raw is None:
            return max(1, int(ticket_qty))
        try:
            value = int(raw)
        except Exception:
            return max(1, int(ticket_qty))
        if value <= 0:
            return max(1, int(ticket_qty))
        if value <= 10 and ticket_qty > 1:
            return value * ticket_qty
        return value

    # ============================
    # EXECUTION (DRY-RUN ONLY)
    # ============================
    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)

        # Estimate entry credit using current LTP and store per-leg price for MTM
        entry_credit_total = self._estimate_entry_credit_and_store_leg_prices(intent)
        intent.entry_credit = entry_credit_total  # type: ignore[attr-defined]

        # Calculate margin requirement using Zerodha order_margins API
        margin_required = self._calculate_margin_requirement(orders)

        # Subscribe symbols to live ticker WebSocket for MTM updates
        try:
            ticket_for_sub = get_ticket(intent)
            symbols = [leg.get("symbol") for leg in ticket_for_sub.get("legs", []) if leg.get("symbol")]
            if symbols:
                subscribe_to_ticker(symbols)
        except Exception as e:
            logger.warning("⚠️  Failed to subscribe to ticker: %s", e)

        if not self.dry_run:
            product = os.getenv("ZERODHA_PRODUCT", "NRML")
            placed = []
            for o in orders:
                order_id = self.kite.place_order(
                    variety=getattr(self.kite, "VARIETY_REGULAR", "regular"),
                    exchange=o["exchange"],
                    tradingsymbol=o["tradingsymbol"],
                    transaction_type=o["transaction_type"],
                    quantity=int(o["quantity"]),
                    order_type=getattr(self.kite, "ORDER_TYPE_MARKET", "MARKET"),
                    product=getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                    validity=getattr(self.kite, "VALIDITY_DAY", "DAY"),
                )
                placed.append({"order_id": order_id, "order": o})

            protection = self.sync_protection(intent)
            return {
                "mode": "ZERODHA_LIVE",
                "orders": orders,
                "placed": placed,
                "filled_at": now_ist().isoformat(),
                "entry_credit": entry_credit_total,
                "margin_required": margin_required,
                "protection": protection,
            }

        protection = self.sync_protection(intent)
        return {
            "mode": "ZERODHA_DRY_RUN",
            "orders": orders,
            "created_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
            "margin_required": margin_required,
            "protection": protection,
        }

    # ============================
    # EXIT
    # ============================
    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)

        # Estimate cost to close using LTP
        final_pnl, exit_cost_total = self._estimate_exit_cost_and_pnl(intent)
        protection_cancel = self.cancel_protection(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
                "exit_cost": exit_cost_total,
                "final_pnl": final_pnl,
                "protection_cancel": protection_cancel,
            }

        product = os.getenv("ZERODHA_PRODUCT", "NRML")
        placed = []
        for o in exit_orders:
            order_id = self.kite.place_order(
                variety=getattr(self.kite, "VARIETY_REGULAR", "regular"),
                exchange=o["exchange"],
                tradingsymbol=o["tradingsymbol"],
                transaction_type=o["transaction_type"],
                quantity=int(o["quantity"]),
                order_type=getattr(self.kite, "ORDER_TYPE_MARKET", "MARKET"),
                product=getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                validity=getattr(self.kite, "VALIDITY_DAY", "DAY"),
            )
            placed.append({"order_id": order_id, "order": o})

        return {
            "mode": "ZERODHA_LIVE",
            "exit_orders": exit_orders,
            "placed": placed,
            "closed_at": now_ist().isoformat(),
            "exit_cost": exit_cost_total,
            "final_pnl": final_pnl,
            "protection_cancel": protection_cancel,
        }

    def sync_protection(self, intent) -> Dict[str, Any]:
        protection = {
            "provider": "ZERODHA_GTT",
            "enabled": False,
            "mode": "PREVIEW" if self.dry_run else "LIVE",
            "synced_at": now_ist().isoformat(),
            "orders": [],
        }
        plans = self._build_protection_plans(intent)
        if not plans:
            protection["reason"] = "No broker-side TP/SL plan could be derived from the current intent."
            store_protection_state(intent, protection)
            return protection

        existing = get_protection_state(intent)
        if not self.dry_run and existing.get("orders"):
            protection["previous_cancel"] = self.cancel_protection(intent)

        for plan in plans:
            row = {
                "tradingsymbol": plan["tradingsymbol"],
                "exchange": plan["exchange"],
                "quantity": plan["quantity"],
                "trigger_type": plan["trigger_type"],
                "trigger_values": plan["trigger_values"],
                "last_price": plan["last_price"],
                "target_price": plan.get("target_price"),
                "stop_price": plan.get("stop_price"),
            }
            if self.dry_run:
                row["preview"] = True
            else:
                try:
                    trigger_id = self.kite.place_gtt(
                        trigger_type=plan["trigger_type"],
                        tradingsymbol=plan["tradingsymbol"],
                        exchange=plan["exchange"],
                        trigger_values=plan["trigger_values"],
                        last_price=plan["last_price"],
                        orders=plan["orders"],
                    )
                    row["trigger_id"] = str(trigger_id)
                except Exception as exc:
                    row["error"] = str(exc)
                    protection.setdefault("errors", []).append(str(exc))
                    logger.warning("Failed to place Zerodha GTT for %s: %s", plan["tradingsymbol"], exc)
            protection["orders"].append(row)

        protection["enabled"] = bool(protection["orders"]) and not protection.get("errors")
        store_protection_state(intent, protection)
        return protection

    def cancel_protection(self, intent) -> Dict[str, Any]:
        existing = get_protection_state(intent)
        cancellation = {
            "provider": existing.get("provider", "ZERODHA_GTT"),
            "cancelled": False,
            "cancelled_at": now_ist().isoformat(),
            "orders": [],
        }
        for row in existing.get("orders", []):
            if not isinstance(row, dict):
                continue
            trigger_id = row.get("trigger_id")
            item = {
                "tradingsymbol": row.get("tradingsymbol"),
                "trigger_id": trigger_id,
            }
            if not trigger_id:
                item["skipped"] = True
            elif self.dry_run:
                item["cancelled"] = True
                item["preview"] = True
            else:
                try:
                    self.kite.delete_gtt(trigger_id)
                    item["cancelled"] = True
                except Exception as exc:
                    item["cancelled"] = False
                    item["error"] = str(exc)
                    logger.warning("Failed to cancel Zerodha GTT %s: %s", trigger_id, exc)
            cancellation["orders"].append(item)

        cancellation["cancelled"] = bool(cancellation["orders"]) and all(
            item.get("cancelled") or item.get("skipped") for item in cancellation["orders"]
        )
        if existing:
            updated_state = dict(existing)
            updated_state["active"] = False
            updated_state["last_cancel"] = cancellation
            store_protection_state(intent, updated_state)
        return cancellation

    def _build_protection_plans(self, intent) -> List[Dict[str, Any]]:
        ticket = get_ticket(intent)
        if not ticket.get("legs"):
            return []
        if getattr(intent, "tp", None) is None and getattr(intent, "sl", None) is None:
            return []

        orders = self._build_orders(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        profit_ratio, loss_ratio = get_protection_ratios(intent)
        latest_prices = get_ltp([leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")])
        product = os.getenv("ZERODHA_PRODUCT", "NRML")

        plans: List[Dict[str, Any]] = []
        for broker_order, leg in zip(orders, ticket.get("legs", [])):
            entry_price = float(leg.get("price") or latest_prices.get(leg.get("symbol")) or 0.0)
            if entry_price <= 0:
                continue

            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            leg_side = str(leg.get("side") or "").upper()
            exit_side = getattr(self.kite, "TRANSACTION_TYPE_BUY", "BUY") if leg_side == "SELL" else getattr(self.kite, "TRANSACTION_TYPE_SELL", "SELL")

            if leg_side == "SELL":
                target_price = round_to_tick(max(0.05, entry_price * (1 - profit_ratio)))
                stop_price = round_to_tick(entry_price * (1 + loss_ratio))
            else:
                target_price = round_to_tick(entry_price * (1 + profit_ratio))
                stop_price = round_to_tick(max(0.05, entry_price * (1 - loss_ratio)))

            trigger_pairs = []
            if getattr(intent, "sl", None) is not None:
                trigger_pairs.append((
                    stop_price,
                    {
                        "exchange": broker_order["exchange"],
                        "tradingsymbol": broker_order["tradingsymbol"],
                        "transaction_type": exit_side,
                        "quantity": int(leg_qty),
                        "order_type": getattr(self.kite, "ORDER_TYPE_LIMIT", "LIMIT"),
                        "product": getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                        "price": stop_price,
                    },
                ))
            if getattr(intent, "tp", None) is not None:
                trigger_pairs.append((
                    target_price,
                    {
                        "exchange": broker_order["exchange"],
                        "tradingsymbol": broker_order["tradingsymbol"],
                        "transaction_type": exit_side,
                        "quantity": int(leg_qty),
                        "order_type": getattr(self.kite, "ORDER_TYPE_LIMIT", "LIMIT"),
                        "product": getattr(self.kite, "PRODUCT_NRML", product) if product == "NRML" else product,
                        "price": target_price,
                    },
                ))

            if not trigger_pairs:
                continue

            trigger_pairs.sort(key=lambda item: item[0])
            trigger_type = getattr(self.kite, "GTT_TYPE_OCO", "two-leg") if len(trigger_pairs) > 1 else getattr(self.kite, "GTT_TYPE_SINGLE", "single")
            plans.append({
                "tradingsymbol": broker_order["tradingsymbol"],
                "exchange": broker_order["exchange"],
                "quantity": int(leg_qty),
                "trigger_type": trigger_type,
                "trigger_values": [pair[0] for pair in trigger_pairs],
                "orders": [pair[1] for pair in trigger_pairs],
                "last_price": round_to_tick(entry_price),
                "target_price": target_price,
                "stop_price": stop_price,
            })

        return plans

    # ============================
    # ORDER BUILDERS
    # ============================
    def _build_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = get_ticket(intent)
        qty = int(ticket["lots"]) * int(ticket["lot_size"])

        # Parse expiry string to date object
        expiry_date = _parse_expiry(intent.expiry)
        if expiry_date is None:
            raise ValueError(f"Invalid or missing expiry: {intent.expiry}")

        orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=expiry_date,
                strike=leg["strike"],
                option_type=leg["type"],
            )
            leg_qty = self._resolve_leg_qty(leg, qty)

            orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "SELL" if leg["side"] == "SELL" else "BUY",
                "quantity": leg_qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return orders

    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = get_ticket(intent)
        qty = int(ticket["lots"]) * int(ticket["lot_size"])

        # Parse expiry string to date object
        expiry_date = _parse_expiry(intent.expiry)
        if expiry_date is None:
            raise ValueError(f"Invalid or missing expiry: {intent.expiry}")

        exit_orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=expiry_date,
                strike=leg["strike"],
                option_type=leg["type"],
            )
            leg_qty = self._resolve_leg_qty(leg, qty)

            exit_orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "BUY" if leg["side"] == "SELL" else "SELL",
                "quantity": leg_qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return exit_orders

    # ============================
    # MTM (READ ONLY)
    # ============================
    def mtm(self, intent) -> float:
        """
        Mark-to-market PnL using Zerodha LTP.
        Uses entry_credit if leg prices are not available.
        """

        ticket = get_ticket(intent)

        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        if not symbols:
            return 0.0
            
        ltp_map = get_ltp(symbols)

        # Correct quantity: prefer per-leg qty, then ticket-level lots × lot_size
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        # Check if we have leg prices
        has_leg_prices = all(leg.get("price") is not None for leg in ticket["legs"])
        
        if has_leg_prices:
            # Use per-leg calculation with actual leg quantities
            pnl = 0.0
            for leg in ticket["legs"]:
                sym = leg.get("symbol")
                if not sym:
                    continue
                ltp = float(ltp_map.get(sym) or 0.0)
                entry = leg.get("price")
                if entry is None:
                    continue
                entry_f = float(entry)
                leg_qty = self._resolve_leg_qty(leg, ticket_qty)

                if leg["side"] == "SELL":
                    pnl += (entry_f - ltp) * leg_qty
                else:
                    pnl += (ltp - entry_f) * leg_qty
        else:
            # Use entry_credit method (credit spread calculation)
            entry_credit = getattr(intent, "entry_credit", None) or 0.0
            
            # Calculate current cost to close
            cost_to_close = 0.0
            for leg in ticket["legs"]:
                sym = leg.get("symbol")
                if not sym:
                    continue
                ltp = float(ltp_map.get(sym) or 0.0)
                leg_qty = self._resolve_leg_qty(leg, ticket_qty)
                
                if leg["side"] == "SELL":
                    cost_to_close += ltp * leg_qty
                else:
                    cost_to_close -= ltp * leg_qty
            
            # PnL = entry_credit - cost_to_close
            pnl = entry_credit - cost_to_close

        return pnl

    def _estimate_entry_credit_and_store_leg_prices(self, intent) -> float:
        ticket = get_ticket(intent)

        # Parse expiry string to date object
        expiry_date = _parse_expiry(intent.expiry)
        if expiry_date is None:
            raise ValueError(f"Invalid or missing expiry: {intent.expiry}")

        # Ensure tradingsymbol exists on each leg (for MTM)
        symbols: List[str] = []
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                # Build from strike/type if missing
                sym = build_zerodha_option_symbol(
                    underlying=intent.underlying,
                    expiry=expiry_date,
                    strike=int(leg["strike"]),
                    option_type=str(leg["type"]),
                )
                leg["symbol"] = sym
            symbols.append(sym)

        ltp = get_ltp(symbols)

        # Compute per-leg quantity from ticket-level lots × lot_size
        qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        entry_credit_total = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            px = float(ltp.get(sym) or 0.0)
            leg["price"] = px
            leg_qty = self._resolve_leg_qty(leg, qty)
            leg["qty"] = leg_qty  # persist so MTM can use it later
            if leg.get("side") == "SELL":
                entry_credit_total += px * leg_qty
            else:
                entry_credit_total -= px * leg_qty

        return round(entry_credit_total, 2)

    def _estimate_exit_cost_and_pnl(self, intent) -> tuple[float, float]:
        ticket = get_ticket(intent)
        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        ltp = get_ltp(symbols)

        exit_cost_total = 0.0
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                continue
            px = float(ltp.get(sym) or 0.0)
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            if leg.get("side") == "SELL":
                exit_cost_total += px * leg_qty
            else:
                exit_cost_total -= px * leg_qty

        entry_credit_total = float(getattr(intent, "entry_credit", 0.0) or 0.0)
        final_pnl = round(entry_credit_total - exit_cost_total, 2)
        return float(final_pnl), round(exit_cost_total, 2)

    def calculate_margin_required(self, intent) -> float:
        """Convenience wrapper to compute margin for a given `intent`.

        Builds current basket orders from the intent and queries Zerodha
        `basket_order_margins` to get the total margin required.
        Returns 0.0 if anything fails.
        """
        try:
            orders = self._build_orders(intent)
            return float(self._calculate_margin_requirement(orders))
        except Exception:
            return 0.0

    def per_leg_metrics(self, intent) -> List[Dict[str, Any]]:
        """Return per-leg metrics: entry price, current LTP, and P&L.

        P&L per unit is computed as:
          SELL: entry - ltp
          BUY:  ltp - entry

        Total P&L per leg = per_unit * quantity (lot_size * lots).
        """
        metrics: List[Dict[str, Any]] = []
        try:
            ticket = get_ticket(intent)
            qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

            # Ensure symbols are present; build if needed
            expiry_date = _parse_expiry(intent.expiry)
            symbols: List[str] = []
            legs: List[Dict[str, Any]] = list(ticket.get("legs", []))
            for leg in legs:
                sym = leg.get("symbol")
                if not sym:
                    try:
                        sym = build_zerodha_option_symbol(
                            underlying=intent.underlying,
                            expiry=expiry_date,
                            strike=int(leg.get("strike", 0)),
                            option_type=str(leg.get("type", "")),
                        )
                        leg["symbol"] = sym
                    except Exception:
                        sym = None
                if sym:
                    symbols.append(sym)

            if not symbols:
                return metrics

            ltp_map = get_ltp(symbols)

            # Entry prices may be stored in leg["price"]; if not, default 0
            for leg in legs:
                sym = leg.get("symbol")
                if not sym:
                    continue
                entry_raw = leg.get("price")
                entry = float(entry_raw) if entry_raw is not None else None
                ltp = float(ltp_map.get(sym) or 0.0)
                side = str(leg.get("side") or "")

                pnl_unit = None
                pnl_total = None
                if entry is not None and entry > 0:
                    per_unit = (entry - ltp) if side == "SELL" else (ltp - entry)
                    pnl_unit = round(per_unit, 2)
                    pnl_total = round(per_unit * qty, 2)

                metrics.append({
                    "symbol": sym,
                    "side": side,
                    "entry": entry,
                    "ltp": ltp,
                    "pnl_unit": pnl_unit,
                    "pnl_total": pnl_total,
                    "quantity": qty,
                })

            return metrics
        except Exception:
            return metrics
    
    def _calculate_margin_requirement(self, orders: List[Dict[str, Any]]) -> float:
        """
        Calculate margin requirement using Zerodha basket_order_margins API.
        Returns total margin required for the basket of orders.
        """
        if not orders:
            return 0.0
        
        try:
            # Format orders for Zerodha basket_order_margins API
            basket = []
            product = os.getenv("ZERODHA_PRODUCT", "NRML")
            
            for o in orders:
                basket.append({
                    "exchange": o["exchange"],
                    "tradingsymbol": o["tradingsymbol"],
                    "transaction_type": o["transaction_type"],
                    "variety": "regular",
                    "product": product,
                    "order_type": "MARKET",
                    "quantity": int(o["quantity"]),
                })
            
            # Get margin calculation from Zerodha
            margin_response = self.kite.basket_order_margins(basket)
            
            # Extract total margin required
            # Response format: {"final": {"total": <amount>}, "orders": [...]}
            if isinstance(margin_response, dict):
                final = margin_response.get("final", {})
                total_margin = final.get("total", 0.0)
                return round(float(total_margin), 2)
            
            return 0.0
            
        except Exception as e:
            # If margin calculation fails, return 0 (don't block execution)
            print(f"⚠️  Margin calculation failed: {e}")
            return 0.0
