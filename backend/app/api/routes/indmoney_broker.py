"""
INDMoney positions API endpoint
Fetches live positions from INDMoney / INDstocks broker
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

from app.core.broker.indmoney.client import get_indmoney_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/indmoney", tags=["INDMoney"])


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _pick(data: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _extract_list(obj: Any, preferred_keys: List[str]) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if not isinstance(obj, dict):
        return []

    for key in preferred_keys:
        value = obj.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

    # One more level deep for shapes like {"data": {"positions": [...]}}
    nested_data = obj.get("data")
    if isinstance(nested_data, dict):
        for key in preferred_keys:
            value = nested_data.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    if isinstance(nested_data, list):
        return [x for x in nested_data if isinstance(x, dict)]

    return []


def _extract_trade_qty(trade: Dict[str, Any]) -> int:
    return _to_int(_pick(trade, ["qty", "quantity", "traded_qty", "fill_qty"], 0), 0)


def _extract_trade_price(trade: Dict[str, Any]) -> float:
    return _to_float(_pick(trade, ["price", "trade_price", "average_price"], 0.0), 0.0)


def _extract_trade_side(trade: Dict[str, Any]) -> str:
    side = str(_pick(trade, ["txn_type", "transaction_type", "side"], "")).upper().strip()
    return side


def _extract_security_id(row: Dict[str, Any]) -> str:
    return str(_pick(row, ["security_id", "scrip_code", "securityId"], "")).strip()


def _normalize_order_symbol_map(order_book_payload: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    rows = _extract_list(order_book_payload, ["data", "orders"])
    for row in rows:
        sid = _extract_security_id(row)
        if not sid:
            continue
        sym = str(_pick(row, ["trading_symbol", "tradingsymbol", "symbol", "security_desc"], "")).strip()
        if sym:
            out[sid] = sym
    return out


def _derive_positions_from_trade_book(
    trade_book_payload: Dict[str, Any],
    symbol_by_security_id: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows = _extract_list(trade_book_payload, ["data", "trades"])
    if not rows:
        return []

    agg: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sid = _extract_security_id(row)
        if not sid:
            continue

        side = _extract_trade_side(row)
        qty = _extract_trade_qty(row)
        price = _extract_trade_price(row)
        if qty <= 0:
            continue

        bucket = agg.setdefault(
            sid,
            {
                "security_id": sid,
                "buy_qty": 0,
                "sell_qty": 0,
                "buy_notional": 0.0,
                "sell_notional": 0.0,
            },
        )

        if side == "BUY":
            bucket["buy_qty"] += qty
            bucket["buy_notional"] += qty * price
        elif side == "SELL":
            bucket["sell_qty"] += qty
            bucket["sell_notional"] += qty * price

    out: List[Dict[str, Any]] = []
    for sid, a in agg.items():
        net_qty = int(a["buy_qty"] - a["sell_qty"])
        if net_qty == 0:
            continue

        if net_qty > 0:
            avg = (a["buy_notional"] / a["buy_qty"]) if a["buy_qty"] > 0 else 0.0
        else:
            avg = (a["sell_notional"] / a["sell_qty"]) if a["sell_qty"] > 0 else 0.0

        out.append(
            {
                "tradingsymbol": symbol_by_security_id.get(sid, sid),
                "quantity": net_qty,
                "average_price": round(float(avg), 4),
                "last_price": 0.0,
                "pnl": 0.0,
                "security_id": sid,
                "source": "trade_book_fallback",
            }
        )

    return out


def _normalize_position(p: Dict[str, Any]) -> Dict[str, Any]:
    buy_qty = _to_int(_pick(p, ["buy_qty", "buy_quantity", "buyQty"], 0), 0)
    sell_qty = _to_int(_pick(p, ["sell_qty", "sell_quantity", "sellQty"], 0), 0)

    quantity = _pick(p, ["quantity", "qty", "net_quantity", "net_qty", "netQuantity", "netQty"], None)
    if quantity is None:
        quantity = buy_qty - sell_qty
    qty_i = _to_int(quantity, 0)

    avg_price = _to_float(_pick(p, ["average_price", "avg_price", "avgPrice", "net_avg"], 0.0), 0.0)
    last_price = _to_float(_pick(p, ["last_traded_price", "last_price", "ltp", "mark_price"], 0.0), 0.0)
    pnl = _to_float(_pick(p, ["pnl", "m2m", "unrealised", "unrealized_pnl", "net_pnl"], 0.0), 0.0)

    symbol = _pick(
        p,
        ["tradingsymbol", "trading_symbol", "symbol", "security_desc", "security_name", "display_symbol"],
        "",
    )

    return {
        "tradingsymbol": str(symbol or ""),
        "quantity": qty_i,
        "average_price": avg_price,
        "last_price": last_price,
        "pnl": pnl,
        "raw": p,
    }


@router.get("/positions")
def get_indmoney_positions(
    segment: str = "derivative",
    product: str = "margin",
) -> Dict[str, Any]:
    """
    Fetch live positions from INDMoney.

    Returns a normalized payload with `net` list to match frontend expectations.
    """
    try:
        client = get_indmoney_client()

        # Try requested pair first, then common alternates because broker payloads
        # may vary by account/product mode.
        attempts = [
            (segment, product),
            (segment.upper(), product.upper()),
            ("derivative", "intraday"),
            ("DERIVATIVE", "INTRADAY"),
            ("equity", "cnc"),
            ("EQUITY", "CNC"),
        ]

        seen = set()
        ordered_attempts = []
        for seg, prod in attempts:
            key = f"{seg}|{prod}"
            if key not in seen:
                seen.add(key)
                ordered_attempts.append((seg, prod))

        raw_responses: List[Dict[str, Any]] = []
        merged_net: List[Dict[str, Any]] = []
        merged_day: List[Dict[str, Any]] = []

        for seg, prod in ordered_attempts:
            try:
                payload = client.get_portfolio_positions(segment=seg, product=prod)
                if isinstance(payload, dict):
                    raw_responses.append({"segment": seg, "product": prod, "payload": payload})

                net_list = _extract_list(payload, ["net_positions", "netPositions", "positions", "net"])
                day_list = _extract_list(payload, ["day_positions", "dayPositions", "day"])

                for p in net_list:
                    merged_net.append(_normalize_position(p))
                for p in day_list:
                    merged_day.append(_normalize_position(p))
            except Exception as exc:
                logger.debug("INDMoney positions attempt failed (%s/%s): %s", seg, prod, exc)

        # Deduplicate by symbol+qty+avg to avoid repeats across attempt variants.
        dedup: Dict[str, Dict[str, Any]] = {}
        for p in merged_net:
            key = f"{p.get('tradingsymbol')}|{p.get('quantity')}|{p.get('average_price')}"
            dedup[key] = p
        net_positions = list(dedup.values())

        day_dedup: Dict[str, Dict[str, Any]] = {}
        for p in merged_day:
            key = f"{p.get('tradingsymbol')}|{p.get('quantity')}|{p.get('average_price')}"
            day_dedup[key] = p
        day_positions = list(day_dedup.values())

        # Some accounts return empty /portfolio/positions despite valid order/trade
        # activity. Fallback to trade-book derived net positions in that case.
        used_trade_fallback = False
        if not net_positions:
            try:
                order_book = client.get_order_book()
                trade_book_deriv = client.get_trade_book(segment="DERIVATIVE")
                trade_book_equity = client.get_trade_book(segment="EQUITY")

                symbol_map = _normalize_order_symbol_map(order_book)
                derived = _derive_positions_from_trade_book(trade_book_deriv, symbol_map)
                derived += _derive_positions_from_trade_book(trade_book_equity, symbol_map)

                # Dedup fallback as well.
                fallback_dedup: Dict[str, Dict[str, Any]] = {}
                for p in derived:
                    key = f"{p.get('security_id')}|{p.get('quantity')}"
                    fallback_dedup[key] = p
                net_positions = list(fallback_dedup.values())
                used_trade_fallback = bool(net_positions)
            except Exception as exc:
                logger.debug("INDMoney trade-book fallback failed: %s", exc)

        logger.info("Fetched %s INDMoney positions (net) after %s attempts", len(net_positions), len(ordered_attempts))
        return {
            "net": net_positions,
            "day": day_positions,
            "used_trade_fallback": used_trade_fallback,
            "raw": raw_responses,
        }
    except Exception as e:
        logger.error("Error fetching INDMoney positions: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch positions from INDMoney: {str(e)}",
        )
