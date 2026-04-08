import json
import os
from typing import Any, Dict


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def get_execution_result_dict(intent) -> Dict[str, Any]:
    return _as_dict(getattr(intent, "execution_result_dict", None) or getattr(intent, "execution_result", None) or {})


def get_protection_state(intent) -> Dict[str, Any]:
    state = get_execution_result_dict(intent).get("protection")
    return state if isinstance(state, dict) else {}


def store_protection_state(intent, protection: Dict[str, Any]) -> Dict[str, Any]:
    current = get_execution_result_dict(intent)
    current["protection"] = protection
    intent.execution_result = current
    return current


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def round_to_tick(price: float, tick_size: float = 0.05) -> float:
    safe_price = max(float(price or 0.0), tick_size)
    return round(round(safe_price / tick_size) * tick_size, 2)


def get_protection_ratios(intent) -> tuple[float, float]:
    entry_credit = abs(float(getattr(intent, "entry_credit", 0.0) or 0.0))
    tp_value = abs(float(getattr(intent, "tp", 0.0) or 0.0))
    sl_value = abs(float(getattr(intent, "sl", 0.0) or 0.0))

    default_tp = float(os.getenv("BROKER_PROTECTION_DEFAULT_TP_PCT", "0.25"))
    default_sl = float(os.getenv("BROKER_PROTECTION_DEFAULT_SL_PCT", "0.15"))

    profit_ratio = (tp_value / max(entry_credit, 1.0)) if tp_value else default_tp
    loss_ratio = (sl_value / max(entry_credit, 1.0)) if sl_value else default_sl

    return (
        clamp(profit_ratio, 0.05, 0.80),
        clamp(loss_ratio, 0.05, 1.20),
    )
