import json
import logging
import os
from typing import Any, Dict, List

from app.core.broker.indmoney.client import INDMoneyClient
from app.core.broker.indmoney.instruments import INDMoneyInstrumentsResolver
from app.core.execution.base import get_ticket
from app.core.execution.protection import (
    get_protection_ratios,
    get_protection_state,
    round_to_tick,
    store_protection_state,
)
from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist

logger = logging.getLogger(__name__)


class INDMoneyExecutionAdapter:
    """Execution adapter for INDstocks/INDMoney order placement.

    Execution uses INDstocks REST order APIs while market data and MTM continue
    to use the existing LTP pipeline.
    """

    def __init__(self, client: INDMoneyClient, dry_run: bool = True):
        self.client = client
        self.dry_run = dry_run
        self.algo_id = os.getenv("INDMONEY_ALGO_ID", "99999")
        self.default_product = os.getenv("INDMONEY_PRODUCT", "MARGIN")
        self.default_validity = os.getenv("INDMONEY_VALIDITY", "DAY")
        self.default_order_type = os.getenv("INDMONEY_ORDER_TYPE", "MARKET")
        self.default_segment = os.getenv("INDMONEY_SEGMENT", "DERIVATIVE")
        self.default_exchange = os.getenv("INDMONEY_EXCHANGE", "NSE")
        self.security_map = self._load_security_map()
        self.instruments_resolver = INDMoneyInstrumentsResolver(client)

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

    @staticmethod
    def _load_security_map() -> Dict[str, str]:
        raw = os.getenv("INDMONEY_SECURITY_MAP_JSON", "{}").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                return {}
            return {str(k): str(v) for k, v in parsed.items()}
        except Exception:
            return {}

    def _resolve_security_id(self, leg: Dict[str, Any], ticket: Dict[str, Any]) -> str:
        direct = leg.get("security_id") or leg.get("scrip_code")
        if direct:
            return str(direct)

        symbol = str(leg.get("symbol") or "")
        normalized_symbol = symbol.strip().upper().replace(" ", "")
        ticket_map = ticket.get("security_map") or {}
        if symbol and isinstance(ticket_map, dict):
            if symbol in ticket_map:
                return str(ticket_map[symbol])
            if normalized_symbol in ticket_map:
                return str(ticket_map[normalized_symbol])

        if symbol:
            if symbol in self.security_map:
                return str(self.security_map[symbol])
            if normalized_symbol in self.security_map:
                return str(self.security_map[normalized_symbol])

            auto_resolved = self.instruments_resolver.resolve_security_id(symbol)
            if auto_resolved:
                return str(auto_resolved)

        raise ValueError(
            f"Missing security_id for leg symbol '{symbol}'. Provide leg.security_id, INDMONEY_SECURITY_MAP_JSON, or ensure symbol exists in INDstocks instruments."
        )

    def _normalize_exchange(self, value: str | None) -> str:
        raw = (value or "").strip().upper()
        if raw in {"NFO", "NSE_FNO", "NSE_DERIVATIVE"}:
            return "NSE"
        if raw in {"BFO", "BSE_FNO", "BSE_DERIVATIVE"}:
            return "BSE"
        return raw or self.default_exchange

    def _build_indstocks_order(
        self,
        *,
        security_id: str,
        txn_type: str,
        qty: int,
        order_type: str,
        exchange: str,
        limit_price: float | None = None,
        trigger_price: float | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "txn_type": txn_type,
            "exchange": self._normalize_exchange(exchange),
            "segment": self.default_segment,
            "security_id": security_id,
            "qty": int(qty),
            "order_type": order_type,
            "validity": self.default_validity,
            "product": self.default_product,
            "is_amo": False,
            "algo_id": self.algo_id,
        }
        if order_type == "LIMIT" and limit_price is not None:
            payload["limit_price"] = float(limit_price)
        if trigger_price is not None:
            payload["trigger_price"] = float(trigger_price)
            if limit_price is not None:
                payload["limit_price"] = float(limit_price)
        return payload

    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)
        entry_credit_total = self._estimate_entry_credit_and_store_leg_prices(intent)
        intent.entry_credit = entry_credit_total  # type: ignore[attr-defined]

        if self.dry_run:
            protection = self.sync_protection(intent)
            return {
                "mode": "INDMONEY_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
                "entry_credit": entry_credit_total,
                "protection": protection,
            }

        placed = []
        for order in orders:
            result = self.client.place_order(order)
            placed.append({"order_id": result.get("order_id"), "order": order, "raw": result.get("response")})

        protection = self.sync_protection(intent)
        return {
            "mode": "INDMONEY_LIVE",
            "orders": orders,
            "placed": placed,
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
            "protection": protection,
        }

    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)
        final_pnl, exit_cost_total = self._estimate_exit_cost_and_pnl(intent)
        protection_cancel = self.cancel_protection(intent)

        if self.dry_run:
            return {
                "mode": "INDMONEY_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
                "exit_cost": exit_cost_total,
                "final_pnl": final_pnl,
                "protection_cancel": protection_cancel,
            }

        placed = []
        for order in exit_orders:
            result = self.client.place_order(order)
            placed.append({"order_id": result.get("order_id"), "order": order, "raw": result.get("response")})

        return {
            "mode": "INDMONEY_LIVE",
            "exit_orders": exit_orders,
            "placed": placed,
            "closed_at": now_ist().isoformat(),
            "exit_cost": exit_cost_total,
            "final_pnl": final_pnl,
            "protection_cancel": protection_cancel,
        }

    def mtm(self, intent) -> float:
        ticket = get_ticket(intent)
        symbols = [leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")]
        if not symbols:
            return 0.0

        ltp_map = get_ltp(symbols)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        has_leg_prices = all(leg.get("price") is not None for leg in ticket.get("legs", []))
        if has_leg_prices:
            pnl = 0.0
            for leg in ticket.get("legs", []):
                sym = leg.get("symbol")
                if not sym:
                    continue
                ltp = float(ltp_map.get(sym) or 0.0)
                entry = leg.get("price")
                if entry is None:
                    continue
                entry_f = float(entry)
                leg_qty = self._resolve_leg_qty(leg, ticket_qty)
                if leg.get("side") == "SELL":
                    pnl += (entry_f - ltp) * leg_qty
                else:
                    pnl += (ltp - entry_f) * leg_qty
            return round(pnl, 2)

        entry_credit = float(getattr(intent, "entry_credit", 0.0) or 0.0)
        cost_to_close = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if not sym:
                continue
            ltp = float(ltp_map.get(sym) or 0.0)
            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            if leg.get("side") == "SELL":
                cost_to_close += ltp * leg_qty
            else:
                cost_to_close -= ltp * leg_qty

        return round(entry_credit - cost_to_close, 2)

    def sync_protection(self, intent) -> Dict[str, Any]:
        gtt_supported = bool(getattr(self.client, "gtt_path", "")) and hasattr(self.client, "place_gtt")
        provider = "INDMONEY_GTT" if gtt_supported else "INDMONEY_BROKER_ORDERS"
        protection = {
            "provider": provider,
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
                "security_id": plan["security_id"],
                "symbol": plan.get("symbol"),
                "target_price": plan.get("target_price"),
                "stop_price": plan.get("stop_price"),
            }
            if self.dry_run:
                row["preview"] = True
            else:
                try:
                    if gtt_supported:
                        result = self.client.place_gtt(plan["gtt_payload"])
                        row["trigger_id"] = result.get("trigger_id")
                    else:
                        target_result = self.client.place_order(plan["target_order"])
                        stop_result = self.client.place_order(plan["stop_order"])
                        row["target_order_id"] = target_result.get("order_id")
                        row["stop_order_id"] = stop_result.get("order_id")
                except Exception as exc:
                    row["error"] = str(exc)
                    protection.setdefault("errors", []).append(str(exc))
                    logger.warning("Failed to place INDMoney broker-side protection for %s: %s", plan.get("symbol"), exc)
            protection["orders"].append(row)

        protection["enabled"] = bool(protection["orders"]) and not protection.get("errors")
        store_protection_state(intent, protection)
        return protection

    def cancel_protection(self, intent) -> Dict[str, Any]:
        existing = get_protection_state(intent)
        cancellation = {
            "provider": existing.get("provider", "INDMONEY_BROKER_ORDERS"),
            "cancelled": False,
            "cancelled_at": now_ist().isoformat(),
            "orders": [],
        }
        for row in existing.get("orders", []):
            if not isinstance(row, dict):
                continue
            item = {
                "symbol": row.get("symbol"),
                "security_id": row.get("security_id"),
            }
            if self.dry_run:
                item["cancelled"] = True
                item["preview"] = True
            else:
                try:
                    if row.get("trigger_id") and hasattr(self.client, "cancel_gtt"):
                        self.client.cancel_gtt(str(row["trigger_id"]))
                    for order_key in ("target_order_id", "stop_order_id"):
                        order_id = row.get(order_key)
                        if order_id and hasattr(self.client, "cancel_order"):
                            self.client.cancel_order(str(order_id))
                    item["cancelled"] = True
                except Exception as exc:
                    item["cancelled"] = False
                    item["error"] = str(exc)
                    logger.warning("Failed to cancel INDMoney broker-side protection for %s: %s", row.get("symbol"), exc)
            cancellation["orders"].append(item)

        cancellation["cancelled"] = bool(cancellation["orders"]) and all(item.get("cancelled") for item in cancellation["orders"])
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

        entry_orders = self._build_orders(intent)
        ticket_qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))
        profit_ratio, loss_ratio = get_protection_ratios(intent)
        latest_prices = get_ltp([leg.get("symbol") for leg in ticket.get("legs", []) if leg.get("symbol")])
        stop_order_type = os.getenv("INDMONEY_STOP_ORDER_TYPE", "SL")

        plans: List[Dict[str, Any]] = []
        for entry_order, leg in zip(entry_orders, ticket.get("legs", [])):
            entry_price = float(leg.get("price") or latest_prices.get(leg.get("symbol")) or 0.0)
            if entry_price <= 0:
                continue

            leg_qty = self._resolve_leg_qty(leg, ticket_qty)
            leg_side = str(leg.get("side") or "").upper()
            exit_side = "BUY" if leg_side == "SELL" else "SELL"

            if leg_side == "SELL":
                target_price = round_to_tick(max(0.05, entry_price * (1 - profit_ratio)))
                stop_price = round_to_tick(entry_price * (1 + loss_ratio))
            else:
                target_price = round_to_tick(entry_price * (1 + profit_ratio))
                stop_price = round_to_tick(max(0.05, entry_price * (1 - loss_ratio)))

            target_order = self._build_indstocks_order(
                security_id=str(entry_order["security_id"]),
                txn_type=exit_side,
                qty=int(leg_qty),
                order_type="LIMIT",
                exchange=str(entry_order["exchange"]),
                limit_price=target_price,
            )
            stop_order = self._build_indstocks_order(
                security_id=str(entry_order["security_id"]),
                txn_type=exit_side,
                qty=int(leg_qty),
                order_type=stop_order_type,
                exchange=str(entry_order["exchange"]),
                limit_price=None if stop_order_type.upper() == "SL-M" else stop_price,
                trigger_price=stop_price,
            )

            plans.append({
                "security_id": str(entry_order["security_id"]),
                "symbol": leg.get("symbol"),
                "entry_price": round_to_tick(entry_price),
                "target_price": target_price,
                "stop_price": stop_price,
                "target_order": target_order,
                "stop_order": stop_order,
                "gtt_payload": {
                    "security_id": str(entry_order["security_id"]),
                    "exchange": str(entry_order["exchange"]),
                    "segment": self.default_segment,
                    "product": self.default_product,
                    "qty": int(leg_qty),
                    "txn_type": exit_side,
                    "last_price": round_to_tick(entry_price),
                    "target_price": target_price,
                    "stop_price": stop_price,
                    "validity": self.default_validity,
                },
            })

        return plans

    def _build_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = get_ticket(intent)
        qty = int(ticket.get("lots", 1)) * int(ticket.get("lot_size", 1))

        orders: List[Dict[str, Any]] = []
        for leg in ticket.get("legs", []):
            leg_qty = self._resolve_leg_qty(leg, qty)
            security_id = self._resolve_security_id(leg, ticket)
            txn_type = "SELL" if leg.get("side") == "SELL" else "BUY"
            order_type = self.default_order_type
            exchange = str(leg.get("exchange") or ticket.get("exchange") or self.default_exchange)
            limit_price = float(leg.get("price")) if leg.get("price") is not None else None
            orders.append(
                self._build_indstocks_order(
                    security_id=security_id,
                    txn_type=txn_type,
                    qty=leg_qty,
                    order_type=order_type,
                    exchange=exchange,
                    limit_price=limit_price,
                )
            )

        return orders

    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = get_ticket(intent)
        qty = int(ticket.get("lots", 1)) * int(ticket.get("lot_size", 1))

        orders: List[Dict[str, Any]] = []
        for leg in ticket.get("legs", []):
            leg_qty = self._resolve_leg_qty(leg, qty)
            security_id = self._resolve_security_id(leg, ticket)
            txn_type = "BUY" if leg.get("side") == "SELL" else "SELL"
            order_type = self.default_order_type
            exchange = str(leg.get("exchange") or ticket.get("exchange") or self.default_exchange)
            limit_price = float(leg.get("price")) if leg.get("price") is not None else None
            orders.append(
                self._build_indstocks_order(
                    security_id=security_id,
                    txn_type=txn_type,
                    qty=leg_qty,
                    order_type=order_type,
                    exchange=exchange,
                    limit_price=limit_price,
                )
            )

        return orders

    def _estimate_entry_credit_and_store_leg_prices(self, intent) -> float:
        ticket = get_ticket(intent)
        symbols: List[str] = []
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            if sym:
                symbols.append(sym)

        ltp = get_ltp(symbols)
        qty = int(ticket.get("lot_size", 1)) * int(ticket.get("lots", 1))

        entry_credit_total = 0.0
        for leg in ticket.get("legs", []):
            sym = leg.get("symbol")
            px = float(ltp.get(sym) or 0.0)
            leg["price"] = px
            leg_qty = self._resolve_leg_qty(leg, qty)
            leg["qty"] = leg_qty
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
