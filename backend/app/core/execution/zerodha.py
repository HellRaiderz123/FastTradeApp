import os
from typing import Dict, Any, List
from datetime import date

from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.services.zerodha_ticker import subscribe_symbols as subscribe_to_ticker


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

    # ============================
    # EXECUTION (DRY-RUN ONLY)
    # ============================
    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)

        # Estimate entry credit using current LTP and store per-leg price for MTM
        entry_credit_total = self._estimate_entry_credit_and_store_leg_prices(intent)
        
        # Calculate margin requirement using Zerodha order_margins API
        margin_required = self._calculate_margin_requirement(orders)

        # Subscribe symbols to live ticker WebSocket for MTM updates
        try:
            symbols = [leg.get("symbol") for leg in intent.ticket.get("legs", []) if leg.get("symbol")]
            if symbols:
                subscribe_to_ticker(symbols)
        except Exception as e:
            # Non-blocking: if subscription fails, execution still proceeds
            import logging
            logging.getLogger(__name__).warning(f"⚠️  Failed to subscribe to ticker: {e}")

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
                "entry_credit": entry_credit_total,
                "margin_required": margin_required,
            }

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

        return {
            "mode": "ZERODHA_LIVE",
            "orders": orders,
            "placed": placed,
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
            "margin_required": margin_required,
        }

    # ============================
    # EXIT
    # ============================
    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)

        # Estimate cost to close using LTP
        final_pnl, exit_cost_total = self._estimate_exit_cost_and_pnl(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
                "exit_cost": exit_cost_total,
                "final_pnl": final_pnl,
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
        }

    # ============================
    # ORDER BUILDERS
    # ============================
    def _build_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

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

            orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "SELL" if leg["side"] == "SELL" else "BUY",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return orders

    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

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

            exit_orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "BUY" if leg["side"] == "SELL" else "SELL",
                "quantity": qty,
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

        ticket = intent.ticket

        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        if not symbols:
            return 0.0
            
        ltp_map = get_ltp(symbols)

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
                leg_qty = int(leg.get("qty", 1))

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
                leg_qty = int(leg.get("qty", 1))
                
                if leg["side"] == "SELL":
                    cost_to_close += ltp * leg_qty
                else:
                    cost_to_close -= ltp * leg_qty
            
            # PnL = entry_credit - cost_to_close
            pnl = entry_credit - cost_to_close

        return pnl

    def _estimate_entry_credit_and_store_leg_prices(self, intent) -> float:
        ticket = intent.ticket

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

        entry_credit_total = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            px = float(ltp.get(sym) or 0.0)
            leg["price"] = px
            leg_qty = int(leg.get("qty", 1))
            if leg.get("side") == "SELL":
                entry_credit_total += px * leg_qty
            else:
                entry_credit_total -= px * leg_qty

        return round(entry_credit_total, 2)

    def _estimate_exit_cost_and_pnl(self, intent) -> tuple[float, float]:
        ticket = intent.ticket
        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        ltp = get_ltp(symbols)

        exit_cost_total = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                continue
            px = float(ltp.get(sym) or 0.0)
            leg_qty = int(leg.get("qty", 1))
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
            ticket = intent.ticket or {}
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
