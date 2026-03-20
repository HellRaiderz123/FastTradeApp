import json
import os
from typing import Any, Dict, List

from app.core.broker.indmoney.client import INDMoneyClient
from app.core.broker.indmoney.instruments import INDMoneyInstrumentsResolver
from app.core.execution.base import get_ticket
from app.core.market.ltp import get_ltp
from app.core.utils.time import now_ist


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
        return payload

    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)
        entry_credit_total = self._estimate_entry_credit_and_store_leg_prices(intent)

        if self.dry_run:
            return {
                "mode": "INDMONEY_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
                "entry_credit": entry_credit_total,
            }

        placed = []
        for order in orders:
            result = self.client.place_order(order)
            placed.append({"order_id": result.get("order_id"), "order": order, "raw": result.get("response")})

        return {
            "mode": "INDMONEY_LIVE",
            "orders": orders,
            "placed": placed,
            "filled_at": now_ist().isoformat(),
            "entry_credit": entry_credit_total,
        }

    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)
        final_pnl, exit_cost_total = self._estimate_exit_cost_and_pnl(intent)

        if self.dry_run:
            return {
                "mode": "INDMONEY_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
                "exit_cost": exit_cost_total,
                "final_pnl": final_pnl,
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
